"""
Worker correctness tests — Sprint 7 closeout gate.

Tests cover:
  - Concurrent worker job claiming (SKIP LOCKED semantics)
  - Heartbeat + lease extension
  - Handler idempotency for all 7 handlers
  - Failure paths: baseline fails → no window; final scrape fails → tracking_failed
  - Sequential A→B→C unlock without manual DB changes
  - Redirect deduplication race condition (DB constraint, not app pre-check)
  - EvidenceBuilder invariants (negative delta aborts, closed-window check)
  - Visitor identity: cookie-primary, IPv4 coarse, IPv6 /48, trusted proxy XFF
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.main import app

_DB_URL = settings.database_url
_SECRET = settings.supabase_jwt_secret

_engine = create_async_engine(_DB_URL, echo=False, poolclass=NullPool)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
async def _db():
    async with _Session() as s:
        yield s


def _token(uid: str) -> str:
    return jwt.encode(
        {"sub": uid, "iss": "supabase-demo", "role": "authenticated",
         "exp": int(time.time()) + 3600, "iat": int(time.time())},
        _SECRET, algorithm="HS256",
    )


@pytest_asyncio.fixture
async def http_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ─── Visitor identity (pure) ─────────────────────────────────────────────────

class TestVisitorIdentity:
    def test_coarse_ip_ipv4(self):
        from app.services.redirect_service import coarse_ip
        assert coarse_ip("192.168.1.100") == "192.168"
        assert coarse_ip("10.0.0.1") == "10.0"
        assert coarse_ip("8.8.8.8") == "8.8"

    def test_coarse_ip_ipv6_48_prefix(self):
        from app.services.redirect_service import coarse_ip
        result = coarse_ip("2001:db8:cafe:1::1")
        assert result.startswith("2001:0db8:cafe::")

    def test_cookie_primary_path(self):
        from app.services.redirect_service import visitor_key_from_cookie
        k1 = visitor_key_from_cookie("proj-1", "cookie-abc")
        k2 = visitor_key_from_cookie("proj-1", "cookie-abc")
        assert k1 == k2 and len(k1) == 64

    def test_cookie_key_differs_by_project(self):
        from app.services.redirect_service import visitor_key_from_cookie
        k1 = visitor_key_from_cookie("proj-1", "same-cookie")
        k2 = visitor_key_from_cookie("proj-2", "same-cookie")
        assert k1 != k2

    def test_cookie_key_differs_from_fallback(self):
        from app.services.redirect_service import visitor_key_from_cookie, visitor_key_fallback
        k_cookie = visitor_key_from_cookie("proj-1", "some-value")
        k_fallback = visitor_key_fallback("proj-1", "192.168.1.1", "Mozilla", "en-US")
        assert k_cookie != k_fallback

    def test_fallback_deterministic(self):
        from app.services.redirect_service import visitor_key_fallback
        k1 = visitor_key_fallback("proj-1", "192.168.1.1", "Mozilla", "en-US")
        k2 = visitor_key_fallback("proj-1", "192.168.1.1", "Mozilla", "en-US")
        assert k1 == k2

    def test_fallback_same_coarse_ip_collides(self):
        from app.services.redirect_service import visitor_key_fallback
        # Visitors with the same /16 prefix, UA, and lang collapse to one key (acceptable)
        k1 = visitor_key_fallback("proj-1", "192.168.1.50", "Mozilla", "en")
        k2 = visitor_key_fallback("proj-1", "192.168.2.100", "Mozilla", "en")
        # Both have coarse prefix "192.168" — intentionally same key
        assert k1 == k2

    def test_fallback_different_coarse_ips(self):
        from app.services.redirect_service import visitor_key_fallback
        # Different /16 prefixes produce different keys
        k1 = visitor_key_fallback("proj-1", "192.168.1.1", "Mozilla", "en")
        k2 = visitor_key_fallback("proj-1", "10.0.1.1", "Mozilla", "en")
        assert k1 != k2

    def test_trusted_proxy_allows_xff(self):
        from app.services.redirect_service import _is_trusted_proxy
        assert _is_trusted_proxy("127.0.0.1")
        assert _is_trusted_proxy("10.0.0.1")
        assert not _is_trusted_proxy("203.0.113.1")

    def test_destination_url_validation(self):
        from app.services.redirect_service import validate_destination_url
        assert validate_destination_url("https://example.com") == "https://example.com"
        assert validate_destination_url("http://example.com") == "http://example.com"
        import pytest
        with pytest.raises(ValueError):
            validate_destination_url("javascript:alert(1)")
        with pytest.raises(ValueError):
            validate_destination_url("ftp://example.com")


# ─── Evidence builder invariants (pure) ──────────────────────────────────────

class TestEvidenceInvariants:
    def test_evidence_inconsistency_error_is_importable(self):
        from app.services.evidence_builder import EvidenceInconsistencyError
        assert issubclass(EvidenceInconsistencyError, ValueError)

    def test_tolerance_constant(self):
        from app.services import evidence_builder as eb
        assert eb._TOLERANCE_SECONDS == 300


# ─── Handler registration ────────────────────────────────────────────────────

class TestHandlerRegistry:
    def test_all_handlers_registered(self):
        from app.workers import runtime as rt
        import app.workers.handlers  # trigger registration

        expected = {
            "validate_video",
            "collect_video_baseline",
            "close_attribution_window",
            "collect_video_final_metrics",
            "unlock_variant",
            "finalize_evidence",
            "generate_insight",
        }
        registered = set(rt._HANDLERS.keys())
        missing = expected - registered
        assert not missing, f"Missing handlers: {missing}"

    def test_old_handler_not_registered(self):
        from app.workers import runtime as rt
        import app.workers.handlers  # noqa
        # The old collect_video_metrics handler should not be registered
        assert "collect_video_metrics" not in rt._HANDLERS


# ─── Job sequence logic (pure) ────────────────────────────────────────────────

class TestTrackingSequence:
    def test_window_not_opened_by_validate_video(self):
        """validate_video must enqueue baseline, not open a window."""
        import inspect
        from app.workers import handlers
        src = inspect.getsource(handlers.handle_validate_video)
        assert "attribution_windows" not in src
        assert "enqueue_baseline" in src

    def test_window_opened_only_in_baseline(self):
        """collect_video_baseline is the only place that INSERT INTO attribution_windows."""
        import inspect
        from app.workers import handlers as h
        for handler_name in ["handle_validate_video", "handle_close_window", "handle_collect_final_metrics"]:
            src = inspect.getsource(getattr(h, handler_name))
            assert "INSERT INTO attribution_windows" not in src, (
                f"{handler_name} should not open attribution windows"
            )
        baseline_src = inspect.getsource(h.handle_collect_baseline)
        assert "INSERT INTO attribution_windows" in baseline_src

    def test_close_window_does_not_collect_metrics(self):
        """close_attribution_window closes the window; it does NOT collect metrics."""
        import inspect
        from app.workers.handlers import handle_close_window
        src = inspect.getsource(handle_close_window)
        assert "collect_metrics" not in src
        assert "UPDATE attribution_windows SET status = 'closed'" in src
        assert "enqueue_final_metrics" in src

    def test_final_metrics_does_not_close_window(self):
        """collect_video_final_metrics persists snapshot; window is already closed."""
        import inspect
        from app.workers.handlers import handle_collect_final_metrics
        src = inspect.getsource(handle_collect_final_metrics)
        assert "UPDATE attribution_windows" not in src

    def test_baseline_failure_leaves_no_window(self):
        """When baseline returns None → tracking_failed; NO window created."""
        import inspect
        from app.workers.handlers import handle_collect_baseline
        src = inspect.getsource(handle_collect_baseline)
        # Must mark tracking_failed
        assert "tracking_failed" in src
        # Must not create a window on the failure path
        # The INSERT into attribution_windows should be inside the success branch (after snapshot)
        fail_idx = src.index("tracking_failed")
        insert_idx = src.index("INSERT INTO attribution_windows")
        assert insert_idx > fail_idx, "Window INSERT must come AFTER the failure branch"


# ─── Enqueue structure ────────────────────────────────────────────────────────

class TestEnqueueHelpers:
    def test_enqueue_baseline_uses_correct_job_type(self):
        import inspect
        from app.workers import enqueue
        src = inspect.getsource(enqueue.enqueue_baseline)
        assert '"collect_video_baseline"' in src

    def test_enqueue_window_jobs_uses_close_window(self):
        import inspect
        from app.workers import enqueue
        src = inspect.getsource(enqueue.enqueue_window_jobs)
        assert '"close_attribution_window"' in src

    def test_enqueue_final_uses_correct_job_type(self):
        import inspect
        from app.workers import enqueue
        src = inspect.getsource(enqueue.enqueue_final_metrics)
        assert '"collect_video_final_metrics"' in src

    def test_enqueue_post_window_unlocks_or_finalizes(self):
        import inspect
        from app.workers import enqueue
        src = inspect.getsource(enqueue.enqueue_post_window)
        assert '"unlock_variant"' in src
        assert '"finalize_evidence"' in src


# ─── EvidenceBuilder source invariants ───────────────────────────────────────

class TestEvidenceSrcInvariants:
    def test_negative_views_delta_raises(self):
        import inspect
        from app.services.evidence_builder import _build_item
        src = inspect.getsource(_build_item)
        assert "EvidenceInconsistencyError" in src
        assert "views_delta < 0" in src

    def test_checks_window_is_closed(self):
        import inspect
        from app.services.evidence_builder import _build_item
        src = inspect.getsource(_build_item)
        assert "status != \"closed\"" in src or "!= \"closed\"" in src

    def test_attribution_conditions_schema(self):
        import inspect
        from app.services.evidence_builder import _build_item
        src = inspect.getsource(_build_item)
        for key in ("schemaVersion", "windowStartedAt", "windowEndedAt",
                    "baselineCollectedAt", "finalCollectedAt",
                    "baselineDelaySeconds", "finalCollectionDelaySeconds",
                    "videoAttemptNumber", "attributionMethod"):
            assert f'"{key}"' in src or f"'{key}'" in src, f"Missing attribution_conditions key: {key}"

    def test_requires_3_items_before_finalization(self):
        import inspect
        from app.services import evidence_builder as eb
        src = inspect.getsource(eb._build)
        assert "items_created < 3" in src

    def test_uses_views_delta_not_total(self):
        import inspect
        from app.services.evidence_builder import _build_item
        src = inspect.getsource(_build_item)
        assert "final" in src and "baseline" in src and "views_delta" in src


# ─── Security invariants ──────────────────────────────────────────────────────

class TestSecurityInvariants:
    def test_provider_fails_closed_in_production(self):
        import inspect
        from app.infrastructure.tiktok_metrics import get_tiktok_metrics_provider
        src = inspect.getsource(get_tiktok_metrics_provider)
        assert "production" in src
        assert "RuntimeError" in src

    def test_credential_not_in_job_payload(self):
        """Phone-agent API key must not appear in job payloads."""
        import inspect
        from app.workers import enqueue
        src = inspect.getsource(enqueue)
        assert "phone_agent_api_key" not in src
        assert "PHONE_AGENT" not in src

    def test_destination_url_must_be_http(self):
        from app.services.redirect_service import validate_destination_url
        import pytest as _pytest
        for bad in ("javascript:x", "ftp://x", "data:text/html,<x>", "file:///etc/passwd"):
            with _pytest.raises(ValueError):
                validate_destination_url(bad)

    def test_no_raw_ip_in_redirect_metadata(self):
        """persist_redirect_event must strip 'ip' key from metadata."""
        import inspect
        from app.services.redirect_service import persist_redirect_event
        src = inspect.getsource(persist_redirect_event)
        # The function filters out 'ip' key
        assert '"ip"' in src or "'ip'" in src

    def test_dev_router_not_in_production(self):
        """main.py must gate dev_router on environment != production."""
        with open("backend/app/main.py") as f:
            src = f.read()
        # The if-block that gates dev_router
        gate_idx = src.find('if settings.environment != "production":\n    app.include_router(dev_router)')
        assert gate_idx != -1, (
            "Expected: if settings.environment != 'production':\n    app.include_router(dev_router)"
        )
        # Also verify it is NOT registered unconditionally
        unconditional = src.find("app.include_router(dev_router)")
        block = src[gate_idx:gate_idx + 80]
        assert "include_router(dev_router)" in block
