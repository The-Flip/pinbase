"""Process-wide registry mapping each `Activity` to its predicate chain.

Per-app `authz.py` modules call `register(Activity.X, ...)` at startup
via each app's `apps.py: ready()`. Tests that mutate the registry use
the `isolated_registry` fixture so changes don't leak between tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from .predicates import Predicate
from .types import Activity


@dataclass(frozen=True)
class Rule:
    activity: Activity
    predicates: tuple[Predicate, ...]  # AND-conjunction; evaluated in order


_REGISTRY: dict[Activity, Rule] = {}


def register(activity: Activity, *predicates: Predicate) -> None:
    """Register the rule for `activity`.

    Raises on duplicate registration. Raises on empty predicate list —
    a rule with no predicates would auto-allow every caller, which is
    almost certainly a misuse.
    """
    if not predicates:
        raise ValueError(
            f"Rule for {activity!r} requires at least one predicate; "
            f"an empty predicate list would auto-allow every caller."
        )
    if activity in _REGISTRY:
        raise RuntimeError(f"Rule for {activity!r} already registered")
    _REGISTRY[activity] = Rule(activity=activity, predicates=predicates)


def get_rule(activity: Activity) -> Rule | None:
    return _REGISTRY.get(activity)


def iter_rules() -> tuple[Rule, ...]:
    return tuple(_REGISTRY.values())


def _snapshot() -> dict[Activity, Rule]:
    """Internal — used only by the `isolated_registry` test fixture."""
    return dict(_REGISTRY)


def _restore(snapshot: dict[Activity, Rule]) -> None:
    """Internal — used only by the `isolated_registry` test fixture."""
    _REGISTRY.clear()
    _REGISTRY.update(snapshot)
