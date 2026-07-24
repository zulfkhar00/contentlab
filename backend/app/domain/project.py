import re
import secrets

def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip())
    return slug.strip("-") or "project"

def normalize_tiktok_handle(handle: str) -> str:
    return handle.strip().lstrip("@").strip()

def slug_with_suffix(base: str) -> str:
    return f"{base}-{secrets.token_hex(2)}"
