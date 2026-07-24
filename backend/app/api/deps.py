from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.jwt import extract_user_id
from app.db.session import get_db
from app.domain.errors import ProjectNotFound, Unauthorized
from app.domain.scope import ProjectScope
from app.repositories.project_repo import ProjectRepository
from sqlalchemy.ext.asyncio import AsyncSession

_bearer = HTTPBearer(auto_error=False)


async def get_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UUID:
    """Extract and validate user_id from Bearer JWT. Raises 401 on failure."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    try:
        return extract_user_id(credentials.credentials)
    except Unauthorized as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


async def get_project_scope(
    user_id: UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> ProjectScope:
    """Resolve user to their active project. Raises 404 if no project exists."""
    repo = ProjectRepository(db)
    project = await repo.find_active_by_user(user_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active project found. Complete onboarding first.",
        )
    return ProjectScope(user_id=user_id, project_id=project["id"])
