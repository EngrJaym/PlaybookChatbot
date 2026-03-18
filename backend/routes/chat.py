from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from logic.flow import get_node, get_meta, get_all_node_ids

router = APIRouter(prefix="/api", tags=["chat"])


# ── Models ──────────────────────────────────────────────────
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


class MetaResponse(BaseModel):
    title: str
    version: str
    company: str


# ── Endpoints ───────────────────────────────────────────────
@router.get("/meta", response_model=MetaResponse)
async def meta():
    """Return playbook metadata (title, version, company)."""
    return MetaResponse(**get_meta())


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Return the playbook node for the requested node_id."""
    node = get_node(req.node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node '{req.node_id}' not found")
    return ChatResponse(
        id=node["id"],
        message=node["message"],
        answer=node.get("answer"),
        buttons=[ButtonOut(**b) for b in node["buttons"]],
        type=node.get("type"),
    )


@router.get("/nodes")
async def nodes():
    """Return all node IDs (for debugging)."""
    return {"node_ids": get_all_node_ids(), "count": len(get_all_node_ids())}
