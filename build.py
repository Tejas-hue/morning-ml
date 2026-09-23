#!/usr/bin/env python3
# =============================================================================
# build.py — fetch all sources, split into News / Papers, score, write HTML.
# Only external dependency: feedparser. arXiv uses stdlib urllib.
# =============================================================================

import html
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

# A real browser UA. Some feeds (Substack especially) refuse the default
# python/feedparser agent from datacenter IPs; this reduces silent drops.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/rss+xml, application/xml, text/xml, */*"}


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


def clean(text, limit=380):
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
        # fetch bytes ourselves with a browser UA, then hand to feedparser
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
            "summary": clean(entry.findtext(f"{ATOM}summary") or ""),
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


def card(it, blurb=False):
    kw = f'<span class="tag">{it["_kw"]} kw</span>' if it.get("_kw") else ""
    auth = f'<div class="auth">{esc(it["authors"])}</div>' if it["authors"] else ""
    body = f'<p class="blurb">{esc(it["summary"])}</p>' if blurb and it["summary"] else ""
    when = it["date"].strftime("%b %d")
    return f"""<article class="card tier{it['tier']}">
  <div class="meta"><span class="src">{esc(it['source'])}</span>
    <span class="dot">·</span><span class="when">{when}</span>{kw}</div>
  <h3><a href="{esc(it['url'])}" target="_blank" rel="noopener">{esc(it['title'])}</a></h3>
  {auth}{body}
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
        '<p class="empty">No news items fetched today — check the Actions log for feeds that failed.</p>'
    ptop_html = "\n".join(card(i, blurb=True) for i in papers_top)
    prest_html = "\n".join(card(i) for i in papers_rest)
    stamp = NOW.strftime("%A, %d %B %Y · %H:%M UTC")

    out = TEMPLATE.format(
        title=esc(C.PAGE_TITLE), tagline=esc(C.PAGE_TAGLINE), stamp=stamp,
        news=news_html, n_news=len(news),
        ptop=ptop_html, n_ptop=len(papers_top),
        prest=prest_html, n_prest=len(papers_rest),
    )
    import os
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote public/index.html — {len(news)} news, "
          f"{len(papers_top)} top papers, {len(papers_rest)} more papers")


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
    padding-top:env(safe-area-inset-top,0px);
    padding-bottom:env(safe-area-inset-bottom,0px);
  }}
  @media (prefers-color-scheme:dark) {{
    :root:not([data-theme="light"]) {{
      --ink:#e9e6df; --soft:#a4aab0; --faint:#6f767c;
      --bg:#14171a; --panel:#1c2024; --line:#2b3036;
      --accent:#6bbfa4; --accent-soft:#1e2a26; --news:#d6a95f;
    }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:32px 20px 80px; }}
  header {{ border-bottom:2px solid var(--ink); padding-bottom:18px; }}
  h1 {{ font-size:2.1rem; letter-spacing:-.02em; margin:0 0 4px; }}
  .tagline {{ color:var(--soft); margin:0; }}
  .stamp {{ font-family:var(--mono); font-size:.74rem; color:var(--faint); margin-top:10px; }}
  .section-head {{ display:flex; align-items:baseline; gap:10px; margin:42px 0 4px; }}
  .section-head h2 {{ font-size:1.2rem; margin:0; }}
  .section-head .count {{ font-family:var(--mono); font-size:.72rem; color:var(--faint); }}
  .lead {{ color:var(--soft); font-size:.9rem; margin:.2rem 0 1.2rem; }}
  .card {{ padding:16px 0; border-bottom:1px solid var(--line); }}
  .card h3 {{ font-size:1.02rem; line-height:1.35; margin:.15rem 0 0; font-weight:600; }}
  .card h3 a {{ color:var(--ink); text-decoration:none;
    background-image:linear-gradient(var(--accent),var(--accent));
    background-size:0% 1.5px; background-repeat:no-repeat; background-position:0 100%;
    transition:background-size .18s ease; }}
  .card h3 a:hover {{ background-size:100% 1.5px; }}
  .meta {{ font-family:var(--mono); font-size:.72rem; color:var(--soft);
    display:flex; align-items:center; gap:7px; flex-wrap:wrap; }}
  .src {{ color:var(--accent); font-weight:600; }}
  .dot {{ color:var(--faint); }}
  .tag {{ background:var(--accent-soft); color:var(--accent);
    padding:1px 6px; border-radius:20px; font-size:.66rem; }}
  .auth {{ font-size:.8rem; color:var(--faint); margin-top:3px;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .blurb {{ font-size:.9rem; color:var(--soft); margin:.5rem 0 0; }}
  .empty {{ color:var(--faint); font-style:italic; }}
  #news .card {{ padding-left:16px; border-left:2px solid transparent; }}
  #news .card:hover {{ border-left-color:var(--news); }}
  #news .card h3 {{ font-size:1.08rem; }}
  footer {{ margin-top:56px; font-family:var(--mono); font-size:.72rem;
    color:var(--faint); border-top:1px solid var(--line); padding-top:16px; }}
  footer code {{ background:var(--accent-soft); padding:1px 5px; border-radius:4px; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{title}</h1>
    <p class="tagline">{tagline}</p>
    <div class="stamp">Rebuilt {stamp}</div>
  </header>

  <div class="section-head"><h2>News &amp; releases</h2><span class="count">{n_news}</span></div>
  <p class="lead">What the labs, curators and companies actually said — announcements,
     model releases, and the "why it matters" reads. Start here.</p>
  <div id="news">
{news}
  </div>

  <div class="section-head"><h2>Papers — top picks</h2><span class="count">{n_ptop}</span></div>
  <p class="lead">The arXiv preprints that matched your interests hardest, last few days.</p>
  <div id="papers-top">
{ptop}
  </div>

  <div class="section-head"><h2>More papers</h2><span class="count">{n_prest}</span></div>
  <p class="lead">Everything else from arXiv, newest first. Skim it.</p>
  <div id="papers-rest">
{prest}
  </div>

  <footer>Built from your own source list · edit <code>config.py</code> to retune.</footer>
</div>
</body>
</html>"""


if __name__ == "__main__":
    main()
