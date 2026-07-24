from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_scope, get_user_id
from app.config import settings
from app.db.session import get_db
from app.domain.errors import ProjectAlreadyExists, ProjectNotFound
from app.domain.scope import ProjectScope
from app.schemas.project import ProjectCreateRequest, ProjectResponse, ProjectUpdateRequest
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    user_id: UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Create a project for the authenticated user.
    Called by the onboarding UI on step 5 (Finish Setup).
    Returns 409 if the user already has an active project.
    """
    svc = ProjectService(db)
    try:
        row = await svc.create_project(user_id, body.model_dump())
    except ProjectAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return ProjectResponse.from_row(row, settings.tracking_base_url)


@router.get("/current", response_model=ProjectResponse)
async def get_current_project(
    user_id: UUID = Depends(get_user_id),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Return the authenticated user's active project.
    Called on every app load to hydrate the project context.
    Returns 404 if onboarding has not been completed yet.
    """
    svc = ProjectService(db)
    try:
        row = await svc.get_current_project(user_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ProjectResponse.from_row(row, settings.tracking_base_url)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdateRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Update project fields. context_version and tracking_slug are immutable.
    The database trigger increments context_version when AI-context fields change.
    Returns 403 if the project_id doesn't match the authenticated user's project.
    """
    if scope.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Project ID mismatch")
    svc = ProjectService(db)
    try:
        row = await svc.update_project(scope, body.model_dump(exclude_none=True))
    except ProjectNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ProjectResponse.from_row(row, settings.tracking_base_url)
