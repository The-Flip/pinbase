"""Asserts every app that owns activities imported its `authz` module.

Catches the "forgot `from . import authz` in `apps.py: ready()`" bug
class. Without this test, the failure mode is "new Activity enum
member silently has no rule" — which `test_authz_registry_complete`
also catches, but only after the symptom appears. This test catches
the cause: a missing `ready()` import.
"""

from __future__ import annotations

import sys

import pytest

# Apps that own at least one Activity. Update if a new app starts
# registering rules.
_APPS_WITH_AUTHZ = (
    "apps.catalog",
    "apps.provenance",
    "apps.citation",
    "apps.media",
    "apps.kiosk",
)


@pytest.mark.parametrize("app_module", _APPS_WITH_AUTHZ)
def test_app_authz_module_is_imported(app_module: str) -> None:
    authz_module = f"{app_module}.authz"
    assert authz_module in sys.modules, (
        f"{authz_module} not imported. Add `from . import authz` to "
        f"the app's `apps.py: ready()` so registration runs at "
        f"startup."
    )
