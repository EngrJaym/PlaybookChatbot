"""
Feature Flags & Central Configuration
======================================
All runtime switches for the NDS Playbook Chatbot are defined here.
Values are read from PlaybookChatbot/.env at import time.

DATA SOURCE MODE  (DATA_SOURCE)
--------------------------------
  "json"        →  Use JSON files only.  No Google Docs calls.
  "google"      →  JSON defines nodes; Google Docs supply answers by meaning.
                   If Docs fetch fails the JSON answer is kept as fallback.
  "both"        →  (RECOMMENDED) Same as "google" but lenient on failures.
                   Best quality: JSON structure + Docs real-time answers
                   + JSON fallback for any unmatched nodes.

CACHE
-----
  CACHE_TTL_SECONDS  int   — seconds before Docs answers are re-fetched (0=off)

FEATURE FLAGS
-------------
  ENABLE_CHAT           bool  — enable/disable the chat endpoint entirely
  ENABLE_RELOAD         bool  — enable/disable the /api/reload hot-reload endpoint
  ENABLE_DEBUG_ENDPOINTS bool — enable /api/nodes and /api/flags (debug info)
  ENABLE_META_ENDPOINT  bool  — enable /api/meta
  MAINTENANCE_MODE      bool  — return 503 on all chat requests with a message
  MAINTENANCE_MESSAGE   str   — message shown during maintenance mode

GOOGLE DOCS
-----------
  GOOGLE_SERVICE_ACCOUNT_FILE  — path to service_account.json
  GOOGLE_DOC_ID_<NAME>         — one per Google Doc
  GOOGLE_DOC_NODES_<NAME>      — comma-separated node IDs to narrow that doc

GENERAL
-------
  APP_ENV          — "development" | "production"  (affects logging verbosity)
  LOG_LEVEL        — "DEBUG" | "INFO" | "WARNING" | "ERROR"
"""

from __future__ import annotations

import os
import logging
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent
_ROOT_DIR    = _BACKEND_DIR.parent
load_dotenv(_ROOT_DIR / ".env")


def _bool(key: str, default: bool = True) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


DATA_SOURCE: str = _str("DATA_SOURCE", "both").lower()

if DATA_SOURCE not in ("json", "google", "both"):
    DATA_SOURCE = "both"

ENABLE_CHAT:             bool = _bool("ENABLE_CHAT",             True)
ENABLE_RELOAD:           bool = _bool("ENABLE_RELOAD",           True)
ENABLE_DEBUG_ENDPOINTS:  bool = _bool("ENABLE_DEBUG_ENDPOINTS",  True)
ENABLE_META_ENDPOINT:    bool = _bool("ENABLE_META_ENDPOINT",    True)

MAINTENANCE_MODE:        bool = _bool("MAINTENANCE_MODE",        False)
MAINTENANCE_MESSAGE:     str  = _str(
    "MAINTENANCE_MESSAGE",
    "The playbook is currently under maintenance. Please try again shortly."
)

_SA_REL   = _str("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
SA_FILE: Path = (Path(_SA_REL) if Path(_SA_REL).is_absolute() else _BACKEND_DIR / _SA_REL)

DATA_DIR_ENV: str = _str("DATA_DIR", "")

APP_ENV:   str = _str("APP_ENV",   "development")
LOG_LEVEL: str = _str("LOG_LEVEL", "INFO").upper()

# -----------------------------------------------------------------------------
# Team Resolution via trusted proxy headers (no backend LDAP calls)
# -----------------------------------------------------------------------------
TEAM_HEADER_NAME: str = _str("TEAM_HEADER_NAME", "X-User-Team")
TEAM_GROUPS_HEADER_NAME: str = _str("TEAM_GROUPS_HEADER_NAME", "X-User-Groups")
TEAM_REQUIRE_AUTH: bool = _bool("TEAM_REQUIRE_AUTH", False)
TEAM_PLAYBOOK_FALLBACK_FILE: str = _str("TEAM_PLAYBOOK_FALLBACK_FILE", "cm.json")
DEV_USER_GROUP_CNS: str = _str("DEV_USER_GROUP_CNS", "")

# Team mapping:
#   TEAM_MAP__<TEAM_OR_GROUP>=<playbook_file.json>
TEAM_MAP_PREFIX: str = "TEAM_MAP__"
TEAM_GROUP_PLAYBOOK_MAP: dict[str, str] = {}
for key, value in os.environ.items():
    if not key.startswith(TEAM_MAP_PREFIX):
        continue
    group_key = key[len(TEAM_MAP_PREFIX):].strip().upper()
    playbook_file = value.strip()
    if group_key and playbook_file:
        TEAM_GROUP_PLAYBOOK_MAP[group_key] = playbook_file

TEAM_GROUP_PRIORITY: list[str] = [
    g.strip().upper() for g in _str("TEAM_PRIORITY", "").split(",") if g.strip()
]


def as_dict() -> dict:
    """Return all feature flags as a serialisable dict for the /api/flags endpoint."""
    return {
        "app_env":             APP_ENV,
        "data_source":         DATA_SOURCE,
        "cache_ttl_seconds":   CACHE_TTL_SECONDS,
        "maintenance_mode":    MAINTENANCE_MODE,
        "maintenance_message": MAINTENANCE_MESSAGE if MAINTENANCE_MODE else None,
        "features": {
            "chat":            ENABLE_CHAT,
            "reload":          ENABLE_RELOAD,
            "debug_endpoints": ENABLE_DEBUG_ENDPOINTS,
            "meta_endpoint":   ENABLE_META_ENDPOINT,
        },
        "google_docs": {
            "credentials_file":  str(SA_FILE),
            "credentials_found": SA_FILE.exists(),
        },
        "team_resolution": {
            "header_name": TEAM_HEADER_NAME,
            "groups_header_name": TEAM_GROUPS_HEADER_NAME,
            "require_auth": TEAM_REQUIRE_AUTH,
            "fallback_playbook": TEAM_PLAYBOOK_FALLBACK_FILE,
            "mapped_group_count": len(TEAM_GROUP_PLAYBOOK_MAP),
            "priority_count": len(TEAM_GROUP_PRIORITY),
        },
    }


logging.getLogger().setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

