"""Asserts every Activity has a registered rule at startup.

This test deliberately does NOT use the `isolated_registry` fixture.
It reads the real, app-`ready()`-populated registry and would pass
trivially against an empty one.

A new `Activity` enum member with no per-app rule registration is what
this catches: the runtime would `LookupError` instead of returning a
permission decision, which is correct but only useful if someone hits
the route. This test makes that misconfiguration a CI failure.
"""

from __future__ import annotations

import pytest

from apps.core.authz.registry import get_rule
from apps.core.authz.types import Activity


@pytest.mark.parametrize("activity", list(Activity))
def test_every_activity_has_a_registered_rule(activity: Activity) -> None:
    rule = get_rule(activity)
    assert rule is not None, (
        f"Activity {activity!r} has no registered rule. Add a "
        f"`register({activity.name}, ...)` call to the relevant app's "
        f"`authz.py`, and ensure that `apps.py: ready()` imports the "
        f"module."
    )
    assert rule.predicates, (
        f"Activity {activity!r} registered with no predicates — that "
        f"would auto-allow every caller. Register at least "
        f"`is_authenticated, is_active`."
    )
