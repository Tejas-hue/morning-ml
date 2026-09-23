#!/usr/bin/env python3
# =============================================================================
# build.py — fetch sources, split into ML News / Papers / Finance / World,
# cluster finance & world by story (coverage across outlets = importance),
# and write an interactive mobile page (tabs, dismiss, expandable text).
# Only external dependency: feedparser. arXiv uses stdlib urllib.
# =============================================================================

import html
import re
import time
import hashlib
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

# words ignored when deciding if two headlines are the same story
STOP = set("""a an the of to in on for and or but with without from by at as is are was
were be been being this that these those it its he she they them his her their our your
you we i my me new latest says say said report reports update updates amid over after
before how why what when who which will would could may might can up down out about into
than then also more most other some any all no not vs """.split())


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
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:limit] + "…") if len(text) > limit else text


def source_of(entry, fallback):
    # Google News puts the real outlet in entry.source.title
    try:
        s = entry.get("source")
        if s and s.get("title"):
            return s["title"]
    except Exception:
        pass
    return fallback


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
            "date": dt,
            "source": source_of(e, src["name"]),
            "tier": src["tier"], "section": src["section"],
            "region": src.get("region", ""),
        })
    print(f"  ok {src['name']}: {len(items)} recent")
    return items


ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(src):
    items = []
    q = urllib.parse.urlencode({
        "search_query": f"cat:{src['cat']}",
        "sortBy": "submittedDate", "sortOrder": "descending", "max_results": 40,
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
            "summary": clean(entry.findtext(f"{ATOM}summary") or "", 1600),
            "authors": clean(authors, 200), "date": dt,
            "source": src["name"], "tier": src["tier"],
            "section": src["section"], "region": "",
        })
    print(f"  ok {src['name']}: {len(items)} recent")
    return items


def score(item):
    s = C.TIER_BASE.get(item["tier"], 0)
    hay = (item["title"] + " " + item["summary"]).lower()
    kw = sum(1 for k in C.KEYWORDS if k in hay)
    s += kw * C.KEYWORD_WEIGHT
    s += sum(1 for n in C.NOTABLE if n in item["authors"].lower()) * C.AUTHOR_WEIGHT
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


def keywords_of(title):
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if len(w) > 2 and w not in STOP}


def cluster(items):
    """Greedy single-link clustering by shared significant words in titles.
    Returns list of clusters (each a list of items), sorted by coverage
    (distinct outlets) desc, then recency."""
    for it in items:
        it["_kwset"] = keywords_of(it["title"])
    clusters = []
    for it in sorted(items, key=lambda x: x["date"], reverse=True):
        placed = False
        for cl in clusters:
            # compare against the cluster's seed (first, most recent) item
            if len(it["_kwset"] & cl[0]["_kwset"]) >= C.CLUSTER_MIN_SHARED:
                cl.append(it)
                placed = True
                break
        if not placed:
            clusters.append([it])

    def outlets(cl):
        return len({i["source"] for i in cl})
    def newest(cl):
        return max(i["date"] for i in cl)
    clusters.sort(key=lambda cl: (outlets(cl), newest(cl)), reverse=True)
    return clusters


def esc(s):
    return html.escape(s or "")


def item_id(it):
    return "i" + hashlib.md5((it["url"] or it["title"]).encode()).hexdigest()[:12]


def card(it, blurb=False):
    kw = f'<span class="tag">{it["_kw"]} kw</span>' if it.get("_kw") else ""
    auth = f'<div class="auth">{esc(it["authors"])}</div>' if it["authors"] else ""
    when = it["date"].strftime("%b %d")
    expand = ""
    if it["summary"]:
        label = "Show abstract" if it["section"] == "papers" else "Show summary"
        expand = (f'<button class="expand" data-label="{label}" '
                  f'aria-expanded="false">{label}</button>'
                  f'<div class="full" hidden>{esc(it["summary"])}</div>')
    return f"""<article class="card tier{it['tier']}" id="{item_id(it)}" data-id="{item_id(it)}">
  <button class="dismiss" title="Mark as read / dismiss" aria-label="Dismiss">×</button>
  <div class="meta"><span class="src">{esc(it['source'])}</span>
    <span class="dot">·</span><span class="when">{when}</span>{kw}</div>
  <h3><a href="{esc(it['url'])}" target="_blank" rel="noopener">{esc(it['title'])}</a></h3>
  {auth}{expand}
</article>"""


