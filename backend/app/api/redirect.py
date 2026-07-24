"""
Public redirect endpoint — GET /p/{tracking_slug}

Registered WITHOUT authentication middleware.
Must be fast (<50ms target), always redirect, never expose internal errors.

Visitor identity precedence:
  1. cl_visitor cookie → HMAC(secret, "v1:cookie:" + project_id + ":" + cookie_value)
  2. Fallback (no cookie) → HMAC(secret, "v1:fallback:" + project_id + coarse_ip + ua + lang)

Click attribution ends when the AttributionWindow.ends_at passes (database time),
not when this handler runs.
"""
import logging
import time

from fastapi import APIRouter, Cookie, Request, Response
from fastapi.responses import RedirectResponse

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.services.redirect_service import (
    find_active_window,
    generate_visitor_cookie_value,
    get_client_ip,
    persist_redirect_event,
    resolve_redirect,
    ua_hash,
    validate_destination_url,
    visitor_key_fallback,
    visitor_key_from_cookie,
)

router = APIRouter(tags=["redirect"])
log = logging.getLogger("redirect.endpoint")

_FALLBACK_URL = "https://contentlab.app"


@router.get("/p/{tracking_slug}")
async def handle_redirect(
    tracking_slug: str,
    request: Request,
    cl_visitor: str | None = Cookie(default=None),
) -> Response:
    """
    Resolve tracking_slug → destination_url.
    Persist RedirectEvent with cookie-first deduplication.
    Always redirect regardless of persistence outcome.
    """
    t_start = time.monotonic()

    destination_url = _FALLBACK_URL
    visitor_key: str | None = None
    new_cookie_value: str | None = None

    try:
        async with AsyncSessionLocal() as db:
            project = await resolve_redirect(db, tracking_slug)
            if not project:
                # Unknown slug — still redirect to fallback
                resp = _build_response(_FALLBACK_URL, None, None, t_start)
                return resp

            try:
                destination_url = validate_destination_url(project["destination_url"])
            except ValueError:
                destination_url = _FALLBACK_URL

            project_id = str(project["id"])

            # ── Visitor identity ─────────────────────────────────────────────
            if cl_visitor:
                # Cookie exists: primary path — project-scoped HMAC over the cookie value
                visitor_key = visitor_key_from_cookie(project_id, cl_visitor)
            else:
                # Fallback: coarse IP + UA + accept-language
                client_ip = get_client_ip(request)
                ua = request.headers.get("user-agent", "")
                lang = request.headers.get("accept-language", "")
                visitor_key = visitor_key_fallback(project_id, client_ip, ua, lang)
                # Assign a new cookie so future requests use the primary path
                new_cookie_value = generate_visitor_cookie_value()

            # ── Attribution ──────────────────────────────────────────────────
            window = await find_active_window(db, project_id)
            window_id = str(window["id"]) if window else None

            # Metadata — no raw IPs
            ua_str = request.headers.get("user-agent", "")[:200]
            meta = {"ua_hash": ua_hash(ua_str)}

            try:
                await persist_redirect_event(
                    db, project_id, destination_url,
                    visitor_key, window_id, meta,
                )
            except Exception as exc:
                # Log and count but never block the redirect
                log.warning("Redirect event persistence failed for slug=%s: %s", tracking_slug, exc)

    except Exception as exc:
        log.error("Redirect error for slug=%s: %s", tracking_slug, exc, exc_info=True)

    return _build_response(
        destination_url,
        new_cookie_value or cl_visitor,
        new_cookie_value is not None,
        t_start,
    )


def _build_response(
    url: str,
    cookie_value: str | None,
    set_new_cookie: bool,
    t_start: float,
) -> Response:
    latency_ms = int((time.monotonic() - t_start) * 1000)
    resp = RedirectResponse(url=url, status_code=302)
    resp.headers["X-Redirect-Latency-Ms"] = str(latency_ms)
    resp.headers["Cache-Control"] = "no-store"

    if set_new_cookie and cookie_value:
        resp.set_cookie(
            key=settings.visitor_cookie_name,
            value=cookie_value,
            max_age=settings.visitor_cookie_max_age,
            httponly=True,
            samesite="lax",
            secure=settings.environment == "production",
        )

    return resp
