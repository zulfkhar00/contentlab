"""
Worker handlers — each registered with @register_handler.

All handlers are idempotent: re-running them with the same job produces
the same outcome without side effects.

Correct tracking sequence
─────────────────────────
  validate_video
      → persist video identity only (tiktok_video_id, normalized_url)
      → enqueue collect_video_baseline
  collect_video_baseline
      → collect baseline snapshot
      → set tracking_started_at / tracking_window_ends_at
      → open AttributionWindow (active)
      → Video → tracking; Experiment → tracking
      → enqueue close_attribution_window at ends_at
  close_attribution_window  ← runs at exactly tracking_window_ends_at
      → closes window by database time
      → enqueue collect_video_final_metrics
  collect_video_final_metrics  ← may retry after window already closed
      → collect final snapshot
      → Video → completed
      → enqueue unlock_variant or finalize_evidence
  unlock_variant  → B unlocks after A completes; C after B
  finalize_evidence  → EvidenceBuilder; 3 items required
  generate_insight  → existing Claude analysis pipeline
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.workers.runtime import register_handler

log = logging.getLogger("worker.handlers")


# ── validate_video ─────────────────────────────────────────────────────────────

@register_handler("validate_video")
async def handle_validate_video(job: dict) -> dict:
    """
    Validate URL identity via TikTokMetricsProvider.

    On success: persist tiktok_video_id + normalized_url → enqueue baseline.
    On failure: mark Video with terminal error status; no window created.

    This handler does NOT open an AttributionWindow. That happens only after
    the baseline snapshot is successfully collected.
    """
    payload = job["payload"]
    video_id = payload["video_id"]
    project_id = payload["project_id"]

    from app.infrastructure.tiktok_metrics import get_tiktok_metrics_provider
    provider = get_tiktok_metrics_provider()

    async with AsyncSessionLocal() as db:
        vid_r = await db.execute(
            text(
                "SELECT v.id, v.variant_id, v.submitted_url, v.status, "
                "p.tiktok_handle, e.tracking_window_hours, e.id AS exp_id "
                "FROM videos v "
                "JOIN variants vr ON vr.id = v.variant_id "
                "JOIN experiments e ON e.id = vr.experiment_id "
                "JOIN projects p ON p.id = v.project_id "
                "WHERE v.id = :vid AND v.project_id = :pid"
            ),
            {"vid": video_id, "pid": project_id},
        )
        vid = vid_r.mappings().first()
        if not vid:
            raise ValueError(f"Video {video_id} not found")

        if vid["status"] not in ("validating", "needs_url"):
            return {"status": vid["status"], "idempotent": True}

        url = vid["submitted_url"]
        handle = vid["tiktok_handle"] or ""
        result = await provider.validate_video(url, handle)

        if not result.valid:
            error_status = result.error_code or "invalid_url"
            await db.execute(
                text(
                    "UPDATE videos SET status = :st, "
                    "validation_error_code = :ec, validation_error_detail = :ed "
                    "WHERE id = :vid AND project_id = :pid"
                ),
                {
                    "st": error_status, "ec": error_status,
                    "ed": (result.error_detail or "")[:500],
                    "vid": video_id, "pid": project_id,
                },
            )
            await db.commit()
            return {"valid": False, "error_code": error_status}

        # Persist identity only — no tracking timestamps, no window yet
        await db.execute(
            text(
                "UPDATE videos SET "
                "normalized_tiktok_url = :nu, tiktok_video_id = :tvid, "
                "validated_at = now() "
                "WHERE id = :vid AND project_id = :pid AND status = 'validating'"
            ),
            {
                "nu": result.normalized_tiktok_url,
                "tvid": result.tiktok_video_id,
                "vid": video_id, "pid": project_id,
            },
        )
        await db.commit()

    from app.workers.enqueue import enqueue_baseline
    await enqueue_baseline(
        project_id=project_id,
        video_id=video_id,
        tiktok_video_id=result.tiktok_video_id,
        tiktok_url=result.normalized_tiktok_url or url,
        window_hours=float(vid["tracking_window_hours"]),
        experiment_id=str(vid["exp_id"]),
        variant_id=str(vid["variant_id"]),
    )
    return {"valid": True, "tiktok_video_id": result.tiktok_video_id}


# ── collect_video_baseline ─────────────────────────────────────────────────────

@register_handler("collect_video_baseline")
async def handle_collect_baseline(job: dict) -> dict:
    """
    Collect baseline snapshot; only then open the AttributionWindow.

    If baseline collection fails terminally:
      - Video stays at validating/tracking_failed
      - No window is created
      - Next Variant remains queued
    """
    payload = job["payload"]
    video_id = payload["video_id"]
    project_id = payload["project_id"]
    tiktok_video_id = payload["tiktok_video_id"]
    tiktok_url = payload.get("tiktok_url", "")
    window_hours = float(payload.get("window_hours", 72))
    experiment_id = payload["experiment_id"]
    variant_id = payload["variant_id"]

    async with AsyncSessionLocal() as db:
        # Idempotent: window already open means baseline was collected
        aw_r = await db.execute(
            text("SELECT id FROM attribution_windows WHERE video_id = :vid"),
            {"vid": video_id},
        )
        if aw_r.first():
            return {"idempotent": True, "reason": "window already exists"}

        vid_r = await db.execute(
            text("SELECT status FROM videos WHERE id = :vid AND project_id = :pid"),
            {"vid": video_id, "pid": project_id},
        )
        vid_row = vid_r.first()
        if not vid_row:
            raise ValueError(f"Video {video_id} not found")
        if vid_row[0] in ("tracking", "completed"):
            return {"idempotent": True, "reason": f"already in {vid_row[0]}"}
        if vid_row[0] == "tracking_failed":
            return {"idempotent": True, "reason": "already failed"}

    from app.infrastructure.tiktok_metrics import get_tiktok_metrics_provider
    provider = get_tiktok_metrics_provider()
    snapshot = await provider.collect_metrics(tiktok_video_id, tiktok_url)

    if snapshot is None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE videos SET status = 'tracking_failed' "
                    "WHERE id = :vid AND project_id = :pid "
                    "AND status NOT IN ('completed', 'tracking_failed')"
                ),
                {"vid": video_id, "pid": project_id},
            )
            await db.commit()
        log.error("Baseline collection failed for video %s — no window opened", video_id)
        raise ValueError(f"Baseline collection returned None for video {video_id}")

    now = datetime.now(timezone.utc)
    window_ends = now + timedelta(hours=window_hours)

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "INSERT INTO video_metric_snapshots "
                "(project_id, video_id, collected_at, views, likes, comments) "
                "VALUES (:pid, :vid, :ts, :v, :l, :c)"
            ),
            {
                "pid": project_id, "vid": video_id, "ts": now,
                "v": snapshot.views, "l": snapshot.likes, "c": snapshot.comments,
            },
        )
        await db.execute(
            text(
                "UPDATE videos SET status = 'tracking', "
                "tracking_started_at = :now, tracking_window_ends_at = :ends "
                "WHERE id = :vid AND project_id = :pid "
                "AND status NOT IN ('tracking', 'completed', 'tracking_failed')"
            ),
            {"now": now, "ends": window_ends, "vid": video_id, "pid": project_id},
        )
        await db.execute(
            text(
                "INSERT INTO attribution_windows "
                "(project_id, experiment_id, variant_id, video_id, starts_at, ends_at, status) "
                "VALUES (:pid, :eid, :vrid, :vid, :ts, :te, 'active') "
                "ON CONFLICT (video_id) DO NOTHING"
            ),
            {
                "pid": project_id, "eid": experiment_id, "vrid": variant_id,
                "vid": video_id, "ts": now, "te": window_ends,
            },
        )
        await db.execute(
            text(
                "UPDATE experiments SET status = 'tracking' "
                "WHERE id = :eid AND project_id = :pid AND status IN ('ready', 'in_progress')"
            ),
            {"eid": experiment_id, "pid": project_id},
        )
        await db.commit()

    from app.workers.enqueue import enqueue_window_jobs
    await enqueue_window_jobs(
        project_id=project_id, video_id=video_id,
        tiktok_video_id=tiktok_video_id, tiktok_url=tiktok_url,
        window_ends=window_ends,
    )

    log.info(
        "Baseline collected for video %s: views=%d, window ends %s",
        video_id, snapshot.views, window_ends.isoformat(),
    )
    return {
        "views": snapshot.views, "likes": snapshot.likes, "comments": snapshot.comments,
        "window_ends_at": window_ends.isoformat(),
    }


# ── close_attribution_window ───────────────────────────────────────────────────

@register_handler("close_attribution_window")
async def handle_close_window(job: dict) -> dict:
    """
    Close the AttributionWindow at its scheduled end time.

    This runs at tracking_window_ends_at via the scheduler — independent of
    phone-agent availability. Click attribution ends here.

    After closing, enqueues collect_video_final_metrics. Retries of the final
    scrape do not re-open or extend the window.
    """
    payload = job["payload"]
    video_id = payload["video_id"]
    project_id = payload["project_id"]
    tiktok_video_id = payload["tiktok_video_id"]
    tiktok_url = payload.get("tiktok_url", "")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "UPDATE attribution_windows SET status = 'closed' "
                "WHERE video_id = :vid AND project_id = :pid AND status = 'active' "
                "RETURNING id"
            ),
            {"vid": video_id, "pid": project_id},
        )
        closed_row = result.first()
        await db.commit()

    if not closed_row:
        log.info("Window for video %s already closed — idempotent", video_id)
    else:
        log.info("Attribution window closed for video %s at database time", video_id)

    from app.workers.enqueue import enqueue_final_metrics
    await enqueue_final_metrics(
        project_id=project_id, video_id=video_id,
        tiktok_video_id=tiktok_video_id, tiktok_url=tiktok_url,
    )
    return {"closed": True}


# ── collect_video_final_metrics ────────────────────────────────────────────────

@register_handler("collect_video_final_metrics")
async def handle_collect_final_metrics(job: dict) -> dict:
    """
    Collect the final metric snapshot after the window has already been closed.

    The window closes on schedule via close_attribution_window. This handler
    may run or retry after that close — delay is expected and logged in
    attribution_conditions on the EvidenceItem. It must not re-open the window.

    On terminal failure: Video → tracking_failed, next Variant stays queued.
    """
    payload = job["payload"]
    video_id = payload["video_id"]
    project_id = payload["project_id"]
    tiktok_video_id = payload["tiktok_video_id"]
    tiktok_url = payload.get("tiktok_url", "")

    async with AsyncSessionLocal() as db:
        vid_r = await db.execute(
            text("SELECT status FROM videos WHERE id = :vid AND project_id = :pid"),
            {"vid": video_id, "pid": project_id},
        )
        vid_row = vid_r.first()
        if not vid_row:
            raise ValueError(f"Video {video_id} not found")
        if vid_row[0] == "completed":
            return {"idempotent": True}
        if vid_row[0] == "tracking_failed":
            return {"idempotent": True, "already_failed": True}

    from app.infrastructure.tiktok_metrics import get_tiktok_metrics_provider
    provider = get_tiktok_metrics_provider()
    snapshot = await provider.collect_metrics(tiktok_video_id, tiktok_url)

    if snapshot is None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE videos SET status = 'tracking_failed' "
                    "WHERE id = :vid AND project_id = :pid AND status NOT IN ('completed')"
                ),
                {"vid": video_id, "pid": project_id},
            )
            await db.commit()
        raise ValueError(
            f"Final metric collection returned None for video {video_id} — marked tracking_failed"
        )

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        aw_r = await db.execute(
            text(
                "SELECT ends_at FROM attribution_windows "
                "WHERE video_id = :vid AND project_id = :pid"
            ),
            {"vid": video_id, "pid": project_id},
        )
        aw_row = aw_r.first()
        delay_seconds = None
        if aw_row and aw_row[0]:
            delay_seconds = max(0, int((now - aw_row[0]).total_seconds()))
            if delay_seconds > 0:
                log.info(
                    "Final scrape for video %s is %ds late (window closed; delay recorded)",
                    video_id, delay_seconds,
                )

        await db.execute(
            text(
                "INSERT INTO video_metric_snapshots "
                "(project_id, video_id, collected_at, views, likes, comments) "
                "VALUES (:pid, :vid, :ts, :v, :l, :c)"
            ),
            {
                "pid": project_id, "vid": video_id, "ts": now,
                "v": snapshot.views, "l": snapshot.likes, "c": snapshot.comments,
            },
        )
        await db.execute(
            text(
                "UPDATE videos SET status = 'completed' "
                "WHERE id = :vid AND project_id = :pid AND status NOT IN ('completed')"
            ),
            {"vid": video_id, "pid": project_id},
        )
        await db.commit()

    from app.workers.enqueue import enqueue_post_window
    await enqueue_post_window(project_id, video_id)

    return {
        "views": snapshot.views, "likes": snapshot.likes, "comments": snapshot.comments,
        "final_collection_delay_seconds": delay_seconds,
    }


# ── unlock_next_variant ────────────────────────────────────────────────────────

@register_handler("unlock_variant")
async def handle_unlock_variant(job: dict) -> dict:
    """
    Unlock next variant. Idempotent: no-op if already past queued.
    B unlocks after A completes; C unlocks after B completes.
    If A fails, B never unlocks.
    """
    payload = job["payload"]
    project_id = payload["project_id"]
    next_variant_id = payload["next_variant_id"]
    experiment_id = payload["experiment_id"]

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(
                "UPDATE variants SET status = 'ready_to_review' "
                "WHERE id = :vid AND project_id = :pid AND status = 'queued'"
            ),
            {"vid": next_variant_id, "pid": project_id},
        )
        await db.execute(
            text(
                "UPDATE experiments SET status = 'in_progress' "
                "WHERE id = :eid AND project_id = :pid AND status = 'tracking'"
            ),
            {"eid": experiment_id, "pid": project_id},
        )
        await db.commit()
    return {"unlocked": next_variant_id}


# ── finalize_evidence ──────────────────────────────────────────────────────────

@register_handler("finalize_evidence")
async def handle_finalize_evidence(job: dict) -> dict:
    """
    Build EvidenceItems; finalize snapshot only when all 3 valid items exist.
    Negative view deltas abort finalization with an error.
    """
    payload = job["payload"]
    project_id = payload["project_id"]
    experiment_id = payload["experiment_id"]

    from app.services.evidence_builder import build_and_finalize_evidence
    snapshot_id = await build_and_finalize_evidence(project_id, experiment_id)
    return {"evidence_snapshot_id": str(snapshot_id)}


# ── generate_insight ───────────────────────────────────────────────────────────

@register_handler("generate_insight")
async def handle_generate_insight(job: dict) -> dict:
    """Trigger the existing Claude analyze + candidates pipeline. Idempotent."""
    payload = job["payload"]
    project_id = payload["project_id"]
    experiment_id = payload["experiment_id"]

    from app.intelligence.factory import get_intelligence_provider
    from app.domain.scope import ProjectScope
    from app.services.insight_service import InsightService

    provider = get_intelligence_provider()

    async with AsyncSessionLocal() as db:
        proj_r = await db.execute(
            text("SELECT id, user_id FROM projects WHERE id = :pid"),
            {"pid": project_id},
        )
        proj_row = proj_r.mappings().first()
        if not proj_row:
            raise ValueError(f"Project {project_id} not found")
        scope = ProjectScope(user_id=proj_row["user_id"], project_id=proj_row["id"])
        svc = InsightService(db)
        insight = await svc.analyze(scope, UUID(experiment_id), provider)

    return {"insight_id": str(insight["id"])}
