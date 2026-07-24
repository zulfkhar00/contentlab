from uuid import UUID
import jwt
from jwt.exceptions import InvalidTokenError
from app.config import settings
from app.domain.errors import Unauthorized

def _decode(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=settings.supabase_jwt_algorithms,
            options={"verify_aud": False},
        )
    except InvalidTokenError as exc:
        raise Unauthorized(f"Invalid JWT: {exc}") from exc

def extract_user_id(token: str) -> UUID:
    payload = _decode(token)
    sub = payload.get("sub")
    if not sub:
        raise Unauthorized("JWT missing sub claim")
    try:
        return UUID(sub)
    except ValueError as exc:
        raise Unauthorized(f"JWT sub is not a valid UUID: {sub}") from exc
