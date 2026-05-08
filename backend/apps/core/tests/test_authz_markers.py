"""Unit tests for the authz marker decorators.

The route-inventory test exercises `requires` and `gated_inline`
indirectly via every classified route, but `public_mutation`'s
validation logic only has the success path covered there. These tests
also lock the "marker returns the original callable" invariant so any
future change to that contract fails loudly.
"""

from __future__ import annotations

import pytest

from apps.core.authz.markers import (
    ACTIVITY_ATTR,
    GATED_INLINE_ATTR,
    PUBLIC_ATTR,
    gated_inline,
    public_mutation,
    requires,
)
from apps.core.authz.types import Activity


class TestRequires:
    def test_stamps_activity_attribute(self) -> None:
        @requires(Activity.CATALOG_EDIT)
        def view() -> None: ...

        assert getattr(view, ACTIVITY_ATTR) is Activity.CATALOG_EDIT

    def test_returns_original_callable_unchanged(self) -> None:
        # The marker is a stamp, not a wrapper — the wrapped callable
        # is the *same object* the caller passed in. Locking the
        # invariant here means any future change to it fails loudly.
        def view() -> None: ...

        assert requires(Activity.CATALOG_EDIT)(view) is view


class TestGatedInline:
    def test_stamps_activity_attribute(self) -> None:
        @gated_inline(Activity.CLAIM_REVERT)
        def view() -> None: ...

        assert getattr(view, GATED_INLINE_ATTR) is Activity.CLAIM_REVERT

    def test_returns_original_callable_unchanged(self) -> None:
        def view() -> None: ...

        assert gated_inline(Activity.CLAIM_REVERT)(view) is view


class TestPublicMutation:
    def test_stamps_reason_attribute(self) -> None:
        @public_mutation("session teardown")
        def view() -> None: ...

        assert getattr(view, PUBLIC_ATTR) == "session teardown"

    def test_returns_original_callable_unchanged(self) -> None:
        def view() -> None: ...

        assert public_mutation("ok")(view) is view

    def test_empty_string_raises_at_decoration_time(self) -> None:
        with pytest.raises(ValueError, match="non-empty reason"):
            public_mutation("")

    def test_whitespace_only_raises_at_decoration_time(self) -> None:
        # Catches the "developer typed a space to silence the test" case.
        with pytest.raises(ValueError, match="non-empty reason"):
            public_mutation("   ")

    def test_non_string_raises_at_decoration_time(self) -> None:
        with pytest.raises(ValueError, match="non-empty reason"):
            public_mutation(None)  # type: ignore[arg-type]
