#!/usr/bin/env python3
# =============================================================================
# build.py — fetch all sources, score, and write index.html
# Only dependency: feedparser (for RSS) + stdlib. arXiv uses stdlib urllib.
# Run: python build.py   ->   produces ./public/index.html
# =============================================================================

import html
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import feedparser  # pip install feedparser

import config as C

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=C.LOOKBACK_DAYS)
UA = {"User-Agent": "morning-ml/1.0 (personal daily reader)"}


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def parse_date(entry):
    """Best-effort published datetime, tz-aware UTC. Falls back to now."""
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
    """Strip tags-ish, unescape, truncate for a blurb."""
    if not text:
        return ""
    # feedparser usually gives us text or light html; crude tag strip:
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:limit] + "…") if len(text) > limit else text


def fetch_rss(src):
    items = []
    try:
        feed = feedparser.parse(src["url"], request_headers=UA)
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
            "authors": clean(
                ", ".join(a.get("name", "") for a in e.get("authors", [])), 200
            ),
            "date": dt,
            "source": src["name"],
            "tier": src["tier"],
        })
    print(f"  ok {src['name']}: {len(items)} recent")
    return items


ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"


def fetch_arxiv(src):
    items = []
    q = urllib.parse.urlencode({
        "search_query": f"cat:{src['cat']}",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": 40,
    })
    try:
        req = urllib.request.Request(f"{ARXIV_API}?{q}", headers=UA)
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
        title = clean(entry.findtext(f"{ATOM}title") or "", 240)
        summ = clean(entry.findtext(f"{ATOM}summary") or "")
        link = ""
        for l in entry.findall(f"{ATOM}link"):
            if l.get("rel") == "alternate":
                link = l.get("href", "")
        authors = ", ".join(
            (a.findtext(f"{ATOM}name") or "") for a in entry.findall(f"{ATOM}author")
        )
        items.append({
            "title": title, "url": link, "summary": summ,
            "authors": clean(authors, 200), "date": dt,
            "source": src["name"], "tier": src["tier"],
        })
    print(f"  ok {src['name']}: {len(items)} recent")
    return items


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score(item):
    s = C.TIER_BASE.get(item["tier"], 0)
    hay = (item["title"] + " " + item["summary"]).lower()
    kw_hits = sum(1 for k in C.KEYWORDS if k in hay)
    s += kw_hits * C.KEYWORD_WEIGHT
    auth = item["authors"].lower()
    au_hits = sum(1 for n in C.NOTABLE if n in auth)
    s += au_hits * C.AUTHOR_WEIGHT
    age = NOW - item["date"]
    if age <= timedelta(days=1):
        s += C.FRESHNESS_TODAY_BONUS
    elif age <= timedelta(days=2):
        s += C.FRESHNESS_2DAY_BONUS
    item["_kw"] = kw_hits
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


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def esc(s):
    return html.escape(s or "")


def render_card(it, ranked=False):
    kw = f'<span class="tag">{it["_kw"]} kw</span>' if it["_kw"] else ""
    auth = f'<div class="auth">{esc(it["authors"])}</div>' if it["authors"] else ""
    blurb = f'<p class="blurb">{esc(it["summary"])}</p>' if ranked and it["summary"] else ""
    when = it["date"].strftime("%b %d")
    return f"""<article class="card tier{it['tier']}">
  <div class="meta"><span class="src">{esc(it['source'])}</span>
    <span class="dot">·</span><span class="when">{when}</span>{kw}</div>
  <h3><a href="{esc(it['url'])}" target="_blank" rel="noopener">{esc(it['title'])}</a></h3>
  {auth}{blurb}
</article>"""


def render(top, rest):
    top_html = "\n".join(render_card(i, ranked=True) for i in top)
    rest_html = "\n".join(render_card(i) for i in rest)
    stamp = NOW.strftime("%A, %d %B %Y · %H:%M UTC")
    return TEMPLATE.format(
        title=esc(C.PAGE_TITLE), tagline=esc(C.PAGE_TAGLINE),
        stamp=stamp, top=top_html, rest=rest_html,
        n_top=len(top), n_rest=len(rest),
    )


def main():
    all_items = []
    print("Fetching…")
    for src in C.SOURCES:
        if src["kind"] == "arxiv":
            all_items += fetch_arxiv(src)
        else:
            all_items += fetch_rss(src)
        time.sleep(1)  # be polite to arXiv/servers

    all_items = dedupe(all_items)
    for it in all_items:
        score(it)
    all_items.sort(key=lambda x: x["score"], reverse=True)

    top = all_items[:C.TOP_N]
    rest = all_items[C.TOP_N:]
    # rest sorted by date so scanning feels chronological, not score-y
    rest.sort(key=lambda x: x["date"], reverse=True)

    import os
    os.makedirs("public", exist_ok=True)
    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(render(top, rest))
    print(f"Wrote public/index.html — {len(top)} top, {len(rest)} more")


