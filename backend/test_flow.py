"""Quick smoke test for the flow engine."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from logic.flow import get_all_node_ids, get_meta, get_node

meta = get_meta()
ids = get_all_node_ids()

print(f"Title : {meta.get('title')}")
print(f"Company: {meta.get('company')}")
print(f"Version: {meta.get('version')}")
print(f"Total nodes: {len(ids)}")
print()

# Validate every node's buttons point to real nodes
broken = []
for nid in ids:
    node = get_node(nid)
    for btn in node["buttons"]:
        if btn["next"] not in ids:
            broken.append((nid, btn["next"]))

if broken:
    print("BROKEN LINKS:")
    for src, tgt in broken:
        print(f"  {src} -> {tgt}")
else:
    print("All button links valid!")

# Show home node
home = get_node("home")
print(f"\nHome message: {home['message']}")
print(f"Home buttons ({len(home['buttons'])}):")
for b in home["buttons"]:
    print(f"  [{b['label']}] -> {b['next']}")

