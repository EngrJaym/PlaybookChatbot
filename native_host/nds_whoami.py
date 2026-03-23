import sys
import json
import struct
import os
import re
import subprocess


def get_windows_username():
    try:
        import ctypes
        GetUserNameEx = ctypes.windll.secur32.GetUserNameExW
        size = ctypes.c_ulong(256)
        buf  = ctypes.create_unicode_buffer(256)
        ok   = GetUserNameEx(2, buf, ctypes.byref(size))
        if ok and buf.value:
            raw = buf.value
            return raw.split("\\", 1)[1].strip().lower() if "\\" in raw else raw.strip().lower()
    except Exception:
        pass
    return os.environ.get("USERNAME", "").strip().lower() or None


def _cn_from_dn(dn):
    m = re.match(r"CN=([^,]+)", dn, re.IGNORECASE)
    return m.group(1).strip() if m else dn.strip()


def get_ad_groups(sam, ad_server, base_dn):
    ps = f"""
$dc = "{ad_server}"
$root = [ADSI]"LDAP://$dc/RootDSE"
$base = $root.defaultNamingContext
$de = New-Object System.DirectoryServices.DirectoryEntry("LDAP://$dc/$base")
$ds = New-Object System.DirectoryServices.DirectorySearcher($de)
$ds.Filter = "(&(objectCategory=person)(objectClass=user)(sAMAccountName={sam}))"
$ds.PropertiesToLoad.Add("memberOf") | Out-Null
$result = $ds.FindOne()
if ($null -eq $result) {{ exit 1 }}
$result.Properties["memberOf"] | ForEach-Object {{ Write-Output $_.ToString() }}
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            return []
        return [_cn_from_dn(l.strip()) for l in proc.stdout.splitlines() if l.strip()]
    except Exception:
        return []


def send_message(payload):
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("I", len(encoded)))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def read_message():
    try:
        raw = sys.stdin.buffer.read(4)
        if not raw or len(raw) < 4:
            return {}
        length = struct.unpack("I", raw)[0]
        if length == 0:
            return {}
        return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    try:
        msg = read_message() or {}
    except Exception:
        msg = {}

    ad_server = msg.get("ad_server", "samba-ad.ad.one-nds.net")
    base_dn   = msg.get("base_dn",   "DC=ad,DC=one-nds,DC=net")
    sam       = get_windows_username()

    if not sam:
        send_message({"username": None, "groups": []})
        sys.exit(0)

    send_message({"username": sam, "groups": get_ad_groups(sam, ad_server, base_dn)})
