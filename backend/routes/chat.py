from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from logic.flow import (
    get_node, get_meta, get_all_node_ids,
    get_source, reload,
    list_playbooks, get_active_playbook,
    _resolve_playbook, _load_playbook_file,
    _CITATIONS, _INDEX,
    get_playbook_titles,
)
from logic.access import resolve_groups, reload_rules
from logic.ad import lookup_ad_groups

router = APIRouter(prefix="/api", tags=["chat"])


def _maintenance_check():
    if config.MAINTENANCE_MODE:
        raise HTTPException(
            status_code=503,
            detail={"maintenance": True, "message": config.MAINTENANCE_MESSAGE},
        )


def _flag_check(flag: bool, name: str):
    if not flag:
        raise HTTPException(status_code=404, detail=f"Endpoint disabled: '{name}'.")


class ADLoginRequest(BaseModel):
    username: str
    groups: list[str] = []

class WhoamiRequest(BaseModel):
    username: str

class ChatRequest(BaseModel):
    node_id:  str = "home"
    username: str | None = None
    groups:   list[str] = []
    playbook: str | None = None

class ButtonOut(BaseModel):
    label: str
    next: str

class ChatResponse(BaseModel):
    id: str
    message: str
    answer: str | None = None
    buttons: list[ButtonOut]
    type: str | None = None
    citation: dict | None = None

class MetaResponse(BaseModel):
    title: str
    version: str
    company: str
    source: str


@router.post("/ad-login")
async def ad_login(req: ADLoginRequest):
    if not config.ENABLE_ACCESS_CONTROL:
        return {"username": req.username.strip().lower(), "team": "all", "playbooks": [], "playbook_titles": {}}
    result = resolve_groups(req.username, req.groups)
    if not result["valid"]:
        raise HTTPException(
            status_code=403,
            detail=f"'{req.username}' is not in any authorised AD group. Contact your team lead.",
        )
    titles = get_playbook_titles(result["playbooks"])
    return {
        "username":        result["username"],
        "team":            result["team"],
        "playbooks":       result["playbooks"],
        "playbook_titles": titles,
    }


@router.post("/whoami")
async def whoami(req: WhoamiRequest):
    sam = (req.username or "").strip().lower()
    if not sam:
        raise HTTPException(status_code=400, detail="Username is required")

    ad_result = lookup_ad_groups(sam)

    if not config.ENABLE_ACCESS_CONTROL:
        return {
            "username":        sam,
            "groups":          ad_result["groups"],
            "team":            "all",
            "playbooks":       [],
            "playbook_titles": {},
            "ad_error":        ad_result.get("error"),
        }

    access = resolve_groups(sam, ad_result["groups"])
    if not access["valid"]:
        raise HTTPException(
            status_code=403,
            detail=f"'{sam}' is not in any authorised AD group. Contact your team lead.",
        )

    titles = get_playbook_titles(access["playbooks"])
    return {
        "username":        access["username"],
        "groups":          ad_result["groups"],
        "team":            access["team"],
        "playbooks":       access["playbooks"],
        "playbook_titles": titles,
        "ad_error":        ad_result.get("error"),
    }


@router.get("/meta", response_model=MetaResponse)
async def meta():
    _flag_check(config.ENABLE_META_ENDPOINT, "ENABLE_META_ENDPOINT")
    return MetaResponse(**get_meta(), source=get_source())


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    _flag_check(config.ENABLE_CHAT, "ENABLE_CHAT")
    _maintenance_check()

    if config.ENABLE_ACCESS_CONTROL and req.username:
        result = resolve_groups(req.username, req.groups)
        if not result["valid"]:
            raise HTTPException(status_code=403, detail=f"Access denied for '{req.username}'.")
        node = _get_node_filtered(req.node_id, result["playbooks"], req.playbook)
    else:
        node = _get_node_for_playbook(req.node_id, req.playbook) if req.playbook else get_node(req.node_id)

    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{req.node_id}' not found.")

    return ChatResponse(
        id=node["id"],
        message=node["message"],
        answer=node.get("answer"),
        buttons=[ButtonOut(**b) for b in node["buttons"]],
        type=node.get("type"),
        citation=node.get("citation"),
    )