# ---------------------------------------------------------------------------
# HTML template (kept at bottom so build.py reads top-down)
# ---------------------------------------------------------------------------

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<style>
  :root {{
    --ink: #1a1f24; --soft: #5c6670; --faint: #8a949e;
    --bg: #fbfaf7; --panel: #ffffff; --line: #e7e3db;
    --accent: #2f6d5b; --accent-soft: #e6efe9; --top: #b8863b;
    --mono: ui-monospace, "SF Mono", Menlo, monospace;
    box-sizing: border-box;
    padding-top: env(safe-area-inset-top, 0px);
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --ink:#e9e6df; --soft:#a4aab0; --faint:#6f767c;
      --bg:#14171a; --panel:#1c2024; --line:#2b3036;
      --accent:#6bbfa4; --accent-soft:#1e2a26; --top:#d6a95f;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin:0; background:var(--bg); color:var(--ink);
    font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 32px 20px 80px; }}
  header {{ border-bottom: 2px solid var(--ink); padding-bottom: 18px; margin-bottom: 8px; }}
  h1 {{ font-size: 2.1rem; letter-spacing:-0.02em; margin:0 0 4px; }}
  .tagline {{ color: var(--soft); margin:0; }}
  .stamp {{ font-family: var(--mono); font-size:.74rem; color:var(--faint);
    margin-top:10px; }}
  .section-head {{ display:flex; align-items:baseline; gap:10px;
    margin: 40px 0 4px; }}
  .section-head h2 {{ font-size: 1.15rem; margin:0; }}
  .section-head .count {{ font-family:var(--mono); font-size:.72rem;
    color:var(--faint); }}
  .lead {{ color:var(--soft); font-size:.9rem; margin:.2rem 0 1.2rem; }}

  .card {{ padding: 16px 0; border-bottom: 1px solid var(--line); }}
  .card h3 {{ font-size: 1.02rem; line-height:1.35; margin:.15rem 0 0;
    font-weight: 600; }}
  .card h3 a {{ color: var(--ink); text-decoration: none;
    background-image: linear-gradient(var(--accent),var(--accent));
    background-size:0% 1.5px; background-repeat:no-repeat;
    background-position:0 100%; transition: background-size .18s ease; }}
  .card h3 a:hover {{ background-size:100% 1.5px; }}
  .meta {{ font-family:var(--mono); font-size:.72rem; color:var(--soft);
    display:flex; align-items:center; gap:7px; flex-wrap:wrap; }}
  .src {{ color: var(--accent); font-weight:600; }}
  .dot {{ color: var(--faint); }}
  .tag {{ background:var(--accent-soft); color:var(--accent);
    padding:1px 6px; border-radius:20px; font-size:.66rem; }}
  .auth {{ font-size:.8rem; color:var(--faint); margin-top:3px;
    overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .blurb {{ font-size:.9rem; color:var(--soft); margin:.5rem 0 0; }}

  /* top section gets a left accent to feel picked */
  #top .card {{ padding-left:16px; border-left:2px solid transparent; }}
  #top .card:hover {{ border-left-color: var(--top); }}
  #top .card h3 {{ font-size:1.08rem; }}

  footer {{ margin-top:56px; font-family:var(--mono); font-size:.72rem;
    color:var(--faint); border-top:1px solid var(--line); padding-top:16px; }}
  footer a {{ color:var(--accent); }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>{title}</h1>
    <p class="tagline">{tagline}</p>
    <div class="stamp">Rebuilt {stamp}</div>
  </header>

  <div class="section-head" id="top-head">
    <h2>Top picks</h2><span class="count">{n_top}</span>
  </div>
  <p class="lead">Curators and lab releases first, then the arXiv papers that
     matched your interests hardest.</p>
  <div id="top">
{top}
  </div>

  <div class="section-head">
    <h2>Everything else</h2><span class="count">{n_rest}</span>
  </div>
  <p class="lead">The rest of the last few days, newest first. Skim it.</p>
  <div id="rest">
{rest}
  </div>

  <footer>
    Built from your own source list · edit <code>config.py</code> to retune.
  </footer>
</div>
</body>
</html>"""


if __name__ == "__main__":
    main()
