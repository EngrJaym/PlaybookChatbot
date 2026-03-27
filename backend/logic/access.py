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
        logger.warning("access.json not found — access control will deny all")
        _rules = {}
        return
    with open(_ACCESS_FILE, "r", encoding="utf-8") as fh:
        _rules = json.load(fh)
    total_groups = sum(len(t.get("ad_groups", [])) for t in _rules.get("teams", []))
    logger.info(
        "Access rules loaded: %d teams, %d AD groups",
        len(_rules.get("teams", [])),
        total_groups,
    )


_load()


def reload_rules() -> None:
    _load()


def resolve_groups(username: str, groups: list[str]) -> dict:
    sam = (username or "").strip().lower()
    if not sam:
        return {"valid": False, "username": "", "team": None, "playbooks": []}

    groups_lower = [g.strip().lower() for g in (groups or [])]
    logger.debug(
        "resolve_groups: user='%s' groups_received=%s",
        sam,
        groups_lower,
    )

    for team in _rules.get("teams", []):
        team_groups = [g.strip().lower() for g in team.get("ad_groups", [])]
        logger.debug(
            "resolve_groups: checking team='%s' against ad_groups=%s",
            team.get("team"),
            team_groups,
        )
        for tg in team_groups:
            if tg in groups_lower:
                logger.info(
                    "resolve_groups: GRANTED user='%s' team='%s' matched='%s'",
                    sam,
                    team["team"],
                    tg,
                )
                return {
                    "valid": True,
                    "username": sam,
                    "team": team["team"],
                    "playbooks": list(team.get("playbooks", [])),
                }

    if _rules.get("defaults", {}).get("allow_all_if_no_rule", False):
        return {"valid": True, "username": sam, "team": "default", "playbooks": []}

    logger.warning(
        "resolve_groups: DENIED user='%s' — no team matched. groups_received=%s",
        sam,
        groups_lower,
    )
    return {"valid": False, "username": sam, "team": None, "playbooks": []}
