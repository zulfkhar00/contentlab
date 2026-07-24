"""
Variant + Video service — Sprint 5.
All operations require ProjectScope.
Fake validator used for URL validation in development.
"""
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError, ProjectNotFound
from app.domain.scope import ProjectScope
from app.infrastructure.video_validator import FakeVideoValidator
from app.repositories.variant_repo import VariantRepository
from app.repositories.video_repo import VideoRepository
from app.repositories.project_repo import ProjectRepository

_VALIDATOR = FakeVideoValidator()

_BRIEF_FIELDS = frozenset({
    "hook", "hook_delivery_note", "context", "on_screen_text",
    "script_sections", "recording_guidance",
})


class VariantService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = VariantRepository(db)
        self._video_repo = VideoRepository(db)

    # ── Read ─────────────────────────────────────────────────────────────────

    async def get(self, scope: ProjectScope, variant_id: UUID) -> dict:
        v = await self._repo.get(scope, variant_id)
        if not v:
            raise ProjectNotFound(f"Variant {variant_id} not found")
        v["current_video"] = await self._repo.get_current_video(scope, variant_id)
        if v["current_video"]:
            v["observation"] = await self._video_repo.get_observation(scope, v["current_video"]["id"])
        else:
            v["observation"] = None
        return v

    # ── Brief edits ──────────────────────────────────────────────────────────

    async def update_brief(self, scope: ProjectScope, variant_id: UUID, data: dict) -> dict:
        v = await self._repo.get(scope, variant_id)
        if not v:
            raise ProjectNotFound(f"Variant {variant_id} not found")
        if v["status"] in ("queued",):
            raise DomainError("Cannot edit brief while variant is queued.")
        allowed = {k: val for k, val in data.items() if k in _BRIEF_FIELDS and val is not None}
        if not allowed:
            return v
        updated = await self._repo.update(scope, variant_id, allowed)
        return updated

    async def revise_brief(
        self, scope: ProjectScope, variant_id: UUID, instruction: str,
        provider,
    ) -> dict:
        """Call provider.revise_variant_brief and return proposed edit (not persisted)."""
        v = await self._repo.get(scope, variant_id)
        if not v:
            raise ProjectNotFound(f"Variant {variant_id} not found")
        project_repo = ProjectRepository(self._db)
        project = await project_repo.get_by_scope(scope) or {}
        revision, input_payload, input_hash = await provider.revise_variant_brief(
            variant=v, instruction=instruction, project=project, facts=[]
        )
        # Insert ai_run but do NOT persist revision to variant
        zero = json.dumps({"inputTokens": 0, "outputTokens": 0})
        await self._db.execute(
            text(
                "INSERT INTO ai_runs "
                "(project_id, entity_type, entity_id, operation, model, prompt_version, "
                "context_version, input_hash, input_payload, output_payload, "
                "validation_result, token_usage, cost_usd, latency_ms, status) "
                "VALUES (:pid, 'Variant', :vid, 'reviseBrief', :model, :pv, "
                ":cv, :ih, :ip, :op, 'valid', :tu, 0, 0, 'success')"
            ),
            {
                "pid": scope.project_id, "vid": variant_id,
                "model": provider.MODEL, "pv": provider.PROMPT_VERSION,
                "cv": project.get("context_version", 1), "ih": input_hash,
                "ip": json.dumps(input_payload), "op": json.dumps(revision),
                "tu": zero,
            },
        )
        await self._db.commit()
        return {"proposed_revision": revision, "variant_id": str(variant_id)}

    # ── Status transitions ────────────────────────────────────────────────────

    async def approve_for_recording(self, scope: ProjectScope, variant_id: UUID) -> dict:
        v = await self._repo.get(scope, variant_id)
        if not v:
            raise ProjectNotFound(f"Variant {variant_id} not found")
        if v["status"] != "ready_to_review":
            raise DomainError(
                f"Variant must be ready_to_review to approve; current: {v['status']}"
            )
        now = datetime.now(timezone.utc)
        return await self._repo.update(
            scope, variant_id,
            {"status": "approved_for_recording", "approved_for_recording_at": now},
        )

    async def confirm_recorded(self, scope: ProjectScope, variant_id: UUID) -> dict:
        v = await self._repo.get(scope, variant_id)
        if not v:
            raise ProjectNotFound(f"Variant {variant_id} not found")
        if v["status"] != "approved_for_recording":
            raise DomainError(
                f"Variant must be approved_for_recording to confirm; current: {v['status']}"
            )
        now = datetime.now(timezone.utc)
        return await self._repo.update(
            scope, variant_id,
            {"status": "recorded", "recorded_at": now},
        )

    # ── Video ─────────────────────────────────────────────────────────────────

    async def create_video(self, scope: ProjectScope, variant_id: UUID) -> dict:
        v = await self._repo.get(scope, variant_id)
        if not v:
            raise ProjectNotFound(f"Variant {variant_id} not found")
        if v["status"] != "recorded":
            raise DomainError(
                f"Variant must be recorded before creating a video; current: {v['status']}"
            )
        attempt = await self._repo.get_next_video_attempt(scope, variant_id)
        return await self._video_repo.create(scope, variant_id, attempt)

    async def submit_url(
        self, scope: ProjectScope, video_id: UUID, url: str,
        confirmed_checks: dict,
    ) -> dict:
        """
        Validate URL → set video tracking → create AttributionWindow →
        transition experiment status.
        """
        video = await self._video_repo.get(scope, video_id)
        if not video:
            raise ProjectNotFound(f"Video {video_id} not found")
        if video["status"] != "needs_url":
            raise DomainError(f"Video is already in status: {video['status']}")

        # Get project for handle check
        project_repo = ProjectRepository(self._db)
        project = await project_repo.get_by_scope(scope) or {}
        expected_handle = project.get("tiktok_handle", "")

        result = _VALIDATOR.validate(url, expected_handle)
        if not result.valid:
            raise DomainError(f"[{result.error_code}] {result.error_detail}")

        now = datetime.now(timezone.utc)
        # Get tracking window hours from experiment
        exp_result = await self._db.execute(
            text("SELECT e.tracking_window_hours FROM experiments e JOIN variants v ON v.experiment_id = e.id WHERE v.id = :vid AND v.project_id = :pid"),
            {"vid": video["variant_id"], "pid": scope.project_id},
        )
        exp_row = exp_result.first()
        window_hours = int(exp_row[0]) if exp_row else 72
        window_ends = now + timedelta(hours=window_hours)

        user_confirmed_at = now if confirmed_checks.get("video_live") else None

        updated_video = await self._video_repo.update(
            scope, video_id,
            {
                "status": "tracking",
                "submitted_url": url,
                "normalized_tiktok_url": result.normalized_tiktok_url,
                "tiktok_video_id": result.tiktok_video_id,
                "validated_at": now,
                "tracking_started_at": now,
                "tracking_window_ends_at": window_ends,
                "user_confirmed_published_at": user_confirmed_at,
            },
        )

        # Create AttributionWindow
        await self._db.execute(
            text(
                "INSERT INTO attribution_windows "
                "(project_id, experiment_id, variant_id, video_id, starts_at, ends_at, status) "
                "SELECT :pid, v.experiment_id, v.id, :viid, :ts, :te, 'active' "
                "FROM variants v WHERE v.id = :vaid AND v.project_id = :pid"
            ),
            {
                "pid": scope.project_id, "viid": video_id,
                "vaid": video["variant_id"],
                "ts": now, "te": window_ends,
            },
        )

        # Transition experiment to tracking
        await self._db.execute(
            text(
                "UPDATE experiments SET status = 'tracking' "
                "WHERE id = (SELECT experiment_id FROM variants WHERE id = :vaid AND project_id = :pid) "
                "AND project_id = :pid "
                "AND status IN ('ready', 'in_progress')"
            ),
            {"vaid": video["variant_id"], "pid": scope.project_id},
        )
        await self._db.commit()
        return updated_video
