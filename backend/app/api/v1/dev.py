"""
Development-only routes. Never exposed in production.
Guarded by ENVIRONMENT check in main.py.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_scope
from app.db.session import get_db
from app.domain.errors import DomainError, ProjectNotFound
from app.domain.scope import ProjectScope
from app.services.dev_fixture_service import DevFixtureService

router = APIRouter(prefix="/api/dev", tags=["dev"])


@router.post(
    "/experiments/{experiment_id}/seed-evidence",
    status_code=status.HTTP_201_CREATED,
)
async def seed_experiment_evidence(
    experiment_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Seeds deterministic Flagd fixture evidence for the given experiment.
    Creates Videos, VideoMetricSnapshots, AttributionWindows, and a finalized
    ExperimentEvidenceSnapshot with EvidenceItems using canonical fixture metrics:
      A (control):              8,204 views / 24 unique clicks / 2.9 per 1K
      B (hypothesis_treatment): 4,500 views / 53 unique clicks / 11.7 per 1K
      C (alternative_treatment):6,000 views / 36 unique clicks / 6.0 per 1K

    Sets experiment.status = 'analyzing' so /analyze can be called next.
    Returns 409 if evidence already seeded.
    """
    svc = DevFixtureService(db)
    try:
        result = await svc.seed_experiment_evidence(scope, experiment_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result
