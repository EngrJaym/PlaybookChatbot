"""
Playbook flow engine - multi-playbook auto-routing edition.
"""
from __future__ import annotations
import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional
import config
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ROOT_DIR    = _BACKEND_DIR.parent
_DATA_DIR_ENV = os.getenv("DATA_DIR", "").strip()
DATA_DIR: Path = Path(_DATA_DIR_ENV) if _DATA_DIR_ENV else _ROOT_DIR / "data"
SA_FILE = config.SA_FILE
_SCOPES         = ["https://www.googleapis.com/auth/documents.readonly"]
_HEADING_STYLES = {"HEADING_1", "HEADING_2", "HEADING_3", "HEADING_4", "TITLE"}
_INDEX:    dict[str, Path]  = {}
_CACHE:    dict[Path, dict] = {}
_SOURCE:   str              = "unknown"
_CITATIONS: dict[str, dict] = {}
_docs_service = None
logger = logging.getLogger(__name__)
def _collect_doc_entries() -> list:
    entries = []
    seen: set = set()
    prefix = "GOOGLE_DOC_ID_"
    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue
        doc_id = value.strip()
        if not doc_id:
            continue
        name = key[len(prefix):]
        if name in seen:
            continue
        seen.add(name)
        nodes_raw = os.getenv(f"GOOGLE_DOC_NODES_{name}", "").strip()
        node_ids = (
            {n.strip() for n in nodes_raw.split(",") if n.strip()}
            if nodes_raw else None
        )
        entries.append({"name": name, "doc_id": doc_id, "node_ids": node_ids})
        logger.info(f"  Registered doc {name!r}: id={doc_id[:16]}  scope={'ALL' if node_ids is None else len(node_ids)}")
    return entries
def _get_docs_service():
    global _docs_service
    if _docs_service is not None:
        return _docs_service
    if not SA_FILE.exists():
        raise FileNotFoundError(f"Service account credentials not found: {SA_FILE}")
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(str(SA_FILE), scopes=_SCOPES)
    _docs_service = build("docs", "v1", credentials=creds, cache_discovery=False)
    logger.info("Google Docs API service initialised.")
    return _docs_service
def _fetch_google_doc(doc_id: str) -> dict:
    return _get_docs_service().documents().get(documentId=doc_id).execute()
def _paragraph_text(paragraph: dict) -> str:
    parts = []
    for el in paragraph.get("elements", []):
        content = el.get("textRun", {}).get("content", "")
        if content:
            parts.append(content)
    return "".join(parts).rstrip("\n")
def _extract_doc_sections(doc: dict) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current_heading_norm: Optional[str] = None
    current_heading_text: Optional[str] = None
    body_lines: list[str] = []
    def _flush() -> None:
        nonlocal current_heading_norm, current_heading_text, body_lines
        if current_heading_norm is not None:
            content = "\n".join(body_lines).strip()
            if content:
                existing = sections.get(current_heading_norm)
                if existing:
                    existing["body"] = f'{existing["body"]}\n{content}'
                else:
                    sections[current_heading_norm] = {
                        "heading": current_heading_text or current_heading_norm,
                        "body": content,
                    }
        body_lines.clear()
    def _walk(elements: list) -> None:
        nonlocal current_heading_norm, current_heading_text
        for el in elements:
            if "table" in el:
                continue
            if "paragraph" in el:
                para  = el["paragraph"]
                style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
                text  = _paragraph_text(para).strip()
                if not text:
                    continue
                if style in _HEADING_STYLES:
                    _flush()
                    current_heading_norm = _normalize(text)
                    current_heading_text = text
                elif current_heading_norm is not None:
                    pfx = "* " if "bullet" in para else ""
                    body_lines.append(f"{pfx}{text}")
    _walk(doc.get("body", {}).get("content", []))
    _flush()
    return sections
def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
def _build_local_citations(flow: dict[str, dict]) -> dict[str, dict]:
    citations: dict[str, dict] = {}
    for node_id, node in flow.items():
        if node.get("answer") is None:
            continue
        citations[node_id] = {
            "source": "local_file",
            "doc": "cm.json",
            "heading": node.get("message") or node_id,
            "match": "exact",
        }
    return citations
def _overlay_sections(
    sections: dict[str, dict[str, str]],
    flow: dict[str, dict],
    citations: dict[str, dict],
    doc_name: str,
    allowed_ids: Optional[set[str]] = None,
) -> int:
    candidates: dict[str, str] = {
        _normalize(node["message"]): nid
        for nid, node in flow.items()
        if node.get("message")
        and "answer" in node
        and node["answer"] is not None
        and (allowed_ids is None or nid in allowed_ids)
    }
    updated = 0
    for heading_norm, section in sections.items():
        body_text = section["body"]
        if not body_text:
            continue
        node_id = candidates.get(heading_norm)
        match_type = "exact"
        if not node_id:
            best_len = 0
            for msg_norm, nid in candidates.items():
                if heading_norm in msg_norm or msg_norm in heading_norm:
                    if len(msg_norm) > best_len:
                        best_len = len(msg_norm)
                        node_id  = nid
                        match_type = "partial"
        if node_id and node_id in flow:
            flow[node_id]["answer"] = body_text
            citations[node_id] = {
                "source": "google_docs",
                "doc": doc_name,
                "heading": section["heading"],
                "match": match_type,
            }
            updated += 1
            logger.debug(f"    overlay {heading_norm!r} -> {node_id!r}")
    return updated
