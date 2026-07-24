from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ProjectNotFound
from app.domain.scope import ProjectScope
from app.repositories.experiment_repo import ExperimentRepository


class ExperimentService:
    def __init__(self, db: AsyncSession) -> None:
        self._repo = ExperimentRepository(db)

    async def get_active(self, scope: ProjectScope) -> dict:
        exp = await self._repo.get_active(scope)
        if not exp:
            raise ProjectNotFound("No active experiment found")
        return exp

    async def get(self, scope: ProjectScope, experiment_id: UUID) -> dict:
        exp = await self._repo.get_by_id(scope, experiment_id)
        if not exp:
            raise ProjectNotFound(f"Experiment {experiment_id} not found")
        return exp