def _get_node_for_playbook(node_id: str, playbook_file: str) -> dict | None:
    from pathlib import Path
    data_dir = Path(config.DATA_DIR_ENV) if config.DATA_DIR_ENV else Path(__file__).resolve().parent.parent.parent / "data"
    path = data_dir / playbook_file
    if not path.exists():
        return get_node(node_id)
    try:
        book = _load_playbook_file(path)
    except Exception:
        return None
    node = book["flow"].get(node_id)
    if node is None:
        return None
    return {
        "id":       node["id"],
        "message":  node["message"],
        "answer":   node.get("answer"),
        "buttons":  node.get("buttons", []),
        "type":     node.get("type"),
        "citation": _CITATIONS.get(node_id),
    }


def _get_node_filtered(node_id: str, allowed: list[str], playbook_file: str | None = None) -> dict | None:
    from pathlib import Path
    data_dir = Path(config.DATA_DIR_ENV) if config.DATA_DIR_ENV else Path(__file__).resolve().parent.parent.parent / "data"

    targets = []
    if playbook_file and playbook_file in (allowed or []):
        targets = [playbook_file]
    elif allowed:
        targets = list(allowed)

    for fname in targets:
        path = data_dir / fname
        if not path.exists():
            continue
        try:
            book = _load_playbook_file(path)
        except Exception:
            continue
        node = book["flow"].get(node_id)
        if node is None:
            continue
        filtered_buttons = [b for b in node.get("buttons", []) if _btn_allowed(b.get("next", ""), allowed)] if allowed else node.get("buttons", [])
        return {
            "id":       node["id"],
            "message":  node["message"],
            "answer":   node.get("answer"),
            "buttons":  filtered_buttons,
            "type":     node.get("type"),
            "citation": _CITATIONS.get(node_id),
        }

    path = _resolve_playbook(node_id)
    if path is None:
        return None
    if allowed and path.name not in allowed:
        return None
    try:
        book = _load_playbook_file(path)
    except Exception:
        return None
    node = book["flow"].get(node_id)
    if node is None:
        return None
    filtered_buttons = [b for b in node.get("buttons", []) if _btn_allowed(b.get("next", ""), allowed)] if allowed else node.get("buttons", [])
    return {
        "id":       node["id"],
        "message":  node["message"],
        "answer":   node.get("answer"),
        "buttons":  filtered_buttons,
        "type":     node.get("type"),
        "citation": _CITATIONS.get(node_id),
    }


def _btn_allowed(next_id: str, allowed: list[str]) -> bool:
    path = _INDEX.get(next_id)
    if path is None:
        return True
    return path.name in allowed


@router.post("/reload")
async def reload_playbook():
    _flag_check(config.ENABLE_RELOAD, "ENABLE_RELOAD")
    try:
        reload_rules()
        source = reload()
        return {
            "status":           "ok",
            "source":           source,
            "node_count":       len(get_all_node_ids()),
            "data_source_mode": config.DATA_SOURCE,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flags")
async def flags():
    _flag_check(config.ENABLE_DEBUG_ENDPOINTS, "ENABLE_DEBUG_ENDPOINTS")
    return config.as_dict()


@router.get("/nodes")
async def nodes():
    _flag_check(config.ENABLE_DEBUG_ENDPOINTS, "ENABLE_DEBUG_ENDPOINTS")
    return {
        "source":           get_source(),
        "active_playbook":  get_active_playbook(),
        "node_count":       len(get_all_node_ids()),
        "node_ids":         get_all_node_ids(),
    }


@router.get("/playbooks")
async def playbooks():
    return {"active": get_active_playbook(), "playbooks": list_playbooks()}
