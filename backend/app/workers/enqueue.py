"""
Enqueue helpers — schedule jobs from within handlers and services.
All calls are idempotent via idempotency_key.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import text

from app.db.session import AsyncSessionLocal


async def enqueue_baseline(
    project_id: str,
    video_id: str,
    tiktok_video_id: str,
    tiktok_url: str,
    window_hours: int,
    experiment_id: str,
    variant_id: str,
) -> None:
    """Enqueue collect_video_baseline immediately after validation succeeds."""
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT enqueue_job(:type, :key, :payload, :etype, :eid, :pid, now(), 3)"),
            {
                "type": "collect_video_baseline",
                "key": f"collect_baseline:{video_id}",
                "payload": json.dumps({
                    "project_id": project_id,
                    "video_id": video_id,
                    "tiktok_video_id": tiktok_video_id,
                    "tiktok_url": tiktok_url,
                    "window_hours": window_hours,
                    "experiment_id": experiment_id,
                    "variant_id": variant_id,
                }),
                "etype": "Video", "eid": video_id, "pid": project_id,
            },
        )
        await db.commit()


async def enqueue_window_jobs(
    project_id: str,
    video_id: str,
    tiktok_video_id: str,
    tiktok_url: str,
    window_ends: datetime,
) -> None:
    """
    Schedule the two jobs that govern a tracking window:
      1. close_attribution_window — runs at exactly window_ends
      2. collect_video_final_metrics — runs shortly after close (with retries)

    The close job runs at window_ends regardless of phone-agent availability.
    The final-metrics job is enqueued *by close_window*, not here, so that
    the enqueue time records the actual window close time in the job record.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT enqueue_job(:type, :key, :payload, :etype, :eid, :pid, :run_at, 3)"),
            {
                "type": "close_attribution_window",
                "key": f"close_window:{video_id}",
                "payload": json.dumps({
                    "project_id": project_id,
                    "video_id": video_id,
                    "tiktok_video_id": tiktok_video_id,
                    "tiktok_url": tiktok_url,
                }),
                "etype": "Video", "eid": video_id, "pid": project_id,
                "run_at": window_ends,
            },
        )
        await db.commit()


async def enqueue_final_metrics(
    project_id: str,
    video_id: str,
    tiktok_video_id: str,
    tiktok_url: str,
) -> None:
    """
    Enqueue final metric collection immediately after the window is closed.
    This is called by close_attribution_window so it runs after close, not before.
    Up to 5 retry attempts to handle transient phone-agent unavailability.
    """
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("SELECT enqueue_job(:type, :key, :payload, :etype, :eid, :pid, now(), 5)"),
            {
                "type": "collect_video_final_metrics",
                "key": f"collect_final:{video_id}",
                "payload": json.dumps({
                    "project_id": project_id,
                    "video_id": video_id,
                    "tiktok_video_id": tiktok_video_id,
                    "tiktok_url": tiktok_url,
                }),
                "etype": "Video", "eid": video_id, "pid": project_id,
            },
        )
        await db.commit()


async def enqueue_post_window(project_id: str, video_id: str) -> None:
    """
    After a Video completes:
      - A completed → unlock B
      - B completed → unlock C
      - C completed → transition experiment + finalize evidence
    """
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text(
                "SELECT vr.position, vr.experiment_id "
                "FROM videos v JOIN variants vr ON vr.id = v.variant_id "
                "WHERE v.id = :vid AND v.project_id = :pid"
            ),
            {"vid": video_id, "pid": project_id},
        )
        row = r.mappings().first()
        if not row:
            return

        position = row["position"]
        exp_id = str(row["experiment_id"])
        next_pos = {"A": "B", "B": "C"}.get(position)

        if next_pos:
            nxt = await db.execute(
                text(
                    "SELECT id FROM variants WHERE experiment_id = :eid "
                    "AND project_id = :pid AND position = :pos"
                ),
                {"eid": exp_id, "pid": project_id, "pos": next_pos},
            )
            nxt_row = nxt.first()
            if nxt_row:
                await db.execute(
                    text("SELECT enqueue_job(:type, :key, :payload, :etype, :eid, :pid, now(), 3)"),
                    {
                        "type": "unlock_variant",
                        "key": f"unlock:{nxt_row[0]}",
                        "payload": json.dumps({
                            "project_id": project_id,
                            "next_variant_id": str(nxt_row[0]),
                            "experiment_id": exp_id,
                        }),
                        "etype": "Variant", "eid": str(nxt_row[0]), "pid": project_id,
                    },
                )
        else:
            # C completed
            await db.execute(
                text(
                    "UPDATE experiments SET status = 'analyzing', "
                    "tracking_completed_at = now(), analysis_started_at = now() "
                    "WHERE id = :eid AND project_id = :pid AND status = 'tracking'"
                ),
                {"eid": exp_id, "pid": project_id},
            )
            await db.execute(
                text("SELECT enqueue_job(:type, :key, :payload, :etype, :eid, :pid, now(), 3)"),
                {
                    "type": "finalize_evidence",
                    "key": f"finalize_evidence:{exp_id}",
                    "payload": json.dumps({"project_id": project_id, "experiment_id": exp_id}),
                    "etype": "Experiment", "eid": exp_id, "pid": project_id,
                },
            )

        await db.commit()
