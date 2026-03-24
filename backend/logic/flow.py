"""
Playbook flow engine — JSON nodes + Google Docs answers.

Priority:
  1. JSON files in data/ define the node tree (IDs, buttons, messages).
  2. Google Docs supply answer text, matched to nodes by MEANING.
  3. If Docs match fails for a node the JSON answer is kept as fallback.
  4. If NO JSON files exist, auto-generate the full tree from Docs headings.

TTL-based refresh keeps answers in sync with live document edits.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import threading
import unicodedata
from pathlib import Path
from typing import Optional

import config

_BACKEND_DIR  = Path(__file__).resolve().parent.parent
_ROOT_DIR     = _BACKEND_DIR.parent
_DATA_DIR_ENV = os.getenv("DATA_DIR", "").strip()
DATA_DIR: Path = Path(_DATA_DIR_ENV) if _DATA_DIR_ENV else _ROOT_DIR / "data"

SA_FILE = config.SA_FILE

_SCOPES         = ["https://www.googleapis.com/auth/documents.readonly"]
_HEADING_STYLES = {"HEADING_1", "HEADING_2", "HEADING_3", "HEADING_4", "TITLE"}

_GDOCS_SENTINEL = Path("__google_docs__")

_INDEX:     dict[str, Path]  = {}
_CACHE:     dict[Path, dict] = {}
_SOURCE:    str              = "unknown"
_CITATIONS: dict[str, dict]  = {}
_docs_service = None

_CACHE_TTL: int   = int(os.getenv("CACHE_TTL_SECONDS", "300"))
_cache_ts:  float = 0.0
_refresh_lock      = threading.Lock()

logger = logging.getLogger(__name__)


_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "to", "in", "for", "is", "it",
    "on", "at", "by", "with", "from", "as", "what", "do", "you", "need",
    "help", "which", "how", "back", "home", "your", "this", "that",
})

_SKIP_HEADINGS = frozenset({
    "document access tracker", "table of contents", "revision history",
    "name", "role", "access", "owner", "editor", "commentor", "viewer",
    "tag", "tags", "note", "notes", "comment", "comments",
    "member", "members", "document", "tracker", "include",
})

_MIN_BODY_LENGTH = 50


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
        logger.info(
            "  Registered doc %r: id=%s  scope=%s",
            name, doc_id[:16],
            "ALL" if node_ids is None else len(node_ids),
        )
    return entries


def _get_docs_service():
    global _docs_service
    if _docs_service is not None:
        return _docs_service
    if not SA_FILE.exists():
        raise FileNotFoundError(
            f"Service account credentials not found: {SA_FILE}"
        )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        str(SA_FILE), scopes=_SCOPES,
    )
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


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _slugify(text: str, max_len: int = 48) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:max_len].rstrip("-") or "node"


def _meaningful_tokens(text: str) -> set[str]:
    return set(_normalize(text).split()) - _STOP_WORDS


def _extract_doc_sections_flat(doc: dict) -> list[dict]:
    """Extract sections from Google Doc headings (any level). Returns flat list."""
    sections: list[dict] = []
    cur_heading: Optional[str] = None
    cur_norm:    Optional[str] = None
    body_lines:  list[str]     = []

    def _flush():
        nonlocal cur_heading, cur_norm, body_lines
        if cur_norm is not None:
            body = "\n".join(body_lines).strip()
            if body and len(body) >= _MIN_BODY_LENGTH:
                sections.append({
                    "heading":      cur_heading,
                    "heading_norm": cur_norm,
                    "body":         body,
                })
        body_lines = []

    for el in doc.get("body", {}).get("content", []):
        if "table" in el:
            continue
        if "paragraph" not in el:
            continue
        para  = el["paragraph"]
        style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        text  = _paragraph_text(para).strip()
        if not text:
            continue
        if style in _HEADING_STYLES:
            _flush()
            norm = _normalize(text)
            if norm in _SKIP_HEADINGS or len(norm) < 3:
                cur_heading = None
                cur_norm    = None
            else:
                cur_heading = text
                cur_norm    = norm
        elif cur_norm is not None:
            pfx = "* " if "bullet" in para else ""
            body_lines.append(f"{pfx}{text}")

    _flush()
    return sections


def _build_match_index(
    flow: dict[str, dict],
    allowed_ids: Optional[set[str]] = None,
) -> dict[str, dict]:
    """Build lookup for nodes eligible for answer overlay."""
    idx: dict[str, dict] = {}
    for nid, node in flow.items():
        if allowed_ids is not None and nid not in allowed_ids:
            continue
        msg = node.get("message", "")
        if not msg:
            continue
        idx[nid] = {
            "msg_norm":   _normalize(msg),
            "msg_tokens": _meaningful_tokens(msg),
            "id_tokens":  set(nid.replace("-", " ").split()),
        }
    return idx


def _match_section_to_node(
    section: dict,
    match_index: dict[str, dict],
    min_score: float = 0.35,
) -> tuple[Optional[str], str]:
    """Match doc section to node using word-overlap scoring. Returns (node_id, match_type)."""
    h_norm   = section["heading_norm"]
    h_tokens = _meaningful_tokens(section["heading"])

    if not h_tokens:
        return None, "none"

    best_id:    Optional[str] = None
    best_score: float         = 0.0
    best_type:  str           = "none"

    for nid, info in match_index.items():
        m_norm   = info["msg_norm"]
        m_tokens = info["msg_tokens"]

        if h_norm == m_norm:
            return nid, "exact"

        if h_norm in m_norm or m_norm in h_norm:
            candidate_score = len(m_norm) + 10000
            if candidate_score > best_score:
                best_id    = nid
                best_score = candidate_score
                best_type  = "substring"
                continue

        if not m_tokens:
            continue

        overlap = h_tokens & m_tokens
        union   = h_tokens | m_tokens
        jaccard = len(overlap) / len(union) if union else 0.0

        id_overlap = h_tokens & info["id_tokens"]
        id_bonus   = len(id_overlap) * 0.15

        score = jaccard + id_bonus
        if score > best_score and score >= min_score:
            best_id    = nid
            best_score = score
            best_type  = "semantic"

    return best_id, best_type


def _overlay_docs_on_flow(
    flow: dict[str, dict],
    citations: dict[str, dict],
    entries: list[dict],
) -> int:
    """Overlay Docs content onto JSON nodes. Unmatched nodes keep JSON answers. Returns update count."""
    global _docs_service
    _docs_service = None
    total_updated = 0

    for entry in entries:
        try:
            doc      = _fetch_google_doc(entry["doc_id"])
            sections = _extract_doc_sections_flat(doc)
            m_index  = _build_match_index(flow, allowed_ids=entry["node_ids"])
            matched: set[str] = set()
            updated  = 0

            for sec in sections:
                if not sec["body"]:
                    continue
                node_id, match_type = _match_section_to_node(sec, m_index)
                if node_id and node_id not in matched:
                    if node_id == "home":
                        logger.debug("    Skipping overlay for home node (protected)")
                        continue
                    flow[node_id]["answer"] = sec["body"]
                    citations[node_id] = {
                        "source":  "google_docs",
                        "doc":     entry["name"],
                        "heading": sec["heading"],
                        "match":   match_type,
                    }
                    matched.add(node_id)
                    updated += 1
                    logger.debug(
                        "    [%s] %r -> %r", match_type, sec["heading_norm"], node_id,
                    )

            total_updated += updated
            logger.info(
                "  Doc %r: %d sections, %d nodes updated, %d unmatched (JSON fallback kept)",
                entry["name"], len(sections), updated,
                len(m_index) - updated,
            )
        except Exception as exc:
            logger.warning(
                "  Doc %r fetch/parse failed: %s — all JSON answers retained as fallback",
                entry["name"], exc,
            )

    return total_updated


_LEVEL_MAP = {
    "TITLE": 0,  "HEADING_1": 1,  "HEADING_2": 2,
    "HEADING_3": 3,  "HEADING_4": 4,
}


def _extract_doc_tree(doc: dict) -> list[dict]:
    flat: list[dict] = []
    for el in doc.get("body", {}).get("content", []):
        if "table" in el:
            continue
        if "paragraph" not in el:
            continue
        para  = el["paragraph"]
        style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
        text  = _paragraph_text(para).strip()
        if not text:
            continue
        if style in _LEVEL_MAP:
            norm = _normalize(text)
            if norm in _SKIP_HEADINGS or len(norm) < 3:
                continue
            flat.append({
                "text": text, "slug": _slugify(text),
                "level": _LEVEL_MAP[style], "body_lines": [], "children": [],
            })
        elif flat:
            pfx = "* " if "bullet" in para else ""
            flat[-1]["body_lines"].append(f"{pfx}{text}")

    def _nest(items, parent_level):
        roots = []
        for item in items:
            if not roots or item["level"] <= parent_level:
                roots.append(item)
            else:
                roots[-1]["children"].append(item)
        for r in roots:
            if r["children"]:
                r["children"] = _nest(r["children"], r["level"])
        return roots

    if not flat:
        return []
    return _nest(flat, min(i["level"] for i in flat) - 1)


def _unique_slug(slug: str, used: set[str]) -> str:
    if slug not in used:
        used.add(slug)
        return slug
    n = 2
    while f"{slug}-{n}" in used:
        n += 1
    result = f"{slug}-{n}"
    used.add(result)
    return result


def _tree_to_flow(children, parent_id, flow, citations, doc_name, used_slugs):
    buttons = []
    for item in children:
        node_slug = _unique_slug(item["slug"], used_slugs)
        body = "\n".join(item["body_lines"]).strip() or None
        has_children = bool(item["children"])

        child_buttons = []
        if has_children:
            child_buttons = _tree_to_flow(
                item["children"], node_slug, flow, citations, doc_name, used_slugs,
            )

        node_buttons = list(child_buttons)
        node_buttons.append({"label": "\u2b05 Back", "next": parent_id})

        flow[node_slug] = {
            "id": node_slug, "message": item["text"], "answer": body,
            "buttons": node_buttons, "type": "leaf" if not has_children else "category",
        }
        if body:
            citations[node_slug] = {
                "source": "google_docs", "doc": doc_name,
                "heading": item["text"], "match": "auto_generated",
            }
        buttons.append({"label": item["text"], "next": node_slug})
    return buttons


def _build_tree_from_docs() -> dict:
    global _docs_service
    _docs_service = None
    entries = _collect_doc_entries()
    if not entries:
        raise RuntimeError(
            "No GOOGLE_DOC_ID_* env vars found. "
            "Set at least one Google Doc ID in .env."
        )
    if not SA_FILE.exists():
        raise FileNotFoundError(f"Service account credentials not found: {SA_FILE}")

    flow: dict[str, dict] = {}
    citations: dict[str, dict] = {}
    used_slugs: set[str] = {"home"}
    home_buttons: list[dict] = []
    doc_title = "NDS Playbook Chatbot"

    for entry in entries:
        doc  = _fetch_google_doc(entry["doc_id"])
        tree = _extract_doc_tree(doc)
        logger.info("  Doc %r: %d top-level sections", entry["name"], len(tree))

        title_from_doc = doc.get("title", "").strip()
        if title_from_doc:
            doc_title = title_from_doc
        if len(tree) == 1 and tree[0]["children"]:
            root = tree[0]
            if root["text"].strip():
                doc_title = root["text"]
            sections = root["children"]
        else:
            sections = tree

        home_buttons.extend(
            _tree_to_flow(sections, "home", flow, citations, entry["name"], used_slugs)
        )

    flow["home"] = {
        "id": "home",
        "message": f"Welcome to the {doc_title}. What do you need help with?",
        "answer": None, "buttons": home_buttons, "type": "home",
    }
    meta = {"title": doc_title, "version": "1.0", "company": "NDS"}
    logger.info("Auto-generated %d nodes from %d Google Doc(s).", len(flow), len(entries))
    return {"flow": flow, "meta": meta, "citations": citations}


def _build_local_citations(flow: dict[str, dict], filename: str) -> dict[str, dict]:
    cit: dict[str, dict] = {}
    for nid, node in flow.items():
        if node.get("answer") is None:
            continue
        cit[nid] = {
            "source": "local_file", "doc": filename,
            "heading": node.get("message") or nid, "match": "json_fallback",
        }
    return cit


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
            logger.info("  Indexed '%s': %d nodes", path.name, count)
        except Exception as exc:
            logger.warning("  Could not index '%s': %s", path.name, exc)
    logger.info("Index complete: %d node IDs across %d file(s).", len(index), len(files))
    return index


def _load_playbook_file(path: Path) -> dict:
    global _SOURCE, _CITATIONS
    if path in _CACHE:
        return _CACHE[path]
    if path == _GDOCS_SENTINEL:
        return _CACHE.get(_GDOCS_SENTINEL, {"flow": {}, "meta": {}})

    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    meta: dict = data.get("meta", {})
    flow: dict = {n["id"]: dict(n) for n in data.get("nodes", []) if n.get("id")}

    local_cit = _build_local_citations(flow, path.name)
    _CITATIONS.update(local_cit)

    ds = config.DATA_SOURCE

    if ds == "json":
        _SOURCE = "local_file"
        logger.info("  [%s] DATA_SOURCE=json — using JSON answers only", path.name)

    elif ds in ("google", "both"):
        entries = _collect_doc_entries()
        if entries and SA_FILE.exists():
            updated = _overlay_docs_on_flow(flow, _CITATIONS, entries)
            if updated > 0:
                _SOURCE = "google_docs"
                logger.info(
                    "  [%s] %d/%d nodes got live Docs answers, rest use JSON fallback",
                    path.name, updated, len(flow),
                )
            else:
                _SOURCE = "local_file"
                logger.info(
                    "  [%s] No Docs matches — all %d nodes use JSON answers",
                    path.name, len(flow),
                )
        else:
            _SOURCE = "local_file"
            if not entries:
                logger.info("  [%s] No GOOGLE_DOC_ID_* set — JSON answers only", path.name)
            elif not SA_FILE.exists():
                logger.warning("  [%s] Credentials file missing — JSON answers only", path.name)

    _CACHE[path] = {"flow": flow, "meta": meta}
    logger.info("Loaded & cached '%s' (%d nodes, source=%s)", path.name, len(flow), _SOURCE)
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
    if _GDOCS_SENTINEL in _CACHE:
        return _GDOCS_SENTINEL
    tokens = set(_normalize(node_id).split())
    best_score = 0
    best_path: Optional[Path] = None
    if DATA_DIR.exists():
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
    if DATA_DIR.exists():
        files = sorted(DATA_DIR.glob("*.json"))
        if files:
            return files[0]
    return None


def _load() -> None:
    global _INDEX, _CACHE, _SOURCE, _CITATIONS, _docs_service, _cache_ts
    _docs_service = None
    _CACHE.clear()
    _CITATIONS.clear()
    _SOURCE = "local_file"
    logger.info("Scanning DATA_DIR=%s  DATA_SOURCE=%r", DATA_DIR, config.DATA_SOURCE)

    _INDEX = _scan_data_dir()

    if _INDEX:
        for path in sorted({p for p in _INDEX.values()}):
            try:
                _load_playbook_file(path)
            except Exception as exc:
                logger.warning("Pre-load failed for '%s': %s", path.name, exc)
        _cache_ts = time.time()
        return

    if config.DATA_SOURCE == "json":
        raise RuntimeError(
            f"DATA_SOURCE=json but no JSON files found in '{DATA_DIR}'. "
            "Add at least one playbook JSON file to the data directory."
        )

    logger.info("No local JSON files — building tree from Google Docs...")
    try:
        result = _build_tree_from_docs()
        _CACHE[_GDOCS_SENTINEL] = {"flow": result["flow"], "meta": result["meta"]}
        _CITATIONS.update(result["citations"])
        for nid in result["flow"]:
            _INDEX[nid] = _GDOCS_SENTINEL
        _SOURCE = "google_docs_only"
        logger.info("Google Docs tree ready: %d nodes, source=%s", len(result["flow"]), _SOURCE)
    except Exception as exc:
        logger.error("Failed to build tree from Google Docs: %s", exc)
        _SOURCE = "error"
        _CACHE[_GDOCS_SENTINEL] = {
            "flow": {
                "home": {
                    "id": "home", "message": "Playbook Unavailable",
                    "answer": (
                        f"Could not load playbook data. "
                        f"No JSON files in data/ and Google Docs fetch failed: {exc}"
                    ),
                    "buttons": [], "type": "error",
                }
            },
            "meta": {"title": "NDS Playbook Chatbot", "version": "1.0", "company": "NDS"},
        }
        _INDEX["home"] = _GDOCS_SENTINEL

    _cache_ts = time.time()


def _maybe_refresh() -> None:
    global _cache_ts
    if config.DATA_SOURCE == "json":
        return
    if _CACHE_TTL <= 0:
        return
    if time.time() - _cache_ts < _CACHE_TTL:
        return
    if not _refresh_lock.acquire(blocking=False):
        return
    try:
        logger.info("Cache TTL expired — refreshing Docs answers…")
        _load()
    except Exception as exc:
        logger.error("Background refresh failed: %s", exc)
    finally:
        _refresh_lock.release()


_load()


def reload() -> str:
    _load()
    return _SOURCE


def get_source() -> str:
    return _SOURCE


def get_meta() -> dict:
    _maybe_refresh()
    if _GDOCS_SENTINEL in _CACHE:
        return dict(_CACHE[_GDOCS_SENTINEL]["meta"])
    home_path = _INDEX.get("home")
    if home_path is None and DATA_DIR.exists():
        files = sorted(DATA_DIR.glob("*.json"))
        home_path = files[0] if files else None
    if home_path and home_path in _CACHE:
        return dict(_CACHE[home_path]["meta"])
    return {"title": "NDS Playbook Chatbot", "version": "1.0", "company": "NDS"}

def get_meta_for_playbook_file(playbook_file: str) -> dict:
    path = (
        playbook_file
        if Path(playbook_file).is_absolute()
        else (DATA_DIR / playbook_file)
    )
    if not path.exists():
        raise FileNotFoundError(f"Playbook file not found: {playbook_file}")
    if path in _CACHE:
        return dict(_CACHE[path]["meta"])
    book = _load_playbook_file(path)
    return dict(book["meta"])

def get_node(node_id: str) -> Optional[dict]:
    _maybe_refresh()
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

def get_node_for_playbook_file(node_id: str, playbook_file: str) -> Optional[dict]:
    path = (
        playbook_file
        if Path(playbook_file).is_absolute()
        else (DATA_DIR / playbook_file)
    )
    if not path.exists():
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
    books = []
    if _GDOCS_SENTINEL in _CACHE:
        gd = _CACHE[_GDOCS_SENTINEL]
        books.append({
            "file": "(google_docs)",
            "title": gd.get("meta", {}).get("title", "Google Docs Playbook"),
            "company": gd.get("meta", {}).get("company", ""),
            "version": gd.get("meta", {}).get("version", ""),
            "node_count": len(gd.get("flow", {})),
            "cached": True,
        })
    if DATA_DIR.exists():
        for f in sorted(DATA_DIR.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                meta  = data.get("meta", {})
                nodes = data.get("nodes", [])
                books.append({
                    "file": f.name, "title": meta.get("title", f.stem),
                    "company": meta.get("company", ""), "version": meta.get("version", ""),
                    "node_count": len(nodes), "cached": f in _CACHE,
                })
            except Exception:
                books.append({"file": f.name, "title": f.stem, "node_count": 0, "cached": False})
    return books


def get_active_playbook() -> str:
    cached = []
    for p in _CACHE:
        cached.append("google_docs" if p == _GDOCS_SENTINEL else p.name)
    return ", ".join(cached) if cached else "none"
    