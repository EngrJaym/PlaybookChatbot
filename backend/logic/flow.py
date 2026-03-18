"""
Playbook flow engine — driven by config.py feature flags.

DATA_SOURCE modes  (set in .env):
  "json"   → load cm.json only, skip all Google Docs calls.
  "google" → load cm.json for navigation backbone, overlay answers from Docs.
             If cm.json is absent, navigation must come from Docs too.
  "both"   → same as "google" but cm.json answers fill any node that Docs
             did not update (safest / most complete).
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

_BACKEND_DIR  = Path(__file__).resolve().parent.parent
_ROOT_DIR     = _BACKEND_DIR.parent
LOCAL_PATH    = _ROOT_DIR / "data" / "cm.json"
SA_FILE       = config.SA_FILE

_SCOPES         = ["https://www.googleapis.com/auth/documents.readonly"]
_HEADING_STYLES = {"HEADING_1", "HEADING_2", "HEADING_3", "HEADING_4", "TITLE"}

_FLOW:         dict[str, dict] = {}
_META:         dict            = {}
_SOURCE:       str             = "unknown"
_docs_service                  = None

logger = logging.getLogger(__name__)


def _collect_doc_entries() -> list[dict]:
    """Scan os.environ for GOOGLE_DOC_ID_<NAME> + optional GOOGLE_DOC_NODES_<NAME>."""
    entries: list[dict] = []
    seen:    set[str]   = set()
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
        node_ids: Optional[set[str]] = (
            {n.strip() for n in nodes_raw.split(",") if n.strip()}
            if nodes_raw else None
        )
        entries.append({"name": name, "doc_id": doc_id, "node_ids": node_ids})
        logger.info(
            f"  Registered doc '{name}': id={doc_id[:16]}…  "
            f"scope={'ALL' if node_ids is None else f'{len(node_ids)} nodes'}"
        )
    return entries


def _get_docs_service():
    """Build and cache the Google Docs API service."""
    global _docs_service
    if _docs_service is not None:
        return _docs_service
    if not SA_FILE.exists():
        raise FileNotFoundError(
            f"Service account credentials not found: {SA_FILE}\n"
            "Place the JSON key from Google Cloud Console at that path."
        )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        str(SA_FILE), scopes=_SCOPES
    )
    _docs_service = build("docs", "v1", credentials=creds, cache_discovery=False)
    logger.info("Google Docs API service initialised (OAuth 2.0).")
    return _docs_service


def _fetch_google_doc(doc_id: str) -> dict:
    """Fetch a single Google Doc by ID."""
    return _get_docs_service().documents().get(documentId=doc_id).execute()


def _paragraph_text(paragraph: dict) -> str:
    """Extract plain text from a paragraph."""
    parts: list[str] = []
    for el in paragraph.get("elements", []):
        content = el.get("textRun", {}).get("content", "")
        if content:
            parts.append(content)
    return "".join(parts).rstrip("\n")


def _extract_doc_sections(doc: dict) -> dict[str, str]:
    """Return { normalised_heading → body_text }. Tables are skipped."""
    sections:        dict[str, str] = {}
    current_heading: Optional[str]  = None
    body_lines:      list[str]      = []

    def _flush() -> None:
        nonlocal current_heading, body_lines
        if current_heading is not None:
            content = "\n".join(body_lines).strip()
            if content:
                sections[current_heading] = (
                    sections[current_heading] + "\n" + content
                    if current_heading in sections else content
                )
        body_lines.clear()

    def _walk(elements: list) -> None:
        nonlocal current_heading
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
                    current_heading = _normalize(text)
                elif current_heading is not None:
                    prefix = "• " if "bullet" in para else ""
                    body_lines.append(f"{prefix}{text}")

    _walk(doc.get("body", {}).get("content", []))
    _flush()
    return sections


def _normalize(text: str) -> str:
    """Normalise text for fuzzy matching."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _overlay_sections(
    sections: dict[str, str],
    flow: dict[str, dict],
    allowed_ids: Optional[set[str]] = None,
) -> int:
    """Write Google Docs section body text into matching flow nodes."""
    candidates: dict[str, str] = {
        _normalize(node["message"]): nid
        for nid, node in flow.items()
        if node.get("message")
        and "answer" in node
        and node["answer"] is not None
        and (allowed_ids is None or nid in allowed_ids)
    }

    updated = 0
    for heading_norm, body_text in sections.items():
        if not body_text:
            continue
        node_id = candidates.get(heading_norm)
        if not node_id:
            best_len = 0
            for msg_norm, nid in candidates.items():
                if heading_norm in msg_norm or msg_norm in heading_norm:
                    if len(msg_norm) > best_len:
                        best_len = len(msg_norm)
                        node_id  = nid
        if node_id and node_id in flow:
            flow[node_id]["answer"] = body_text
            updated += 1
            logger.debug(f"    overlay '{heading_norm}' → '{node_id}'")
    return updated


