"""
TikTokMetricsProvider protocol + implementations.

FakeTikTokMetricsProvider  — deterministic fixture data, used in tests.
PhoneAgentTikTokMetricsProvider — calls internal phone-agent HTTP API.
  The phone agent does NOT access Supabase directly.
  FastAPI never executes ADB or phone automation inline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import httpx

from app.infrastructure.video_validator import FakeVideoValidator, ValidationResult


@dataclass
class MetricSnapshot:
    views: int
    likes: int
    comments: int


@runtime_checkable
class TikTokMetricsProvider(Protocol):
    async def validate_video(
        self, url: str, expected_handle: str
    ) -> ValidationResult:
        """
        Normalize URL, confirm video is accessible and public,
        extract tiktok_video_id and actual handle.
        """
        ...

    async def collect_metrics(
        self, tiktok_video_id: str, tiktok_url: str
    ) -> MetricSnapshot | None:
        """
        Collect current public metrics for a video.
        Returns None if video is inaccessible (private/deleted).
        """
        ...


# ── Fake provider ─────────────────────────────────────────────────────────────

_FAKE_METRICS = {
    "A": MetricSnapshot(views=8204, likes=412, comments=38),
    "B": MetricSnapshot(views=4500, likes=267, comments=52),
    "C": MetricSnapshot(views=6000, likes=180, comments=24),
}


class FakeTikTokMetricsProvider:
    """
    Deterministic metrics for tests.
    Uses FakeVideoValidator for URL validation (same logic as existing tests).
    """
    _validator = FakeVideoValidator()
    _call_count: dict[str, int] = {}

    async def validate_video(self, url: str, expected_handle: str) -> ValidationResult:
        return self._validator.validate(url, expected_handle)

    async def collect_metrics(
        self, tiktok_video_id: str, tiktok_url: str
    ) -> MetricSnapshot | None:
        # Determine which variant from the video ID suffix or fallback to B
        for pos, metrics in _FAKE_METRICS.items():
            if pos.lower() in tiktok_video_id.lower():
                return metrics
        return _FAKE_METRICS["B"]


# ── Phone-agent provider ──────────────────────────────────────────────────────

class PhoneAgentTikTokMetricsProvider:
    """
    Calls the internal phone-agent HTTP API.
    The phone agent is a separate process that has access to a physical/virtual
    device. It never receives Supabase credentials or user JWTs.
    FastAPI sends it only: video URL, expected handle, tiktok_video_id.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"X-Phone-Agent-Key": api_key},
            timeout=90.0,
        )

    async def validate_video(
        self, url: str, expected_handle: str
    ) -> ValidationResult:
        from app.infrastructure.video_validator import ValidationResult as VR
        try:
            resp = await self._client.post(
                "/validate-video",
                json={"url": url, "expected_handle": expected_handle},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("valid"):
                return VR(
                    valid=True,
                    normalized_tiktok_url=data.get("normalized_url"),
                    tiktok_video_id=data.get("video_id"),
                    tiktok_handle=data.get("handle"),
                )
            return VR(
                valid=False,
                error_code=data.get("error_code", "invalid_url"),
                error_detail=data.get("error_detail", "Validation failed"),
            )
        except Exception as exc:
            import logging
            logging.getLogger("phone_agent").warning("validate_video error: %s", exc)
            return VR(valid=False, error_code="validation_error", error_detail=type(exc).__name__)

    async def collect_metrics(
        self, tiktok_video_id: str, tiktok_url: str
    ) -> MetricSnapshot | None:
        try:
            resp = await self._client.post(
                "/collect-metrics",
                json={"video_id": tiktok_video_id, "url": tiktok_url},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            return MetricSnapshot(
                views=int(data.get("views", 0)),
                likes=int(data.get("likes", 0)),
                comments=int(data.get("comments", 0)),
            )
        except Exception:
            return None

    async def aclose(self) -> None:
        await self._client.aclose()


# ── Factory ───────────────────────────────────────────────────────────────────

def get_tiktok_metrics_provider() -> TikTokMetricsProvider:
    from app.config import settings
    provider_name = (settings.tiktok_metrics_provider or "").lower().strip()

    if provider_name == "phone_agent":
        if not settings.phone_agent_api_key:
            raise RuntimeError(
                "PHONE_AGENT_API_KEY must be set when TIKTOK_METRICS_PROVIDER=phone_agent."
            )
        return PhoneAgentTikTokMetricsProvider(
            base_url=settings.phone_agent_url,
            api_key=settings.phone_agent_api_key,
        )

    if provider_name == "fake":
        return FakeTikTokMetricsProvider()

    if settings.environment == "production":
        raise RuntimeError(
            f"TIKTOK_METRICS_PROVIDER={provider_name!r} is not valid in production. "
            "Configure it to phone_agent and set PHONE_AGENT_API_KEY."
        )

    import logging
    logging.getLogger("tiktok_metrics").warning(
        "TIKTOK_METRICS_PROVIDER=%r is unrecognised — defaulting to FakeTikTokMetricsProvider",
        provider_name,
    )
    return FakeTikTokMetricsProvider()
