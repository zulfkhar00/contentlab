"""
FakeVideoValidator — Sprint 5.
Normalizes TikTok URLs, extracts handle + video ID,
optionally checks handle against the project's tiktok_handle.
Returns structured validation result; never calls TikTok.
"""
import re
from dataclasses import dataclass


_FULL_PATTERN = re.compile(
    r"^https?://(?:www\.)?tiktok\.com/@(?P<handle>[^/]+)/video/(?P<vid>\d+)",
    re.IGNORECASE,
)
_SHORT_PATTERN = re.compile(r"^https?://vm\.tiktok\.com/(?P<code>[A-Za-z0-9]+)/?")


@dataclass
class ValidationResult:
    valid: bool
    normalized_tiktok_url: str | None = None
    tiktok_video_id: str | None = None
    tiktok_handle: str | None = None
    error_code: str | None = None
    error_detail: str | None = None


class FakeVideoValidator:
    """
    Deterministic validator for development and tests.
    Accepts any well-formed TikTok URL whose account matches the project handle.
    Never contacts TikTok.
    """

    def validate(self, url: str, expected_handle: str) -> ValidationResult:
        url = url.strip()

        # Full URL
        m = _FULL_PATTERN.match(url)
        if m:
            handle = m.group("handle")
            video_id = m.group("vid")
            normalized = f"https://www.tiktok.com/@{handle}/video/{video_id}"

            expected_norm = expected_handle.lstrip("@").lower()
            if expected_norm and handle.lower() != expected_norm:
                return ValidationResult(
                    valid=False,
                    error_code="account_mismatch",
                    error_detail=(
                        f"URL account @{handle} does not match "
                        f"project TikTok handle @{expected_handle}"
                    ),
                )
            return ValidationResult(
                valid=True,
                normalized_tiktok_url=normalized,
                tiktok_video_id=video_id,
                tiktok_handle=handle,
            )

        # Short URL — accept without handle check (fake validation only)
        m = _SHORT_PATTERN.match(url)
        if m:
            code = m.group("code")
            return ValidationResult(
                valid=True,
                normalized_tiktok_url=url,
                tiktok_video_id=f"vm-{code}",
                tiktok_handle=expected_handle.lstrip("@"),
            )

        return ValidationResult(
            valid=False,
            error_code="invalid_url",
            error_detail=(
                "URL must be a TikTok video URL: "
                "https://www.tiktok.com/@handle/video/VIDEO_ID"
            ),
        )