def cluster_block(cl):
    """A story cluster: lead item, plus the other outlets covering it."""
    lead = cl[0]
    n = len({i["source"] for i in cl})
    others = ""
    if len(cl) > 1:
        rows = "\n".join(
            f'<li><a href="{esc(i["url"])}" target="_blank" rel="noopener">'
            f'<span class="osrc">{esc(i["source"])}</span> {esc(i["title"])}</a></li>'
            for i in cl[1:])
        others = f'<ul class="others">{rows}</ul>'
    badge = (f'<span class="cov">{n} outlets</span>' if n > 1
             else '<span class="cov solo">1 outlet</span>')
    cid = item_id(lead)
    when = lead["date"].strftime("%b %d")
    expand = ""
    if lead["summary"]:
        expand = ('<button class="expand" data-label="Show summary" '
                  'aria-expanded="false">Show summary</button>'
                  f'<div class="full" hidden>{esc(lead["summary"])}</div>')
    return f"""<article class="card cluster" id="{cid}" data-id="{cid}">
  <button class="dismiss" title="Dismiss" aria-label="Dismiss">×</button>
  <div class="meta">{badge}<span class="dot">·</span><span class="when">{when}</span></div>
  <h3><a href="{esc(lead['url'])}" target="_blank" rel="noopener">{esc(lead['title'])}</a></h3>
  {expand}{others}
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

    news = sorted([i for i in all_items if i["section"] == "news"],
                  key=lambda x: x["score"], reverse=True)
    papers = sorted([i for i in all_items if i["section"] == "papers"],
                    key=lambda x: x["score"], reverse=True)
    finance = [i for i in all_items if i["section"] == "finance"]
    world = [i for i in all_items if i["section"] == "world"]

    papers_top = papers[:C.PAPERS_TOP_N]
    papers_rest = sorted(papers[C.PAPERS_TOP_N:], key=lambda x: x["date"], reverse=True)

    # ---- render pieces
    news_html = "\n".join(card(i, blurb=True) for i in news) or \
        '<p class="empty">No ML news fetched — check the Actions log.</p>'
    ptop_html = "\n".join(card(i, blurb=True) for i in papers_top) or \
        '<p class="empty">No papers matched today.</p>'
    prest_html = "\n".join(card(i) for i in papers_rest)

    fin_clusters = cluster(finance)
    fin_html = "\n".join(cluster_block(cl) for cl in fin_clusters) or \
        '<p class="empty">No finance news fetched — check the Actions log.</p>'

    # world grouped by region, each region clustered
    world_html_parts = []
    counts = {}
    for region in C.REGION_ORDER:
        reg_items = [i for i in world if i["region"] == region]
        counts[region] = len(reg_items)
        if not reg_items:
            continue
        cls = cluster(reg_items)
        blocks = "\n".join(cluster_block(cl) for cl in cls)
        rid = "region-" + re.sub(r"[^a-z]+", "-", region.lower())
        world_html_parts.append(
            f'<div class="section-head"><h2>{esc(region)}</h2>'
            f'<span class="count">{len(reg_items)}</span></div>\n'
            f'<div id="{rid}">{blocks}</div>')
    world_html = "\n".join(world_html_parts) or \
        '<p class="empty">No world news fetched — check the Actions log.</p>'

    stamp = NOW.strftime("%A, %d %B %Y · %H:%M UTC")
    out = TEMPLATE.format(
        title=esc(C.PAGE_TITLE), tagline=esc(C.PAGE_TAGLINE), stamp=stamp,
        news=news_html, n_news=len(news),
        ptop=ptop_html, n_ptop=len(papers_top),
        prest=prest_html, n_prest=len(papers_rest), n_papers=len(papers),
        finance=fin_html, n_fin=len(finance),
        world=world_html, n_world=len(world),
    )
    import os
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote public/index.html — news {len(news)}, papers {len(papers)}, "
          f"finance {len(finance)} ({len(fin_clusters)} clusters), world {len(world)}")


TEMPLATE = r"""<!DOCTYPE html>
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
  html {{ scroll-padding-top:130px; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:760px; margin:0 auto;
    padding:calc(18px + env(safe-area-inset-top,0px)) 16px
            calc(60px + env(safe-area-inset-bottom,0px)); }}
  h1 {{ font-size:1.7rem; letter-spacing:-.02em; margin:0 0 2px; }}
  .tagline {{ color:var(--soft); margin:0; font-size:.9rem; }}
  .stamp {{ font-family:var(--mono); font-size:.7rem; color:var(--faint); margin-top:8px; }}

  .tabs {{ position:sticky; top:0; z-index:10; display:flex; gap:5px;
    padding:calc(9px + env(safe-area-inset-top,0px)) 0 9px; margin-top:12px;
    background:var(--bg); border-bottom:1px solid var(--line);
    overflow-x:auto; -webkit-overflow-scrolling:touch; }}
  .tab {{ flex:1 0 auto; padding:9px 12px; border:1px solid var(--line);
    background:var(--panel); color:var(--soft); border-radius:10px;
    font-size:.85rem; font-weight:600; cursor:pointer; white-space:nowrap;
    display:flex; align-items:center; gap:6px; }}
  .tab .n {{ font-family:var(--mono); font-size:.68rem; color:var(--faint);
    background:var(--bg); padding:1px 6px; border-radius:20px; }}
  .tab[aria-selected="true"] {{ border-color:var(--accent); color:var(--accent);
    background:var(--accent-soft); }}
  .tab[aria-selected="true"] .n {{ color:var(--accent); }}

  .panel {{ display:none; }}
  .panel.active {{ display:block; }}
  .section-head {{ display:flex; align-items:baseline; gap:10px; margin:24px 0 2px; }}
  .section-head h2 {{ font-size:1.02rem; margin:0; }}
  .section-head .count {{ font-family:var(--mono); font-size:.7rem; color:var(--faint); }}
  .lead {{ color:var(--soft); font-size:.84rem; margin:.2rem 0 1rem; }}

  .card {{ position:relative; padding:14px 40px 14px 0;
    border-bottom:1px solid var(--line);
    transition:transform .18s ease, opacity .18s ease; }}
  .card.dismissed {{ display:none; }}
  .card.swiping {{ transition:none; }}
  .card h3 {{ font-size:1rem; line-height:1.35; margin:.15rem 0 0; font-weight:600; }}
  .card h3 a {{ color:var(--ink); text-decoration:none; }}
  .card h3 a:hover {{ color:var(--accent); }}
  .meta {{ font-family:var(--mono); font-size:.7rem; color:var(--soft);
    display:flex; align-items:center; gap:7px; flex-wrap:wrap; }}
  .src {{ color:var(--accent); font-weight:600; }}
  .dot {{ color:var(--faint); }}
  .tag {{ background:var(--accent-soft); color:var(--accent);
    padding:1px 6px; border-radius:20px; font-size:.64rem; }}
  .cov {{ background:var(--news); color:#fff; padding:1px 8px; border-radius:20px;
    font-size:.64rem; font-weight:600; }}
  .cov.solo {{ background:transparent; color:var(--faint);
    border:1px solid var(--line); }}
  .auth {{ font-size:.78rem; color:var(--faint); margin-top:3px;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .expand {{ margin-top:9px; padding:4px 10px; font-size:.74rem;
    font-family:var(--mono); color:var(--accent); background:var(--accent-soft);
    border:none; border-radius:20px; cursor:pointer; }}
  .full {{ margin-top:9px; font-size:.88rem; color:var(--soft); line-height:1.6;
    padding:10px 12px; background:var(--panel); border:1px solid var(--line);
    border-radius:8px; }}
  .others {{ list-style:none; margin:10px 0 0; padding:10px 0 0;
    border-top:1px dashed var(--line); }}
  .others li {{ margin:0 0 7px; font-size:.85rem; line-height:1.4; }}
  .others a {{ color:var(--soft); text-decoration:none; }}
  .others a:hover {{ color:var(--accent); }}
  .osrc {{ color:var(--accent); font-family:var(--mono); font-size:.7rem;
    font-weight:600; margin-right:5px; }}
  .dismiss {{ position:absolute; top:11px; right:0; width:30px; height:30px;
    border:none; background:transparent; color:var(--faint);
    font-size:1.4rem; line-height:1; cursor:pointer; border-radius:8px; }}
  .dismiss:hover {{ background:var(--accent-soft); color:var(--accent); }}
  #news .card {{ padding-left:14px; border-left:2px solid transparent; }}
  #news .card:hover {{ border-left-color:var(--news); }}
  .empty {{ color:var(--faint); font-style:italic; }}
  .barctl {{ display:flex; gap:14px; align-items:center; margin:18px 0 0;
    font-family:var(--mono); font-size:.7rem; }}
  .barctl button {{ background:none; border:none; color:var(--accent);
    cursor:pointer; font-family:var(--mono); font-size:.7rem; padding:0; }}
  .barctl .muted {{ color:var(--faint); }}
  footer {{ margin-top:40px; font-family:var(--mono); font-size:.7rem;
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
    <button class="tab" role="tab" aria-selected="true"  data-panel="news">ML News <span class="n">{n_news}</span></button>
    <button class="tab" role="tab" aria-selected="false" data-panel="papers">Papers <span class="n">{n_papers}</span></button>
    <button class="tab" role="tab" aria-selected="false" data-panel="finance">Finance <span class="n">{n_fin}</span></button>
    <button class="tab" role="tab" aria-selected="false" data-panel="world">World <span class="n">{n_world}</span></button>
  </div>

  <section class="panel active" id="news" role="tabpanel">
    <div class="section-head"><h2>ML news &amp; releases</h2><span class="count">{n_news}</span></div>
    <p class="lead">Announcements, model releases, curator reads. × or swipe left to clear.</p>
{news}
    <div class="barctl"><span class="muted" id="news-left"></span>
      <button data-show="news">Show dismissed</button>
      <button data-reset="news">Reset</button></div>
  </section>

  <section class="panel" id="papers" role="tabpanel">
    <div class="section-head"><h2>Top picks</h2><span class="count">{n_ptop}</span></div>
    <p class="lead">arXiv preprints matching your interests. Tap to read the abstract inline.</p>
    <div id="papers-top">
{ptop}
    </div>
    <div class="section-head"><h2>More papers</h2><span class="count">{n_prest}</span></div>
    <p class="lead">Everything else from arXiv, newest first.</p>
    <div id="papers-rest">
{prest}
    </div>
    <div class="barctl"><span class="muted" id="papers-left"></span>
      <button data-show="papers">Show dismissed</button>
      <button data-reset="papers">Reset</button></div>
  </section>

  <section class="panel" id="finance" role="tabpanel">
    <div class="section-head"><h2>Finance &amp; markets</h2><span class="count">{n_fin}</span></div>
    <p class="lead">Stories grouped across outlets. The "N outlets" badge shows how many
       are covering it — more coverage floats up. Expand to see who else ran it.</p>
{finance}
    <div class="barctl"><span class="muted" id="finance-left"></span>
      <button data-show="finance">Show dismissed</button>
      <button data-reset="finance">Reset</button></div>
  </section>

  <section class="panel" id="world" role="tabpanel">
    <div class="section-head"><h2>World</h2><span class="count">{n_world}</span></div>
    <p class="lead">By country, India first. Stories grouped across outlets so you can see
       the spread — and what one outlet is quiet about.</p>
{world}
    <div class="barctl"><span class="muted" id="world-left"></span>
      <button data-show="world">Show dismissed</button>
      <button data-reset="world">Reset</button></div>
  </section>

  <footer>Built from your own source list · edit <code>config.py</code> to retune.
    Dismissals saved on this device only.</footer>
</div>

<script>
(function() {{
  var LS = "morningml_dismissed";
  function load() {{ try {{ return JSON.parse(localStorage.getItem(LS)||"[]"); }} catch(e){{ return []; }} }}
  function save(a) {{ try {{ localStorage.setItem(LS, JSON.stringify(a)); }} catch(e){{}} }}
  var dismissed = load();
  var PANELS = ["news","papers","finance","world"];

  function apply() {{
    document.querySelectorAll(".card").forEach(function(c) {{
      if (dismissed.indexOf(c.dataset.id) !== -1) c.classList.add("dismissed");
      else c.classList.remove("dismissed");
    }});
    counts();
  }}
  function counts() {{
    PANELS.forEach(function(p) {{
      var el = document.getElementById(p); if (!el) return;
      var live = el.querySelectorAll(".card:not(.dismissed)").length;
      var lab = document.getElementById(p+"-left");
      if (lab) lab.textContent = live + " left";
    }});
  }}
  function dismiss(card) {{
    var id = card.dataset.id;
    if (dismissed.indexOf(id) === -1) dismissed.push(id);
    save(dismissed); card.classList.add("dismissed"); counts();
  }}

  document.querySelectorAll(".tab").forEach(function(t) {{
    t.addEventListener("click", function() {{
      document.querySelectorAll(".tab").forEach(function(x){{ x.setAttribute("aria-selected","false"); }});
      t.setAttribute("aria-selected","true");
      document.querySelectorAll(".panel").forEach(function(p){{ p.classList.remove("active"); }});
      document.getElementById(t.dataset.panel).classList.add("active");
      window.scrollTo(0,0);
    }});
  }});

  document.addEventListener("click", function(e) {{
    if (e.target.classList.contains("dismiss")) dismiss(e.target.closest(".card"));
    if (e.target.classList.contains("expand")) {{
      var f = e.target.nextElementSibling, open = !f.hidden, lab = e.target.dataset.label;
      f.hidden = open; e.target.setAttribute("aria-expanded", String(!open));
      e.target.textContent = open ? lab : lab.replace("Show","Hide");
    }}
  }});
  document.querySelectorAll("[data-show]").forEach(function(b) {{
    b.addEventListener("click", function() {{
      var panel = document.getElementById(b.dataset.show);
      var showing = b.textContent.indexOf("Show") !== -1;
      panel.querySelectorAll(".card").forEach(function(c) {{
        if (dismissed.indexOf(c.dataset.id) !== -1) c.style.display = showing ? "block" : "";
      }});
      b.textContent = showing ? "Hide dismissed" : "Show dismissed";
    }});
  }});
  document.querySelectorAll("[data-reset]").forEach(function(b) {{
    b.addEventListener("click", function() {{
      var panel = document.getElementById(b.dataset.reset);
      panel.querySelectorAll(".card").forEach(function(c) {{
        var i = dismissed.indexOf(c.dataset.id);
        if (i !== -1) dismissed.splice(i,1);
        c.style.display = "";
      }});
      save(dismissed); apply();
    }});
  }});

  var startX=0,startY=0,cur=null,dragging=false;
  document.addEventListener("touchstart", function(e) {{
    var card = e.target.closest(".card");
    if (!card || e.target.classList.contains("expand") || e.target.tagName==="A") return;
    cur=card; startX=e.touches[0].clientX; startY=e.touches[0].clientY; dragging=false;
  }}, {{passive:true}});
  document.addEventListener("touchmove", function(e) {{
    if (!cur) return;
    var dx=e.touches[0].clientX-startX, dy=e.touches[0].clientY-startY;
    if (!dragging && Math.abs(dx)>Math.abs(dy) && Math.abs(dx)>10) {{ dragging=true; cur.classList.add("swiping"); }}
    if (dragging && dx<0) cur.style.transform="translateX("+dx+"px)";
  }}, {{passive:true}});
  document.addEventListener("touchend", function(e) {{
    if (!cur) return;
    var dx=e.changedTouches[0].clientX-startX;
    cur.classList.remove("swiping");
    if (dragging && dx<-80) {{
      cur.style.transform="translateX(-100%)";
      var c=cur; setTimeout(function(){{ c.style.transform=""; dismiss(c); }},160);
    }} else {{ cur.style.transform=""; }}
    cur=null; dragging=false;
  }});

  apply();
}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