def _load_local_json() -> dict | None:
    """Load cm.json if it exists."""
    if not LOCAL_PATH.exists():
        logger.info("data/cm.json not found.")
        return None
    with open(LOCAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _load() -> None:
    """Load playbook from configured data source."""
    global _FLOW, _META, _SOURCE, _docs_service
    _docs_service = None

    ds = config.DATA_SOURCE
    logger.info(f"Loading playbook  DATA_SOURCE={ds!r}")

    if ds == "json":
        base = _load_local_json()
        if base is None:
            raise RuntimeError(
                "DATA_SOURCE=json but data/cm.json not found. "
                "Restore the file or switch DATA_SOURCE to 'google' or 'both'."
            )
        _META   = base.get("meta", {})
        _FLOW   = {n["id"]: dict(n) for n in base.get("nodes", []) if n.get("id")}
        _SOURCE = "local_file"
        logger.info(f"[json] {len(_FLOW)} nodes loaded from cm.json.")
        return

    base = _load_local_json()
    if base is not None:
        _META = base.get("meta", {})
        _FLOW = {n["id"]: dict(n) for n in base.get("nodes", []) if n.get("id")}
        logger.info(f"Navigation backbone: {len(_FLOW)} nodes from cm.json.")
        _SOURCE = "local_file"
    else:
        _META = {
            "title":   "NDS Client Management Playbook",
            "version": "1.1",
            "company": "National Data & Surveying Services",
        }
        _FLOW   = {}
        _SOURCE = "google_docs_only"
        logger.info("cm.json absent — navigation will come from Google Docs.")

    entries = _collect_doc_entries()
    if not entries:
        logger.warning(
            f"DATA_SOURCE={ds!r} but no GOOGLE_DOC_ID_* vars are set. "
            "Serving whatever is in cm.json."
        )
        return

    if not SA_FILE.exists():
        msg = f"Credentials file missing: {SA_FILE}"
        if ds == "google":
            raise FileNotFoundError(msg)
        logger.warning(f"{msg} → falling back to cm.json answers.")
        return

    total_updated = 0
    any_success   = False

    for entry in entries:
        name     = entry["name"]
        doc_id   = entry["doc_id"]
        node_ids = entry["node_ids"]
        try:
            doc      = _fetch_google_doc(doc_id)
            sections = _extract_doc_sections(doc)
            n        = _overlay_sections(sections, _FLOW, allowed_ids=node_ids)
            total_updated += n
            any_success    = True
            scope = f"{len(node_ids)} nodes" if node_ids else "all nodes"
            logger.info(f"  Doc '{name}': {len(sections)} sections → {n} nodes updated  [{scope}]")
        except Exception as exc:
            logger.warning(f"  Doc '{name}' failed: {exc}")
            if ds == "google":
                raise

    if any_success:
        _SOURCE = "google_docs"
        logger.info(f"Overlay done — {total_updated} total nodes updated from Google Docs.")
    else:
        if ds == "google":
            raise RuntimeError("DATA_SOURCE=google but all doc fetches failed.")
        logger.warning("All doc fetches failed — serving cm.json answers only.")


_load()


def reload() -> str:
    """Re-fetch from configured data source."""
    _load()
    return _SOURCE


def get_source() -> str:
    """Get the active data source."""
    return _SOURCE


def get_meta() -> dict:
    """Get playbook metadata."""
    return dict(_META)


def get_node(node_id: str) -> dict | None:
    """Get a specific node by ID."""
    node = _FLOW.get(node_id)
    if node is None:
        return None
    return {
        "id":      node["id"],
        "message": node["message"],
        "answer":  node.get("answer"),
        "buttons": node.get("buttons", []),
        "type":    node.get("type"),
    }


def get_all_node_ids() -> list[str]:
    """Get all node IDs."""
    return list(_FLOW.keys())

