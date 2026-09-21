import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
AICREDITS_API_KEY = os.getenv("AICREDITS_API_KEY", "").strip()
AICREDITS_BASE_URL = os.getenv("AICREDITS_BASE_URL", "https://aicredits.in/v1").strip()
AI_MODEL = os.getenv("AI_MODEL", "z-ai/glm-5.3-flash").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
BOT_PREFIX = os.getenv("BOT_PREFIX", "!ng").strip()
ADMIN_ROLE_NAME = os.getenv("ADMIN_ROLE_NAME", "Admin").strip().lower()

_raw_admin_ids = os.getenv("ADMIN_USER_IDS", "").strip()
ADMIN_USER_IDS = {int(uid.strip()) for uid in _raw_admin_ids.split(",") if uid.strip().isdigit()}

MEDIA_DIR = BASE_DIR / "src" / "media"
TEMP_MEDIA_DIR = MEDIA_DIR / "temp_media"
MEMORY_DIR = BASE_DIR / "src" / "utils" / "memory"

TEMP_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_DIR.mkdir(parents=True, exist_ok=True)
