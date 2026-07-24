class DomainError(Exception):
    """Base for all domain-level errors."""

class ProjectNotFound(DomainError):
    pass

class ProjectAlreadyExists(DomainError):
    pass

class Unauthorized(DomainError):
    pass
