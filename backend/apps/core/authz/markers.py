"""Marker decorators that classify mutating routes for the inventory test.

`@requires` is the canonical gate: today it stamps an `Activity` on the
view; once enforcement is wired in, its body will call `policy.check`
and raise on deny. Either way, the marker is what the inventory walker
sees.

`@gated_inline` is for routes that can't fit the single-decorator form
(multiple activities, branch on decision, etc.) and call `policy.check`
inline. The decorator stays stamp-only — it exists so the inventory
test still recognizes the route as gated; the inline call is what
enforces.

`@public_mutation` declares a route as deliberately ungated, with the
reason captured in the inventory output for later audit.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .types import Activity

F = TypeVar("F", bound=Callable[..., object])

# Attribute names the inventory walker reads. Centralized so the walker,
# the markers, and any forward-compat wrapper agree on the wire format.
ACTIVITY_ATTR = "_authz_activity"
GATED_INLINE_ATTR = "_authz_gated_inline"
PUBLIC_ATTR = "_authz_public"


def requires(activity: Activity) -> Callable[[F], F]:
    """Stamp `activity` on the view and return it unchanged.

    When this decorator becomes an enforcing wrapper, the wrapper must
    use `functools.wraps` and re-stamp the marker — Ninja resolves
    `op.view_func` to the callable passed into `router.<verb>(...)`,
    and the inventory walker reads markers off that object.
    """

    def decorator(func: F) -> F:
        setattr(func, ACTIVITY_ATTR, activity)
        return func

    return decorator


def gated_inline(activity: Activity) -> Callable[[F], F]:
    """Mark a view that calls `policy.check` inline in its body.

    Always stamp-only. The decorator's only job is to declare the
    activity to the inventory test; the inline `check()` call in the
    view body is what enforces.
    """

    def decorator(func: F) -> F:
        setattr(func, GATED_INLINE_ATTR, activity)
        return func

    return decorator


def public_mutation(reason: str) -> Callable[[F], F]:
    """Declare a mutating route as deliberately ungated.

    `reason` is required and must be non-empty after `.strip()` — an
    empty or whitespace-only rationale fails at decoration time so a
    missing reason can't slip into the inventory output.
    """
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(
            "@public_mutation requires a non-empty reason string. "
            "The reason is captured in the inventory output so a future "
            "reviewer can audit 'do we still want this public?'."
        )

    def decorator(func: F) -> F:
        setattr(func, PUBLIC_ATTR, reason)
        return func

    return decorator
