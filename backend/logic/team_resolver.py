from __future__ import annotations

from typing import Tuple

from fastapi import HTTPException, Request

import config


def _normalize_key(raw: str) -> str:
    raw = raw.strip()
    return raw.upper() if raw else ""


def _split_header_values(raw: str) -> list[str]:
    values = []
    for part in raw.replace(";", ",").split(","):
        token = part.strip()
        if token:
            values.append(token)
    return values


def _resolve_playbook_by_member_groups(member_groups: list[str]) -> Tuple[str, str]:
    member_group_keys = {_normalize_key(g) for g in member_groups if _normalize_key(g)}
    group_map = config.TEAM_GROUP_PLAYBOOK_MAP
    if not group_map:
        raise HTTPException(
            status_code=500,
            detail="Team mapping is empty. Configure TEAM_MAP__<TEAM_OR_GROUP>=<playbook.json>.",
        )

    for group_key in config.TEAM_GROUP_PRIORITY:
        if group_key in member_group_keys and group_key in group_map:
            return group_key, group_map[group_key]

    for group_key, playbook_file in group_map.items():
        if group_key in member_group_keys:
            return group_key, playbook_file

    raise HTTPException(status_code=403, detail="User team/group is not allowed for this chatbot.")


def resolve_team_and_playbook(request: Request) -> Tuple[str, str]:
    dev_groups_raw = config.DEV_USER_GROUP_CNS
    if dev_groups_raw:
        dev_groups = [g.strip() for g in dev_groups_raw.split(",") if g.strip()]
        return _resolve_playbook_by_member_groups(dev_groups)

    team_header_val = request.headers.get(config.TEAM_HEADER_NAME, "").strip()
    if team_header_val:
        team_key = _normalize_key(team_header_val)
        if team_key in config.TEAM_GROUP_PLAYBOOK_MAP:
            return team_key, config.TEAM_GROUP_PLAYBOOK_MAP[team_key]
        raise HTTPException(status_code=403, detail="Provided team is not mapped/allowed.")

    groups_header_val = request.headers.get(config.TEAM_GROUPS_HEADER_NAME, "").strip()
    if groups_header_val:
        proxy_groups = _split_header_values(groups_header_val)
        return _resolve_playbook_by_member_groups(proxy_groups)

    if config.TEAM_REQUIRE_AUTH:
        raise HTTPException(
            status_code=401,
            detail=(
                f"Missing required proxy team headers: "
                f"{config.TEAM_HEADER_NAME} or {config.TEAM_GROUPS_HEADER_NAME}."
            ),
        )

    return "fallback", config.TEAM_PLAYBOOK_FALLBACK_FILE

