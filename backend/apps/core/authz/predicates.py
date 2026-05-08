"""Built-in predicates and the `Predicate` callable type.

A predicate is a pure function `(user, target, context) -> Decision`.
Predicates return `Decision` rather than `bool` so each names its own
denial code; the evaluator combines those codes via priority order
when multiple predicates fail.
"""

from __future__ import annotations

from collections.abc import Callable

from django.db.models import Model

from .types import Allow, Decision, DenialCode, Deny, PolicyContext, PolicyUser

# Per-app rules narrow `target` further via Protocol typing on the
# predicate parameter; the registry-facing alias stays generic because
# the registry holds rules for many target types.
# Provisional. Phase 3's target-aware predicates (e.g. is_claim_author with
# target: ClaimPolicyView) won't satisfy this signature — Protocol isn't a
# Model subclass, and Callable params are contravariant. Proposal: replace with a
# contravariant Predicate Protocol when the first target-aware rule lands.
Predicate = Callable[[PolicyUser, Model | None, PolicyContext | None], Decision]


def is_authenticated(
    user: PolicyUser, target: Model | None, context: PolicyContext | None
) -> Decision:
    if not user.is_authenticated:
        return Deny(DenialCode.AUTH_REQUIRED)
    return Allow()


def is_active(
    user: PolicyUser, target: Model | None, context: PolicyContext | None
) -> Decision:
    if not user.is_active:
        return Deny(DenialCode.ACCOUNT_DEACTIVATED)
    return Allow()
