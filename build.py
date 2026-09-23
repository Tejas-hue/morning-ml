#!/usr/bin/env python3
# =============================================================================
# build.py — fetch sources, split News / Papers, score, write an interactive
# mobile-friendly page (tabs, dismiss, expandable abstracts).
# Only external dependency: feedparser. arXiv uses stdlib urllib.
# =============================================================================

import html
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser
import config as C

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=C.LOOKBACK_DAYS)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA,
           "Accept": "application/rss+xml, application/xml, text/xml, */*"}


def parse_date(entry):
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            return datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
    return NOW


def clean(text, limit=1200):
    if not text:
        return ""
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:limit] + "…") if len(text) > limit else text


def fetch_rss(src):
    items = []
    try:
        req = urllib.request.Request(src["url"], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
        feed = feedparser.parse(raw)
    except Exception as e:
        print(f"  ! {src['name']} failed: {e}")
        return items
    for e in feed.entries:
        dt = parse_date(e)
        if dt < CUTOFF:
            continue
        items.append({
            "title": clean(e.get("title", ""), 240),
            "url": e.get("link", ""),
            "summary": clean(e.get("summary", "") or e.get("description", "")),
            "authors": clean(", ".join(a.get("name", "") for a in e.get("authors", [])), 200),
            "date": dt, "source": src["name"], "tier": src["tier"],
            "section": src["section"],
        })
    print(f"  ok {src['name']}: {len(items)} recent")
    return items


ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(src):
    items = []
    q = urllib.parse.urlencode({
        "search_query": f"cat:{src['cat']}",
        "sortBy": "submittedDate", "sortOrder": "descending",
        "max_results": 40,
    })
    try:
        req = urllib.request.Request(f"{ARXIV_API}?{q}", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            root = ET.fromstring(r.read())
    except Exception as e:
        print(f"  ! {src['name']} failed: {e}")
        return items
    for entry in root.findall(f"{ATOM}entry"):
        pub = entry.findtext(f"{ATOM}published") or ""
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except Exception:
            dt = NOW
        if dt < CUTOFF:
            continue
        link = ""
        for l in entry.findall(f"{ATOM}link"):
            if l.get("rel") == "alternate":
                link = l.get("href", "")
        authors = ", ".join((a.findtext(f"{ATOM}name") or "")
                            for a in entry.findall(f"{ATOM}author"))
        items.append({
            "title": clean(entry.findtext(f"{ATOM}title") or "", 240),
            "url": link,
            # keep the FULL abstract for the expandable dropdown
            "summary": clean(entry.findtext(f"{ATOM}summary") or "", 1600),
            "authors": clean(authors, 200),
            "date": dt, "source": src["name"], "tier": src["tier"],
            "section": src["section"],
        })
    print(f"  ok {src['name']}: {len(items)} recent")
    return items


def score(item):
    s = C.TIER_BASE.get(item["tier"], 0)
    hay = (item["title"] + " " + item["summary"]).lower()
    kw = sum(1 for k in C.KEYWORDS if k in hay)
    s += kw * C.KEYWORD_WEIGHT
    auth = item["authors"].lower()
    s += sum(1 for n in C.NOTABLE if n in auth) * C.AUTHOR_WEIGHT
    age = NOW - item["date"]
    if age <= timedelta(days=1):
        s += C.FRESHNESS_TODAY_BONUS
    elif age <= timedelta(days=2):
        s += C.FRESHNESS_2DAY_BONUS
    item["_kw"] = kw
    item["score"] = s
    return s


def dedupe(items):
    seen, out = set(), []
    for it in items:
        key = it["url"] or it["title"]
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def esc(s):
    return html.escape(s or "")


def item_id(it):
    # stable id so a dismissal survives daily rebuilds as long as the url holds
    import hashlib
    return "i" + hashlib.md5((it["url"] or it["title"]).encode()).hexdigest()[:12]


def card(it, blurb=False):
    kw = f'<span class="tag">{it["_kw"]} kw</span>' if it.get("_kw") else ""
    auth = f'<div class="auth">{esc(it["authors"])}</div>' if it["authors"] else ""
    when = it["date"].strftime("%b %d")
    # expandable full text (abstract / newsletter blurb)
    expand = ""
    if it["summary"]:
        expand = f"""<button class="expand" aria-expanded="false">Show abstract</button>
    <div class="full" hidden>{esc(it["summary"])}</div>"""
    return f"""<article class="card tier{it['tier']}" id="{item_id(it)}" data-id="{item_id(it)}">
  <button class="dismiss" title="Mark as read / dismiss" aria-label="Dismiss">×</button>
  <div class="meta"><span class="src">{esc(it['source'])}</span>
    <span class="dot">·</span><span class="when">{when}</span>{kw}</div>
  <h3><a href="{esc(it['url'])}" target="_blank" rel="noopener">{esc(it['title'])}</a></h3>
  {auth}{expand}
</article>"""


def main():
    all_items = []
    print("Fetching…")
    for src in C.SOURCES:
        all_items += fetch_arxiv(src) if src["kind"] == "arxiv" else fetch_rss(src)
        time.sleep(1)

    all_items = dedupe(all_items)
    for it in all_items:
        score(it)

    news = [i for i in all_items if i["section"] == "news"]
    papers = [i for i in all_items if i["section"] == "papers"]
    news.sort(key=lambda x: x["score"], reverse=True)
    papers.sort(key=lambda x: x["score"], reverse=True)
    papers_top = papers[:C.PAPERS_TOP_N]
    papers_rest = papers[C.PAPERS_TOP_N:]
    papers_rest.sort(key=lambda x: x["date"], reverse=True)

    news_html = "\n".join(card(i, blurb=True) for i in news) or \
        '<p class="empty">No news fetched today — check the Actions log for feeds that failed.</p>'
    ptop_html = "\n".join(card(i, blurb=True) for i in papers_top) or \
        '<p class="empty">No papers matched today.</p>'
    prest_html = "\n".join(card(i) for i in papers_rest)
    stamp = NOW.strftime("%A, %d %B %Y · %H:%M UTC")

    out = TEMPLATE.format(
        title=esc(C.PAGE_TITLE), tagline=esc(C.PAGE_TAGLINE), stamp=stamp,
        news=news_html, n_news=len(news),
        ptop=ptop_html, n_ptop=len(papers_top),
        prest=prest_html, n_prest=len(papers_rest),
        n_papers=len(papers),
    )
    import os
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote public/index.html — {len(news)} news, "
          f"{len(papers_top)} top papers, {len(papers_rest)} more papers")


# =============================================================================
# HTML TEMPLATE  (doubled braces {{ }} because this is a .format string)
# =============================================================================
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<style>
  :root {{
    --ink:#1a1f24; --soft:#5c6670; --faint:#8a949e;
    --bg:#fbfaf7; --panel:#fff; --line:#e7e3db;
    --accent:#2f6d5b; --accent-soft:#e6efe9; --news:#b8863b;
    --mono:ui-monospace,"SF Mono",Menlo,monospace;
    box-sizing:border-box;
  }}
  @media (prefers-color-scheme:dark) {{
    :root:not([data-theme="light"]) {{
      --ink:#e9e6df; --soft:#a4aab0; --faint:#6f767c;
      --bg:#14171a; --panel:#1c2024; --line:#2b3036;
      --accent:#6bbfa4; --accent-soft:#1e2a26; --news:#d6a95f;
    }}
  }}
  * {{ box-sizing:border-box; }}
  html {{ scroll-padding-top:120px; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:760px; margin:0 auto;
    padding:calc(20px + env(safe-area-inset-top,0px)) 18px
            calc(60px + env(safe-area-inset-bottom,0px)); }}
  header {{ margin-bottom:8px; }}
  h1 {{ font-size:1.8rem; letter-spacing:-.02em; margin:0 0 2px; }}
  .tagline {{ color:var(--soft); margin:0; font-size:.92rem; }}
  .stamp {{ font-family:var(--mono); font-size:.72rem; color:var(--faint); margin-top:8px; }}

  /* sticky tab bar — the phone switcher */
  .tabs {{ position:sticky;
    top:0; z-index:10; display:flex; gap:6px;
    padding:calc(10px + env(safe-area-inset-top,0px)) 0 10px;
    margin-top:14px; background:var(--bg);
    border-bottom:1px solid var(--line); }}
  .tab {{ flex:1; padding:10px 8px; border:1px solid var(--line);
    background:var(--panel); color:var(--soft); border-radius:10px;
    font-size:.9rem; font-weight:600; cursor:pointer; text-align:center;
    display:flex; align-items:center; justify-content:center; gap:6px; }}
  .tab .n {{ font-family:var(--mono); font-size:.7rem; color:var(--faint);
    background:var(--bg); padding:1px 6px; border-radius:20px; }}
  .tab[aria-selected="true"] {{ border-color:var(--accent); color:var(--accent);
    background:var(--accent-soft); }}
  .tab[aria-selected="true"] .n {{ color:var(--accent); }}

  .panel {{ display:none; }}
  .panel.active {{ display:block; }}

  .section-head {{ display:flex; align-items:baseline; gap:10px; margin:26px 0 2px; }}
  .section-head h2 {{ font-size:1.05rem; margin:0; }}
  .section-head .count {{ font-family:var(--mono); font-size:.72rem; color:var(--faint); }}
  .lead {{ color:var(--soft); font-size:.86rem; margin:.2rem 0 1rem; }}

  .card {{ position:relative; padding:15px 40px 15px 0;
    border-bottom:1px solid var(--line);
    transition:transform .18s ease, opacity .18s ease; }}
  .card.dismissed {{ display:none; }}
  .card.swiping {{ transition:none; }}
  .card h3 {{ font-size:1rem; line-height:1.35; margin:.15rem 0 0; font-weight:600; }}
  .card h3 a {{ color:var(--ink); text-decoration:none;
    background-image:linear-gradient(var(--accent),var(--accent));
    background-size:0% 1.5px; background-repeat:no-repeat; background-position:0 100%;
    transition:background-size .18s ease; }}
  .card h3 a:hover {{ background-size:100% 1.5px; }}
  .meta {{ font-family:var(--mono); font-size:.7rem; color:var(--soft);
    display:flex; align-items:center; gap:7px; flex-wrap:wrap; }}
  .src {{ color:var(--accent); font-weight:600; }}
  .dot {{ color:var(--faint); }}
  .tag {{ background:var(--accent-soft); color:var(--accent);
    padding:1px 6px; border-radius:20px; font-size:.64rem; }}
  .auth {{ font-size:.78rem; color:var(--faint); margin-top:3px;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}

  .expand {{ margin-top:9px; padding:4px 10px; font-size:.76rem;
    font-family:var(--mono); color:var(--accent); background:var(--accent-soft);
    border:none; border-radius:20px; cursor:pointer; }}
  .full {{ margin-top:9px; font-size:.9rem; color:var(--soft);
    line-height:1.6; padding:10px 12px; background:var(--panel);
    border:1px solid var(--line); border-radius:8px; }}

  .dismiss {{ position:absolute; top:12px; right:0; width:30px; height:30px;
    border:none; background:transparent; color:var(--faint);
    font-size:1.4rem; line-height:1; cursor:pointer; border-radius:8px; }}
  .dismiss:hover {{ background:var(--accent-soft); color:var(--accent); }}

  #news .card {{ padding-left:14px; border-left:2px solid transparent; }}
  #news .card:hover {{ border-left-color:var(--news); }}
  #news .card h3 {{ font-size:1.05rem; }}

  .empty {{ color:var(--faint); font-style:italic; }}
  .barctl {{ display:flex; gap:14px; align-items:center; margin:18px 0 0;
    font-family:var(--mono); font-size:.72rem; }}
  .barctl button {{ background:none; border:none; color:var(--accent);
    cursor:pointer; font-family:var(--mono); font-size:.72rem; padding:0; }}
  .barctl .muted {{ color:var(--faint); }}
  footer {{ margin-top:44px; font-family:var(--mono); font-size:.72rem;
    color:var(--faint); border-top:1px solid var(--line); padding-top:14px; }}
  footer code {{ background:var(--accent-soft); padding:1px 5px; border-radius:4px; }}
  @media (prefers-reduced-motion:reduce) {{ * {{ transition:none !important; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{title}</h1>
    <p class="tagline">{tagline}</p>
    <div class="stamp">Rebuilt {stamp}</div>
  </header>

  <div class="tabs" role="tablist">
    <button class="tab" role="tab" aria-selected="true"  data-panel="news">
      News <span class="n">{n_news}</span></button>
    <button class="tab" role="tab" aria-selected="false" data-panel="papers">
      Papers <span class="n">{n_papers}</span></button>
  </div>

  <!-- NEWS -->
  <section class="panel active" id="news" role="tabpanel">
    <div class="section-head"><h2>News &amp; releases</h2><span class="count">{n_news}</span></div>
    <p class="lead">Announcements, model releases, and curator reads. Tap × or swipe
       left to clear ones you've read.</p>
{news}
    <div class="barctl">
      <span class="muted" id="news-left"></span>
      <button data-show="news">Show dismissed</button>
      <button data-reset="news">Reset</button>
    </div>
  </section>

  <!-- PAPERS -->
  <section class="panel" id="papers" role="tabpanel">
    <div class="section-head"><h2>Top picks</h2><span class="count">{n_ptop}</span></div>
    <p class="lead">arXiv preprints that matched your interests hardest. Tap
       "Show abstract" to read without leaving the page.</p>
    <div id="papers-top">
{ptop}
    </div>
    <div class="section-head"><h2>More papers</h2><span class="count">{n_prest}</span></div>
    <p class="lead">Everything else from arXiv, newest first.</p>
    <div id="papers-rest">
{prest}
    </div>
    <div class="barctl">
      <span class="muted" id="papers-left"></span>
      <button data-show="papers">Show dismissed</button>
      <button data-reset="papers">Reset</button>
    </div>
  </section>

  <footer>Built from your own source list · edit <code>config.py</code> to retune.
    Dismissals are saved on this device only.</footer>
</div>

<script>
(function() {{
  var LS = "morningml_dismissed";
  function load() {{
    try {{ return JSON.parse(localStorage.getItem(LS) || "[]"); }}
    catch (e) {{ return []; }}
  }}
  function save(a) {{
    try {{ localStorage.setItem(LS, JSON.stringify(a)); }} catch (e) {{}}
  }}
  var dismissed = load();

  // ---- apply saved dismissals on load
  function apply() {{
    document.querySelectorAll(".card").forEach(function(c) {{
      if (dismissed.indexOf(c.dataset.id) !== -1) c.classList.add("dismissed");
      else c.classList.remove("dismissed");
    }});
    counts();
  }}
  function counts() {{
    ["news", "papers"].forEach(function(p) {{
      var el = document.getElementById(p);
      if (!el) return;
      var live = el.querySelectorAll(".card:not(.dismissed)").length;
      var lab = document.getElementById(p + "-left");
      if (lab) lab.textContent = live + " left";
    }});
  }}
  function dismiss(card) {{
    var id = card.dataset.id;
    if (dismissed.indexOf(id) === -1) dismissed.push(id);
    save(dismissed);
    card.classList.add("dismissed");
    counts();
  }}

  // ---- tabs
  document.querySelectorAll(".tab").forEach(function(t) {{
    t.addEventListener("click", function() {{
      document.querySelectorAll(".tab").forEach(function(x) {{
        x.setAttribute("aria-selected", "false"); }});
      t.setAttribute("aria-selected", "true");
      document.querySelectorAll(".panel").forEach(function(p) {{
        p.classList.remove("active"); }});
      document.getElementById(t.dataset.panel).classList.add("active");
      window.scrollTo(0, 0);
    }});
  }});

  // ---- dismiss buttons
  document.addEventListener("click", function(e) {{
    if (e.target.classList.contains("dismiss")) {{
      dismiss(e.target.closest(".card"));
    }}
    if (e.target.classList.contains("expand")) {{
      var f = e.target.nextElementSibling;
      var open = !f.hidden;
      f.hidden = open;
      e.target.setAttribute("aria-expanded", String(!open));
      e.target.textContent = open ? "Show abstract" : "Hide abstract";
    }}
  }});

  // ---- show-dismissed / reset controls
  document.querySelectorAll("[data-show]").forEach(function(b) {{
    b.addEventListener("click", function() {{
      var panel = document.getElementById(b.dataset.show);
      var showing = b.textContent.indexOf("Show") !== -1;
      panel.querySelectorAll(".card").forEach(function(c) {{
        if (dismissed.indexOf(c.dataset.id) !== -1)
          c.style.display = showing ? "block" : "";
      }});
      b.textContent = showing ? "Hide dismissed" : "Show dismissed";
    }});
  }});
  document.querySelectorAll("[data-reset]").forEach(function(b) {{
    b.addEventListener("click", function() {{
      var panel = document.getElementById(b.dataset.reset);
      panel.querySelectorAll(".card").forEach(function(c) {{
        var i = dismissed.indexOf(c.dataset.id);
        if (i !== -1) dismissed.splice(i, 1);
        c.style.display = "";
      }});
      save(dismissed);
      apply();
    }});
  }});

  // ---- swipe-left to dismiss (touch)
  var startX = 0, startY = 0, cur = null, dragging = false;
  document.addEventListener("touchstart", function(e) {{
    var card = e.target.closest(".card");
    if (!card || e.target.classList.contains("expand") ||
        e.target.tagName === "A") return;
    cur = card; startX = e.touches[0].clientX; startY = e.touches[0].clientY;
    dragging = false;
  }}, {{passive:true}});
  document.addEventListener("touchmove", function(e) {{
    if (!cur) return;
    var dx = e.touches[0].clientX - startX;
    var dy = e.touches[0].clientY - startY;
    if (!dragging && Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {{
      dragging = true; cur.classList.add("swiping");
    }}
    if (dragging && dx < 0) cur.style.transform = "translateX(" + dx + "px)";
  }}, {{passive:true}});
  document.addEventListener("touchend", function(e) {{
    if (!cur) return;
    var dx = e.changedTouches[0].clientX - startX;
    cur.classList.remove("swiping");
    if (dragging && dx < -80) {{
      cur.style.transform = "translateX(-100%)";
      var c = cur;
      setTimeout(function() {{ c.style.transform = ""; dismiss(c); }}, 160);
    }} else {{
      cur.style.transform = "";
    }}
    cur = null; dragging = false;
  }});

  apply();
}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
