"""
Dev-only service: seeds deterministic fixture evidence for a given experiment.
Only callable when ENVIRONMENT != 'production'.

Creates:
  - Video rows for each variant
  - VideoMetricSnapshot rows (start + end) per video
  - AttributionWindow rows (sequential non-overlapping 72h windows)
  - ExperimentEvidenceSnapshot (finalized)
  - ExperimentEvidenceItem per variant (with canonical fixture metrics)
  - Sets experiment.status = 'analyzing'
"""
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError, ProjectNotFound
from app.domain.scope import ProjectScope

# Canonical fixture metrics per variant position
_FIXTURE_METRICS = {
    "A": {"views": 8204, "likes": 412, "comments": 38, "unique_clicks": 24},   # 2.9/1K
    "B": {"views": 4500, "likes": 267, "comments": 52, "unique_clicks": 53},   # 11.7/1K
    "C": {"views": 6000, "likes": 180, "comments": 24, "unique_clicks": 36},   # 6.0/1K
}


class DevFixtureService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def seed_experiment_evidence(
        self, scope: ProjectScope, experiment_id: UUID
    ) -> dict:
        """
        Idempotent: if a finalized evidence snapshot already exists, returns its id.
        """
        # Verify experiment exists and belongs to project
        exp_result = await self._db.execute(
            text(
                "SELECT id, status, tracking_window_hours, project_id "
                "FROM experiments WHERE id = :eid AND project_id = :pid"
            ),
            {"eid": experiment_id, "pid": scope.project_id},
        )
        exp_row = exp_result.mappings().first()
        if not exp_row:
            raise ProjectNotFound(f"Experiment {experiment_id} not found")

        # Check for existing finalized snapshot
        existing = await self._db.execute(
            text(
                "SELECT id FROM experiment_evidence_snapshots "
                "WHERE experiment_id = :eid AND project_id = :pid AND status = 'finalized'"
            ),
            {"eid": experiment_id, "pid": scope.project_id},
        )
        if existing.first():
            raise DomainError("Evidence already seeded for this experiment.")

        window_hours = int(exp_row["tracking_window_hours"])
        now = datetime.now(timezone.utc)

        # Get variants
        variants_result = await self._db.execute(
            text(
                "SELECT id, position, treatment_role, project_id "
                "FROM variants WHERE experiment_id = :eid ORDER BY position ASC"
            ),
            {"eid": experiment_id},
        )
        variants = [dict(r) for r in variants_result.mappings()]
        if len(variants) != 3:
            raise DomainError(f"Expected 3 variants, found {len(variants)}")

        # Build sequential non-overlapping attribution windows
        # C ends now, B before C, A before B
        window_duration = timedelta(hours=window_hours)
        c_end   = now
        c_start = c_end   - window_duration
        b_end   = c_start
        b_start = b_end   - window_duration
        a_end   = b_start
        a_start = a_end   - window_duration

        window_times = {"A": (a_start, a_end), "B": (b_start, b_end), "C": (c_start, c_end)}

        video_ids = {}
        start_snap_ids = {}
        end_snap_ids = {}
        window_ids = {}

        for v in variants:
            pos = v["position"]
            vid = v["id"]
            pid = scope.project_id
            metrics = _FIXTURE_METRICS[pos]
            (w_start, w_end) = window_times[pos]

            # Create Video
            video_res = await self._db.execute(
                text(
                    "INSERT INTO videos "
                    "(project_id, variant_id, attempt_number, is_current, status, "
                    "tracking_started_at, tracking_window_ends_at, published_at, "
                    "tiktok_video_id, normalized_tiktok_url) "
                    "VALUES (:pid, :vid, 1, true, 'completed', "
                    ":ts, :te, :pub, :tvid, :url) "
                    "RETURNING id"
                ),
                {
                    "pid": pid, "vid": vid,
                    "ts": w_start, "te": w_end, "pub": w_start,
                    "tvid": f"dev-{pos.lower()}-{str(experiment_id)[:8]}",
                    "url": f"https://www.tiktok.com/@dev/video/dev{pos.lower()}{str(experiment_id)[:8]}",
                },
            )
            video_id = video_res.scalar()
            video_ids[pos] = video_id

            # Create start VideoMetricSnapshot (at window start — zero views for simplicity)
            start_res = await self._db.execute(
                text(
                    "INSERT INTO video_metric_snapshots "
                    "(project_id, video_id, collected_at, views, likes, comments) "
                    "VALUES (:pid, :viid, :ts, 0, 0, 0) RETURNING id"
                ),
                {"pid": pid, "viid": video_id, "ts": w_start},
            )
            start_snap_ids[pos] = start_res.scalar()

            # Create end VideoMetricSnapshot (final values)
            end_res = await self._db.execute(
                text(
                    "INSERT INTO video_metric_snapshots "
                    "(project_id, video_id, collected_at, views, likes, comments) "
                    "VALUES (:pid, :viid, :te, :views, :likes, :comments) RETURNING id"
                ),
                {
                    "pid": pid, "viid": video_id, "te": w_end,
                    "views": metrics["views"],
                    "likes": metrics["likes"],
                    "comments": metrics["comments"],
                },
            )
            end_snap_ids[pos] = end_res.scalar()

            # Create AttributionWindow
            aw_res = await self._db.execute(
                text(
                    "INSERT INTO attribution_windows "
                    "(project_id, experiment_id, variant_id, video_id, "
                    "starts_at, ends_at, status) "
                    "VALUES (:pid, :eid, :vid, :viid, :ts, :te, 'closed') "
                    "RETURNING id"
                ),
                {
                    "pid": pid, "eid": experiment_id, "vid": vid, "viid": video_id,
                    "ts": w_start, "te": w_end,
                },
            )
            window_ids[pos] = aw_res.scalar()

        # Create ExperimentEvidenceSnapshot as pending; finalize after items are inserted
        snap_res = await self._db.execute(
            text(
                "INSERT INTO experiment_evidence_snapshots "
                "(project_id, experiment_id, version, status, attribution_method, "
                "generated_at) "
                "VALUES (:pid, :eid, 1, 'pending', 'isolated_window', :now) "
                "RETURNING id"
            ),
            {"pid": scope.project_id, "eid": experiment_id, "now": now},
        )
        snapshot_id = snap_res.scalar()

        # Create ExperimentEvidenceItems
        for v in variants:
            pos = v["position"]
            metrics = _FIXTURE_METRICS[pos]
            clicks_per_1k = round(metrics["unique_clicks"] / metrics["views"] * 1000, 2)
            await self._db.execute(
                text(
                    "INSERT INTO experiment_evidence_items "
                    "(project_id, evidence_snapshot_id, variant_id, video_id, "
                    "start_metric_snapshot_id, end_metric_snapshot_id, "
                    "views_delta, likes_delta, comments_delta, "
                    "attributed_unique_clicks, unique_clicks_per_1k, "
                    "attribution_window_id, attribution_conditions) "
                    "VALUES (:pid, :sid, :vid, :viid, :sms, :ems, "
                    ":vd, :ld, :cd, :uc, :ck, :awid, :ac)"
                ),
                {
                    "pid": scope.project_id,
                    "sid": snapshot_id,
                    "vid": v["id"],
                    "viid": video_ids[pos],
                    "sms": start_snap_ids[pos],
                    "ems": end_snap_ids[pos],
                    "vd": metrics["views"],
                    "ld": metrics["likes"],
                    "cd": metrics["comments"],
                    "uc": metrics["unique_clicks"],
                    "ck": clicks_per_1k,
                    "awid": window_ids[pos],
                    "ac": json.dumps({"schemaVersion": 1}),
                },
            )

        # Finalize the snapshot now that all items are inserted
        await self._db.execute(
            text(
                "UPDATE experiment_evidence_snapshots "
                "SET status = 'finalized', finalized_at = :now "
                "WHERE id = :sid AND project_id = :pid"
            ),
            {"now": now, "sid": snapshot_id, "pid": scope.project_id},
        )

        # Update experiment status to 'analyzing'
        await self._db.execute(
            text(
                "UPDATE experiments SET status = 'analyzing', "
                "tracking_completed_at = :now, analysis_started_at = :now "
                "WHERE id = :eid AND project_id = :pid"
            ),
            {"now": now, "eid": experiment_id, "pid": scope.project_id},
        )

        await self._db.commit()
        return {"snapshot_id": str(snapshot_id), "experiment_id": str(experiment_id)}
