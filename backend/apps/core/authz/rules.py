"""Rules owned by the core app itself.

Per-app rule files normally live at `apps/<app>/authz.py`. Core uses
`apps/core/authz/` as the engine package, so its rule registrations
live in this submodule instead and are imported by `core/apps.py:
ready()`.

Today this only covers user-state activities the rate limiter and
similar cross-cutting consumers ask about — activities that don't
correspond to a single domain app's models.

User-state activities registered here are exempt from the
"every activity requires email_verified" pin in
``test_authz_registry_complete.py``; new ones must be added to the
``_USER_STATE_ACTIVITIES`` set there.
"""

from __future__ import annotations

from .predicates import is_staff
from .registry import register
from .types import Activity

register(Activity.RATE_LIMIT_EXEMPT, is_staff)
