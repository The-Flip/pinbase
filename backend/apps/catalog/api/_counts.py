"""Bulk count helpers for taxonomy list endpoints.

Centralized so the active-model + non-variant + active-title filter set is
defined exactly once across the 10 model-attached taxonomy list views.
"""

from __future__ import annotations

from collections.abc import Iterable

from apps.core.models import active_status_q

from ..models import MachineModel


def bulk_title_counts_via_models(
    taxonomy_pks: Iterable[int],
    mm_relation: str,
    *,
    children_map: dict[int, list[int]] | None = None,
) -> dict[int, int]:
    """Return ``{taxonomy_pk: distinct_active_title_count}``.

    *mm_relation* is the ``MachineModel`` field name pointing at the taxonomy
    (FK or M2M). For example: ``"gameplay_features"``, ``"themes"``,
    ``"technology_generation"``, ``"display_type"``.

    Filters applied uniformly:
      - ``machinemodel.is_active`` (via ``MachineModel.objects.active()``)
      - ``machinemodel.variant_of__isnull=True``
      - ``machinemodel.title.is_active`` (via ``active_status_q("title")``)

    When *children_map* is provided, each node's count is the size of the
    *union* of its own + descendants' title sets (deduped — not summed).
    """
    pks = list(taxonomy_pks)
    if not pks:
        return {}

    pairs = (
        MachineModel.objects.active()
        .filter(variant_of__isnull=True, **{f"{mm_relation}__in": pks})
        .filter(active_status_q("title"))
        .values_list(mm_relation, "title_id")
    )

    direct: dict[int, set[int]] = {}
    for tax_pk, title_pk in pairs:
        if tax_pk is None or title_pk is None:
            continue
        direct.setdefault(tax_pk, set()).add(title_pk)

    if children_map is None:
        return {pk: len(direct.get(pk, ())) for pk in pks}

    counts: dict[int, int] = {}
    for pk in pks:
        seen: set[int] = set(direct.get(pk, ()))
        visited: set[int] = {pk}
        stack = list(children_map.get(pk, []))
        while stack:
            child = stack.pop()
            if child in visited:
                continue
            visited.add(child)
            seen |= direct.get(child, set())
            stack.extend(children_map.get(child, []))
        counts[pk] = len(seen)
    return counts
