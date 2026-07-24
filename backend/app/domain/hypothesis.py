"""
Hypothesis domain rules: valid status transitions and field constraints.
"""
from app.domain.errors import DomainError

_VALID_STATUSES = frozenset({"generated", "draft", "approved", "testing", "tested", "rejected"})

# Transitions allowed by explicit user actions in the API layer
_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "generated": frozenset({"draft", "rejected"}),
    "draft":     frozenset({"approved", "rejected"}),
    "approved":  frozenset({"rejected"}),
    "rejected":  frozenset({"draft"}),
    # testing / tested are set by the experiment lifecycle, not the API
    "testing":   frozenset(),
    "tested":    frozenset(),
}

# Statuses from which approve-and-generate-experiment is permitted
APPROVABLE_STATUSES = frozenset({"generated", "draft"})


def assert_can_approve(status: str) -> None:
    if status not in APPROVABLE_STATUSES:
        raise DomainError(
            f"Cannot approve hypothesis with status '{status}'. "
            f"Allowed: {sorted(APPROVABLE_STATUSES)}"
        )


def assert_can_reject(status: str) -> None:
    if status not in _ALLOWED_TRANSITIONS or "rejected" not in _ALLOWED_TRANSITIONS[status]:
        raise DomainError(
            f"Cannot reject hypothesis with status '{status}'."
        )


def assert_can_patch(status: str) -> None:
    """Material edits allowed only before approval."""
    if status in ("testing", "tested"):
        raise DomainError(
            f"Hypothesis is in status '{status}' and cannot be edited."
        )
