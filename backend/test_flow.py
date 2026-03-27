"""
Smoke test — NDS Playbook Flow Engine (OAuth 2.0 / Service Account)
Run from the backend/ directory:
    python test_flow.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from logic.flow import (
    SA_FILE,
    _collect_doc_entries,
    _normalize,
    get_all_node_ids,
    get_meta,
    get_node,
    get_source,
)

SEP = "=" * 60

print(SEP)
print("NDS Playbook Flow Engine — Smoke Test")
print(SEP)

# ── 1. Meta ───────────────────────────────────────────────────
meta = get_meta()
print("\n[META]")
print(f"  Title   : {meta.get('title')}")
print(f"  Company : {meta.get('company')}")
print(f"  Version : {meta.get('version')}")
print(f"  Source  : {get_source()}")

# ── 2. Node count ─────────────────────────────────────────────
ids = get_all_node_ids()
print(f"\n[NODES]  Total: {len(ids)}")

# ── 3. Broken link check ──────────────────────────────────────
broken = []
for nid in ids:
    node = get_node(nid)
    for btn in node["buttons"]:
        if btn["next"] not in ids:
            broken.append((nid, btn["label"], btn["next"]))

total_buttons = sum(len(get_node(n)["buttons"]) for n in ids)
if broken:
    print(f"\n[BROKEN LINKS] {len(broken)} found:")
    for src, lbl, tgt in broken:
        print(f"  {src} → [{lbl}] → '{tgt}'  ← MISSING")
else:
    print(f"  All {total_buttons} button links valid ✓")

# ── 4. Home node ──────────────────────────────────────────────
home = get_node("home")
print(f"\n[HOME NODE]  message: {home['message']}")
print(f"  Buttons ({len(home['buttons'])}):")
for b in home["buttons"]:
    print(f"    [{b['label']}] → {b['next']}")

# ── 5. Sample answers ─────────────────────────────────────────
samples = ["map-tmc", "pricing-fuel", "psu-step1", "region-fl", "addons-tmc"]
print("\n[SAMPLE ANSWERS]")
for nid in samples:
    n = get_node(nid)
    if n:
        preview = (n["answer"] or "(no answer)").replace("\n", " ")[:90]
        print(f"  {nid}: {preview}…")

# ── 6. Nodes WITH answers ─────────────────────────────────────
with_answers = [nid for nid in ids if get_node(nid).get("answer")]
without = [nid for nid in ids if not get_node(nid).get("answer")]
print("\n[ANSWER COVERAGE]")
print(f"  Nodes with answers  : {len(with_answers)}")
print(f"  Nodes without answer: {len(without)}")
if without:
    print(
        f"  Nav-only nodes (expected): {without[:10]}{'...' if len(without) > 10 else ''}"
    )

# ── 7. OAuth / Google Docs status ────────────────────────────
doc_entries = _collect_doc_entries()
print("\n[GOOGLE DOCS / OAUTH 2.0 STATUS]")
print(f"  Service account file : {SA_FILE}")
print(f"  File exists          : {SA_FILE.exists()}")
print(f"  Registered docs      : {len(doc_entries)}")
for e in doc_entries:
    print(f"    {e['name']}: {e['doc_id'][:20]}…")
print(f"  Active source        : {get_source()}")

if not SA_FILE.exists():
    print("\n  ⚠  Place your service_account.json at the path above.")
    print("     Then share the Google Doc with the service account email.")
if not doc_entries:
    print(
        "\n  ⚠  Set GOOGLE_DOC_ID_MAIN in .env to enable live content from Google Docs."
    )

# ── 8. Normalise helper ───────────────────────────────────────
print("\n[_normalize TESTS]")
cases = [
    ("TMC Mapping Rules", "tmc mapping rules"),
    ("Email Account Setup", "email account setup"),
    ("Fuel Surcharge — Computation", "fuel surcharge  computation"),
    ("Ped & Bike (P&B)", "ped  bike p b"),
]
for raw, expected in cases:
    got = _normalize(raw)
    ok = "✓" if got == expected else f"✗  expected '{expected}'"
    print(f"  '{raw}' → '{got}'  {ok}")

print(f"\n{SEP}")
print("Smoke test complete.")
print(SEP)
