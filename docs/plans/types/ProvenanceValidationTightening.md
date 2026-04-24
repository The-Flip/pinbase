# Provenance Validation Tightening

> **Status: ON HOLD.** This doc predates the model-driven metadata work. The registry-based design it proposes is the wrong shape once [CatalogRelationshipSpec](../model_driven_metadata/ModelDrivenCatalogRelationshipMetadata.md) lands — relationship schemas will be derived from model-owned specs, not a hand-maintained `_relationship_schemas` registry. This doc needs a full rewrite against the finalized spec; do not act on its current contents. See [ModelDrivenMetadata.md](../model_driven_metadata/ModelDrivenMetadata.md) for the umbrella principle and [ModelDrivenMetadataPlanning.md](../model_driven_metadata/ModelDrivenMetadataPlanning.md) for the "Rewrite `ProvenanceValidationTightening.md`" next step.

## Context

The provenance write path admits malformed relationship claims through three independent holes. Each one is a silent-data-loss path today:

- **`assert_claim` bypasses relationship validation.** [claim.py:121-127](../../../backend/apps/provenance/models/claim.py#L121) classifies each claim and only validates `DIRECT` payloads; `RELATIONSHIP` passes through untouched. User edits via `execute_claims` → `assert_claim` therefore never reach any relationship shape check.
- **Malformed payloads misclassify as EXTRA.** [classify_claim](../../../backend/apps/provenance/validation.py#L86) returns `RELATIONSHIP` only if `"exists" in value`. On any model with an `extra_data` field (MachineModel, Title, …), a malformed credit/theme/alias payload lacking `"exists"` falls through to `EXTRA` and gets silently stored as free-form staging data — never hitting the relationship validator at all.
- **Literal namespaces have no schema.** [validate_relationship_claims_batch](../../../backend/apps/provenance/validation.py#L359) only validates namespaces registered via `register_relationship_targets`, which covers FK value_keys. Aliases (`alias_value`, `alias_display`) and abbreviations (`value`) are intentionally unregistered today and pass through without any schema check.

We're pre-launch. Loosening later is a one-line change; tightening later requires auditing every production row. **Err tight.**

This work also unblocks [Step 10.4 of MypyFixing.md](MypyFixing.md#step-104-subscript-flip-in-catalogresolve) — the resolver read path can flip from `cast + .get()` to subscript access for required keys once the write path guarantees them.

## Non-goals

- **Not adding target-existence validation to the single-write path.** Existence stays batch-only. `validate_relationship_claims_batch` already groups claims by namespace and issues one SQL query per group — cheap amortized. Doing the same check in `assert_claim` would be one query per claim, and `execute_claims` writes many claims per user edit (e.g. editing a Title's gameplay features). The brief window of tolerated stale FK targets is an explicit trade-off: stale targets get caught at the next bulk resolve. If we later see drift in practice, benchmark before changing.
- **Not reworking `extra_data` semantics.** Claims that genuinely belong in `EXTRA` (unrecognized field names on models with `extra_data`) still flow through untouched.
- **Not touching DIRECT claim validation.** `validate_claim_value` stays as-is.

### Registry unification — in scope (added after initial draft)

Originally flagged as a follow-up, now folded in. `catalog/claims.py` today carries `_entity_ref_targets` (`namespace → [RefKey(name, model)]`) and `_literal_schemas` (`namespace → LiteralKey(value_key, identity_key)`) driving claim construction and namespace enumeration. `provenance/validation.py` carries `_relationship_target_registry` (FK existence checks only). Adding a fourth `_relationship_schemas` registry without unifying would mean three hand-maintained registries covering overlapping namespace knowledge — strictly worse than today, drift risk every time a namespace is added.

Unification kills `_entity_ref_targets`, `_literal_schemas`, and `_relationship_target_registry`. **One registry** (`_relationship_schemas`) drives construction (`build_relationship_claim`), namespace enumeration (`get_relationship_namespaces`), validation (shape + existence), and — via a consistency test in Step 10.3 — the read-side TypedDicts in `_claim_values.py`. After this work, adding a new namespace is: one `register_relationship_schema(...)` call + one TypedDict (test-enforced to match). Two places.

## Design

### Registry API

Module-level registry of relationship schemas in [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py). Replaces `_relationship_target_registry` and (via the catalog-side refactor below) also replaces `_entity_ref_targets` and `_literal_schemas` from `catalog/claims.py`.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class ValueKeySpec:
    """One key in a relationship claim's value dict."""
    name: str
    scalar_type: type  # int, str, or bool — matched with `type(v) is scalar_type`
    required: bool
    nullable: bool = False  # True allows `None` in addition to scalar_type
    identity: bool = False
    # True if this key participates in the claim_key identity. Used by
    # build_relationship_claim to derive the identity dict. For literal
    # namespaces (aliases/abbreviations) the identity key may differ from
    # the value_key name — see `identity_name` below.
    identity_name: str | None = None
    # Overrides `name` when the claim_key identity uses a different label
    # (e.g. value_key "alias_value" → identity "alias"). Only meaningful
    # when identity=True.
    fk_target: tuple[type[models.Model], str] | None = None
    # If set, (target_model, lookup_field) — this value_key is an FK reference
    # and batch-path existence checks apply via validate_relationship_claims_batch.

@dataclass(frozen=True, slots=True)
class RelationshipSchema:
    namespace: str  # claim field_name, e.g. "credit", "theme_alias", "abbreviation"
    value_keys: tuple[ValueKeySpec, ...]

_relationship_schemas: dict[str, RelationshipSchema] = {}

def register_relationship_schema(schema: RelationshipSchema) -> None:
    _relationship_schemas[schema.namespace] = schema

def get_relationship_schema(namespace: str) -> RelationshipSchema | None:
    return _relationship_schemas.get(namespace)
```

`identity` and `identity_name` subsume what `RefKey` and `LiteralKey` carry today. An FK reference like `{"person": int}` has `identity=True`, `identity_name=None` (defaults to `name`). An alias key like `alias_value: str` has `identity=True, identity_name="alias"` — matching the current `LiteralKey("alias_value", "alias")` shape. Non-identity optional keys (`count`, `category`, `is_primary`, `alias_display`) have `identity=False`.

### Catalog-side consolidation

[apps/catalog/claims.py](../../../backend/apps/catalog/claims.py) loses `_entity_ref_targets`, `_literal_schemas`, `RefKey`, `LiteralKey`, `_get_entity_ref_targets`, `_get_literal_schemas`, and `register_relationship_targets`. In their place:

- `register_catalog_relationship_schemas()` — one function called from `CatalogConfig.ready()`. Replaces `register_relationship_targets()`. Body is a series of `register_relationship_schema(RelationshipSchema(...))` calls, one per namespace. The schemas are _the_ source: no intermediate dict.
- `build_relationship_claim(field_name, identity, exists)` — reworked to read from `get_relationship_schema(field_name)` and iterate `schema.value_keys` where `identity=True`, using `identity_name or name` as the claim_key label and `name` as the value_dict key. Behavior preserved for every existing call site.
- `get_relationship_namespaces()` — returns `frozenset(_relationship_schemas.keys())` (or a wrapper that filters to catalog-owned namespaces if future apps register their own).
- `get_all_namespace_keys()` — derived from the registry via a similar iteration. Used only in tests today; safe to rewrite.

Identity-key discovery from the schema means alias types added dynamically via `discover_alias_types()` must now call `register_relationship_schema` at discovery time instead of populating `_literal_schemas`. That hook lives in `register_catalog_relationship_schemas()` — same spot, same `ready()`-time timing, different target registry.

No behavior change for any consumer of the public surface (`build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys`). Existing call-site tests stay green.

Namespaces registered (full coverage — must match the read-side TypedDicts in `catalog/resolve/_claim_values.py`):

- `"credit"` → `{person: int (required, fk=Person.pk), role: int (required, fk=CreditRole.pk)}`
- `"gameplay_feature"` → `{gameplay_feature: int (required, fk=GameplayFeature.pk), count: int | None (optional)}`
- `"theme"` / `"tag"` / `"reward_type"` → `{<namespace>: int (required, fk=<target>.pk)}`
- `"theme_alias"` / `"manufacturer_alias"` / `"person_alias"` / `"gameplay_feature_alias"` / `"reward_type_alias"` / `"corporate_entity_alias"` / `"location_alias"` → `{alias_value: str (required), alias_display: str (optional)}`
- `"abbreviation"` → `{value: str (required)}` — shared by Title and MachineModel resolvers (same `field_name`, distinguished by `content_type`); registry keyed by `field_name` alone is fine today because both share the shape.
- `"media_attachment"` → `{media_asset: int (required, fk=MediaAsset.pk), category: str | None (optional), is_primary: bool (optional)}`
- `"location"` (CorporateEntity → Location) → `{location: int (required, fk=Location.pk)}`
- `"theme_parent"` / `"gameplay_feature_parent"` → `{parent: int (required, fk=<self>.pk)}`

### Classification change

Preserve DIRECT precedence. Keep the existing `field_name in claim_fields → DIRECT` check first. **After** DIRECT detection, classify any remaining `field_name` appearing in `_relationship_schemas` as `RELATIONSHIP` regardless of whether `"exists"` is present. The new registry check **replaces** the old structural relationship check (`claim_key != field_name and isinstance(value, dict) and "exists" in value`) for non-direct fields; it does **not** override legitimate direct fields whose name collides with a relationship namespace.

### Single-claim validator

Factor a new `validate_single_relationship_claim(claim: Claim) -> None` out of `validate_relationship_claims_batch`. Raises `ValidationError` on shape violation. Called from:

- `ClaimManager.assert_claim` at [claim.py:127](../../../backend/apps/provenance/models/claim.py#L127), in a new branch for `ct_result == RELATIONSHIP` that propagates the `ValidationError`.
- `validate_claims_batch` at [validation.py:251](../../../backend/apps/provenance/validation.py#L251), replacing the accumulate-then-batch-validate path for shape. Existence checks remain batched in `validate_relationship_claims_batch`.

### Rejection conditions (shape)

Applied by `validate_single_relationship_claim` in both paths:

- `value` is not a `dict`.
- `value` is missing `"exists"`, or `value["exists"]` is not a `bool`.
- Missing any **required** registered `ValueKeySpec` for the namespace. Optional keys are type-checked only when present.
- Wrong scalar type for any present registered key (required or optional). Applies to identity keys (`person: int`, `alias_value: str`) and non-identity keys (`count: int | None`, `category: str | None`, `is_primary: bool`, `alias_display: str`).

**Why `type(value) is scalar_type`, not `isinstance(value, scalar_type)`.** `bool` is a subclass of `int` in Python, so `isinstance(True, int)` is `True`. A payload carrying `{"person": True}` or `{"count": False}` should be rejected, not silently accepted as PK `1` / count `0`. The primary threat is Python-side code (tests, ingest adapters) passing bools where ints belong; `json.loads` of `{"x": true}` also produces `bool`, so the rule catches wire payloads too. Future readers should not loosen this to `isinstance`. For `nullable=True` specs, accept `None` in addition to `type(v) is scalar_type`.

### Rejection conditions (existence — batch only)

Unchanged from today. `validate_relationship_claims_batch` continues to do per-namespace group queries for FK `ValueKeySpec`s where `exists=True`. `assert_claim` does not do existence checks — see Non-goals.

## Commit sequence

The audit can't run before the registry exists. Split into two commits:

1. **Commit A — unified registry + scaffolding (no behavior change).**
   - Add `ValueKeySpec` / `RelationshipSchema` / `register_relationship_schema` / `get_relationship_schema` to [validation.py](../../../backend/apps/provenance/validation.py).
   - Rewrite [catalog/claims.py](../../../backend/apps/catalog/claims.py): delete `_entity_ref_targets`, `_literal_schemas`, `RefKey`, `LiteralKey`, `_get_entity_ref_targets`, `_get_literal_schemas`, `register_relationship_targets`. Add `register_catalog_relationship_schemas()` with one `register_relationship_schema(...)` call per namespace (17 total — list below). Rework `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys` to read from the unified registry.
   - Rewrite `validate_relationship_claims_batch` internals to read `fk_target` tuples off `ValueKeySpec` entries (same existence-check semantics, new source).
   - Delete `_relationship_target_registry` and the old `register_relationship_targets` function in validation.py.
   - At this point `classify_claim` still uses the old structural check and no new shape rejections fire — runtime behavior is identical. Mypy passes, full test suite passes, baseline unchanged.

2. **Audit against prod snapshot.** Run `scripts/audit_relationship_claims.py` (below) using Commit A's registry against a prod DB. Record counts + breakdown. Expected outcome on a clean pre-launch DB: all zeros. Non-zero counts inform Commit B.

3. **Commit B — classifier, validator, cleanup.** Flip `classify_claim` to registry-driven classification (preserving DIRECT precedence). Add `validate_single_relationship_claim`. Wire it into `assert_claim` and `validate_claims_batch`. If the audit found offending rows, include the `Claim.objects.filter(...).update(is_active=False)` cleanup in the same commit, with counts and namespace breakdown in the commit message.

Commit A is larger than a pure "scaffolding" commit would be, but the blast radius is bounded to `catalog/claims.py` and `provenance/validation.py` plus their tests. The size is bounded because every consumer of `build_relationship_claim` / `get_relationship_namespaces` sees unchanged behavior — those functions keep their signatures and semantics; only their implementation moves.

### Registered namespaces

Every catalog relationship namespace gets a `register_relationship_schema(...)` call in `register_catalog_relationship_schemas()`. Identity keys (`identity=True`) drive `build_relationship_claim`'s claim_key composition; non-identity keys are shape-validated only. Missing any of these means resolver reads for that namespace stay unvalidated and Step 10.4 of MypyFixing.md can't subscript those keys safely.

- **Alias namespaces (7):** `theme_alias`, `manufacturer_alias`, `person_alias`, `gameplay_feature_alias`, `reward_type_alias`, `corporate_entity_alias`, `location_alias`. Each → `alias_value: str (required, identity, identity_name="alias")`, `alias_display: str (optional)`. Dynamic discovery via `discover_alias_types()` still happens — it just calls `register_relationship_schema` instead of populating `_literal_schemas`.
- **Abbreviation namespace (1):** `abbreviation` → `value: str (required, identity)`. Shared by Title and MachineModel resolvers.
- **Parent namespaces (2):** `theme_parent`, `gameplay_feature_parent`. Each → `parent: int (required, identity, fk=<self>.pk)`.
- **Location namespace (1):** `location` (CorporateEntity → Location) → `location: int (required, identity, fk=Location.pk)`.
- **Credit namespace (1):** `credit` → `person: int (required, identity, fk=Person.pk)`, `role: int (required, identity, fk=CreditRole.pk)`.
- **Gameplay feature namespace (1):** `gameplay_feature` → `gameplay_feature: int (required, identity, fk=GameplayFeature.pk)`, `count: int | None (optional)`.
- **Simple M2M namespaces (3):** `theme`, `tag`, `reward_type`. Each → `<namespace>: int (required, identity, fk=<target>.pk)`.
- **Media attachment namespace (1):** `media_attachment` → `media_asset: int (required, identity, fk=MediaAsset.pk)`, `category: str | None (optional)`, `is_primary: bool (optional)`.

17 namespaces. All registered fresh in the unified API — no migration shim needed because the old registries are deleted wholesale in the same commit.

## Audit queries

Draft the script below into `scripts/audit_relationship_claims.py` (or a Django management command) and run against a production DB snapshot after Commit A lands but before Commit B. Counts and breakdowns go in the Commit B PR description.

```python
# scripts/audit_relationship_claims.py
"""One-shot audit ahead of ProvenanceValidationTightening.

Reports three counts:
  a. Active claims where field_name is a relationship-registry name but
     classify_claim currently returns EXTRA (the silent-fallthrough case).
  b. Active claims under a registered relationship namespace whose value
     fails the new shape rejection conditions (non-dict, missing/non-bool
     exists, missing required key, wrong scalar type).
  c. A breakdown of (b) by namespace so we know what to deactivate.
"""
from collections import Counter

from apps.provenance.models import Claim
from apps.provenance.validation import (
    EXTRA,
    _relationship_schemas,   # Commit A adds this registry; script runs after Commit A.
    classify_claim,
)
from apps.core.models import get_claim_fields


def reason_for_rejection(value: object, schema: "RelationshipSchema") -> str | None:
    if not isinstance(value, dict):
        return "not-dict"
    exists = value.get("exists")
    if not isinstance(exists, bool):
        return "missing-or-non-bool-exists"
    for spec in schema.value_keys:
        v = value.get(spec.name)
        if v is None:
            if spec.required and not spec.nullable:
                return f"missing-required-{spec.name}"
            continue
        if spec.nullable and v is None:
            continue
        if type(v) is not spec.scalar_type:
            return f"wrong-type-{spec.name}"
    return None


def run() -> None:
    namespaces = set(_relationship_schemas.keys())

    # (a) silent EXTRA fallthrough
    a_count = 0
    for claim in Claim.objects.filter(is_active=True, field_name__in=namespaces).iterator():
        model_class = claim.content_type.model_class()
        if model_class is None:
            continue
        ct = classify_claim(
            model_class, claim.field_name, claim.claim_key, claim.value,
            claim_fields=get_claim_fields(model_class),
        )
        if ct == EXTRA:
            a_count += 1

    # (b) + (c) shape violations by namespace
    breakdown: Counter[tuple[str, str]] = Counter()
    b_count = 0
    for schema in _relationship_schemas.values():
        for claim in Claim.objects.filter(
            is_active=True, field_name=schema.namespace
        ).iterator():
            reason = reason_for_rejection(claim.value, schema)
            if reason:
                breakdown[(schema.namespace, reason)] += 1
                b_count += 1

    print(f"(a) silent-EXTRA-fallthrough active claims: {a_count}")
    print(f"(b) shape-violation active claims: {b_count}")
    print("(c) breakdown by (namespace, reason):")
    for (ns, reason), n in sorted(breakdown.items(), key=lambda kv: -kv[1]):
        print(f"    {n:>6}  {ns}  {reason}")
```

Run on a prod DB snapshot (`railway ssh` + DJANGO_SETTINGS connection, or a fresh `make pull-ingest` against current data). Expected outcome on a clean pre-launch DB: all zeros. Any non-zero count is either a legacy ingest artifact (deactivate in the cleanup step) or a bug in the script — investigate before writing the validator.

## TDD plan

Assumes the "Commit sequence" above: Commit A (registry scaffolding) → audit → Commit B (classifier + validator + cleanup). Tests land with Commit B.

1. **Commit A is not TDD-gated for new behavior** (there isn't any), but **existing `catalog/claims.py` tests are the regression gate**. The full test suite must pass green — `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys`, and all their downstream callers are rewritten to read from the unified registry, and their existing tests are what prove the rewrite preserves behavior. If a test fails, the rewrite has drifted from today's semantics — fix the rewrite, not the test.
2. **Run the audit script** (above) against a prod snapshot. Counts + breakdown inform Commit B's PR description.
3. **If audit is all zero:** Commit B is a straight code change — the three tightenings in one PR.
4. **If non-zero:** cleanup step in the same PR — `Claim.objects.filter(...).update(is_active=False)` on offending rows using the breakdown from step 2, with counts and namespace breakdown in the commit message. Don't hand-edit payloads; the audit trail is the truth.
5. **Failing tests, one per rejection mode, per path:**
   - `assert_claim` path: assert `ValidationError` raised for each of — non-dict value, missing `exists`, non-bool `exists`, missing required key, wrong-scalar-type required key, wrong-scalar-type optional key, `bool` passed where `int` expected.
   - Batch path: `validate_claims_batch(...)` returns `(valid, rejected_count)` — assert `rejected_count == 1` and the malformed claim is **not** in `valid`. For rejection-reason assertions, call `validate_relationship_claims_batch(...)` directly (that function returns the rejected `list[Claim]`).
   - Classify-by-registry fix: a malformed relationship payload on a model with `extra_data` must reach the relationship validator (and be rejected), not land as `EXTRA`.
   - DIRECT precedence preserved: a `field_name` that is both a DIRECT claim field on the model **and** a name in the relationship registry must classify as `DIRECT`. (Likely synthetic — no real collision today, but pin the ordering.)
6. Implement the three tightenings. Tests go green.

## Files touched

**Commit A — unified registry:**

- [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — new `ValueKeySpec` / `RelationshipSchema` / `register_relationship_schema` / `get_relationship_schema`. Delete `_relationship_target_registry` and the old `register_relationship_targets`. Rewrite `validate_relationship_claims_batch` internals to read `fk_target` tuples off `ValueKeySpec` entries.
- [apps/catalog/claims.py](../../../backend/apps/catalog/claims.py) — delete `RefKey`, `LiteralKey`, `_entity_ref_targets`, `_literal_schemas`, `_get_entity_ref_targets`, `_get_literal_schemas`, `register_relationship_targets`. Add `register_catalog_relationship_schemas()` with 17 `register_relationship_schema(...)` calls. Rewrite `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys` to read from the unified registry. Alias-type dynamic discovery hooks into the new registration function.
- [apps/catalog/apps.py](../../../backend/apps/catalog/apps.py) — `CatalogConfig.ready()` calls `register_catalog_relationship_schemas()` instead of `register_relationship_targets()`.
- [apps/catalog/tests/test_claims.py](../../../backend/apps/catalog/tests/test_claims.py) (or wherever the existing claim-building tests live) — behavior-preserving; trivial touches if any.

**Commit B — classifier, validator, cleanup:**

- [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — `classify_claim` registry-driven; new `validate_single_relationship_claim`.
- [apps/provenance/models/claim.py](../../../backend/apps/provenance/models/claim.py) — `assert_claim` new `RELATIONSHIP` branch calling `validate_single_relationship_claim`.
- [apps/provenance/tests/test_validation.py](../../../backend/apps/provenance/tests/test_validation.py) — new rejection-mode tests.
- `scripts/audit_relationship_claims.py` — new, one-shot script.
- If audit non-zero: a data-cleanup call in the same commit, noted in the commit message.

## Verification

- `uv run --directory backend pytest apps/provenance/tests/test_validation.py apps/catalog/tests/test_bulk_resolve*.py` — all tests pass.
- `./scripts/mypy` — baseline unchanged (this step has no mypy impact).
- `make ingest` end-to-end against R2 data — no new rejections on clean data. If rejections appear, they're real malformed payloads upstream ingest is producing and must be fixed at the source.
- After landing, Step 10.4 of MypyFixing.md (resolver subscript flip) is unblocked.
