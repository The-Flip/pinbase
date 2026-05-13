"""Build display labels for relationship-claim values in edit history.

A relationship claim's stored value is a dict like
``{"person": 13, "role": 9, "exists": true}`` — fine for the data model,
unfriendly for users. This module turns those into strings like
``"Pat Lawlor — Art"`` by resolving FK references via a pre-built label
lookup.

Usage::

    labels = resolve_labels([FieldValue(field_name, value), ...])
    display = build_display_label(field_name, value, labels)

``resolve_labels`` queries one row per FK target model (no per-row N+1).
Bare scalars (direct-field claims like ``technology_generation``) are not
formatted here — they render as-is. ``None`` is returned for any value the
formatter doesn't recognise (non-dict, unknown namespace, no registered
formatter).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Iterable
from typing import NamedTuple

from django.db.models import Model

from .validation import (
    RelationshipSchema,
    ValueKeySpec,
    get_relationship_schema,
)

# A relationship claim's value payload: a dict with ``exists: bool`` plus
# the namespace-specific keys declared in :class:`ValueKeySpec`. Per-key
# types vary by namespace (int pks, optional counts, str literals), so the
# value type is ``object`` and formatters narrow with ``isinstance`` at the
# few sites that read non-pk fields. Schema validation enforces shape at
# the data-layer boundary; this alias just names the concept.
RelationshipClaimValue = dict[str, object]


class FieldValue(NamedTuple):
    """A claim value paired with the field name that interprets it.

    The field name picks which relationship schema (and therefore which
    formatter) applies; the value is the raw payload. Callers feed
    :func:`resolve_labels` with these so FK pks can be collected for
    batched resolution before per-row formatting.
    """

    field_name: str
    value: object


class FkRef(NamedTuple):
    """A reference to a specific row in an FK target model.

    ``model`` is the target class (e.g. ``Person``); ``pk`` identifies the
    row. Used as the lookup key in :class:`LabelLookup` so the keying is
    a single named concept rather than an opaque ``(model, pk)`` tuple.
    """

    model: type[Model]
    pk: int


class LabelLookup:
    """Display labels resolved from :class:`FkRef`\\ s.

    Built once per response by :func:`resolve_labels`; consulted by the
    per-namespace formatters when they need to turn a pk into a name.
    """

    __slots__ = ("_labels",)

    def __init__(self) -> None:
        self._labels: dict[FkRef, str] = {}

    def add(self, ref: FkRef, label: str) -> None:
        self._labels[ref] = label

    def get(self, ref: FkRef) -> str | None:
        return self._labels.get(ref)


# A formatter receives the value dict, its registered schema, and the
# pre-built label lookup. Returning ``None`` signals the value isn't
# formatable (callers fall back to raw rendering).
ValueFormatter = Callable[
    [RelationshipClaimValue, RelationshipSchema, LabelLookup], str | None
]


def value_formatter(fn: ValueFormatter) -> ValueFormatter:
    """No-op decorator that pins a function to the :data:`ValueFormatter` shape.

    Apply to each formatter so signature drift is caught at the function
    definition rather than at the ``_FORMATTERS`` registry assignment.
    Returns the input unchanged — no runtime overhead.
    """
    return fn


def _spec(schema: RelationshipSchema, name: str) -> ValueKeySpec:
    for s in schema.value_keys:
        if s.name == name:
            return s
    raise KeyError(f"value key {name!r} not found in namespace {schema.namespace!r}")


def _fk_label(
    value: RelationshipClaimValue,
    schema: RelationshipSchema,
    key_name: str,
    labels: LabelLookup,
) -> str:
    spec = _spec(schema, key_name)
    assert spec.fk_target is not None, (
        f"{schema.namespace!r}.{key_name!r} is not declared as an FK"
    )
    # Display assumes pk lookups. Validation honours ``lookup_field``, so a
    # future ``FkTarget(Model, "slug")`` registration would silently miss
    # labels here. Fail loud until that case is actually needed.
    assert spec.fk_target.lookup_field == "pk", (
        f"{schema.namespace!r}.{key_name!r} uses non-pk lookup "
        f"{spec.fk_target.lookup_field!r}; build_display_label only supports pk"
    )
    pk = value.get(key_name)
    if pk is None:
        return "?"
    # ``type(pk) is int`` (not ``isinstance``): ``isinstance(True, int)`` is
    # ``True`` and would let a stray bool slip through as a pk.
    assert type(pk) is int, (
        f"expected int pk for {schema.namespace}.{key_name}, got {type(pk).__name__}"
    )
    label = labels.get(FkRef(spec.fk_target.model, pk))
    # Reference points to a row that no longer exists — fall back to the pk
    # so the row is still identifiable, and prefix `?#` to flag the miss.
    return label if label is not None else f"?#{pk}"


@value_formatter
def _format_credit(
    value: RelationshipClaimValue, schema: RelationshipSchema, labels: LabelLookup
) -> str:
    person = _fk_label(value, schema, "person", labels)
    role = _fk_label(value, schema, "role", labels)
    return f"{person} — {role}"


@value_formatter
def _format_gameplay_feature(
    value: RelationshipClaimValue, schema: RelationshipSchema, labels: LabelLookup
) -> str:
    feat = _fk_label(value, schema, "gameplay_feature", labels)
    count = value.get("count")
    if isinstance(count, int) and count > 1:
        return f"{feat} ×{count}"
    return feat


def _single_fk_formatter(key_name: str) -> ValueFormatter:
    @value_formatter
    def fmt(
        value: RelationshipClaimValue, schema: RelationshipSchema, labels: LabelLookup
    ) -> str:
        return _fk_label(value, schema, key_name, labels)

    return fmt


@value_formatter
def _format_alias(
    value: RelationshipClaimValue, schema: RelationshipSchema, labels: LabelLookup
) -> str:
    # ``alias_value`` is the required identity key; ``alias_display`` is an
    # optional friendlier label that ingest sources may attach. ``.get`` with
    # a ``?`` fallback matches the contract used by ``_fk_label`` so a
    # malformed shape (e.g. ``{"exists": false}``) renders visibly instead
    # of raising mid-response.
    display = value.get("alias_display")
    raw = value.get("alias_value")
    if display:
        return str(display)
    if raw:
        return str(raw)
    return "?"


@value_formatter
def _format_abbreviation(
    value: RelationshipClaimValue, schema: RelationshipSchema, labels: LabelLookup
) -> str:
    raw = value.get("value")
    return str(raw) if raw is not None else "?"


@value_formatter
def _format_media_attachment(
    value: RelationshipClaimValue, schema: RelationshipSchema, labels: LabelLookup
) -> str:
    media = _fk_label(value, schema, "media_asset", labels)
    parts = [media]
    category = value.get("category")
    if category:
        parts.append(f"({category})")
    if value.get("is_primary"):
        parts.append("[primary]")
    return " ".join(parts)


# Per-namespace explicit formatters. Aliases are dispatched dynamically below
# (one namespace per AliasModel subclass, all sharing the alias_value shape).
_FORMATTERS: dict[str, ValueFormatter] = {
    "credit": _format_credit,
    "gameplay_feature": _format_gameplay_feature,
    "theme": _single_fk_formatter("theme"),
    "tag": _single_fk_formatter("tag"),
    "reward_type": _single_fk_formatter("reward_type"),
    "location": _single_fk_formatter("location"),
    "theme_parent": _single_fk_formatter("parent"),
    "gameplay_feature_parent": _single_fk_formatter("parent"),
    "media_attachment": _format_media_attachment,
    "abbreviation": _format_abbreviation,
}


def _formatter_for(schema: RelationshipSchema) -> ValueFormatter | None:
    explicit = _FORMATTERS.get(schema.namespace)
    if explicit is not None:
        return explicit
    # Aliases register one namespace per AliasModel subclass. They all carry
    # an "alias_value" key, which is the discriminator we use here so we
    # don't have to enumerate them.
    if any(s.name == "alias_value" for s in schema.value_keys):
        return _format_alias
    return None


def _collect_refs(items: Iterable[FieldValue]) -> set[FkRef]:
    """Walk :class:`FieldValue`\\ s and gather every FK reference.

    Non-dict values and direct-field claims (unregistered namespaces) are
    skipped — they have no FKs to resolve.
    """
    refs: set[FkRef] = set()
    for field_name, value in items:
        if not isinstance(value, dict):
            continue
        schema = get_relationship_schema(field_name)
        if schema is None:
            continue
        for spec in schema.value_keys:
            if spec.fk_target is None:
                continue
            # Mirror the assertion in ``_fk_label``: pk-only for now. See
            # the comment there for context.
            assert spec.fk_target.lookup_field == "pk", (
                f"{field_name!r}.{spec.name!r} uses non-pk lookup "
                f"{spec.fk_target.lookup_field!r}; build_display_label only supports pk"
            )
            pk = value.get(spec.name)
            if pk is None:
                continue
            # See ``_fk_label`` for why this isn't ``isinstance``.
            assert type(pk) is int, (
                f"expected int pk for {field_name}.{spec.name}, got {type(pk).__name__}"
            )
            refs.add(FkRef(spec.fk_target.model, pk))
    return refs


def resolve_labels(items: Iterable[FieldValue]) -> LabelLookup:
    """Build a :class:`LabelLookup` for all relationship claims in ``items``.

    One query per FK target model. Resolved labels are ``str(instance)``,
    so each FK target model is expected to define a meaningful ``__str__``
    — registering a relationship whose target falls back to Django's
    default ``"Foo object (13)"`` would leak through to edit history.
    Missing rows (referent deleted) simply don't appear in the result;
    callers render them as ``?#<pk>``.
    """
    pks_by_model: dict[type[Model], set[int]] = defaultdict(set)
    for ref in _collect_refs(items):
        pks_by_model[ref.model].add(ref.pk)

    lookup = LabelLookup()
    for model, pks in pks_by_model.items():
        for inst in model._default_manager.filter(pk__in=pks):
            lookup.add(FkRef(model, inst.pk), str(inst))
    return lookup


def build_display_label(
    field_name: str, value: object, labels: LabelLookup
) -> str | None:
    """Return a friendly display string for a relationship-claim value.

    Returns ``None`` when ``value`` isn't a formatable relationship-claim
    dict — direct-field scalars, unknown namespaces, and namespaces without
    a registered formatter all fall through.
    """
    if not isinstance(value, dict):
        return None
    schema = get_relationship_schema(field_name)
    if schema is None:
        return None
    formatter = _formatter_for(schema)
    if formatter is None:
        return None
    return formatter(value, schema, labels)
