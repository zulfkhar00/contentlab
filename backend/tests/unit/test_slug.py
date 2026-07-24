from app.domain.project import normalize_tiktok_handle, slugify, slug_with_suffix


def test_slugify_basic():
    assert slugify("Content Lab") == "content-lab"


def test_slugify_special_chars():
    assert slugify("My App!! (v2)") == "my-app-v2"


def test_slugify_leading_trailing():
    assert slugify("  hello world  ") == "hello-world"


def test_slugify_empty():
    assert slugify("") == "project"
    assert slugify("---") == "project"


def test_slugify_numbers():
    assert slugify("App2Go") == "app2go"


def test_normalize_handle_strips_at():
    assert normalize_tiktok_handle("@founder_lab") == "founder_lab"


def test_normalize_handle_no_at():
    assert normalize_tiktok_handle("founder_lab") == "founder_lab"


def test_normalize_handle_whitespace():
    assert normalize_tiktok_handle("  @founder_lab  ") == "founder_lab"


def test_normalize_handle_empty():
    assert normalize_tiktok_handle("") == ""


def test_slug_with_suffix_format():
    base = "content-lab"
    result = slug_with_suffix(base)
    assert result.startswith("content-lab-")
    suffix = result[len("content-lab-"):]
    assert len(suffix) == 4
    assert all(c in "0123456789abcdef" for c in suffix)
