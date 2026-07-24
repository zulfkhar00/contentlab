from dataclasses import dataclass
from uuid import UUID

@dataclass(frozen=True)
class ProjectScope:
    """Mandatory tenant context. Every domain operation requires this."""
    user_id: UUID
    project_id: UUID
