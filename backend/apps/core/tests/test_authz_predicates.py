"""Unit tests for the built-in predicates.

Confirms `is_authenticated` and `is_active` produce the right Decision
for both authenticated `User` and `AnonymousUser`, and that both classes
satisfy the attribute surface `PolicyUser` declares.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.core.authz.predicates import is_active, is_authenticated
from apps.core.authz.types import Allow, DenialCode, Deny

# PolicyUser uses @property declarations, so its attributes don't appear
# in __annotations__; hardcode them here for the protocol-fit checks.
_POLICY_USER_ATTRS = ("is_authenticated", "is_active")


def test_anonymous_user_denied_by_is_authenticated():
    decision = is_authenticated(AnonymousUser(), None, None)
    assert isinstance(decision, Deny)
    assert decision.code is DenialCode.AUTH_REQUIRED


def test_anonymous_user_denied_by_is_active():
    """AnonymousUser.is_active is False, so is_active denies with ACCOUNT_DEACTIVATED.

    The "deactivated" framing is wrong for an anonymous user, but
    priority ordering in `check()` will surface AUTH_REQUIRED instead —
    see test_authz_evaluator. This test only locks the predicate's
    contract.
    """
    decision = is_active(AnonymousUser(), None, None)
    assert isinstance(decision, Deny)
    assert decision.code is DenialCode.ACCOUNT_DEACTIVATED


@pytest.mark.django_db
def test_authenticated_active_user_passes_both():
    user = get_user_model().objects.create_user(email="alice@example.com", password="x")
    assert isinstance(is_authenticated(user, None, None), Allow)
    assert isinstance(is_active(user, None, None), Allow)


@pytest.mark.django_db
def test_inactive_user_denied_by_is_active():
    user = get_user_model().objects.create_user(
        email="dormant@example.com", password="x", is_active=False
    )
    decision = is_active(user, None, None)
    assert isinstance(decision, Deny)
    assert decision.code is DenialCode.ACCOUNT_DEACTIVATED


def test_anonymous_user_satisfies_policy_user_protocol():
    user = AnonymousUser()
    for attr in _POLICY_USER_ATTRS:
        assert hasattr(user, attr), f"AnonymousUser missing {attr!r}"


@pytest.mark.django_db
def test_real_user_satisfies_policy_user_protocol():
    user = get_user_model().objects.create_user(email="bob@example.com", password="x")
    for attr in _POLICY_USER_ATTRS:
        assert hasattr(user, attr), f"User missing {attr!r}"
