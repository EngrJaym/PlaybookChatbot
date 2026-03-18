from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import config
from logic.flow import (
    get_node, get_meta, get_all_node_ids,
    get_source, reload, _collect_doc_entries,
    list_playbooks, get_active_playbook,
)

router = APIRouter(prefix="/api", tags=["chat"])


def _maintenance_check():
    """Raise 503 if MAINTENANCE_MODE is on."""
    if config.MAINTENANCE_MODE:
        raise HTTPException(
            status_code=503,
            detail={
                "maintenance": True,
                "message": config.MAINTENANCE_MESSAGE,
            },
        )


def _flag_check(flag: bool, name: str):
    """Raise 404 if a feature flag is disabled."""
    if not flag:
        raise HTTPException(
            status_code=404,
            detail=f"Endpoint disabled by feature flag '{name}'.",
        )



class ChatRequest(BaseModel):
    node_id: str = "home"

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



@router.get("/meta", response_model=MetaResponse)
async def meta():
    _flag_check(config.ENABLE_META_ENDPOINT, "ENABLE_META_ENDPOINT")
    return MetaResponse(**get_meta(), source=get_source())


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    _flag_check(config.ENABLE_CHAT, "ENABLE_CHAT")
    _maintenance_check()
    node = get_node(req.node_id)
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


@router.post("/reload")
async def reload_playbook():
    _flag_check(config.ENABLE_RELOAD, "ENABLE_RELOAD")
    try:
        source = reload()
        return {
            "status":     "ok",
            "source":     source,
            "node_count": len(get_all_node_ids()),
            "data_source_mode": config.DATA_SOURCE,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flags")
async def flags():
    """Return all active feature flags and config (debug)."""
    _flag_check(config.ENABLE_DEBUG_ENDPOINTS, "ENABLE_DEBUG_ENDPOINTS")
    return config.as_dict()


@router.get("/nodes")
async def nodes():
    """Return all node IDs and registered Google Docs info (debug)."""
    _flag_check(config.ENABLE_DEBUG_ENDPOINTS, "ENABLE_DEBUG_ENDPOINTS")
    entries = _collect_doc_entries()
    docs_info = [
        {
            "name":   e["name"],
            "doc_id": e["doc_id"][:20] + "…",
            "scope":  "all nodes" if e["node_ids"] is None else sorted(e["node_ids"]),
        }
        for e in entries
    ]
    return {
        "source":           get_source(),
        "data_source_mode": config.DATA_SOURCE,
        "active_playbook":  get_active_playbook(),
        "node_count":       len(get_all_node_ids()),
        "node_ids":         get_all_node_ids(),
        "google_docs": {
            "credentials_file":  str(config.SA_FILE),
            "credentials_found": config.SA_FILE.exists(),
            "registered_docs":   docs_info,
        },
    }


@router.get("/playbooks")
async def playbooks():
    """List all available playbook JSON files in the data directory."""
    return {
        "active":    get_active_playbook(),
        "playbooks": list_playbooks(),
    }


