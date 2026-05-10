"""Policy entry point: `check(user, activity, target, context)`.

Pure function — no DB, cache, or service calls. Audit logging is the
caller's job; the policy returns a `Decision` and stays I/O-free.
"""

from __future__ import annotations

from typing import cast

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.db.models import Model

from .registry import get_rule
from .types import (
    DENIAL_PRIORITY,
    Activity,
    Allow,
    Decision,
    DenialCode,
    Deny,
    PolicyContext,
    PolicyUser,
)

_PRIORITY_INDEX: dict[DenialCode, int] = {
    code: i for i, code in enumerate(DENIAL_PRIORITY)
}
_PRIORITY_FALLBACK = len(DENIAL_PRIORITY)


def check(
    user: PolicyUser,
    activity: Activity,
    target: Model | None = None,
    context: PolicyContext | None = None,
) -> Decision:
    rule = get_rule(activity)
    if rule is None:
        # Missing rule is engine misconfiguration, not a permission
        # decision — masquerading as a 403 would mislead operators.
        # The registry-completeness test keeps this branch dead.
        raise LookupError(f"No rule registered for {activity!r}")

    denials: list[Deny] = []
    for predicate in rule.predicates:
        decision = predicate(user, target, context)
        if isinstance(decision, Deny):
            denials.append(decision)

    if not denials:
        return Allow()

    return min(
        denials,
        key=lambda d: _PRIORITY_INDEX.get(d.code, _PRIORITY_FALLBACK),
    )


def policy_user(user: AbstractBaseUser | AnonymousUser) -> PolicyUser:
    """Boundary cast: Django's `request.user` → `PolicyUser`.

    `request.user` is typed `AbstractBaseUser | AnonymousUser`. The
    abstract parent doesn't structurally satisfy `PolicyUser` (it's
    missing `email_verified` / `is_staff` / `is_superuser` as
    `@property`), so mypy can't narrow it. Concrete `User` instances
    and `AnonymousUser` both satisfy `PolicyUser` at runtime; this
    helper centralizes the unavoidable cast at one site.
    """
    return cast(PolicyUser, user)
