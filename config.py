# =============================================================================
# config.py — the only file you need to touch to tune your feed.
# Everything here is a plain dial. No code changes required to retune.
# =============================================================================

# -----------------------------------------------------------------------------
# SOURCES
# Each source has a `tier`. Tier sets the base score of everything from it,
# so curators (who filter well and fast) naturally outrank the arXiv firehose.
#   tier 1 = human curators   (highest base score)
#   tier 2 = official labs     (authoritative on releases)
#   tier 3 = raw arXiv         (long tail; only floats up on keyword/author match)
# `kind` is "rss" or "arxiv". arXiv sources use the API; the rest use RSS/Atom.
# Comment out any line to drop a source. Add your own the same way.
# -----------------------------------------------------------------------------

SOURCES = [
    # --- TIER 1: curators (pre-filtered by smart humans, often fastest) ------
    {"name": "HF Daily Papers",        "kind": "rss",   "tier": 1,
     "url": "https://jamesg.blog/hf-papers.xml"},  # mirror of HF daily papers
    {"name": "Import AI",              "kind": "rss",   "tier": 1,
     "url": "https://importai.substack.com/feed"},
    {"name": "Sebastian Raschka",      "kind": "rss",   "tier": 1,
     "url": "https://magazine.sebastianraschka.com/feed"},
    {"name": "Davis Summarizes Papers","kind": "rss",   "tier": 1,
     "url": "https://dsp.substack.com/feed"},
    {"name": "The Batch (DeepLearning.AI)", "kind": "rss", "tier": 1,
     "url": "https://www.deeplearning.ai/the-batch/feed/"},

    # --- TIER 2: official lab / company blogs --------------------------------
    {"name": "Google DeepMind",        "kind": "rss",   "tier": 2,
     "url": "https://deepmind.google/blog/rss.xml"},
    {"name": "Meta AI",                "kind": "rss",   "tier": 2,
     "url": "https://ai.meta.com/blog/rss/"},
    {"name": "NVIDIA Dev Blog",        "kind": "rss",   "tier": 2,
     "url": "https://developer.nvidia.com/blog/feed/"},
    {"name": "OpenAI",                 "kind": "rss",   "tier": 2,
     "url": "https://openai.com/news/rss.xml"},
    {"name": "Anthropic",              "kind": "rss",   "tier": 2,
     "url": "https://www.anthropic.com/rss.xml"},
    {"name": "Hugging Face Blog",      "kind": "rss",   "tier": 2,
     "url": "https://huggingface.co/blog/feed.xml"},

    # --- TIER 3: raw arXiv per category (the long tail) ----------------------
    # cs.CL=NLP/LLMs, cs.CV=vision, cs.LG=ML, cs.RO=robotics/HRI,
    # cs.HC=human-computer interaction, cs.AI=general AI, q-bio.NC=neuro/comp-psych
    {"name": "arXiv cs.CL", "kind": "arxiv", "tier": 3, "cat": "cs.CL"},
    {"name": "arXiv cs.CV", "kind": "arxiv", "tier": 3, "cat": "cs.CV"},
    {"name": "arXiv cs.LG", "kind": "arxiv", "tier": 3, "cat": "cs.LG"},
    {"name": "arXiv cs.RO", "kind": "arxiv", "tier": 3, "cat": "cs.RO"},
    {"name": "arXiv cs.HC", "kind": "arxiv", "tier": 3, "cat": "cs.HC"},
    {"name": "arXiv cs.AI", "kind": "arxiv", "tier": 3, "cat": "cs.AI"},
]

# -----------------------------------------------------------------------------
# SCORING WEIGHTS
# Final score = tier_base + keyword_hits*KEYWORD_WEIGHT + author_hits*AUTHOR_WEIGHT
#               + freshness_bonus.  Everything is transparent and additive.
# -----------------------------------------------------------------------------

TIER_BASE = {1: 100, 2: 70, 3: 0}   # curators start way ahead of raw arXiv
KEYWORD_WEIGHT = 12                  # points per matched interest keyword
AUTHOR_WEIGHT  = 15                  # points per matched notable author/affiliation
FRESHNESS_TODAY_BONUS = 20           # published in last 24h
FRESHNESS_2DAY_BONUS  = 8            # published in last 48h

# How many items go in the ranked "top" section. Rest go to "everything else".
TOP_N = 15

# Only keep items from the last N days (keeps the page from growing forever).
LOOKBACK_DAYS = 3

# -----------------------------------------------------------------------------
# YOUR INTEREST KEYWORDS  (case-insensitive substring match on title+summary)
# These are what pull a raw arXiv paper up into relevance. Tune freely.
# Grouped only for your readability; they're all treated equally.
# -----------------------------------------------------------------------------

KEYWORDS = [
    # LLMs
    "language model", "llm", "transformer", "instruction tuning", "rag",
    "reasoning", "agent", "fine-tun", "in-context", "chain-of-thought", "moe",
    # CV
    "vision", "image", "segmentation", "detection", "diffusion", "multimodal",
    "video", "3d", "nerf", "gaussian splatting",
    # HRI / robotics
    "human-robot", "hri", "robot", "manipulation", "embodied", "teleoperation",
    # computational psychology / affective
    "affective", "emotion", "computational psych", "cognitive", "theory of mind",
    "mental health", "psycholog", "behavior", "social",
    # general ML
    "representation learning", "self-supervised", "reinforcement learning",
    "optimization", "generalization", "scaling", "benchmark", "evaluation",
    # medical (your day job — kept but not dominant)
    "medical imaging", "radiology", "ecg", "clinical", "chest x-ray",
]

# -----------------------------------------------------------------------------
# NOTABLE AUTHORS / AFFILIATIONS  (case-insensitive substring on author string)
# A rough signal that a raw arXiv paper is worth a look. Optional; tune freely.
# -----------------------------------------------------------------------------

NOTABLE = [
    "deepmind", "google research", "fair", "meta ai", "microsoft research",
    "openai", "anthropic", "nvidia", "allen institute", "stanford", "mit",
    "berkeley", "cmu", "eth", "tsinghua",
]

# -----------------------------------------------------------------------------
# PAGE
# -----------------------------------------------------------------------------

PAGE_TITLE = "Morning ML"
PAGE_TAGLINE = "One page. Curators first, firehose filtered."
