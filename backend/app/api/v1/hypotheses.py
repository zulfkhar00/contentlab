from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_scope
from app.db.session import get_db
from app.domain.errors import DomainError, ProjectNotFound
from app.domain.scope import ProjectScope
from app.intelligence.fake import FakeIntelligenceProvider
from app.repositories.project_repo import ProjectRepository
from app.schemas.hypothesis import (
    ApproveAndGenerateRequest,
    HypothesisPatchRequest,
    HypothesisResponse,
)
from app.schemas.experiment import ExperimentResponse
from app.services.hypothesis_service import HypothesisService

router = APIRouter(prefix="/api/hypotheses", tags=["hypotheses"])

_provider = FakeIntelligenceProvider()


async def _get_project_and_facts(scope: ProjectScope, db: AsyncSession) -> tuple[dict, list]:
    repo = ProjectRepository(db)
    project = await repo.get_by_scope(scope)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    # Facts: empty list until project_facts is wired (Sprint 5)
    return project, []


@router.post("/generate", response_model=list[HypothesisResponse], status_code=status.HTTP_201_CREATED)
async def generate_hypotheses(
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> list[HypothesisResponse]:
    """
    Generate initial hypotheses from project context.
    Returns 409 if hypotheses already exist for this project.
    """
    project, facts = await _get_project_and_facts(scope, db)
    svc = HypothesisService(db)
    try:
        created = await svc.generate_initial(scope, project, facts, _provider)
    except DomainError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [HypothesisResponse.from_row(h) for h in created]


@router.get("", response_model=list[HypothesisResponse])
async def list_hypotheses(
    status_filter: str | None = Query(None, alias="status"),
    search: str | None = Query(None),
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> list[HypothesisResponse]:
    svc = HypothesisService(db)
    rows = await svc.list(scope, status_filter=status_filter, search=search)
    return [HypothesisResponse.from_row(h) for h in rows]


@router.get("/{hypothesis_id}", response_model=HypothesisResponse)
async def get_hypothesis(
    hypothesis_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> HypothesisResponse:
    svc = HypothesisService(db)
    try:
        row = await svc.get(scope, hypothesis_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return HypothesisResponse.from_row(row)


@router.patch("/{hypothesis_id}", response_model=HypothesisResponse)
async def patch_hypothesis(
    hypothesis_id: UUID,
    body: HypothesisPatchRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> HypothesisResponse:
    svc = HypothesisService(db)
    try:
        row = await svc.patch(scope, hypothesis_id, body.model_dump(exclude_none=True))
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return HypothesisResponse.from_row(row)


@router.post("/{hypothesis_id}/reject", response_model=HypothesisResponse)
async def reject_hypothesis(
    hypothesis_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> HypothesisResponse:
    svc = HypothesisService(db)
    try:
        row = await svc.reject(scope, hypothesis_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return HypothesisResponse.from_row(row)


@router.post("/{hypothesis_id}/approve-and-generate-experiment", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
async def approve_and_generate(
    hypothesis_id: UUID,
    body: ApproveAndGenerateRequest,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> ExperimentResponse:
    """
    Approve the hypothesis design and create Experiment + 3 Variants in one transaction.
    Provider call happens before the transaction opens.
    """
    project, facts = await _get_project_and_facts(scope, db)
    svc = HypothesisService(db)
    try:
        exp = await svc.approve_and_generate_experiment(
            scope=scope,
            hypothesis_id=hypothesis_id,
            design_fields=body.model_dump(exclude_none=True),
            project=project,
            facts=facts,
            provider=_provider,
        )
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ExperimentResponse.from_row(exp)
