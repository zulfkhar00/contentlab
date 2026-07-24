"""
Redirect service — visitor identity, attribution lookup, and event persistence.

Security rules
──────────────
- No raw IP addresses ever stored or logged
- Cookie is the PRIMARY identity signal; HMAC uses a project-scoped binding
- IP/UA fallback only when no usable cookie is available
- IPv4: first two octets only (e.g. 192.168.x.x → "192.168")
- IPv6: first 48 bits / 3 groups (e.g. 2001:db8::1 → "2001:db8:0::")
- X-Forwarded-For only trusted from known reverse-proxy CIDRs
- destination_url validated to http/https only before redirect
"""
import hashlib
import hmac as _hmac_mod
import ipaddress
import json
import logging
import secrets
from typing import List

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

log = logging.getLogger("redirect")

_SECRET = settings.visitor_hmac_secret.encode()
_COOKIE = settings.visitor_cookie_name

# Parse trusted CIDRs once at import time
_TRUSTED_NETWORKS: List[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
for cidr in settings.trusted_proxy_cidrs.split(","):
    cidr = cidr.strip()
    if cidr:
        try:
            _TRUSTED_NETWORKS.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            log.warning("Invalid trusted proxy CIDR: %r", cidr)


def _is_trusted_proxy(ip_str: str) -> bool:
    """Return True if the connection came from a known reverse-proxy CIDR."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _TRUSTED_NETWORKS)
    except ValueError:
        return False


def get_client_ip(request: Request) -> str:
    """
    Return the real client IP.
    X-Forwarded-For is only trusted when the direct connection comes from a
    known reverse-proxy CIDR — prevents header spoofing by arbitrary clients.
    """
    direct_ip = request.client.host if request.client else ""
    if direct_ip and _is_trusted_proxy(direct_ip):
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            # Leftmost IP in the chain is the originating client
            return xff.split(",")[0].strip()
    return direct_ip


def coarse_ip(ip: str) -> str:
    """
    Return only a coarse network prefix — never the full address.
    IPv4: first two octets  → 192.168
    IPv6: first 3 groups (/48) → 2001:db8:cafe::
    """
    if ":" in ip:
        # IPv6
        try:
            addr = ipaddress.ip_address(ip)
            # /48 prefix: first 3 groups of the full 128-bit address
            full = addr.exploded.split(":")
            prefix = ":".join(full[:3]) + "::"
            return prefix
        except ValueError:
            return ip.split(":")[0]
    parts = ip.split(".")
    if len(parts) >= 2 and all(p.isdigit() for p in parts[:2]):
        return f"{parts[0]}.{parts[1]}"
    return ip


def ua_hash(user_agent: str) -> str:
    """16-char hex digest of the user-agent string."""
    return hashlib.sha256(user_agent.encode()).hexdigest()[:16]


def generate_visitor_cookie_value() -> str:
    """128-bit random hex value — set once, persists across attribution windows."""
    return secrets.token_hex(16)


def visitor_key_from_cookie(project_id: str, cookie_value: str) -> str:
    """
    Primary path: bind the cookie to the project using HMAC.
    Changing networks does not change this key.
    """
    msg = f"v1:cookie:{project_id}:{cookie_value}".encode()
    return _hmac_mod.new(_SECRET, msg, hashlib.sha256).hexdigest()


def visitor_key_fallback(
    project_id: str,
    ip: str,
    ua: str,
    accept_language: str,
) -> str:
    """
    Fallback when no usable cookie is available.
    Uses coarse IP prefix + UA hash + truncated accept-language.
    Multiple people behind one NAT may collide — this is acceptable degradation.
    Never stores the original IP.
    """
    ip_prefix = coarse_ip(ip)
    ua_h = ua_hash(ua)
    lang = (accept_language or "")[:20]
    msg = f"v1:fallback:{project_id}:{ip_prefix}:{ua_h}:{lang}".encode()
    return _hmac_mod.new(_SECRET, msg, hashlib.sha256).hexdigest()


def validate_destination_url(url: str) -> str:
    """
    Ensure destination_url starts with http:// or https://.
    Returns the validated URL or raises ValueError.
    """
    normalized = (url or "").strip()
    if normalized.startswith("https://") or normalized.startswith("http://"):
        return normalized
    raise ValueError(f"destination_url must be http or https, got: {url!r}")


async def resolve_redirect(db: AsyncSession, tracking_slug: str) -> dict | None:
    """Return project row or None if not found."""
    result = await db.execute(
        text(
            "SELECT id, destination_url FROM projects "
            "WHERE tracking_slug = :slug AND deleted_at IS NULL LIMIT 1"
        ),
        {"slug": tracking_slug},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def find_active_window(db: AsyncSession, project_id: str) -> dict | None:
    """Find active attribution window for this project at database time."""
    result = await db.execute(
        text(
            "SELECT id, video_id, variant_id, starts_at, ends_at "
            "FROM attribution_windows "
            "WHERE project_id = :pid "
            "  AND status = 'active' "
            "  AND starts_at <= now() "
            "  AND ends_at >= now() "
            "LIMIT 1"
        ),
        {"pid": project_id},
    )
    row = result.mappings().first()
    return dict(row) if row else None


async def persist_redirect_event(
    db: AsyncSession,
    project_id: str,
    destination_url: str,
    visitor_key: str,
    window_id: str | None,
    request_metadata: dict,
) -> None:
    """
    Insert a RedirectEvent.
    Deduplication: only the first occurrence in a window is is_unique=True.
    No raw IP addresses in request_metadata.
    """
    is_unique = False
    if window_id:
        exists = await db.execute(
            text(
                "SELECT 1 FROM redirect_events "
                "WHERE attribution_window_id = :wid AND visitor_key = :vk AND is_unique = true"
            ),
            {"wid": window_id, "vk": visitor_key},
        )
        is_unique = exists.first() is None

    await db.execute(
        text(
            "INSERT INTO redirect_events "
            "(project_id, attribution_window_id, visitor_key, is_unique, "
            "occurred_at, destination_url, request_metadata) "
            "VALUES (:pid, :wid, :vk, :uniq, now(), :dest, :meta)"
        ),
        {
            "pid": project_id,
            "wid": window_id,
            "vk": visitor_key,
            "uniq": is_unique,
            "dest": destination_url,
            "meta": json.dumps({k: v for k, v in request_metadata.items() if k != "ip"}),
        },
    )
    await db.commit()
