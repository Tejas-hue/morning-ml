# Morning ML

A free, zero-maintenance daily reader. Every morning a GitHub Action fetches
your sources, ranks them (curators first, arXiv firehose filtered by your
interests), and publishes a single readable page to GitHub Pages. You just
bookmark the page.

No servers, no money, no email deliverability headaches. Runs whether or not
your laptop is on.

## What you get

- **Top picks** — human curators (HF Daily Papers, Import AI, Raschka, Davis,
  The Batch) and official lab/company releases (DeepMind, Meta, NVIDIA, OpenAI,
  Anthropic, HF), plus any arXiv papers that strongly match your interests.
- **Everything else** — the rest of the last few days, newest first, to skim.

Covers LLMs, CV, HRI/robotics, computational psychology, general ML, and a
lighter dose of medical ML. All tunable in one file.

## One-time setup (~10 minutes)

1. **Make a GitHub account** if you don't have one (free).
2. **Create a new public repository** — call it whatever, e.g. `morning-ml`.
3. **Upload these files** into it (keep the folder structure — the
   `.github/workflows/build.yml` path matters). You can drag-drop in the
   GitHub web UI via "Add file → Upload files".
4. **Turn on Pages**: repo **Settings → Pages → Build and deployment →
   Source: GitHub Actions**.
5. **Run it once by hand**: go to the **Actions** tab, pick "Build Morning ML",
   click **Run workflow**. Wait ~1 minute.
6. Your page is live at `https://<your-username>.github.io/<repo-name>/`.
   Bookmark it. It rebuilds automatically every morning.

## Tuning

Everything you'd want to change lives in **`config.py`**:

- **Add/remove sources** — edit the `SOURCES` list. Comment out what you don't
  read; paste in new RSS feeds the same way.
- **Change the ranking** — `TIER_BASE` sets how far ahead curators start;
  `KEYWORD_WEIGHT` / `AUTHOR_WEIGHT` control how much a match pulls a paper up.
- **Change your interests** — edit `KEYWORDS`. This is what floats a raw arXiv
  paper into the top section.
- **Size of the top section** — `TOP_N`. How many days to keep — `LOOKBACK_DAYS`.
- **Build time** — edit the cron in `.github/workflows/build.yml` (it's UTC;
  `30 5 * * *` = 11:00 IST).

## Run locally (optional)

```bash
pip install feedparser
python build.py
open public/index.html
```

## Notes

- A couple of feed URLs in `config.py` occasionally move; if a source stops
  showing up, the Actions log will print `! <name> failed` — swap its URL.
- The HF Daily Papers entry uses a community RSS mirror because HF's own daily
  page isn't a clean feed. If it ever breaks, any HF-papers mirror works.
