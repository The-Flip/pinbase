"""Shared Django field classes for ``apps.core``.

Lives alongside ``mixins``, ``constraints``, etc. — mirrors Django's own
``django.db.models.fields`` layout.
"""

from __future__ import annotations

from typing import Any

from django.db import models
from django.db.models.constraints import CheckConstraint
from django.forms import Textarea

# The ``length`` transform that makes ``Q(field__length__lte=N)`` resolve
# is registered in :meth:`apps.core.apps.CoreConfig.ready` — Django doesn't
# register it by default, and doing it here would be a module-import side
# effect on Django's global lookup registry.

# Postgres default identifier length. Constraint names longer than this
# are silently truncated by Postgres, which breaks idempotent migrations.
_PG_IDENTIFIER_MAX = 63


def _contribute_max_length_check(
    field: models.Field[Any, Any], cls: type[models.Model], name: str
) -> None:
    """Append a ``char_length(field) <= max_length`` CHECK to ``cls._meta.constraints``.

    Used by :class:`BoundedTextField` and :class:`MarkdownField` to
    auto-attach a length CHECK without each model having to declare one.

    ``__length`` compiles to Postgres ``char_length()`` — characters, not
    bytes — so emoji and combining marks count as one each.
    """
    max_length = field.max_length
    if max_length is None:  # pragma: no cover - guarded at field __init__
        raise ValueError(f"{type(field).__name__} requires max_length")

    constraint_name = f"{cls._meta.app_label}_{cls._meta.model_name}_{name}_max_length"
    # Hard failure (not assert): Python -O strips asserts, which would
    # silently let an over-long name through to Postgres where it would
    # be truncated and break idempotent migrations.
    if len(constraint_name) > _PG_IDENTIFIER_MAX:
        raise ValueError(
            f"Constraint name {constraint_name!r} is {len(constraint_name)} chars; "
            f"Postgres truncates beyond {_PG_IDENTIFIER_MAX}."
        )

    # The ``length`` transform compiles to Postgres ``char_length()`` —
    # characters, not bytes — so emoji and combining marks count as one.
    constraint = CheckConstraint(
        condition=models.Q(**{f"{name}__length__lte": max_length}),
        name=constraint_name,
    )
    cls._meta.constraints = [*cls._meta.constraints, constraint]


class BoundedTextField(models.TextField[str, str]):
    """A ``TextField`` that auto-contributes a length CHECK constraint.

    Use for prose fields where the cap is a sanity bound, not part of the
    data's identity (where ``CharField`` would be more idiomatic). The
    field stores as ``TEXT`` in Postgres; the cap is enforced by a
    generated ``CHECK (char_length(field) <= max_length)`` constraint
    named ``{app}_{model}_{field}_max_length``.

    ``max_length`` is required. ``__length`` compiles to Postgres
    ``char_length()`` so the cap counts characters, not bytes.
    """

    def __init__(self, *args: Any, max_length: int, **kwargs: Any) -> None:  # noqa: ANN401
        kwargs["max_length"] = max_length
        super().__init__(*args, **kwargs)

    # Django's migration protocol; see Field.deconstruct.
    def deconstruct(self) -> Any:  # noqa: ANN401
        name, _path, args, kwargs = super().deconstruct()
        return name, "django.db.models.TextField", args, kwargs

    def contribute_to_class(
        self,
        cls: type[models.Model],
        name: str,
        private_only: bool = False,
    ) -> None:
        super().contribute_to_class(cls, name, private_only=private_only)
        _contribute_max_length_check(self, cls, name)

    def formfield(self, **kwargs: Any) -> Any:  # type: ignore[override]  # noqa: ANN401
        # Django's TextField.formfield() does not propagate max_length to
        # the form field — without this override, admin form validation
        # would skip the length check and let an over-cap value through
        # to the DB, where it would surface as IntegrityError instead of
        # ValidationError. Also attach a browser-side maxlength hint.
        defaults: dict[str, Any] = {
            "max_length": self.max_length,
            "widget": Textarea(attrs={"maxlength": self.max_length}),
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)
