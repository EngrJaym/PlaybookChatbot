from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR    = _BACKEND_DIR.parent
_DATA_DIR_ENV = os.getenv("DATA_DIR", "").strip()
DATA_DIR: Path = Path(_DATA_DIR_ENV) if _DATA_DIR_ENV else _ROOT_DIR / "data"

_INDEX:     dict[str, Path] = {}
_CACHE:     dict[Path, dict] = {}
_CITATIONS: dict[str, dict] = {}
_SOURCE:    str = "local_file"


logger = logging.getLogger(__name__)


def _scan_data_dir() -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not DATA_DIR.exists():
        logger.warning("DATA_DIR '%s' does not exist.", DATA_DIR)
        return index
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        logger.warning("No JSON files found in '%s'.", DATA_DIR)
        return index
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            count = 0
            for node in data.get("nodes", []):
                nid = node.get("id")
                if nid:
                    index[nid] = path
                    count += 1
            logger.info("Indexed '%s': %d nodes", path.name, count)
        except Exception as exc:
            logger.warning("Could not index '%s': %s", path.name, exc)
    return index


def _load_playbook_file(path: Path) -> dict:
    if path in _CACHE:
        return _CACHE[path]
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    meta: dict = data.get("meta", {})
    flow: dict = {n["id"]: dict(n) for n in data.get("nodes", []) if n.get("id")}
    for nid, node in flow.items():
        if node.get("answer") is not None:
            _CITATIONS[nid] = {
                "source":  "local_file",
                "doc":     path.name,
                "heading": node.get("message") or nid,
                "match":   "json",
            }
    _CACHE[path] = {"flow": flow, "meta": meta}
    logger.info("Loaded '%s' (%d nodes)", path.name, len(flow))
    return _CACHE[path]


def _resolve_playbook(node_id: str) -> Optional[Path]:
    if node_id in _INDEX:
        return _INDEX[node_id]
    if DATA_DIR.exists():
        files = sorted(DATA_DIR.glob("*.json"))
        if files:
            return files[0]
    return None


def _load() -> None:
    global _INDEX, _SOURCE
    _CACHE.clear()
    _CITATIONS.clear()
    _SOURCE = "local_file"
    logger.info("Loading playbooks from DATA_DIR=%s", DATA_DIR)
    _INDEX = _scan_data_dir()
    for path in sorted({p for p in _INDEX.values()}):
        try:
            _load_playbook_file(path)
        except Exception as exc:
            logger.warning("Pre-load failed for '%s': %s", path.name, exc)
    if not _INDEX:
        logger.warning("No playbook nodes loaded.")


_load()


def reload() -> str:
    _load()
    return _SOURCE


def get_source() -> str:
    return _SOURCE


def get_node(node_id: str) -> Optional[dict]:
    path = _resolve_playbook(node_id)
    if path is None:
        return None
    try:
        book = _load_playbook_file(path)
    except Exception as exc:
        logger.error("Failed to load playbook '%s': %s", path, exc)
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


def get_meta() -> dict:
    home_path = _INDEX.get("home")
    if home_path is None and DATA_DIR.exists():
        files = sorted(DATA_DIR.glob("*.json"))
        home_path = files[0] if files else None
    if home_path and home_path in _CACHE:
        return dict(_CACHE[home_path]["meta"])
    return {"title": "NDS Playbook Chatbot", "version": "1.0", "company": "NDS"}


def get_all_node_ids() -> list:
    return list(_INDEX.keys())


def list_playbooks() -> list:
    books = []
    if DATA_DIR.exists():
        for f in sorted(DATA_DIR.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                meta = data.get("meta", {})
                books.append({
                    "file":       f.name,
                    "title":      meta.get("title", f.stem),
                    "company":    meta.get("company", ""),
                    "version":    meta.get("version", ""),
                    "node_count": len(data.get("nodes", [])),
                    "cached":     f in _CACHE,
                })
            except Exception:
                books.append({"file": f.name, "title": f.stem, "node_count": 0, "cached": False})
    return books


def get_active_playbook() -> str:
    cached = [p.name for p in _CACHE]
    return ", ".join(cached) if cached else "none"


def get_playbook_titles(filenames: list[str]) -> dict[str, str]:
    titles = {}
    for fname in filenames:
        path = DATA_DIR / fname
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                titles[fname] = data.get("meta", {}).get("title", path.stem)
            except Exception:
                titles[fname] = path.stem
        else:
            titles[fname] = fname.replace(".json", "").replace("_", " ").replace("-", " ").title()
    return titles

