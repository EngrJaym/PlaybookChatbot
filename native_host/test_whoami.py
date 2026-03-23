"""
Quick test for nds_whoami.py — simulates what Chrome would do.
Run:  python native_host/test_whoami.py
"""
import subprocess
import struct
import json
import sys
from pathlib import Path

HOST   = Path(__file__).parent / "nds_whoami.py"
RESULT = Path(__file__).parent / "_test_result.json"

msg = json.dumps({
    "ad_server": "samba-ad.ad.one-nds.net",
    "base_dn":   "DC=ad,DC=one-nds,DC=net",
}).encode("utf-8")

payload = struct.pack("I", len(msg)) + msg

proc = subprocess.run(
    [sys.executable, str(HOST)],
    input=payload,
    capture_output=True,
    timeout=15,
)

result = {}

if proc.returncode != 0 or len(proc.stdout) < 4:
    result = {"error": proc.stderr.decode(errors="replace") or "no output"}
else:
    length = struct.unpack("I", proc.stdout[:4])[0]
    result = json.loads(proc.stdout[4:4 + length].decode("utf-8"))
    result["_stderr"] = proc.stderr.decode(errors="replace").strip()

RESULT.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))



