# =============================================================================
# config.py — sources + scoring for Morning ML / News.
# Each source has: kind ("rss"|"arxiv"), tier, section, and for world/finance
# a "region" used to group them into sub-sections on the page.
#
# TABS on the page: ML News | Papers | Finance | World
#   section="news"    -> ML News tab
#   section="papers"  -> Papers tab
#   section="finance" -> Finance tab
#   section="world"   -> World tab (grouped by `region`)
#
# GOOGLE NEWS feeds: Reuters killed direct RSS in 2020, so we use Google News
# RSS (free, no key) for wire coverage + per-country headlines. `when:1d` in a
# query keeps results fresh (Google News RSS can otherwise run several days old).
# Direct publisher feeds are the backbone; Google News only fills gaps.
# =============================================================================

def gnews(query, hl="en-US", gl="US", ceid="US:en"):
    """Build a Google News RSS search URL."""
    import urllib.parse
    q = urllib.parse.quote(query)
    return (f"https://news.google.com/rss/search?q={q}"
            f"&hl={hl}&gl={gl}&ceid={ceid}")

SOURCES = [
    # ======================= ML NEWS (tab 1) ================================
    {"name": "Import AI",              "kind": "rss", "tier": 1, "section": "news",
     "url": "https://importai.substack.com/feed"},
    {"name": "Interconnects (Lambert)","kind": "rss", "tier": 1, "section": "news",
     "url": "https://www.interconnects.ai/feed"},
    {"name": "The AI Breakfast",       "kind": "rss", "tier": 1, "section": "news",
     "url": "https://aibreakfast.beehiiv.com/feed"},
    {"name": "Sebastian Raschka",      "kind": "rss", "tier": 1, "section": "news",
     "url": "https://magazine.sebastianraschka.com/feed"},
    {"name": "The Batch",              "kind": "rss", "tier": 1, "section": "news",
     "url": "https://www.deeplearning.ai/the-batch/feed/"},
    {"name": "HF Daily Papers",        "kind": "rss", "tier": 1, "section": "news",
     "url": "https://jamesg.blog/hf-papers.xml"},
    {"name": "Google DeepMind",        "kind": "rss", "tier": 2, "section": "news",
     "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "Meta AI",                "kind": "rss", "tier": 2, "section": "news",
     "url": "https://ai.meta.com/blog/rss/"},
    {"name": "NVIDIA Dev Blog",        "kind": "rss", "tier": 2, "section": "news",
     "url": "https://developer.nvidia.com/blog/feed/"},
    {"name": "OpenAI",                 "kind": "rss", "tier": 2, "section": "news",
     "url": "https://openai.com/news/rss.xml"},
    {"name": "Anthropic",              "kind": "rss", "tier": 2, "section": "news",
     "url": "https://www.anthropic.com/rss.xml"},
    {"name": "Hugging Face Blog",      "kind": "rss", "tier": 2, "section": "news",
     "url": "https://huggingface.co/blog/feed.xml"},

    # ======================= PAPERS (tab 2) ================================
    {"name": "arXiv cs.CL", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.CL"},
    {"name": "arXiv cs.CV", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.CV"},
    {"name": "arXiv cs.LG", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.LG"},
    {"name": "arXiv cs.RO", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.RO"},
    {"name": "arXiv cs.HC", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.HC"},
    {"name": "arXiv cs.AI", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.AI"},

    # ======================= FINANCE (tab 3) ===============================
    # Global markets/macro — direct feeds where they exist, Google News for wires
    {"name": "CNBC Markets",     "kind": "rss", "tier": 2, "section": "finance",
     "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"name": "MarketWatch",      "kind": "rss", "tier": 2, "section": "finance",
     "url": "http://feeds.marketwatch.com/marketwatch/topstories/"},
    {"name": "FT (headlines)",   "kind": "rss", "tier": 1, "section": "finance",
     "url": gnews("when:1d allinurl:ft.com")},
    {"name": "Reuters Business", "kind": "rss", "tier": 1, "section": "finance",
     "url": gnews("when:1d allinurl:reuters.com/business")},
    {"name": "Bloomberg (headlines)", "kind": "rss", "tier": 1, "section": "finance",
     "url": gnews("when:1d allinurl:bloomberg.com")},
    {"name": "Money Stuff (Levine)", "kind": "rss", "tier": 1, "section": "finance",
     "url": gnews('when:2d "Money Stuff" Matt Levine')},
    # India finance
    {"name": "Livemint Markets", "kind": "rss", "tier": 2, "section": "finance",
     "url": "https://www.livemint.com/rss/markets"},
    {"name": "Moneycontrol",     "kind": "rss", "tier": 2, "section": "finance",
     "url": "https://www.moneycontrol.com/rss/latestnews.xml"},
    {"name": "Economic Times Markets", "kind": "rss", "tier": 2, "section": "finance",
     "url": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"},
    {"name": "Business Standard", "kind": "rss", "tier": 2, "section": "finance",
     "url": "https://www.business-standard.com/rss/markets-106.rss"},

    # ======================= WORLD (tab 4), grouped by region ==============
    # --- India ---
    {"name": "The Hindu",   "kind": "rss", "tier": 1, "section": "world", "region": "India",
     "url": "https://www.thehindu.com/news/national/feeder/default.rss"},
    {"name": "Scroll.in",   "kind": "rss", "tier": 1, "section": "world", "region": "India",
     "url": "https://scroll.in/feeds/all.rss"},
    {"name": "India Top (Google News)", "kind": "rss", "tier": 2, "section": "world", "region": "India",
     "url": gnews("when:1d", hl="en-IN", gl="IN", ceid="IN:en")},
    # --- United States ---
    {"name": "AP Top",      "kind": "rss", "tier": 1, "section": "world", "region": "United States",
     "url": gnews("when:1d allinurl:apnews.com")},
    {"name": "NYT World",   "kind": "rss", "tier": 1, "section": "world", "region": "United States",
     "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"name": "US Top (Google News)", "kind": "rss", "tier": 2, "section": "world", "region": "United States",
     "url": gnews("when:1d", hl="en-US", gl="US", ceid="US:en")},
    # --- United Kingdom ---
    {"name": "BBC UK",      "kind": "rss", "tier": 1, "section": "world", "region": "United Kingdom",
     "url": "https://feeds.bbci.co.uk/news/uk/rss.xml"},
    {"name": "The Guardian","kind": "rss", "tier": 1, "section": "world", "region": "United Kingdom",
     "url": "https://www.theguardian.com/uk/rss"},
    # --- China ---
    {"name": "SCMP China",  "kind": "rss", "tier": 1, "section": "world", "region": "China",
     "url": "https://www.scmp.com/rss/91/feed"},
    {"name": "China Top (Google News)", "kind": "rss", "tier": 2, "section": "world", "region": "China",
     "url": gnews("China when:1d", hl="en-US", gl="US", ceid="US:en")},
    # --- Japan ---
    {"name": "Japan Times", "kind": "rss", "tier": 1, "section": "world", "region": "Japan",
     "url": "https://www.japantimes.co.jp/feed/"},
    {"name": "Japan Top (Google News)", "kind": "rss", "tier": 2, "section": "world", "region": "Japan",
     "url": gnews("Japan when:1d", hl="en-US", gl="US", ceid="US:en")},
    # --- Germany ---
    {"name": "Deutsche Welle", "kind": "rss", "tier": 1, "section": "world", "region": "Germany",
     "url": "https://rss.dw.com/rdf/rss-en-ger"},
    {"name": "Germany Top (Google News)", "kind": "rss", "tier": 2, "section": "world", "region": "Germany",
     "url": gnews("Germany when:1d", hl="en-US", gl="US", ceid="US:en")},
    # --- Pakistan ---
    {"name": "Dawn",        "kind": "rss", "tier": 1, "section": "world", "region": "Pakistan",
     "url": "https://www.dawn.com/feeds/home"},
    {"name": "Pakistan Top (Google News)", "kind": "rss", "tier": 2, "section": "world", "region": "Pakistan",
     "url": gnews("Pakistan when:1d", hl="en-US", gl="US", ceid="US:en")},
    # --- European Union ---
    {"name": "Euractiv",    "kind": "rss", "tier": 1, "section": "world", "region": "European Union",
     "url": "https://www.euractiv.com/feed/"},
    {"name": "EU Top (Google News)", "kind": "rss", "tier": 2, "section": "world", "region": "European Union",
     "url": gnews("European Union when:1d", hl="en-US", gl="US", ceid="US:en")},
]

# Order the World sub-sections appear on the page (India first, per your ask).
REGION_ORDER = ["India", "United States", "United Kingdom", "China",
                "Japan", "Germany", "Pakistan", "European Union"]

# -----------------------------------------------------------------------------
# SCORING (used within ML News + Papers). Finance/World use story-clustering
# instead: items are grouped, and clusters with more outlets covering them
# float to the top (that coverage-count is the transparent importance signal).
# -----------------------------------------------------------------------------
TIER_BASE = {1: 100, 2: 70, 3: 0}
KEYWORD_WEIGHT = 12
AUTHOR_WEIGHT  = 15
FRESHNESS_TODAY_BONUS = 20
FRESHNESS_2DAY_BONUS  = 8
PAPERS_TOP_N = 12
LOOKBACK_DAYS = 3

# Clustering: two headlines are "the same story" if they share at least this
# many significant words (names/places/orgs), after removing common words.
CLUSTER_MIN_SHARED = 2

KEYWORDS = [
    "language model", "llm", "transformer", "instruction tuning", "rag",
    "reasoning", "agent", "fine-tun", "in-context", "chain-of-thought", "moe",
    "vision", "image", "segmentation", "detection", "diffusion", "multimodal",
    "video", "3d", "nerf", "gaussian splatting",
    "human-robot", "hri", "robot", "manipulation", "embodied", "teleoperation",
    "affective", "emotion", "computational psych", "cognitive", "theory of mind",
    "mental health", "psycholog", "behavior", "social",
    "representation learning", "self-supervised", "reinforcement learning",
    "optimization", "generalization", "scaling", "benchmark", "evaluation",
    "medical imaging", "radiology", "ecg", "clinical", "chest x-ray",
]

NOTABLE = [
    "deepmind", "google research", "fair", "meta ai", "microsoft research",
    "openai", "anthropic", "nvidia", "allen institute", "stanford", "mit",
    "berkeley", "cmu", "eth", "tsinghua",
]

PAGE_TITLE = "Morning ML"
PAGE_TAGLINE = "ML, papers, finance and world — one page."
