from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_scope
from app.db.session import get_db
from app.domain.errors import ProjectNotFound
from app.domain.scope import ProjectScope
from app.schemas.experiment import ExperimentResponse
from app.services.experiment_service import ExperimentService

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


@router.get("/active", response_model=ExperimentResponse)
async def get_active_experiment(
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
    svc = ExperimentService(db)
    try:
        exp = await svc.get_active(scope)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExperimentResponse.from_row(exp)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
async def get_experiment(
    experiment_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
    svc = ExperimentService(db)
    try:
        exp = await svc.get(scope, experiment_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExperimentResponse.from_row(exp)
