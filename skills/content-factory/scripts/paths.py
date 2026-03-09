"""
Shared path configuration for Content Factory.
All data paths are relative to SKILL_DIR, making the skill portable.
"""
from pathlib import Path

# SKILL_DIR = parent of scripts/
SKILL_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = SKILL_DIR / "data"

HOTPOOL_DIR = DATA_DIR / "hotpool"
TOPICS_DIR = DATA_DIR / "topics"
DRAFTS_DIR = DATA_DIR / "drafts"
REVIEWED_DIR = DATA_DIR / "reviewed"
PUBLISHED_DIR = DATA_DIR / "published"
TEMPLATES_DIR = DATA_DIR / "templates"
CONFIG_DIR = DATA_DIR / "config"
ASSETS_DIR = DATA_DIR / "assets"

LOG_FILE = DATA_DIR / "daily.log"

# Local aggregator
FETCH_ALL = SKILL_DIR / "scripts" / "aggregator" / "fetch_all.py"

# Newsbot: prefer environment variable, then local scripts
import os
_newsbot_env = os.environ.get("NEWSBOT_SEND")
NEWSBOT_SEND = Path(_newsbot_env) if _newsbot_env else (
    Path.home() / "clawd/scripts/newsbot_send.py"
)

# Ensure data dirs exist on import
for d in [HOTPOOL_DIR, TOPICS_DIR, DRAFTS_DIR, REVIEWED_DIR, PUBLISHED_DIR,
          TEMPLATES_DIR, CONFIG_DIR, ASSETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
