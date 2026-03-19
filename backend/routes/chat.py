from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from logic.flow import (
    get_node, get_meta, get_all_node_ids,
    get_source, reload, _collect_doc_entries,
    list_playbooks, get_active_playbook,
    _resolve_playbook, _load_playbook_file,
    _CITATIONS, _GDOCS_SENTINEL, _INDEX, _maybe_refresh,
    get_playbook_titles,
)
from logic.access import validate, get_allowed_playbooks, reload_rules

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


class LoginRequest(BaseModel):
    email: str

class ChatRequest(BaseModel):
    node_id: str = "home"
    email: str | None = None
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


@router.post("/login")
async def login(req: LoginRequest):
    if not config.ENABLE_ACCESS_CONTROL:
        return {"email": req.email.strip().lower(), "team": "all", "playbooks": [], "playbook_titles": {}}
    result = validate(req.email)
    if not result["valid"]:
        raise HTTPException(
            status_code=403,
            detail=f"'{req.email}' is not registered in any team. Contact your lead.",
        )
    titles = get_playbook_titles(result["playbooks"])
    return {
        "email": result["email"],
        "team": result["team"],
        "playbooks": result["playbooks"],
        "playbook_titles": titles,
    }


@router.get("/meta", response_model=MetaResponse)
async def meta():
    _flag_check(config.ENABLE_META_ENDPOINT, "ENABLE_META_ENDPOINT")
    return MetaResponse(**get_meta(), source=get_source())


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    _flag_check(config.ENABLE_CHAT, "ENABLE_CHAT")
    _maintenance_check()

    if config.ENABLE_ACCESS_CONTROL and req.email:
        result = validate(req.email)
        if not result["valid"]:
            raise HTTPException(status_code=403, detail=f"Access denied for '{req.email}'.")
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
    _maybe_refresh()
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
    _maybe_refresh()

    if playbook_file and playbook_file in (allowed or []):
        from pathlib import Path
        data_dir = Path(config.DATA_DIR_ENV) if config.DATA_DIR_ENV else Path(__file__).resolve().parent.parent.parent / "data"
        path = data_dir / playbook_file
        if path.exists():
            try:
                book = _load_playbook_file(path)
            except Exception:
                return None
            node = book["flow"].get(node_id)
            if node is None:
                return None
            if allowed:
                filtered_buttons = [
                    b for b in node.get("buttons", [])
                    if _btn_allowed(b.get("next", ""), allowed)
                ]
            else:
                filtered_buttons = node.get("buttons", [])
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
    if allowed and path != _GDOCS_SENTINEL and path.name not in allowed:
        return None
    try:
        book = _load_playbook_file(path)
    except Exception:
        return None
    node = book["flow"].get(node_id)
    if node is None:
        return None
    if allowed:
        filtered_buttons = [
            b for b in node.get("buttons", [])
            if _btn_allowed(b.get("next", ""), allowed)
        ]
    else:
        filtered_buttons = node.get("buttons", [])
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
    if path is None or path == _GDOCS_SENTINEL:
        return True
    return path.name in allowed


@router.post("/reload")
async def reload_playbook():
    _flag_check(config.ENABLE_RELOAD, "ENABLE_RELOAD")
    try:
        reload_rules()
        source = reload()
        return {
            "status": "ok",
            "source": source,
            "node_count": len(get_all_node_ids()),
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
    entries = _collect_doc_entries()
    return {
        "source":           get_source(),
        "data_source_mode": config.DATA_SOURCE,
        "active_playbook":  get_active_playbook(),
        "node_count":       len(get_all_node_ids()),
        "node_ids":         get_all_node_ids(),
        "google_docs": {
            "credentials_file":  str(config.SA_FILE),
            "credentials_found": config.SA_FILE.exists(),
            "registered_docs": [
                {
                    "name":   e["name"],
                    "doc_id": e["doc_id"][:20] + "\u2026",
                    "scope":  "all nodes" if e["node_ids"] is None else sorted(e["node_ids"]),
                }
                for e in entries
            ],
        },
    }


@router.get("/playbooks")
async def playbooks():
    return {"active": get_active_playbook(), "playbooks": list_playbooks()}
