"""Unit tests for FakeVideoValidator."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from app.infrastructure.video_validator import FakeVideoValidator

v = FakeVideoValidator()


def test_valid_full_url():
    r = v.validate("https://www.tiktok.com/@founder_lab/video/123456", "founder_lab")
    assert r.valid
    assert r.tiktok_video_id == "123456"
    assert r.tiktok_handle == "founder_lab"
    assert r.normalized_tiktok_url == "https://www.tiktok.com/@founder_lab/video/123456"


def test_normalizes_no_www():
    r = v.validate("https://tiktok.com/@founder_lab/video/123456", "founder_lab")
    assert r.valid
    assert "www.tiktok.com" in r.normalized_tiktok_url


def test_account_mismatch():
    r = v.validate("https://www.tiktok.com/@other_user/video/999", "founder_lab")
    assert not r.valid
    assert r.error_code == "account_mismatch"


def test_invalid_url():
    r = v.validate("https://youtube.com/watch?v=abc", "founder_lab")
    assert not r.valid
    assert r.error_code == "invalid_url"


def test_empty_expected_handle_allows_any():
    r = v.validate("https://www.tiktok.com/@anyone/video/111", "")
    assert r.valid


def test_at_prefix_stripped_from_handle():
    r = v.validate("https://www.tiktok.com/@founder_lab/video/123456", "@founder_lab")
    assert r.valid


def test_short_url():
    r = v.validate("https://vm.tiktok.com/ABC123/", "founder_lab")
    assert r.valid
    assert r.tiktok_video_id is not None
