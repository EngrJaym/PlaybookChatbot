from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _BACKEND_DIR.parent
load_dotenv(_ROOT_DIR / ".env")


def _bool(key: str, default: bool = True) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes")


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


ENABLE_CHAT: bool = _bool("ENABLE_CHAT", True)
ENABLE_RELOAD: bool = _bool("ENABLE_RELOAD", True)
ENABLE_DEBUG_ENDPOINTS: bool = _bool("ENABLE_DEBUG_ENDPOINTS", True)
ENABLE_META_ENDPOINT: bool = _bool("ENABLE_META_ENDPOINT", True)
ENABLE_ACCESS_CONTROL: bool = _bool("ENABLE_ACCESS_CONTROL", True)

MAINTENANCE_MODE: bool = _bool("MAINTENANCE_MODE", False)
MAINTENANCE_MESSAGE: str = _str(
    "MAINTENANCE_MESSAGE",
    "The playbook is currently under maintenance. Please try again shortly.",
)

DATA_DIR_ENV: str = _str("DATA_DIR", "")

AD_SERVER: str = _str("AD_SERVER", "samba-ad.ad.one-nds.net")
AD_BASE_DN: str = _str("AD_BASE_DN", "DC=ad,DC=one-nds,DC=net")
AD_BIND_USER: str = _str("AD_BIND_USER", "")
AD_BIND_PASSWORD: str = _str("AD_BIND_PASSWORD", "")

APP_ENV: str = _str("APP_ENV", "development")
LOG_LEVEL: str = _str("LOG_LEVEL", "INFO").upper()


def as_dict() -> dict:
    return {
        "app_env": APP_ENV,
        "maintenance_mode": MAINTENANCE_MODE,
        "maintenance_message": MAINTENANCE_MESSAGE if MAINTENANCE_MODE else None,
        "features": {
            "chat": ENABLE_CHAT,
            "reload": ENABLE_RELOAD,
            "debug_endpoints": ENABLE_DEBUG_ENDPOINTS,
            "meta_endpoint": ENABLE_META_ENDPOINT,
            "access_control": ENABLE_ACCESS_CONTROL,
        },
    }


logging.getLogger().setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
