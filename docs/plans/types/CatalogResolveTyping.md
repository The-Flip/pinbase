# Catalog Resolve Claim-Value Typing

Step 3 of [ResolveHardening.md](ResolveHardening.md). Defines the read-side TypedDict vocabulary for claim values in `backend/apps/catalog/resolve/*.py` and wires each resolver to `cast` to its shape. Pure claim-value shape work — helper-signature and tuple-reuse cleanup are moved to Step 4 ([CatalogResolveBaselineCleanup.md](CatalogResolveBaselineCleanup.md)).

## Context

The user's stated goal is **not** just burning down mypy entries — it's defining the types _up front_ before wiring, to avoid the reverse-engineering pattern from the catalog-app refactor.

Today, `claim.value` is `object` (JSONField payload) and is accessed with string keys across ~10 resolvers. Shape knowledge is implicit at every call site. This step makes that knowledge explicit: 7 TypedDicts, one per distinct relationship-claim payload shape, mirrored to the registry Step 2 ([ProvenanceValidationTightening.md](ProvenanceValidationTightening.md)) establishes, with a consistency test enforcing the mirror.

[\_media.py](../../../backend/apps/catalog/resolve/_media.py) is already the cleanest file — 5 NamedTuples in place — and serves as the shape target for the rest.

## Scope — behavior-preserving

Pure typing work. No resolver logic changes. `.get()` reads stay byte-identical — the subscript flip for Required keys is Step 5's work ([ResolverReadsTightening.md](ResolverReadsTightening.md)), not this step's. Helper-signature and tuple-reuse cleanup also stay out — that's Step 4.

## Prerequisites

[ProvenanceValidationTightening.md](ProvenanceValidationTightening.md) (Step 2) lands first. This plan's TypedDicts mirror the registry schemas Step 2 establishes — required/optional/type per value_key must match. Serializing the two steps means the contract is settled at implementation time, not guessed at design time.

The TypedDicts mark `exists` and FK keys as Required — that's the post-Step-2 wire contract. This step still reads with `cast + .get()` (not subscript) to keep the runtime-adjacent subscript flip out of this typing diff — Step 5 does the flip in isolation.

## Approach

### Phase A — Define the claim-value vocabulary up front

New module `backend/apps/catalog/resolve/_claim_values.py` with **7 TypedDicts**, one per distinct JSON payload shape. No wiring yet — lands in isolation so the vocabulary is reviewable on its own.

| TypedDict                   | Used by                                                              | Required                                   | `NotRequired`                               |
| --------------------------- | -------------------------------------------------------------------- | ------------------------------------------ | ------------------------------------------- |
| `GameplayFeatureClaimValue` | `resolve_all_gameplay_features`                                      | `gameplay_feature: int`, `exists: bool`    | `count: int \| None`                        |
| `CreditClaimValue`          | `resolve_all_credits`                                                | `person: int`, `role: int`, `exists: bool` | —                                           |
| `AbbreviationClaimValue`    | `resolve_all_title_abbreviations`, `resolve_all_model_abbreviations` | `value: str`, `exists: bool`               | —                                           |
| `AliasClaimValue`           | `_resolve_aliases` (6 alias resolvers)                               | `alias_value: str`, `exists: bool`         | `alias_display: str`                        |
| `ParentClaimValue`          | `_resolve_parents`                                                   | `parent: int`, `exists: bool`              | —                                           |
| `MediaAttachmentClaimValue` | `resolve_media_attachments`                                          | `media_asset: int`, `exists: bool`         | `category: str \| None`, `is_primary: bool` |
| `LocationClaimValue`        | `resolve_all_corporate_entity_locations`                             | `location: int`, `exists: bool`            | —                                           |

