# =============================================================================
# config.py — the only file you need to touch to tune your feed.
# Every source now has a `section`: "news" | "papers".
#   news   -> curators + lab/company posts (announcements, releases, analysis)
#   papers -> raw arXiv preprints
# The page renders News first, Papers second, so releases stop drowning.
# =============================================================================

SOURCES = [
    # --- TIER 1: curators (pre-filtered by smart humans, often fastest) ------
    # NOTE: Substack feeds (/feed) sometimes get refused when GitHub's servers
    # fetch them (datacenter IP). They usually still work; if one keeps failing
    # in the Actions log, that's why — not a wrong URL.
    {"name": "Import AI",              "kind": "rss", "tier": 1, "section": "news",
     "url": "https://importai.substack.com/feed"},
    {"name": "Interconnects (Lambert)","kind": "rss", "tier": 1, "section": "news",
     "url": "https://www.interconnects.ai/feed"},
    {"name": "The AI Breakfast",       "kind": "rss", "tier": 1, "section": "news",
     "url": "https://aibreakfast.beehiiv.com/feed"},  # Beehiiv; fetches reliably
    {"name": "Sebastian Raschka",      "kind": "rss", "tier": 1, "section": "news",
     "url": "https://magazine.sebastianraschka.com/feed"},
    {"name": "The Batch (DeepLearning.AI)", "kind": "rss", "tier": 1, "section": "news",
     "url": "https://www.deeplearning.ai/the-batch/feed/"},
    {"name": "HF Daily Papers",        "kind": "rss", "tier": 1, "section": "news",
     "url": "https://jamesg.blog/hf-papers.xml"},

    # --- TIER 2: official lab / company blogs (releases & announcements) ------
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

    # --- TIER 3: raw arXiv per category (the papers section) -----------------
    {"name": "arXiv cs.CL", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.CL"},
    {"name": "arXiv cs.CV", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.CV"},
    {"name": "arXiv cs.LG", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.LG"},
    {"name": "arXiv cs.RO", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.RO"},
    {"name": "arXiv cs.HC", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.HC"},
    {"name": "arXiv cs.AI", "kind": "arxiv", "tier": 3, "section": "papers", "cat": "cs.AI"},
]

# -----------------------------------------------------------------------------
# SCORING (unchanged logic; used to rank *within* each section)
# -----------------------------------------------------------------------------
TIER_BASE = {1: 100, 2: 70, 3: 0}
KEYWORD_WEIGHT = 12
AUTHOR_WEIGHT  = 15
FRESHNESS_TODAY_BONUS = 20
FRESHNESS_2DAY_BONUS  = 8

# How many arXiv papers to feature at the top of the Papers section (ranked).
# The rest of the papers go in a scannable "more papers" list below.
PAPERS_TOP_N = 12
LOOKBACK_DAYS = 3

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
PAGE_TAGLINE = "News and releases first. Papers below."
