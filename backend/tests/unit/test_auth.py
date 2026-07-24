import time
from unittest.mock import patch

import jwt
import pytest

from app.auth.jwt import extract_user_id
from app.config import settings
from app.domain.errors import Unauthorized

_SECRET = settings.supabase_jwt_secret
_USER_ID = "11111111-1111-1111-1111-111111111111"


def _make_token(sub: str | None = _USER_ID, exp_offset: int = 3600) -> str:
    payload = {
        "iss": "supabase-demo",
        "role": "authenticated",
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
    }
    if sub is not None:
        payload["sub"] = sub
    return jwt.encode(payload, _SECRET, algorithm="HS256")


def test_extract_user_id_valid():
    token = _make_token()
    user_id = extract_user_id(token)
    assert str(user_id) == _USER_ID


def test_extract_user_id_expired():
    token = _make_token(exp_offset=-1)
    with pytest.raises(Unauthorized, match="Invalid JWT"):
        extract_user_id(token)


def test_extract_user_id_bad_secret():
    token = jwt.encode({"sub": _USER_ID, "exp": int(time.time()) + 3600}, "wrong-secret", algorithm="HS256")
    with pytest.raises(Unauthorized):
        extract_user_id(token)


def test_extract_user_id_missing_sub():
    token = _make_token(sub=None)
    with pytest.raises(Unauthorized, match="missing sub"):
        extract_user_id(token)


def test_extract_user_id_invalid_uuid():
    token = _make_token(sub="not-a-uuid")
    with pytest.raises(Unauthorized, match="not a valid UUID"):
        extract_user_id(token)
