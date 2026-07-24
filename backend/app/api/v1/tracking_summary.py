"""
GET /api/experiments/{id}/tracking-summary

Backend-computed tracking summary for the Experiment Workspace, Videos, and
Overview screens. The frontend must not reconstruct per-variant state from
raw tables.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_project_scope
from app.db.session import get_db
from app.domain.scope import ProjectScope

router = APIRouter(prefix="/api/experiments", tags=["experiments-tracking"])


@router.get("/{experiment_id}/tracking-summary")
async def get_tracking_summary(
    experiment_id: UUID,
    scope: ProjectScope = Depends(get_project_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    exp_r = await db.execute(
        text(
            "SELECT id, status, tracking_window_hours FROM experiments "
            "WHERE id = :eid AND project_id = :pid"
        ),
        {"eid": str(experiment_id), "pid": str(scope.project_id)},
    )
    exp = exp_r.mappings().first()
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment {experiment_id} not found")

    variants_r = await db.execute(
        text(
            "SELECT vr.id, vr.position, vr.status, "
            "v.id AS video_id, v.status AS video_status, v.attempt_number, "
            "v.tracking_started_at, v.tracking_window_ends_at, v.tiktok_video_id, "
            "v.validation_error_code, v.validation_error_detail "
            "FROM variants vr "
            "LEFT JOIN videos v ON v.variant_id = vr.id AND v.is_current = true "
            "WHERE vr.experiment_id = :eid AND vr.project_id = :pid "
            "ORDER BY vr.position ASC"
        ),
        {"eid": str(experiment_id), "pid": str(scope.project_id)},
    )
    variants = [dict(r) for r in variants_r.mappings()]

    variant_summaries = []
    for vr in variants:
        vid_id = str(vr["video_id"]) if vr.get("video_id") else None
        window = None
        unique_clicks = 0

        if vid_id:
            aw_r = await db.execute(
                text(
                    "SELECT id, status, starts_at, ends_at FROM attribution_windows "
                    "WHERE video_id = :vid AND project_id = :pid "
                    "ORDER BY created_at DESC LIMIT 1"
                ),
                {"vid": vid_id, "pid": str(scope.project_id)},
            )
            window = aw_r.mappings().first()
            if window:
                c = await db.execute(
                    text(
                        "SELECT COUNT(*) FROM redirect_events "
                        "WHERE attribution_window_id = :wid AND is_unique = true "
                        "AND project_id = :pid"
                    ),
                    {"wid": str(window["id"]), "pid": str(scope.project_id)},
                )
                unique_clicks = int(c.scalar() or 0)

        position = vr["position"]
        vr_status = vr["status"]
        vid_status = vr.get("video_status")

        # Next-action label
        next_action = _next_action(position, vr_status, vid_status)

        # Lock reason for queued variants
        lock_reason = None
        if vr_status == "queued":
            wait = {"B": "A", "C": "B"}.get(position)
            if wait:
                lock_reason = f"Waiting for Variant {wait} to complete tracking"

        variant_summaries.append({
            "variant_id": str(vr["id"]),
            "position": position,
            "variant_status": vr_status,
            "video_id": vid_id,
            "video_status": vid_status,
            "attempt_number": vr.get("attempt_number"),
            "tiktok_video_id": vr.get("tiktok_video_id"),
            "tracking_started_at": (
                vr["tracking_started_at"].isoformat()
                if vr.get("tracking_started_at") else None
            ),
            "tracking_window_ends_at": (
                vr["tracking_window_ends_at"].isoformat()
                if vr.get("tracking_window_ends_at") else None
            ),
            "validation_error_code": vr.get("validation_error_code"),
            "attribution_window": {
                "status": window["status"],
                "starts_at": window["starts_at"].isoformat(),
                "ends_at": window["ends_at"].isoformat(),
            } if window else None,
            "unique_attributed_clicks": unique_clicks,
            "lock_reason": lock_reason,
            "next_action": next_action,
        })

    return {
        "experiment_id": str(experiment_id),
        "experiment_status": exp["status"],
        "tracking_window_hours": exp["tracking_window_hours"],
        "variants": variant_summaries,
        "experiment_next_action": _experiment_next_action(exp["status"], variant_summaries),
    }


_TERMINAL_VIDEO_STATUSES = frozenset({
    "invalid_url", "account_mismatch", "video_private", "video_deleted", "tracking_failed",
})


def _next_action(position: str, vr_status: str, vid_status: str | None) -> str:
    """Map variant + video state → human-readable next action label."""
    if vr_status == "queued":
        wait = {"B": "A", "C": "B"}.get(position, "previous variant")
        return f"Waiting for Variant {wait}"
    if vr_status == "ready_to_review":
        return f"Review Variant {position}"
    if vr_status == "approved_for_recording":
        return f"Confirm Variant {position} recorded"
    if vr_status == "recorded":
        if not vid_status or vid_status == "needs_url":
            return f"Paste Variant {position} URL"
        if vid_status == "validating":
            return f"Validating Variant {position}"
        if vid_status in _TERMINAL_VIDEO_STATUSES:
            return f"Retry Variant {position}"
        if vid_status == "tracking":
            return f"Tracking Variant {position}"
        if vid_status == "completed":
            return f"Review Variant {position} observation"
    return ""


def _experiment_next_action(exp_status: str, variants: list) -> str:
    """Top-level experiment next action for the Overview screen."""
    if exp_status in ("completed", "cancelled"):
        return ""
    for vr in variants:
        action = vr.get("next_action", "")
        if action:
            return action
    return {
        "ready": "Review Variant A",
        "in_progress": "Continue experiment",
        "tracking": "Tracking in progress",
        "analyzing": "Finalizing analysis",
    }.get(exp_status, "")
