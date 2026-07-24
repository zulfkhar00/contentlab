from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_scope
from app.db.session import get_db
from app.domain.errors import DomainError, ProjectNotFound
from app.domain.scope import ProjectScope
from app.intelligence.factory import get_intelligence_provider
from app.schemas.hypothesis import HypothesisResponse
from app.schemas.insight import CandidateResponse, InsightDetailResponse, InsightSummaryResponse
from app.services.insight_service import InsightService

router = APIRouter(tags=["insights"])

_provider = get_intelligence_provider()


@router.post(
    "/api/experiments/{experiment_id}/analyze",
    response_model=InsightDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_experiment(
    experiment_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> InsightDetailResponse:
    """
    Reads finalized evidence snapshot, computes metrics, calls provider,
    creates Insight + exactly 3 FollowUpCandidates in one transaction.
    Experiment must be in 'analyzing' status.
    """
    svc = InsightService(db)
    try:
        row = await svc.analyze(scope, experiment_id, _provider)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return InsightDetailResponse.from_row(row)


@router.get("/api/insights", response_model=list[InsightSummaryResponse])
async def list_insights(
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> list[InsightSummaryResponse]:
    svc = InsightService(db)
    rows = await svc.list(scope)
    return [InsightSummaryResponse(**r) for r in rows]


@router.get("/api/insights/{insight_id}", response_model=InsightDetailResponse)
async def get_insight(
    insight_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> InsightDetailResponse:
    svc = InsightService(db)
    try:
        row = await svc.get(scope, insight_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InsightDetailResponse.from_row(row)


@router.post(
    "/api/follow-up-candidates/{candidate_id}/accept",
    response_model=HypothesisResponse,
    status_code=status.HTTP_201_CREATED,
)
async def accept_candidate(
    candidate_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> HypothesisResponse:
    """
    Lock candidate → verify proposed → create child Hypothesis with lineage → commit.
    Returns the created Hypothesis.
    """
    svc = InsightService(db)
    try:
        h_row = await svc.accept_candidate(scope, candidate_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return HypothesisResponse.from_row(h_row)


@router.post(
    "/api/follow-up-candidates/{candidate_id}/dismiss",
    response_model=CandidateResponse,
)
async def dismiss_candidate(
    candidate_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> CandidateResponse:
    svc = InsightService(db)
    try:
        row = await svc.dismiss_candidate(scope, candidate_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CandidateResponse(**row)
