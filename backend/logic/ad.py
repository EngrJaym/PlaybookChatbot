from __future__ import annotations

import logging
import re
import subprocess

import config

logger = logging.getLogger(__name__)


def _cn_from_dn(dn: str) -> str:
    m = re.match(r"CN=([^,]+)", dn, re.IGNORECASE)
    return m.group(1).strip() if m else dn.strip()


def _lookup_via_powershell(sam: str) -> list[str] | None:
    """
    Fallback: use PowerShell + System.DirectoryServices to query AD
    group membership. Works on domain-joined Windows machines without
    LDAP bind credentials.
    """
    ad_server = config.AD_SERVER
    ps = f"""
$dc = "{ad_server}"
$de = New-Object System.DirectoryServices.DirectoryEntry("LDAP://$dc/{config.AD_BASE_DN}")
$ds = New-Object System.DirectoryServices.DirectorySearcher($de)
$ds.Filter = "(&(objectCategory=person)(objectClass=user)(sAMAccountName={sam}))"
$ds.PropertiesToLoad.Add("memberOf") | Out-Null
$result = $ds.FindOne()
if ($null -eq $result) {{ exit 1 }}
$result.Properties["memberOf"] | ForEach-Object {{ Write-Output $_ }}
"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode != 0:
            logger.debug("PowerShell AD fallback: user '%s' not found. stderr: %s", sam, proc.stderr.strip())
            return None
        raw = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        groups = [_cn_from_dn(dn) for dn in raw]
        logger.info("PowerShell AD fallback for '%s': %d groups", sam, len(groups))
        return groups
    except Exception as exc:
        logger.debug("PowerShell AD fallback failed for '%s': %s", sam, exc)
        return None


def _ldap3_search(conn, sam: str) -> list[str] | None:
    """Run the LDAP search on an already-bound connection. Returns group list or None."""
    from ldap3.core.exceptions import LDAPException
    search_filter = f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={sam}))"
    conn.search(
        config.AD_BASE_DN,
        search_filter,
        attributes=["memberOf", "sAMAccountName"],
    )
    if conn.entries:
        entry = conn.entries[0]
        raw_groups = list(entry.memberOf.values) if entry.memberOf else []
        groups = [_cn_from_dn(g) for g in raw_groups]
        logger.info("ldap3 AD lookup for '%s': %d groups found", sam, len(groups))
        return groups
    logger.warning("ldap3: user '%s' not found in directory", sam)
    return None


def lookup_ad_groups(sam: str) -> dict:
    sam = (sam or "").strip().lower()
    if not sam:
        return {"username": None, "groups": [], "error": "No username provided"}

    last_error: str | None = None

    # ── Primary: ldap3 ────────────────────────────────────────────────────────
    try:
        from ldap3 import Server, Connection, ALL, NTLM, SIMPLE, ANONYMOUS
        from ldap3.core.exceptions import LDAPException

        server = Server(config.AD_SERVER, get_info=ALL, connect_timeout=8)

        bind_user = config.AD_BIND_USER.strip()
        bind_pass = config.AD_BIND_PASSWORD.strip()

        conn = None

        if bind_user and bind_pass:
            # ── Option 1: explicit service-account credentials ──────────────
            auth = NTLM if ("\\" in bind_user or "@" in bind_user) else SIMPLE
            logger.debug("ldap3: binding with explicit credentials (auth=%s)", auth)
            conn = Connection(
                server,
                user=bind_user,
                password=bind_pass,
                authentication=auth,
                auto_bind=True,
                receive_timeout=10,
            )
        else:
            # ── Option 2: try anonymous bind (works on many Samba/AD setups) ─
            try:
                logger.debug("ldap3: attempting anonymous bind to %s", config.AD_SERVER)
                conn = Connection(
                    server,
                    authentication=ANONYMOUS,
                    auto_bind=True,
                    receive_timeout=10,
                )
                logger.info("ldap3: anonymous bind succeeded")
            except Exception as anon_exc:
                logger.debug("ldap3: anonymous bind failed: %s", anon_exc)
                conn = None
                last_error = str(anon_exc)

            # ── Option 3: NTLM with machine identity (Windows domain-joined) ─
            if conn is None:
                try:
                    logger.debug("ldap3: attempting NTLM machine-account bind")
                    conn = Connection(
                        server,
                        authentication=NTLM,
                        auto_bind=True,
                        receive_timeout=10,
                    )
                    logger.info("ldap3: NTLM machine-account bind succeeded")
                except Exception as ntlm_exc:
                    logger.debug("ldap3: NTLM machine-account bind failed: %s", ntlm_exc)
                    conn = None
                    last_error = str(ntlm_exc)

        if conn is not None:
            groups = _ldap3_search(conn, sam)
            conn.unbind()
            if groups is not None:
                return {"username": sam, "groups": groups, "error": None}
            last_error = f"User '{sam}' not found in AD"

    except Exception as exc:
        last_error = str(exc)
        logger.warning("ldap3 AD lookup failed for '%s': %s", sam, exc)

    # ── Fallback: PowerShell DirectoryServices (domain-joined Windows only) ──
    logger.info("Attempting PowerShell AD fallback for '%s'", sam)
    ps_groups = _lookup_via_powershell(sam)
    if ps_groups is not None:
        return {"username": sam, "groups": ps_groups, "error": None}

    # ── Both methods failed ───────────────────────────────────────────────────
    logger.error("All AD lookup methods failed for '%s'. Last error: %s", sam, last_error)
    return {"username": sam, "groups": [], "error": last_error}