def _scan_data_dir() -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not DATA_DIR.exists():
        logger.warning(f"DATA_DIR '{DATA_DIR}' does not exist.")
        return index
    files = sorted(DATA_DIR.glob("*.json"))
    if not files:
        logger.warning(f"No JSON files found in '{DATA_DIR}'.")
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
            logger.info(f"  Indexed '{path.name}': {count} nodes")
        except Exception as exc:
            logger.warning(f"  Could not index '{path.name}': {exc}")
    logger.info(f"Index complete: {len(index)} node IDs across {len(files)} file(s).")
    return index
def _load_playbook_file(path: Path) -> dict:
    global _SOURCE, _docs_service, _CITATIONS
    if path in _CACHE:
        return _CACHE[path]
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    meta: dict = data.get("meta", {})
    flow: dict = {n["id"]: dict(n) for n in data.get("nodes", []) if n.get("id")}
    local_cit = _build_local_citations(flow)
    _CITATIONS.update(local_cit)
    ds = config.DATA_SOURCE
    if ds != "json":
        entries = _collect_doc_entries()
        if entries and SA_FILE.exists():
            _docs_service = None
            for entry in entries:
                try:
                    doc      = _fetch_google_doc(entry["doc_id"])
                    sections = _extract_doc_sections(doc)
                    n        = _overlay_sections(
                        sections, flow, _CITATIONS,
                        doc_name=entry["name"],
                        allowed_ids=entry["node_ids"],
                    )
                    logger.info(f"  [{path.name}] Doc {entry['name']!r}: {len(sections)} sections -> {n} nodes updated")
                except Exception as exc:
                    logger.warning(f"  [{path.name}] Doc {entry['name']!r} failed: {exc}")
                    if ds == "google":
                        raise
            _SOURCE = "google_docs"
    _CACHE[path] = {"flow": flow, "meta": meta}
    logger.info(f"Loaded & cached '{path.name}' ({len(flow)} nodes)")
    return _CACHE[path]
def _resolve_playbook(node_id: str) -> Optional[Path]:
    if node_id in _INDEX:
        return _INDEX[node_id]
    parts = node_id.split("-")
    for length in range(len(parts), 0, -1):
        prefix = "-".join(parts[:length])
        for nid, path in _INDEX.items():
            if nid.startswith(prefix + "-") or nid == prefix:
                return path
    tokens = set(_normalize(node_id).split())
    best_score = 0
    best_path: Optional[Path] = None
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                title = json.load(fh).get("meta", {}).get("title", "")
            score = len(tokens & set(_normalize(title).split()))
            if score > best_score:
                best_score = score
                best_path  = path
        except Exception:
            continue
    if best_path:
        return best_path
    files = sorted(DATA_DIR.glob("*.json"))
    return files[0] if files else None
def _load() -> None:
    global _INDEX, _CACHE, _SOURCE, _CITATIONS, _docs_service
    _docs_service = None
    _CACHE.clear()
    _CITATIONS.clear()
    _SOURCE = "local_file"
    logger.info(f"Scanning DATA_DIR={DATA_DIR}  DATA_SOURCE={config.DATA_SOURCE!r}")
    _INDEX = _scan_data_dir()
    if not _INDEX:
        if config.DATA_SOURCE == "json":
            raise RuntimeError(
                f"DATA_SOURCE=json but no JSON files found in '{DATA_DIR}'. "
                "Add at least one playbook JSON file to the data directory."
            )
        logger.warning("No local JSON files found - will rely on Google Docs only.")
        _SOURCE = "google_docs_only"
        return
    for path in sorted({p for p in _INDEX.values()}):
        try:
            _load_playbook_file(path)
        except Exception as exc:
            logger.warning(f"Pre-load failed for '{path.name}': {exc}")
_load()
def reload() -> str:
    _load()
    return _SOURCE
def get_source() -> str:
    return _SOURCE
def get_meta() -> dict:
    home_path = _INDEX.get("home")
    if home_path is None:
        files = sorted(DATA_DIR.glob("*.json"))
        home_path = files[0] if files else None
    if home_path and home_path in _CACHE:
        return dict(_CACHE[home_path]["meta"])
    return {"title": "NDS Playbook Chatbot", "version": "1.0", "company": "NDS"}
def get_node(node_id: str) -> Optional[dict]:
    path = _resolve_playbook(node_id)
    if path is None:
        return None
    try:
        book = _load_playbook_file(path)
    except Exception as exc:
        logger.error(f"Failed to load playbook '{path}': {exc}")
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
def get_all_node_ids() -> list:
    return list(_INDEX.keys())
def list_playbooks() -> list:
    if not DATA_DIR.exists():
        return []
    books = []
    for f in sorted(DATA_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            meta  = data.get("meta", {})
            nodes = data.get("nodes", [])
            books.append({
                "file":       f.name,
                "title":      meta.get("title", f.stem),
                "company":    meta.get("company", ""),
                "version":    meta.get("version", ""),
                "node_count": len(nodes),
                "cached":     f in _CACHE,
            })
        except Exception:
            books.append({"file": f.name, "title": f.stem, "node_count": 0, "cached": False})
    return books
def get_active_playbook() -> str:
    cached = [p.name for p in _CACHE]
    return ", ".join(cached) if cached else "none"