"""Claim-boundary validation: shared rules for all claim write paths.

Provides ``validate_claim_value`` for per-field scalar validation (used by
both the interactive PATCH path and bulk ingest), ``validate_claims_batch``
for batch-mode validation inside ``bulk_assert_claims``, and
``validate_fk_claims_batch`` for batched FK target existence checks.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

logger = logging.getLogger(__name__)


def validate_claim_value(
    field_name: str,
    value: Any,
    model_class: type[models.Model],
) -> Any:
    """Validate and possibly transform a scalar claim value.

    Returns the (possibly transformed) value on success.
    Raises ``django.core.exceptions.ValidationError`` on failure.

    Validates:
    - Mojibake (encoding corruption)
    - Markdown cross-reference links
    - Type coercion via ``field.to_python()``
    - Django field validator chain (range, URL format, etc.)

    Does NOT validate:
    - Unknown/uneditable field names (request-level concern)
    - Null/blank clearability (request-level concern)
    - FK target existence (see ``validate_fk_claims_batch``)
    """
    from apps.core.markdown_links import prepare_markdown_claim_value
    from apps.core.validators import validate_no_mojibake

    field = model_class._meta.get_field(field_name)

    # FK fields are validated in batch by validate_fk_claims_batch.
    if field.is_relation:
        return value

    # Mojibake check — subsumes the old step-0 check in bulk_assert_claims.
    if isinstance(value, str) and validate_no_mojibake in field.validators:
        validate_no_mojibake(value)

    # Markdown cross-ref conversion (authoring → storage format).
    # Returns value unchanged for non-markdown fields.
    value = prepare_markdown_claim_value(field_name, value, model_class)

    # Type coercion + Django field validators.
    if value != "" and field.validators:
        try:
            typed = field.to_python(value)
        except (ValueError, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                raise
            raise ValidationError(f"Invalid value for '{field_name}': {exc}") from exc
        # DecimalField.to_python on a float can produce trailing-zero
        # artifacts (e.g. 8.95 → Decimal('8.950')), which the
        # DecimalValidator rejects. Quantize to the field's decimal_places
        # to match what Django forms do.
        if (
            typed is not None
            and hasattr(field, "decimal_places")
            and field.decimal_places is not None
        ):
            import decimal

            typed = typed.quantize(decimal.Decimal(10) ** -field.decimal_places)
        for validator in field.validators:
            validator(typed)

    return value


def validate_claims_batch(
    pending_claims: list,
) -> tuple[list, int]:
    """Validate claims in batch mode. Returns ``(valid_claims, rejected_count)``.

    Invalid claims are logged and removed from the list.
    Valid scalar claims may have transformed values (e.g. markdown link
    conversion written back to ``claim.value``).

    Claims are classified by ``field_name``:

    1. **Relationship namespace** — in ``RELATIONSHIP_NAMESPACES`` → pass through
    2. **Scalar claim field** — in ``get_claim_fields`` and not a relation → validate
    3. **FK claim field** — in ``get_claim_fields`` and is a relation → batch FK check
    4. **Extra-data** — not in claim fields, but model has ``extra_data`` → pass through
    5. **Unrecognized** — not in claim fields, no ``extra_data`` fallback → reject
    """
    from django.contrib.contenttypes.models import ContentType

    from apps.catalog.claims import RELATIONSHIP_NAMESPACES
    from apps.core.models import get_claim_fields

    rejected: list = []
    fk_claims: list[tuple] = []  # (claim, model_class) pairs

    # Cache model_class, claim_fields, and has_extra_data per content_type_id.
    model_cache: dict[int, type[models.Model]] = {}
    fields_cache: dict[int, dict[str, str]] = {}
    extra_data_cache: dict[int, bool] = {}

    for claim in pending_claims:
        ct_id = claim.content_type_id

        if ct_id not in model_cache:
            model_cache[ct_id] = ContentType.objects.get_for_id(ct_id).model_class()
            fields_cache[ct_id] = get_claim_fields(model_cache[ct_id])
            extra_data_cache[ct_id] = hasattr(model_cache[ct_id], "extra_data")

        model_class = model_cache[ct_id]
        claim_fields = fields_cache[ct_id]
        fn = claim.field_name

        # Category 3: relationship namespace.
        if fn in RELATIONSHIP_NAMESPACES:
            continue

        # Category 4: extra-data claims. These are claims whose field_name
        # doesn't match a concrete Django field — they resolve into the
        # model's extra_data JSONField. Includes dotted namespaces like
        # "wikidata.description" and undotted names like "manufacturer" on
        # MachineModel (where it's not a concrete field).
        if fn not in claim_fields:
            if extra_data_cache[ct_id]:
                continue
            # Category 5: unrecognized — model has no extra_data fallback.
            logger.warning(
                "Rejected claim with unrecognized field_name %r on %s (object_id=%s)",
                fn,
                model_class.__name__,
                claim.object_id,
            )
            rejected.append(claim)
            continue

        # Determine scalar vs FK.
        field = model_class._meta.get_field(fn)
        if field.is_relation:
            # Category 2: FK claim — collect for batch validation.
            fk_claims.append((claim, model_class))
            continue

        # Category 1: scalar claim — validate value.
        try:
            claim.value = validate_claim_value(fn, claim.value, model_class)
        except ValidationError as exc:
            logger.warning(
                "Rejected invalid claim %s.%s (object_id=%s): %s",
                model_class.__name__,
                fn,
                claim.object_id,
                "; ".join(exc.messages),
            )
            rejected.append(claim)

    # Batch FK validation.
    if fk_claims:
        rejected.extend(validate_fk_claims_batch(fk_claims))

    rejected_set = set(id(c) for c in rejected)
    valid = [c for c in pending_claims if id(c) not in rejected_set]
    return valid, len(rejected)


def validate_fk_claims_batch(
    fk_claims: list[tuple],
) -> list:
    """Batch-validate FK scalar claims. Returns list of rejected claims.

    Groups claims by ``(model_class, field_name)``, then issues one query
    per group to check target existence. Mirrors the ``claim_fk_lookups``
    convention from the resolver.
    """
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for claim, model_class in fk_claims:
        groups[(model_class, claim.field_name)].append((claim, model_class))

    rejected: list = []
    for (model_class, field_name), group in groups.items():
        field = model_class._meta.get_field(field_name)
        target_model = field.related_model
        fk_lookups_map = getattr(model_class, "claim_fk_lookups", {})
        lookup_key = fk_lookups_map.get(field_name, "slug")

        # Collect all non-empty slug values, keyed by claim identity.
        slug_by_claim: dict[int, str] = {}
        for claim, _mc in group:
            v = claim.value
            if v is not None and v != "":
                slug_by_claim[id(claim)] = str(v).strip()

        slugs = set(slug_by_claim.values())
        if not slugs:
            continue

        existing = set(
            target_model.objects.filter(**{f"{lookup_key}__in": slugs}).values_list(
                lookup_key, flat=True
            )
        )

        for claim, _mc in group:
            slug = slug_by_claim.get(id(claim))
            if slug is None:
                continue
            if slug not in existing:
                logger.warning(
                    "Rejected FK claim %s.%s (object_id=%s): "
                    "target %s with %s=%r does not exist",
                    model_class.__name__,
                    field_name,
                    claim.object_id,
                    target_model.__name__,
                    lookup_key,
                    slug,
                )
                rejected.append(claim)

    return rejected
