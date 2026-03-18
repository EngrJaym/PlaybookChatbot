"""
Playbook flow engine — loads decision tree from data/cm.json.

Each node has:
  - id       : str           – unique node identifier
  - message  : str           – heading / title shown to user
  - answer   : str | None    – detailed content (optional)
  - buttons  : list[dict]    – each dict has "label" and "next"
"""

import json
import os

_DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "cm.json"
)

_FLOW: dict[str, dict] = {}
_META: dict = {}


def _load():
    global _FLOW, _META
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    _META = data.get("meta", {})
    for node in data.get("nodes", []):
        _FLOW[node["id"]] = node


# Load on import
_load()


def reload():
    """Hot-reload the JSON (useful during development)."""
    _load()


def get_meta() -> dict:
    return dict(_META)


def get_node(node_id: str) -> dict | None:
    """Return a copy of the node dict for the given id, or None."""
    node = _FLOW.get(node_id)
    if node is None:
        return None
    return {
        "id": node["id"],
        "message": node["message"],
        "answer": node.get("answer"),
        "buttons": node["buttons"],
        "type": node.get("type"),
    }


def get_all_node_ids() -> list[str]:
    """Return all node IDs (for debugging / validation)."""
    return list(_FLOW.keys())
