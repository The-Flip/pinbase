"""Marker decorators for the activity-authorization layer.

Phase 1 of the Authz rollout (see docs/plans/auth/Authz.md). The three
decorators here stamp metadata on the wrapped function and return it
unchanged. They do not enforce anything — that's phase 3.

Phase-3 forward-compat note: when `requires` becomes a real wrapper
in phase 3, the wrapper must use `functools.wraps` and re-stamp the
marker attribute on the new wrapper. Ninja resolves `op.view_func` to
whatever was passed into `router.post(...)`; the inventory walker reads
markers off `op.view_func`, so the marker has to ride on whichever
object Ninja keeps a reference to. Pinning this convention now saves a
debug session in phase 3.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from .types import Activity

F = TypeVar("F", bound=Callable[..., object])

# Attribute names the inventory walker reads. Centralized here so the
# walker, the markers, and any future forward-compat wrapper agree on
# the wire.
ACTIVITY_ATTR = "_authz_activity"
GATED_INLINE_ATTR = "_authz_gated_inline"
PUBLIC_ATTR = "_authz_public"


def requires(activity: Activity) -> Callable[[F], F]:
    """Phase 1: stamp the activity on the view; do not wrap.

    In phase 3 this becomes an enforcing wrapper that calls
    `policy.check` and raises a structured 403 on deny. Call sites do
    not change.
    """

    def decorator(func: F) -> F:
        setattr(func, ACTIVITY_ATTR, activity)
        return func

    return decorator


def gated_inline(activity: Activity) -> Callable[[F], F]:
    """Mark a view that calls `policy.check` inline in its body.

    Stays stamp-only across all phases. The decorator's only job is to
    declare the activity to the inventory test; the inline `check()`
    call in the view body is what enforces.
    """

    def decorator(func: F) -> F:
        setattr(func, GATED_INLINE_ATTR, activity)
        return func

    return decorator


def public_mutation(reason: str) -> Callable[[F], F]:
    """Declare a mutating route as deliberately ungated.

    `reason` must be non-empty after `.strip()` — empty or whitespace
    fails at decoration time so a missing rationale fails at import,
    not silently in CI.
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
