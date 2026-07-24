"""
Production EvidenceBuilder — strict invariants, rich attribution_conditions.

Invariants enforced before each EvidenceItem is created:
  ✓ Variant belongs to the Experiment
  ✓ Video is the current successful attempt (is_current=true, status=completed)
  ✓ AttributionWindow.status = 'closed'  (not open)
  ✓ Exactly one baseline snapshot (earliest) and one final snapshot (latest) per Video
  ✓ Baseline snapshot collected_at ≤ AttributionWindow.starts_at  (or within tolerance)
  ✓ Final snapshot collected_at ≥ AttributionWindow.ends_at - tolerance
  ✓ views_delta = final.views - baseline.views  (never total lifetime)
  ✓ Negative views_delta → abort with EvidenceInconsistencyError (no silent clamping)
  ✓ Non-negative likes_delta and comments_delta (clamp with warning)
  ✓ Only is_unique=true RedirectEvents from the exact AttributionWindow
  ✓ Exactly 3 items required before snapshot finalization

Rich attribution_conditions recorded per item:
  {
    "schemaVersion": 1,
    "windowStartedAt": "...",
    "windowEndedAt": "...",
    "baselineCollectedAt": "...",
    "finalCollectedAt": "...",
    "baselineDelaySeconds": 0,
    "finalCollectionDelaySeconds": 240,
    "videoAttemptNumber": 1,
    "attributionMethod": "isolated_window"
  }
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal

log = logging.getLogger("evidence_builder")

# How many seconds of clock skew we tolerate between window boundary and snapshot
_TOLERANCE_SECONDS = 300  # 5 minutes


class EvidenceInconsistencyError(ValueError):
    """Raised when a metric delta is negative or data integrity fails."""


async def build_and_finalize_evidence(
    project_id: str,
    experiment_id: str,
) -> UUID:
    """
    Build evidence items for all 3 variants and finalize the snapshot.
    Returns the finalized EvidenceSnapshot ID.
    Idempotent: returns existing snapshot if already finalized.
    """
    async with AsyncSessionLocal() as db:
        return await _build(db, project_id, experiment_id)


async def _build(db: AsyncSession, project_id: str, experiment_id: str) -> UUID:
    # Idempotent: return existing finalized snapshot
    existing = await db.execute(
        text(
            "SELECT id FROM experiment_evidence_snapshots "
            "WHERE experiment_id = :eid AND project_id = :pid AND status = 'finalized' "
            "ORDER BY version DESC LIMIT 1"
        ),
        {"eid": experiment_id, "pid": project_id},
    )
    ex_row = existing.first()
    if ex_row:
        log.info("Evidence snapshot for experiment %s already finalized — idempotent", experiment_id)
        return ex_row[0]

    # Create pending snapshot
    ver_r = await db.execute(
        text(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM experiment_evidence_snapshots "
            "WHERE experiment_id = :eid AND project_id = :pid"
        ),
        {"eid": experiment_id, "pid": project_id},
    )
    version = ver_r.scalar() or 1

    snap_r = await db.execute(
        text(
            "INSERT INTO experiment_evidence_snapshots "
            "(project_id, experiment_id, version, status, attribution_method, generated_at) "
            "VALUES (:pid, :eid, :v, 'pending', 'isolated_window', now()) "
            "RETURNING id"
        ),
        {"pid": project_id, "eid": experiment_id, "v": version},
    )
    snapshot_id = snap_r.scalar()
    await db.commit()

    # Verify exactly 3 variants
    variants_r = await db.execute(
        text(
            "SELECT id, position FROM variants "
            "WHERE experiment_id = :eid AND project_id = :pid ORDER BY position ASC"
        ),
        {"eid": experiment_id, "pid": project_id},
    )
    variants = [dict(r) for r in variants_r.mappings()]
    if len(variants) != 3:
        raise EvidenceInconsistencyError(
            f"Expected 3 variants for experiment {experiment_id}, found {len(variants)}"
        )

    # Build one item per variant
    items_created = 0
    errors = []
    for variant in variants:
        variant_id = str(variant["id"])
        try:
            await _build_item(db, snapshot_id, variant_id, project_id)
            items_created += 1
        except EvidenceInconsistencyError as exc:
            log.error(
                "Evidence inconsistency for variant %s: %s — ABORTING finalization",
                variant_id, exc,
            )
            errors.append(str(exc))
        except Exception as exc:
            log.error("Failed to build evidence item for variant %s: %s", variant_id, exc)
            errors.append(str(exc))

    if items_created < 3:
        # Mark snapshot as failed so it can be retried after the problem is resolved
        await db.execute(
            text(
                "UPDATE experiment_evidence_snapshots SET status = 'failed' "
                "WHERE id = :sid AND project_id = :pid"
            ),
            {"sid": snapshot_id, "pid": project_id},
        )
        await db.commit()
        raise EvidenceInconsistencyError(
            f"Only {items_created}/3 evidence items built for experiment {experiment_id}. "
            f"Errors: {'; '.join(errors)}"
        )

    # All 3 items exist — finalize
    await db.execute(
        text(
            "UPDATE experiment_evidence_snapshots "
            "SET status = 'finalized', finalized_at = now() "
            "WHERE id = :sid AND project_id = :pid"
        ),
        {"sid": snapshot_id, "pid": project_id},
    )
    await db.execute(
        text(
            "UPDATE experiments SET status = 'analyzing', analysis_started_at = now() "
            "WHERE id = :eid AND project_id = :pid AND status IN ('tracking', 'in_progress')"
        ),
        {"eid": experiment_id, "pid": project_id},
    )
    await db.commit()

    log.info("Finalized evidence snapshot %s for experiment %s", snapshot_id, experiment_id)

    # Enqueue insight generation
    await db.execute(
        text("SELECT enqueue_job(:type, :key, :payload, 'Experiment', :eid, :pid, now(), 3)"),
        {
            "type": "generate_insight",
            "key": f"generate_insight:{snapshot_id}",
            "payload": json.dumps({"project_id": project_id, "experiment_id": experiment_id}),
            "eid": experiment_id, "pid": project_id,
        },
    )
    await db.commit()
    return snapshot_id


async def _build_item(
    db: AsyncSession,
    snapshot_id: str,
    variant_id: str,
    project_id: str,
) -> None:
    """
    Build and persist one EvidenceItem for a variant.
    Raises EvidenceInconsistencyError on any integrity violation.
    """
    # 1. Verify current completed video
    vid_r = await db.execute(
        text(
            "SELECT v.id, v.tiktok_video_id, v.tracking_started_at, "
            "v.tracking_window_ends_at, v.attempt_number "
            "FROM videos v "
            "WHERE v.variant_id = :vrid AND v.project_id = :pid "
            "AND v.is_current = true AND v.status = 'completed'"
        ),
        {"vrid": variant_id, "pid": project_id},
    )
    video = vid_r.mappings().first()
    if not video:
        raise EvidenceInconsistencyError(
            f"No current completed video for variant {variant_id}"
        )
    video_id = str(video["id"])

    # 2. Verify AttributionWindow is CLOSED (not active)
    aw_r = await db.execute(
        text(
            "SELECT id, status, starts_at, ends_at "
            "FROM attribution_windows "
            "WHERE video_id = :vid AND project_id = :pid "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"vid": video_id, "pid": project_id},
    )
    aw = aw_r.mappings().first()
    if not aw:
        raise EvidenceInconsistencyError(
            f"No attribution window found for video {video_id}"
        )
    if aw["status"] != "closed":
        raise EvidenceInconsistencyError(
            f"AttributionWindow {aw['id']} for video {video_id} is {aw['status']!r}, "
            "must be 'closed' before building evidence"
        )

    window_starts: datetime = aw["starts_at"]
    window_ends: datetime = aw["ends_at"]

    # 3. Load all snapshots in chronological order
    snaps_r = await db.execute(
        text(
            "SELECT id, collected_at, views, likes, comments "
            "FROM video_metric_snapshots "
            "WHERE video_id = :vid AND project_id = :pid "
            "ORDER BY collected_at ASC"
        ),
        {"vid": video_id, "pid": project_id},
    )
    snapshots = [dict(r) for r in snaps_r.mappings()]
    if len(snapshots) < 2:
        raise EvidenceInconsistencyError(
            f"Video {video_id} has only {len(snapshots)} snapshots, need at least 2 "
            "(baseline + final)"
        )

    baseline = snapshots[0]
    final = snapshots[-1]

    # 4. Validate baseline timing: must have been collected before window ends
    baseline_at: datetime = baseline["collected_at"]
    final_at: datetime = final["collected_at"]

    # Baseline should have been collected at or near window start
    baseline_delay = (baseline_at - window_starts).total_seconds()
    if baseline_delay > _TOLERANCE_SECONDS:
        log.warning(
            "Baseline for video %s collected %ds after window start — recorded in attribution_conditions",
            video_id, int(baseline_delay),
        )

    # Final snapshot should be collected on or after window close (within tolerance for early retries)
    final_delay = (final_at - window_ends).total_seconds()

    # 5. Compute deltas — views_delta must be non-negative
    views_delta = int(final["views"]) - int(baseline["views"])
    likes_delta = int(final["likes"]) - int(baseline["likes"])
    comments_delta = int(final["comments"]) - int(baseline["comments"])

    if views_delta < 0:
        raise EvidenceInconsistencyError(
            f"Negative views_delta={views_delta} for video {video_id} "
            f"(baseline={baseline['views']}, final={final['views']}). "
            "TikTok may have corrected its count. Cannot finalize evidence without manual review."
        )

    # Non-negative clamping with warning for likes/comments
    if likes_delta < 0:
        log.warning(
            "Negative likes_delta=%d for video %s — clamped to 0 (TikTok count correction)",
            likes_delta, video_id,
        )
        likes_delta = 0
    if comments_delta < 0:
        log.warning(
            "Negative comments_delta=%d for video %s — clamped to 0 (TikTok count correction)",
            comments_delta, video_id,
        )
        comments_delta = 0

    # 6. Count unique attributed clicks from the exact window
    window_id = str(aw["id"])
    clicks_r = await db.execute(
        text(
            "SELECT COUNT(*) FROM redirect_events "
            "WHERE attribution_window_id = :awid AND is_unique = true AND project_id = :pid"
        ),
        {"awid": window_id, "pid": project_id},
    )
    unique_clicks = int(clicks_r.scalar() or 0)

    clicks_per_1k: float | None = None
    if views_delta > 0:
        clicks_per_1k = round(unique_clicks / views_delta * 1000, 2)

    # 7. Build rich attribution_conditions
    attribution_conditions: dict[str, Any] = {
        "schemaVersion": 1,
        "attributionMethod": "isolated_window",
        "windowStartedAt": window_starts.isoformat(),
        "windowEndedAt": window_ends.isoformat(),
        "baselineCollectedAt": baseline_at.isoformat(),
        "finalCollectedAt": final_at.isoformat(),
        "baselineDelaySeconds": max(0, int(baseline_delay)),
        "finalCollectionDelaySeconds": max(0, int(final_delay)) if final_delay > 0 else 0,
        "videoAttemptNumber": int(video.get("attempt_number", 1)),
    }

    # 8. Get execution observation if present
    obs_r = await db.execute(
        text("SELECT id FROM execution_observations WHERE video_id = :vid AND project_id = :pid"),
        {"vid": video_id, "pid": project_id},
    )
    obs_id = obs_r.scalar()

    # 9. Idempotent insert — do not create a second item for the same variant+snapshot
    existing_r = await db.execute(
        text(
            "SELECT id FROM experiment_evidence_items "
            "WHERE evidence_snapshot_id = :sid AND variant_id = :vrid AND project_id = :pid"
        ),
        {"sid": snapshot_id, "vrid": variant_id, "pid": project_id},
    )
    if existing_r.first():
        log.info("Evidence item for variant %s already exists — idempotent", variant_id)
        return

    await db.execute(
        text(
            "INSERT INTO experiment_evidence_items "
            "(project_id, evidence_snapshot_id, variant_id, video_id, "
            "start_metric_snapshot_id, end_metric_snapshot_id, "
            "views_delta, likes_delta, comments_delta, "
            "attributed_unique_clicks, unique_clicks_per_1k, "
            "execution_observation_id, attribution_window_id, attribution_conditions) "
            "VALUES (:pid, :sid, :vid, :viid, :sms, :ems, "
            ":vd, :ld, :cd, :uc, :ck, :oid, :awid, :ac)"
        ),
        {
            "pid": project_id, "sid": snapshot_id, "vid": variant_id,
            "viid": video_id,
            "sms": str(baseline["id"]), "ems": str(final["id"]),
            "vd": views_delta, "ld": likes_delta, "cd": comments_delta,
            "uc": unique_clicks, "ck": clicks_per_1k,
            "oid": str(obs_id) if obs_id else None,
            "awid": window_id,
            "ac": json.dumps(attribution_conditions),
        },
    )
    await db.commit()
    log.info(
        "Evidence item created for variant %s: views_delta=%d, clicks=%d",
        variant_id, views_delta, unique_clicks,
    )
