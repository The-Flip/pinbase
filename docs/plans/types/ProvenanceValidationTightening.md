# Provenance Validation Tightening

## Context

This is **Step 2** of [ResolveHardening.md](ResolveHardening.md) — the write-path foundation of a multi-step sequence that tightens the claim-value contract across `catalog/resolve/*`:

- **Step 2 (this doc)** — unify the three registries that hand-maintain catalog relationship namespace knowledge today, and tighten the write-path shape validation that the unified registry now makes expressible.
- **Step 3** — [Claim-value TypedDicts + resolver casts + consistency test](CatalogResolveTyping.md). Introduces TypedDicts over the resolver read path that mirror this doc's registry, plus a consistency test enforcing the mirror holds.
- **Step 4** — [Mypy baseline burn-down on `catalog/resolve/*`](CatalogResolveBaselineCleanup.md). Helper signatures + tuple-reuse cleanup. Not load-bearing for the hardening story, bundled because it touches the same files.
- **Step 5** — [Subscript flip](ResolverReadsTightening.md). Flips resolver reads from `cast + .get()` to subscript access for required keys — sound only because Step 2's write-path validation now guarantees required keys are present, _and_ because Step 2's post-merge wipe + re-ingest has rebuilt stored rows under the new validator.

### Primary work: unify three hand-maintained registries

Namespace knowledge for catalog relationships lives in three registries today, covering overlapping ground:

