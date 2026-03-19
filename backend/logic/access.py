from __future__ import annotations

import json
import logging
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ACCESS_FILE = _BACKEND_DIR / "access.json"

logger = logging.getLogger(__name__)
_rules: dict = {}


def _load() -> None:
    global _rules
    if not _ACCESS_FILE.exists():
        logger.warning("access.json not found at %s — access control will deny all", _ACCESS_FILE)
        _rules = {}
        return
    with open(_ACCESS_FILE, "r", encoding="utf-8") as fh:
        _rules = json.load(fh)
    total = sum(len(t.get("members", [])) for t in _rules.get("teams", []))
    logger.info("Access rules loaded: %d teams, %d members", len(_rules.get("teams", [])), total)


_load()


def reload_rules() -> None:
    _load()


def validate(email: str) -> dict:
    em = (email or "").strip().lower()
    if not em:
        return {"valid": False, "email": "", "team": None, "playbooks": []}
    for team in _rules.get("teams", []):
        members = [m.strip().lower() for m in team.get("members", [])]
        if em in members:
            return {
                "valid": True,
                "email": em,
                "team": team["team"],
                "playbooks": list(team.get("playbooks", [])),
            }
    if _rules.get("defaults", {}).get("allow_all_if_no_rule", False):
        return {"valid": True, "email": em, "team": "default", "playbooks": []}
    return {"valid": False, "email": em, "team": None, "playbooks": []}


def get_allowed_playbooks(email: str) -> list[str]:
    return validate(email)["playbooks"]