**`exists` is Required on all 7 TypedDicts.** Post-Step-2, [classify_claim](../../../backend/apps/provenance/validation.py#L86) + the shared relationship validator guarantee every relationship-claim row has `exists: bool`.

**`LocationClaimValue` is a relationship claim, not DIRECT.** `CorporateEntity` at [manufacturer.py:129](../../../backend/apps/catalog/models/manufacturer.py#L129) has no `location` column; the payload materializes `CorporateEntityLocation` rows. Step 1 (commit `e1d8886e`) added the `exists=False` retraction handling; the TypedDict models the post-Step-1 wire shape.

**No `M2MClaimValue` TypedDict.** The generic resolver [\_resolve_machine_model_m2m](../../../backend/apps/catalog/resolve/_relationships.py#L86) reads the payload with a runtime key (`val[spec.field_name]`), which TypedDict can't express. Use `Mapping[str, object]` + `type(target_pk) is int` narrowing in that one helper. The field-specific TypedDicts above cover the non-generic relationship resolvers.

**Placement** — `resolve/_claim_values.py` for now. These are read-side only. If a future step types the claim _builders_ in `apps.catalog.claims`, moving the types to `apps.catalog.claims.types` is a rename.

**Consistency test.** Add a unit test in `backend/apps/catalog/resolve/tests/test_claim_values.py` (new file) that iterates each TypedDict in `_claim_values.py`, looks up the matching `RelationshipSchema` from `provenance.validation.get_relationship_schema(namespace)`, and asserts the key sets + types + required/optional flags match. Catches TypedDict-vs-schema drift at test time rather than leaving it to bite at runtime during Step 5's subscript flip.

**Limit of the consistency test — state it explicitly.** The test proves that _each defined TypedDict_ matches its registry namespace. It does NOT prove that every resolver uses the _right_ TypedDict for the namespace it's resolving. A resolver writing `cast(CreditClaimValue, claim.value)` on a `theme` claim would pass mypy and pass this test. That gap is fixable (e.g. a namespace→TypedDict dispatch) but not in scope; for now, the cast site itself is the editorial checkpoint.

**Done when:** `_claim_values.py` exists, the consistency test passes, mypy + tests pass, no baseline delta.

### Phase B — Wire resolvers to their TypedDicts

Per-resolver-family commits in this order (smallest blast radius first):

1. `_media.py` — `resolve_media_attachments` → `MediaAttachmentClaimValue`.
2. `_relationships.py` simple-M2M family — `resolve_all_themes` / `_tags` / `_reward_types` share the generic `_resolve_machine_model_m2m` helper. No TypedDict here; use `val: Mapping[str, object]` + `type(target_pk) is int` narrowing. `resolve_all_gameplay_features` → `GameplayFeatureClaimValue`.
3. `_relationships.py` credits — `resolve_all_credits` → `CreditClaimValue`.
4. `_relationships.py` abbreviations — both resolvers → `AbbreviationClaimValue`.
5. `_relationships.py` aliases + parents — `_resolve_aliases` → `AliasClaimValue`, `_resolve_parents` → `ParentClaimValue`.
6. `_relationships.py` CE locations — `resolve_all_corporate_entity_locations` → `LocationClaimValue`.

**`cast` names the shape; keep every `.get()`.** Defensive reads for required keys stay in place — flipping `.get("person")` to `val["person"]` would turn any pre-Step-2 row into a KeyError mid-bulk-resolve. `cast` is documentation-only for now; Step 5 does the subscript flip once Step 2's runtime guarantees are in place _and_ the post-Step-2 wipe + re-ingest has rebuilt stored rows.

```python
val = cast(CreditClaimValue, claim.value)
if not val.get("exists", True):
    continue
person_pk = val.get("person")      # stays .get()
role_pk   = val.get("role")
if person_pk not in valid_person_pks:
    ...
```

```python
val = cast(MediaAttachmentClaimValue, claim.value)
asset_pk = val.get("media_asset")          # stays .get()
category = val.get("category")
is_primary = val.get("is_primary", False)
```

The TypedDict Required/NotRequired split still encodes the true post-Step-2 wire shape — that's what mypy sees when it checks `val.get("person")` (returns `int | None` here because `.get()` without default widens the type). Callers doing `if person_pk is None: continue` or `if person_pk not in valid_person_pks` narrow from there, same as today.

**Done when:** each resolver has `cast(<Schema>, claim.value)` at the top of its loop body. Every existing `.get()` call, skip-on-None check, and PK-validity narrow stays byte-identical.

## Ordering

A → B. A is independent, small, reviewable. B depends on A.

## Critical files

- `backend/apps/catalog/resolve/_claim_values.py` — **new**, the vocabulary module.
- `backend/apps/catalog/resolve/_relationships.py` — bulk of the wiring.
- `backend/apps/catalog/resolve/_media.py`, `_entities.py`, `__init__.py` — smaller wiring passes.
- `backend/apps/catalog/resolve/tests/test_claim_values.py` — **new**, consistency test.

## Reuse

- `HasEffectivePriority` from [apps/provenance/typing.py](../../../backend/apps/provenance/typing.py) — existing protocol, one read site in `_media.py` keeps its `cast`.
- `ClaimIdentity` / `EntityKey` from [apps/core/types.py](../../../backend/apps/core/types.py) — already used in `_media.py`; carry the pattern.
- NamedTuple shapes in `_media.py` (`CtInfo`, `PrimaryCandidate`, `AttachmentTimestamp`, `MediaRowState`, `EntityCategoryKey`) — the template for any incidental tuple-shape cleanup that falls out.

## Non-goals

- Not introducing dataclass factories or Pydantic Schemas for claim values. Rejected: once Step 2 lands, the write path validates every shape; a read-side validator would be a second source of truth with no correctness win.
- Not refactoring `_resolve_single` / `_resolve_bulk` / `_apply_resolution` architecturally.
- Not consolidating the three parallel M2M / abbreviation / alias diff-and-apply patterns — larger refactor, out of scope.
- Not touching helper signatures or tuple-reuse cleanup — those are Step 4 ([CatalogResolveBaselineCleanup.md](CatalogResolveBaselineCleanup.md)).
- Not flipping required-key reads to subscript — that's Step 5 ([ResolverReadsTightening.md](ResolverReadsTightening.md)).
- Not closing the cast-site correctness gap (wrong TypedDict for the namespace being resolved). Acknowledged in the Phase A consistency-test note.

## Verification

- `./scripts/mypy` — expect baseline `new: 0`.
  - After A: unchanged baseline (no wiring).
  - After B: claim-value-shape entries on resolver files cleared; helper-signature + tuple-reuse entries still outstanding (Step 4 clears those).
- `uv run --directory backend pytest apps/catalog/tests/test_resolve*.py apps/catalog/tests/test_bulk_resolve*.py apps/catalog/resolve/tests/test_claim_values.py` — behavior-preserving plus the new consistency test.
- `make ingest` end-to-end — exercises real bulk-resolution paths against R2 data. Not gating, but the natural integration test.
- After each phase, sync baseline with `uv run --directory backend mypy --config-file pyproject.toml . 2>&1 | uv run --directory backend mypy-baseline sync` once `./scripts/mypy` reports `new: 0`.

## Design decisions locked in after review

- **TypedDicts (not dataclass factories or Pydantic Schemas).** Read-side shape documentation only; zero runtime cost. Factories would duplicate write-path validation (post-Step-2).
- **`cast` is documentation-only in this step.** `.get()` stays everywhere, required and optional alike. Subscript flip for required keys happens in Step 5.
- **`exists` is Required on all 7 TypedDicts.**
- **No `M2MClaimValue` TypedDict.** Generic M2M resolver uses `Mapping[str, object]` + `isinstance`.
- **TypedDicts live in `resolve/_claim_values.py` for now.** Move to `apps.catalog.claims.types` later if claim builders get typed.
- **Consistency test does not cover cast-site correctness.** See Phase A note — that gap is acknowledged and not closed here.
