"""Enforcement entry point: run ``check()``, log, raise on Deny.

Kept separate from ``markers.py`` (whose job is metadata stamping) and
from ``evaluator.py`` (which is bound by "no I/O in policy" — this
module logs and raises, both of which are I/O-shaped).

Both ``@requires`` and future inline target-aware call sites funnel
through ``enforce()`` so audit logging and the structured 403 happen in
exactly one place.
"""

from __future__ import annotations

import logging

from django.db.models import Model

from .evaluator import check
from .exceptions import PolicyDeniedError
from .types import Activity, Deny, PolicyContext, PolicyUser

log = logging.getLogger("authz")


def enforce(
    user: PolicyUser,
    activity: Activity,
    target: Model | None = None,
    context: PolicyContext | None = None,
) -> None:
    """Evaluate ``activity`` and raise :class:`PolicyDeniedError` on deny.

    Allows are logged at DEBUG (mostly off in prod); denials at INFO
    with ``(user_id, activity, code)`` so audit search is straightforward.
    ``LookupError`` from an unregistered activity propagates as a 500 —
    the registry-completeness test keeps that branch dead.
    """
    decision = check(user, activity, target=target, context=context)
    user_id = getattr(user, "id", None)
    if isinstance(decision, Deny):
        log.info(
            "authz.deny",
            extra={
                "user_id": user_id,
                "activity": activity.value,
                "code": decision.code.value,
            },
        )
        raise PolicyDeniedError(decision)
    log.debug(
        "authz.allow",
        extra={"user_id": user_id, "activity": activity.value},
    )
