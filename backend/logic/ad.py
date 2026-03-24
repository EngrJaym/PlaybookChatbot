from __future__ import annotations

import logging
import re

import config

logger = logging.getLogger(__name__)


def _cn_from_dn(dn: str) -> str:
    m = re.match(r"CN=([^,]+)", dn, re.IGNORECASE)
    return m.group(1).strip() if m else dn.strip()


def lookup_ad_groups(sam: str) -> dict:
    sam = (sam or "").strip().lower()
    if not sam:
        return {"username": None, "groups": [], "error": "No username provided"}

    try:
        from ldap3 import Server, Connection, ALL, NTLM, SIMPLE, ANONYMOUS
        from ldap3.core.exceptions import LDAPException

        server = Server(config.AD_SERVER, get_info=ALL, connect_timeout=8)

        bind_user = config.AD_BIND_USER.strip()
        bind_pass = config.AD_BIND_PASSWORD.strip()

        if bind_user and bind_pass:
            conn = Connection(
                server,
                user=bind_user,
                password=bind_pass,
                authentication=SIMPLE,
                auto_bind=True,
                receive_timeout=10,
            )
        else:
            conn = Connection(
                server,
                authentication=NTLM,
                auto_bind=True,
                receive_timeout=10,
            )

        search_filter = f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={sam}))"
        conn.search(
            config.AD_BASE_DN,
            search_filter,
            attributes=["memberOf", "sAMAccountName"],
        )

        if not conn.entries:
            return {"username": sam, "groups": [], "error": "User not found in AD"}

        entry   = conn.entries[0]
        raw_groups = entry.memberOf.values if entry.memberOf else []
        groups  = [_cn_from_dn(g) for g in raw_groups]

        conn.unbind()
        logger.info("AD lookup for '%s': %d groups found", sam, len(groups))
        return {"username": sam, "groups": groups, "error": None}

    except Exception as exc:
        logger.warning("AD lookup failed for '%s': %s", sam, exc)
        return {"username": sam, "groups": [], "error": str(exc)}

