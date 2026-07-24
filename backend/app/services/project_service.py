from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ProjectAlreadyExists, ProjectNotFound
from app.domain.project import normalize_tiktok_handle, slugify, slug_with_suffix
from app.domain.scope import ProjectScope
from app.repositories.project_repo import ProjectRepository

_MAX_SLUG_ATTEMPTS = 8


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ProjectRepository(db)

    async def _unique_slug(self, base: str) -> str:
        """Generate a tracking_slug guaranteed unique in the database."""
        candidate = slugify(base)
        for _ in range(_MAX_SLUG_ATTEMPTS):
            if not await self._repo.slug_exists(candidate):
                return candidate
            candidate = slug_with_suffix(slugify(base))
        raise RuntimeError("Could not generate a unique tracking_slug after retries")

    async def create_project(self, user_id: UUID, data: dict) -> dict:
        """
        Create a project for a new user.
        Raises ProjectAlreadyExists if this user already has an active project.
        """
        existing = await self._repo.find_active_by_user(user_id)
        if existing:
            raise ProjectAlreadyExists("User already has an active project")

        product_name = data.get("product_name", "")
        tracking_slug = await self._unique_slug(product_name)
        destination_url = data.get("product_url", "")
        tiktok_handle = normalize_tiktok_handle(data.get("tiktok_handle", ""))

        fields = {
            "product_name": product_name,
            "product_type": data.get("product_type", "SaaS"),
            "product_description": data.get("product_description", ""),
            "product_url": data.get("product_url", ""),
            "target_audience": data.get("target_audience", ""),
            "problem_solved": data.get("problem_solved", ""),
            "why_it_matters": data.get("why_it_matters", ""),
            "current_alternatives": data.get("current_alternatives", ""),
            "desired_action": data.get("desired_action", ""),
            "primary_cta": data.get("primary_cta", ""),
            "tiktok_handle": tiktok_handle,
            "account_public": bool(data.get("account_public", False)),
            "manual_publish": bool(data.get("manual_publish", False)),
            "tracking_slug": tracking_slug,
            "destination_url": destination_url,
        }

        onboarded = data.get("onboarded", False)
        if onboarded:
            from datetime import datetime, timezone
            fields["onboarded_at"] = datetime.now(timezone.utc)

        return await self._repo.create(user_id=user_id, fields=fields)

    async def get_current_project(self, user_id: UUID) -> dict:
        """Return the user's active project. Raises ProjectNotFound if none."""
        project = await self._repo.find_active_by_user(user_id)
        if not project:
            raise ProjectNotFound("No active project for this user")
        return project

    async def update_project(self, scope: ProjectScope, data: dict) -> dict:
        """
        Update allowed project fields.
        context_version is never accepted from the client — the DB trigger handles it.
        tracking_slug is immutable after creation.
        """
        forbidden = {"context_version", "tracking_slug", "user_id", "id"}
        allowed_data = {k: v for k, v in data.items() if k not in forbidden and v is not None}

        if "tiktok_handle" in allowed_data:
            allowed_data["tiktok_handle"] = normalize_tiktok_handle(allowed_data["tiktok_handle"])

        project = await self._repo.update(scope, allowed_data)
        if not project:
            raise ProjectNotFound("Project not found or access denied")
        return project