- `_entity_ref_targets` in [catalog/claims.py](../../../backend/apps/catalog/claims.py) — `namespace → [RefKey(name, model)]`. Drives FK claim construction.
- `_literal_schemas` in [catalog/claims.py](../../../backend/apps/catalog/claims.py) — `namespace → LiteralKey(value_key, identity_key)`. Drives literal claim construction.
- `_relationship_target_registry` in [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — namespace → FK existence targets. Drives batch validation.

Adding or changing an FK namespace means touching two of these in lockstep; there's no cross-check that they agree. Step 3 is about to introduce a fourth source of truth: TypedDicts over the resolver read path, which must agree with the write-path schema for Step 5's subscript flip to be sound. Adding that fourth without unifying first is strictly worse than today — four hand-maintained registries, drift risk every time a namespace is added, no mechanical way to enforce agreement.

**Unify to one registry** (`_relationship_schemas` in `provenance/validation.py`) that drives claim construction (`build_relationship_claim`), namespace enumeration (`get_relationship_namespaces`), write-path validation (shape + existence), and — via Step 3's consistency test — the read-side TypedDicts in `_claim_values.py`. After this work, adding a namespace is one `register_relationship_schema(...)` call + one TypedDict (test-enforced to match). Two places.

The unified registry is what earns Step 3's consistency test its keep: it's the single authority the TypedDicts are tested against. Without unification, the TypedDicts would have three disagreeing registries to reconcile with, and the test would either not exist or silently gloss over the disagreements.

### Along for the ride: three silent-data-loss bugs

The unified registry makes shape validation expressible in one place, and three pre-existing holes in the write path get closed as a natural consequence rather than as standalone tightening:

- **`assert_claim` bypasses relationship validation.** [claim.py:121-127](../../../backend/apps/provenance/models/claim.py#L121) classifies each claim and only validates `DIRECT` payloads; `RELATIONSHIP` passes through untouched. User edits via `execute_claims` → `assert_claim` therefore never reach any relationship shape check.
- **Malformed payloads misclassify as EXTRA.** [classify_claim](../../../backend/apps/provenance/validation.py#L86) returns `RELATIONSHIP` only if `"exists" in value`. On any model with an `extra_data` field (MachineModel, Title, …), a malformed credit/theme/alias payload lacking `"exists"` falls through to `EXTRA` and gets silently stored as free-form staging data — never hitting the relationship validator at all.
- **Literal namespaces have no schema.** [validate_relationship_claims_batch](../../../backend/apps/provenance/validation.py#L359) only validates namespaces registered via `register_relationship_targets`, which covers FK value_keys. Aliases (`alias_value`, `alias_display`) and abbreviations (`value`) are intentionally unregistered today and pass through without any schema check.

Closing these is also load-bearing for Step 5: the subscript flip only becomes safe once the write path guarantees required keys are present on stored claims. So the bug-fixes aren't just opportunistic — they're the other half of what unblocks Step 5.

We're pre-launch. Loosening later is a one-line change; tightening later requires auditing every production row. **Err tight.**

**Data posture.** The DB can be dropped and all migrations reset to 0001. The remediation path for any malformed legacy rows surfaced by the new validator is: wipe the DB, reset migrations, `make pull-ingest`, `make ingest`. No audit script, no row-level cleanup, no `is_active=False` sweeps. If re-ingestion produces rejections, that is an extractor bug — fix at the source (where the malformed shape originated), re-ingest, repeat.

## Non-goals

- **Not adding target-existence validation to the single-write path.** Existence stays batch-only. `validate_relationship_claims_batch` already groups claims by namespace and issues one SQL query per group — cheap amortized. Doing the same check in `assert_claim` would be one query per claim, and `execute_claims` writes many claims per user edit (e.g. editing a Title's gameplay features). The brief window of tolerated stale FK targets is an explicit trade-off: stale targets get caught at the next bulk resolve. If we later see drift in practice, benchmark before changing.
- **Not reworking `extra_data` semantics.** Claims that genuinely belong in `EXTRA` (unrecognized field names on models with `extra_data`) still flow through untouched.
- **Not touching DIRECT claim validation.** `validate_claim_value` stays as-is.
- **Not collapsing bespoke resolvers into a generic spec-driven resolver.** The registry added here is intentionally consumed by `classify_claim`, `validate_single_relationship_claim`, `validate_relationship_claims_batch`, and `build_relationship_claim` only. Folding `_parent_dispatch` / `_custom_dispatch` / `M2M_FIELDS` into one generic resolver is a plausible follow-up that can consume the same registry, but keeping it out of scope here bounds the PR and avoids bundling a latent behavior change in `resolve_all_corporate_entity_locations` (which today filters `is_active=True` before winner selection) with an otherwise behavior-preserving refactor.
- **Not lifting the identity-vs-UC cross-check from [CatalogRelationshipSpec](../model_driven_metadata/ModelDrivenCatalogRelationshipMetadata.md).** That guard — verifying `subject_fks ∪ identity_fields` matches one `UniqueConstraint` per through-model at `ready()` — is genuinely useful, but it belongs with the model-driven metadata work it was drafted for. Pulling it in here would motivate `through_model` and `subject_fks` on the schema, which would force `(namespace, subject_content_type)` keying and the "abbreviation registers twice" complication — all scaffolding for a check the rest of this PR does not use. Deferred as a whole.

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
    identity: str | None = None
    # If set, this key participates in the claim_key identity and the string
    # is the label used in the identity dict. Use `name` when the label
    # matches the value_key name (e.g. identity="person" for value_key "person").
    # Use a different string when they differ (e.g. identity="alias" for
    # value_key "alias_value" — matches today's LiteralKey("alias_value", "alias")).
    # None means this key is non-identity (e.g. count, category, alias_display).
    fk_target: tuple[type[models.Model], str] | None = None
    # If set, (target_model, lookup_field) — this value_key is an FK reference
    # and batch-path existence checks apply via validate_relationship_claims_batch.

@dataclass(frozen=True, slots=True)
class RelationshipSchema:
    namespace: str                                     # claim field_name, e.g. "credit", "theme_alias", "abbreviation"
    value_keys: tuple[ValueKeySpec, ...]
    valid_subjects: tuple[type[models.Model], ...]     # subject models this namespace applies to

# Registry keyed by namespace. Shared-namespace cases (abbreviation, credit,
# media_attachment) register once with multiple valid_subjects.
_relationship_schemas: dict[str, RelationshipSchema] = {}

def register_relationship_schema(schema: RelationshipSchema) -> None:
    if schema.namespace in _relationship_schemas:
        raise ImproperlyConfigured(f"namespace {schema.namespace!r} registered twice")
    _relationship_schemas[schema.namespace] = schema

def get_relationship_schema(namespace: str) -> RelationshipSchema | None:
    return _relationship_schemas.get(namespace)

def is_valid_subject(schema: RelationshipSchema, subject_content_type: ContentType) -> bool:
    target_id = subject_content_type.id
    return any(
        ContentType.objects.get_for_model(m).id == target_id for m in schema.valid_subjects
    )
```

`ValueKeySpec.identity` subsumes what `RefKey` and `LiteralKey` carry today. An FK reference like `{"person": int}` uses `identity="person"` (label equals name). An alias key like `alias_value: str` uses `identity="alias"` — matching the current `LiteralKey("alias_value", "alias")` shape. Non-identity optional keys (`count`, `category`, `is_primary`, `alias_display`) leave `identity=None`.

### Registry is keyed by namespace

One schema per namespace, not per `(namespace, subject)`. Shared-namespace cases (`abbreviation` on Title vs MachineModel, `credit` on MachineModel vs Series, `media_attachment` on N subjects) register once with multiple `valid_subjects`; this works because the value-key shapes are identical across those subjects today. The subject content type is carried on the claim itself and enters via `is_valid_subject(schema, subject_content_type)` — a check owned by the validator, not a registry-key discriminator. This keying is what a pre-launch hand-maintained registry needs; the `(namespace, subject_ct)` keying required for the UC cross-check belongs with the deferred spec work (see Non-goals).

### Catalog-side consolidation

[apps/catalog/claims.py](../../../backend/apps/catalog/claims.py) loses `_entity_ref_targets`, `_literal_schemas`, `RefKey`, `LiteralKey`, `_get_entity_ref_targets`, `_get_literal_schemas`, and `register_relationship_targets`. In their place:

- `register_catalog_relationship_schemas()` — one function called from `CatalogConfig.ready()`. Replaces `register_relationship_targets()`. Body is a series of `register_relationship_schema(RelationshipSchema(...))` calls, one per namespace. The schemas are _the_ source: no intermediate dict.
- `build_relationship_claim(field_name, subject_content_type, identity, exists)` — reworked to read from `get_relationship_schema(field_name)` and iterate `schema.value_keys` where `identity is not None`, using `spec.identity` as the claim_key label and `spec.name` as the value_dict key. Subject `content_type` still flows through call sites (needed for the wrong-subject rejection below), but the lookup itself is subject-independent.
- `get_relationship_namespaces()` — returns `frozenset(_relationship_schemas)`.
- `get_all_namespace_keys()` — derived from the registry via a similar iteration. Used only in tests today; safe to rewrite.

Alias types added dynamically via `discover_alias_types()` must now call `register_relationship_schema` at discovery time instead of populating `_literal_schemas`. That hook lives in `register_catalog_relationship_schemas()` — same spot, same `ready()`-time timing, different target registry.

No behavior change for any consumer of the public surface (`build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys`). Existing call-site tests stay green.

Registered schemas (full coverage — must match the read-side TypedDicts in `catalog/resolve/_claim_values.py`):

- `"credit"` — `valid_subjects=(MachineModel, Series)`. Value keys: `{person: int (identity="person", fk=Person.pk), role: int (identity="role", fk=CreditRole.pk)}`.
- `"gameplay_feature"` — `valid_subjects=(MachineModel,)`. Value keys: `{gameplay_feature: int (identity="gameplay_feature", fk=GameplayFeature.pk), count: int | None (optional)}`.
- `"theme"` / `"tag"` / `"reward_type"` — `valid_subjects=(MachineModel,)`. Value keys: `{<namespace>: int (identity=<namespace>, fk=<target>.pk)}`.
- Alias namespaces (7) — one schema each. `valid_subjects=(<owner>,)`. Value keys: `{alias_value: str (identity="alias"), alias_display: str (optional)}`.
- `"abbreviation"` — `valid_subjects=(Title, MachineModel)`. Value keys: `{value: str (identity="value")}`.
- `"media_attachment"` — `valid_subjects=(<all supported subjects>)`. Value keys: `{media_asset: int (identity="media_asset", fk=MediaAsset.pk), category: str | None (optional), is_primary: bool (optional)}`.
- `"location"` — `valid_subjects=(CorporateEntity,)`. Value keys: `{location: int (identity="location", fk=Location.pk)}`.
- `"theme_parent"` / `"gameplay_feature_parent"` — `valid_subjects=(Theme,)` / `(GameplayFeature,)`. Value keys: `{parent: int (identity="parent", fk=<self>.pk)}`.

### Classification change

Preserve DIRECT precedence. Keep the existing `field_name in claim_fields → DIRECT` check first. **After** DIRECT detection, classify any remaining claim as `RELATIONSHIP` iff `get_relationship_schema(field_name)` returns a schema — regardless of whether `"exists"` is present and regardless of whether this subject is in the schema's `valid_subjects`. The wrong-subject case (e.g. `field_name="credit"` on `Title`) routes to the relationship validator and is rejected there, not silently routed to `EXTRA`. The new registry check **replaces** the old structural relationship check (`claim_key != field_name and isinstance(value, dict) and "exists" in value`) for non-direct fields; it does **not** override legitimate direct fields whose name collides with a relationship namespace.

### Single-claim validator

Factor a new `validate_single_relationship_claim(claim: Claim) -> None` out of `validate_relationship_claims_batch`. Raises `ValidationError` on shape violation. Called from:

- `ClaimManager.assert_claim` at [claim.py:127](../../../backend/apps/provenance/models/claim.py#L127), in a new branch for `ct_result == RELATIONSHIP` that propagates the `ValidationError`.
- `validate_claims_batch` at [validation.py:251](../../../backend/apps/provenance/validation.py#L251), replacing the accumulate-then-batch-validate path for shape. Existence checks remain batched in `validate_relationship_claims_batch`.

### Rejection conditions (shape)

Applied by `validate_single_relationship_claim` in both paths:

- **Wrong subject**: claim's subject `content_type` is not in `schema.valid_subjects` (e.g. `field_name="credit"` on a `Title`). Closes the silent-EXTRA-fallthrough class for misrouted namespaces. Checked first — before the shape rules below — because a namespace that doesn't belong on this subject can't be validated against the schema's value-key expectations.
- `value` is not a `dict`.
- `value` is missing `"exists"`, or `value["exists"]` is not a `bool`.
- Missing any **required** registered `ValueKeySpec` for the namespace. Optional keys are type-checked only when present.
- Wrong scalar type for any present registered key (required or optional). Applies to identity keys (`person: int`, `alias_value: str`) and non-identity keys (`count: int | None`, `category: str | None`, `is_primary: bool`, `alias_display: str`).
- **Unknown keys**: any key in `value` other than `"exists"` or a name in `schema.value_keys`. Prevents typos (`{person, role, rol}`) and stale fields from accumulating indefinitely in stored claim payloads. Same class of silent-drift as the silent-EXTRA-fallthrough — if extractors or adapters produce typos or leftover keys, nothing else rejects them today.

**Why `type(value) is scalar_type`, not `isinstance(value, scalar_type)`.** `bool` is a subclass of `int` in Python, so `isinstance(True, int)` is `True`. A payload carrying `{"person": True}` or `{"count": False}` should be rejected, not silently accepted as PK `1` / count `0`. The primary threat is Python-side code (tests, ingest adapters) passing bools where ints belong; `json.loads` of `{"x": true}` also produces `bool`, so the rule catches wire payloads too. Future readers should not loosen this to `isinstance`. For `nullable=True` specs, accept `None` in addition to `type(v) is scalar_type`.

### Rejection conditions (existence — batch only)

Unchanged from today, including the explicit carve-out that **retractions (`exists=False`) are exempt from FK-target existence**. A retraction references a previous assertion, not a current row — the target may already have been deleted and the retraction must still succeed, otherwise claims about deleted entities could never be retracted. Identity keys remain required on retractions so batch resolve knows which row to remove; shape validation (above) applies uniformly to positive claims and retractions.

`validate_relationship_claims_batch` continues to do per-namespace group queries for FK `ValueKeySpec`s where `exists=True`; `exists=False` entries skip that check. `assert_claim` does not do existence checks regardless of `exists` — see Non-goals.

Test coverage for the retraction carve-out lives in [`test_validation.py`](../../../backend/apps/provenance/tests/test_validation.py) (explicit case for retractions against deleted targets). Do not remove or loosen without replacing.

## Commit sequence

Two commits in one PR. Commit A is a mechanical registry rewrite, Commit B is the tightening proper. Keeping them separate matters even in one PR — reviewers can check A against today's behavior ("same inputs, same outputs") without tangling that against the shape-rejection rules B introduces.

1. **Commit A — unified registry (no behavior change).**
   - Add `ValueKeySpec` / `RelationshipSchema` (namespace + `value_keys` + `valid_subjects`) / `register_relationship_schema` / `get_relationship_schema` / `is_valid_subject` to [validation.py](../../../backend/apps/provenance/validation.py). Registry keyed by `namespace: str`.
   - Rewrite [catalog/claims.py](../../../backend/apps/catalog/claims.py): delete `_entity_ref_targets`, `_literal_schemas`, `RefKey`, `LiteralKey`, `_get_entity_ref_targets`, `_get_literal_schemas`, `register_relationship_targets`. Add `register_catalog_relationship_schemas()` with one `register_relationship_schema(...)` call per namespace (list below). Rework `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys` to read from the unified registry.
   - Rewrite `validate_relationship_claims_batch` internals to read `fk_target` tuples off `ValueKeySpec` entries (same existence-check semantics, new source).
   - Delete `_relationship_target_registry` and the old `register_relationship_targets` function in validation.py.
   - `classify_claim` still uses the old structural check, no new rejections fire — claim-shape runtime behavior is identical. Mypy passes, full test suite passes, baseline unchanged.

2. **Commit B — classifier + validator.** Flip `classify_claim` to registry-driven classification (preserving DIRECT precedence, using `get_relationship_schema(field_name)` lookup). Add `validate_single_relationship_claim` including the wrong-subject check. Wire it into `assert_claim` and `validate_claims_batch`. No data-cleanup step bundled in — see "Data posture".

3. **Pre-merge dry-run (local).** With Commit B applied locally: `make reset-db` (or equivalent — wipe the localhost DB and reset migrations to 0001), then `make pull-ingest` + `make ingest`. Observe any validator rejections. Clean ⇒ merge. Dirty ⇒ rejections name the offending namespace + reason; fix at the extractor source, re-ingest, repeat until clean. This replaces the removed audit script as the "how bad is it" preview.

4. **Post-merge: wipe + re-ingest.** Same sequence against the shared environment so the DB is rebuilt fresh under the new validator. Behavior should match the pre-merge dry-run exactly.

Commit A is larger than a pure "scaffolding" commit would be, but the blast radius is bounded to `catalog/claims.py` and `provenance/validation.py` plus their tests. The size is bounded because every consumer of `build_relationship_claim` / `get_relationship_namespaces` sees unchanged behavior — those functions keep their signatures and semantics; only their implementation moves.

### Registered schemas

Every catalog relationship gets a `register_relationship_schema(...)` call in `register_catalog_relationship_schemas()`, once per namespace. Identity keys (`identity is not None`) drive `build_relationship_claim`'s claim_key composition; non-identity keys are shape-validated only. Missing any of these means resolver reads for that namespace stay unvalidated and [Step 5 of ResolveHardening.md](ResolveHardening.md) can't subscript those keys safely.

- **Alias (7 schemas, one per alias namespace):** `theme_alias` (valid_subjects=(Theme,)), `manufacturer_alias` ((Manufacturer,)), `person_alias` ((Person,)), `gameplay_feature_alias` ((GameplayFeature,)), `reward_type_alias` ((RewardType,)), `corporate_entity_alias` ((CorporateEntity,)), `location_alias` ((Location,)). Each → `alias_value: str (identity="alias")`, `alias_display: str (optional)`. Dynamic discovery via `discover_alias_types()` still happens — it just calls `register_relationship_schema` instead of populating `_literal_schemas`.
- **Abbreviation (1 schema):** `abbreviation`, `valid_subjects=(Title, MachineModel)`. → `value: str (identity="value")`.
- **Parent (2 schemas):** `theme_parent` ((Theme,)), `gameplay_feature_parent` ((GameplayFeature,)). Each → `parent: int (identity="parent", fk=<self>.pk)`.
- **Location (1 schema):** `location` ((CorporateEntity,)) → `location: int (identity="location", fk=Location.pk)`.
- **Credit (1 schema):** `credit`, `valid_subjects=(MachineModel, Series)`. → `person: int (identity="person", fk=Person.pk)`, `role: int (identity="role", fk=CreditRole.pk)`.
- **Gameplay feature (1 schema):** `gameplay_feature` ((MachineModel,)) → `gameplay_feature: int (identity="gameplay_feature", fk=GameplayFeature.pk)`, `count: int | None (optional)`.
- **Simple M2M (3 schemas):** `theme`, `tag`, `reward_type` each with `valid_subjects=(MachineModel,)`. → `<namespace>: int (identity=<namespace>, fk=<target>.pk)`.
- **Media attachment (1 schema):** `media_attachment`, `valid_subjects=(<all supported subjects>)`. → `media_asset: int (identity="media_asset", fk=MediaAsset.pk)`, `category: str | None (optional)`, `is_primary: bool (optional)`.

All registered fresh in the unified API — no migration shim needed because the old registries are deleted wholesale in the same commit.

## TDD plan

Assumes the "Commit sequence" above: Commit A (registry) → Commit B (classifier + validator) → pre-merge dry-run → post-merge wipe + re-ingest. Tests land with Commit B.

1. **Commit A is not TDD-gated for new behavior** (there isn't any), but **existing `catalog/claims.py` tests are the regression gate**. The full test suite must pass green — `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys`, and all their downstream callers are rewritten to read from the unified registry, and their existing tests are what prove the rewrite preserves behavior. If a test fails, the rewrite has drifted from today's semantics — fix the rewrite, not the test.
2. **Failing tests, one per rejection mode, per path:**
   - `assert_claim` path: assert `ValidationError` raised for each of — wrong subject (`field_name` registered but `subject.content_type not in schema.valid_subjects`), non-dict value, missing `exists`, non-bool `exists`, missing required key, wrong-scalar-type required key, wrong-scalar-type optional key, `bool` passed where `int` expected, unknown key.
   - Batch path: `validate_claims_batch(...)` returns `(valid, rejected_count)` — assert `rejected_count == 1` and the malformed claim is **not** in `valid`. For rejection-reason assertions, call `validate_relationship_claims_batch(...)` directly (that function returns the rejected `list[Claim]`).
   - Classify-by-registry fix: a malformed relationship payload on a model with `extra_data` must reach the relationship validator (and be rejected), not land as `EXTRA`.
   - DIRECT precedence preserved: a `field_name` that is both a DIRECT claim field on the model **and** a name in the relationship registry must classify as `DIRECT`. (Likely synthetic — no real collision today, but pin the ordering.)
3. Implement the tightenings. Tests go green.
4. **Pre-merge dry-run:** wipe localhost DB + reset migrations, `make pull-ingest`, `make ingest`. Any rejections name an extractor bug — fix at source, re-ingest, repeat until clean.
5. **Post-merge:** same wipe + re-ingest against the shared environment.

## Files touched

**Commit A — unified registry:**

- [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — new `ValueKeySpec` / `RelationshipSchema` (namespace + `value_keys` + `valid_subjects`) / `register_relationship_schema` / `get_relationship_schema` / `is_valid_subject`, keyed by `namespace: str`. Delete `_relationship_target_registry` and the old `register_relationship_targets`. Rewrite `validate_relationship_claims_batch` internals to read `fk_target` tuples off `ValueKeySpec` entries.
- [apps/catalog/claims.py](../../../backend/apps/catalog/claims.py) — delete `RefKey`, `LiteralKey`, `_entity_ref_targets`, `_literal_schemas`, `_get_entity_ref_targets`, `_get_literal_schemas`, `register_relationship_targets`. Add `register_catalog_relationship_schemas()` with one `register_relationship_schema(...)` call per namespace. Rewrite `build_relationship_claim`, `get_relationship_namespaces`, `get_all_namespace_keys` to read from the unified registry. Alias-type dynamic discovery hooks into the new registration function.
- [apps/catalog/apps.py](../../../backend/apps/catalog/apps.py) — `CatalogConfig.ready()` calls `register_catalog_relationship_schemas()`.
- [apps/catalog/tests/test_claims.py](../../../backend/apps/catalog/tests/test_claims.py) (or wherever the existing claim-building tests live) — behavior-preserving; trivial touches if any.

**Commit B — classifier + validator:**

- [apps/provenance/validation.py](../../../backend/apps/provenance/validation.py) — `classify_claim` registry-driven; new `validate_single_relationship_claim` (including wrong-subject check).
- [apps/provenance/models/claim.py](../../../backend/apps/provenance/models/claim.py) — `assert_claim` new `RELATIONSHIP` branch calling `validate_single_relationship_claim`.
- [apps/provenance/tests/test_validation.py](../../../backend/apps/provenance/tests/test_validation.py) — new rejection-mode tests (including wrong-subject).

## Verification

- `uv run --directory backend pytest apps/provenance/tests/test_validation.py apps/catalog/tests/test_bulk_resolve*.py` — all tests pass.
- `./scripts/mypy` — baseline unchanged (this step has no mypy impact).
- **Pre-merge dry-run:** wipe localhost DB, reset migrations to 0001, `make pull-ingest`, `make ingest`. No rejections on clean data. If rejections appear, they're real malformed payloads upstream ingest is producing and must be fixed at the source before merging.
- **Post-merge:** same wipe + re-ingest against the shared environment.
- After landing (and after the post-merge wipe + re-ingest), [Step 5 of ResolveHardening.md](ResolveHardening.md) (resolver subscript flip) is unblocked.

## Relation to model-driven metadata

This registry is intentionally hand-maintained. The model-driven metadata umbrella ([ModelDrivenMetadata.md](../model_driven_metadata/ModelDrivenMetadata.md)) proposes moving these declarations onto the through-model classes as a typed `catalog_relationship_spec` ClassVar ([ModelDrivenCatalogRelationshipMetadata.md](../model_driven_metadata/ModelDrivenCatalogRelationshipMetadata.md)), derived at `ready()` and pushed into a registry that looks very much like this one. That move is deferred until a genuinely _independent_ consumer materializes — e.g. frontend edit metadata being actually built, not hypothetical.

Note the distinction: this PR's consumers (`classify_claim`, `validate_single_relationship_claim`, `validate_relationship_claims_batch`, `build_relationship_claim`, and — via Step 3's consistency test — the read-side TypedDicts) are what make the _unified registry_ pay off today. They don't meet the spec-move's ≥2-consumers bar because they're all facets of the same backend write/read path, tested against each other. The spec move is waiting for a second consumer that would motivate the richer `through_model` / `subject_fks` fields and `(namespace, subject_content_type)` keying, which this PR's consumers don't need.

The spec doc's identity-vs-UC cross-check (verifying `subject_fks ∪ identity_fields` matches one `UniqueConstraint` per through-model at `ready()`) is the piece worth lifting eventually, but it's deferred with the rest of the spec work — lifting it alone would require `through_model` and `subject_fks` on the schema and `(namespace, subject_content_type)` keying, which this PR otherwise doesn't need. When the second consumer arrives and the spec move lands, `register_catalog_relationship_schemas()` is replaced with a walk over a `ClaimThroughModel` marker base that emits the same `RelationshipSchema` objects plus the richer fields the cross-check needs. The registry interface (`get_relationship_schema`, `is_valid_subject`) stays the same; consumers don't change.
