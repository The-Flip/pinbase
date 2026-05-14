"""Username format policy.

Kept separate from `models.py` so callers can import the validator without
dragging the User model (and its migration state) along.

Policy (from [docs/plans/auth/Usernames.md](../../../docs/plans/auth/Usernames.md)):

- lowercase ASCII letters and digits, single hyphens between segments
- 3-20 characters
- no leading/trailing hyphen, no consecutive hyphens
"""

from __future__ import annotations

import re
from typing import Literal

from django.core.exceptions import ValidationError

USERNAME_MIN_LEN = 3
USERNAME_MAX_LEN = 20

# Matches the policy: lowercase alphanumeric segments joined by single hyphens.
# Excludes leading/trailing hyphens and consecutive hyphens by construction.
_USERNAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Charset for the granular "bad_charset" diagnostic, distinct from the
# hyphen-shape diagnostics.
_ALLOWED_CHARS_RE = re.compile(r"^[a-z0-9-]+$")

UsernameRejectReason = Literal[
    "too_short",
    "too_long",
    "bad_charset",
    "leading_or_trailing_hyphen",
    "consecutive_hyphens",
    "reserved",
    "taken",
]
"""Reasons a candidate username is rejected.

The format validator raises the first five. `is_reserved()` produces
`reserved`. The DB uniqueness check (or the IntegrityError catch on submit)
produces `taken`. Drives the UI's inline status copy — UI does i18n/wording.
"""

SignupErrorCode = Literal["pending_missing", "pending_expired"]
"""Session-state errors — distinct from username-content errors.

The user has no recourse here except restarting sign-in.
"""


def validate_username_format(value: str) -> None:
    """Raise ValidationError carrying a `UsernameRejectReason` code if invalid.

    The `code` attribute on the ValidationError is the machine-readable
    reason; the `message` is a fallback human string for paths that don't
    map codes themselves (e.g. Django admin's default error rendering).
    """
    if len(value) < USERNAME_MIN_LEN:
        raise ValidationError(
            "Username must be at least 3 characters.", code="too_short"
        )
    if len(value) > USERNAME_MAX_LEN:
        raise ValidationError(
            "Username must be at most 20 characters.", code="too_long"
        )
    if not _ALLOWED_CHARS_RE.fullmatch(value):
        raise ValidationError(
            "Username may only contain lowercase letters, digits, and hyphens.",
            code="bad_charset",
        )
    if value.startswith("-") or value.endswith("-"):
        raise ValidationError(
            "Username may not start or end with a hyphen.",
            code="leading_or_trailing_hyphen",
        )
    if "--" in value:
        raise ValidationError(
            "Username may not contain consecutive hyphens.",
            code="consecutive_hyphens",
        )
    # Belt-and-braces: the four checks above cover everything the regex
    # rejects, but assert via the regex to keep this in lockstep with
    # `_USERNAME_RE` if the policy ever shifts.
    assert _USERNAME_RE.fullmatch(value), value
