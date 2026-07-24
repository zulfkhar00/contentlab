"""
Development-only routes — complete Sprint 5 variant execution loop.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
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
    Seeds deterministic Flagd fixture evidence.
    Sets experiment.status = 'analyzing' so /analyze can be called next.
    """
    svc = DevFixtureService(db)
    try:
        result = await svc.seed_experiment_evidence(scope, experiment_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DomainError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@router.post("/videos/{video_id}/complete-window", status_code=status.HTTP_200_OK)
async def complete_tracking_window(
    video_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Close a Video's tracking window and advance the experiment lifecycle.

    - Video → completed
    - AttributionWindow → closed
    - If variant A or B: unlock next variant (→ ready_to_review), Experiment → in_progress
    - If variant C: Experiment → analyzing
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    # Verify video exists and is tracking
    vid_result = await db.execute(
        text(
            "SELECT v.id, v.variant_id, v.project_id "
            "FROM videos v WHERE v.id = :vid AND v.project_id = :pid AND v.status = 'tracking'"
        ),
        {"vid": video_id, "pid": scope.project_id},
    )
    vid_row = vid_result.mappings().first()
    if not vid_row:
        raise HTTPException(status_code=404, detail="Video not found or not in tracking status")

    variant_id = vid_row["variant_id"]

    # Get variant position + experiment info
    var_result = await db.execute(
        text(
            "SELECT var.position, var.experiment_id, e.tracking_window_hours "
            "FROM variants var JOIN experiments e ON e.id = var.experiment_id "
            "WHERE var.id = :vid AND var.project_id = :pid"
        ),
        {"vid": variant_id, "pid": scope.project_id},
    )
    var_row = var_result.mappings().first()
    if not var_row:
        raise HTTPException(status_code=404, detail="Variant not found")

    position = var_row["position"]
    experiment_id = var_row["experiment_id"]

    # Complete the video
    await db.execute(
        text(
            "UPDATE videos SET status = 'completed', tracking_window_ends_at = :now "
            "WHERE id = :vid AND project_id = :pid"
        ),
        {"now": now, "vid": video_id, "pid": scope.project_id},
    )

    # Close attribution window
    await db.execute(
        text(
            "UPDATE attribution_windows SET status = 'closed' "
            "WHERE video_id = :vid AND project_id = :pid AND status = 'active'"
        ),
        {"vid": video_id, "pid": scope.project_id},
    )

    next_pos = {"A": "B", "B": "C"}.get(position)
    msg = ""

    if next_pos:
        # Unlock next variant
        await db.execute(
            text(
                "UPDATE variants SET status = 'ready_to_review' "
                "WHERE experiment_id = :eid AND project_id = :pid AND position = :pos AND status = 'queued'"
            ),
            {"eid": experiment_id, "pid": scope.project_id, "pos": next_pos},
        )
        # Experiment → in_progress
        await db.execute(
            text(
                "UPDATE experiments SET status = 'in_progress' "
                "WHERE id = :eid AND project_id = :pid AND status = 'tracking'"
            ),
            {"eid": experiment_id, "pid": scope.project_id},
        )
        msg = f"Variant {position} window closed. Variant {next_pos} unlocked. Experiment in_progress."
    else:
        # Variant C completed — move experiment to analyzing
        await db.execute(
            text(
                "UPDATE experiments SET status = 'analyzing', tracking_completed_at = :now, analysis_started_at = :now "
                "WHERE id = :eid AND project_id = :pid AND status = 'tracking'"
            ),
            {"now": now, "eid": experiment_id, "pid": scope.project_id},
        )
        msg = "Variant C window closed. Experiment is now analyzing. Call /analyze to generate insight."

    await db.commit()
    return {"video_id": str(video_id), "position": position, "message": msg}


@router.post("/intelligence/canary")
async def canary_call(
    operation: str,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Sprint 6B: run one live Claude call for the specified operation.
    Requires INTELLIGENCE_PROVIDER=claude and ANTHROPIC_API_KEY.
    Returns latency, model, validation result without persisting ai_run.
    """
    from app.api.v1._canary import run_canary
    return await run_canary(operation, scope, db)
