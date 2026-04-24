# Model-Driven Catalog Relationships

Sibling doc to [ModelDrivenMetadata.md](ModelDrivenMetadata.md). The umbrella doc establishes the principle ("Django model is source of truth; one axis, one typed spec"). This doc is the design for the `catalog_relationship_spec` axis — the typed spec that replaces the six drift surfaces catalogued as Cluster 1 in the umbrella.

## Scope

`catalog_relationship_spec` describes how a **catalog-app through-model** maps to a claim namespace + payload. Consumed by the claim resolver, provenance validation, and (eventually) frontend edit metadata.

Explicitly **out of scope**:

- **`EntityMedia`** (lives in `apps.media`). `apps.media` is peer-isolated from `apps.catalog` per [AppBoundaries.md](../../AppBoundaries.md); declaring a catalog-owned spec on a media-app model would violate that boundary. Media attachment gets its own axis (likely `MediaAttachmentSpec` in the media app) if and when it needs one.
- **Alias models** (ThemeAlias, GameplayFeatureAlias, etc.). These are flat FK rows, not through-models. They already have their own discovery pattern in `_alias_registry` and a different claim shape. Covering them would require a second set of fields on the spec; keep them on a separate axis.

This doc does **not** redesign [ProvenanceValidationTightening.md](../types/ProvenanceValidationTightening.md) or [CatalogResolveTyping.md](../types/CatalogResolveTyping.md) — those are downstream consumers. It also does not design `citation_source_spec`; that's a separate axis and will get its own sibling doc.

## What this replaces

Six Cluster 1 violations from [ModelDrivenMetadataViolations.md](ModelDrivenMetadataViolations.md):

- `_entity_ref_targets`
- `_literal_schemas`
- `_relationship_target_registry`
- `M2M_FIELDS`
- `_parent_dispatch`
- `_custom_dispatch`

Every one answers the same question in a different dialect: _given a claim namespace, what through-model does it live on, and how do I build/resolve/validate it?_ `CatalogRelationshipSpec` subsumes all six. Bespoke-resolver dispatch state (current `_custom_dispatch` stores `(entity model, resolver function name, id kwarg name)`) is orthogonal to the spec — see "Resolver signature standardization" below.

## The spec

### Example

```python
class MachineModelGameplayFeature(models.Model):
    ...
    catalog_relationship_spec: ClassVar[CatalogRelationshipSpec] = CatalogRelationshipSpec(
        namespace="gameplay_feature",
        subject=SingleSubject("machinemodel"),
        value_key_overrides={"gameplayfeature": "gameplay_feature"},
        optional_value_fields=("count",),
        # resolver defaults to None → use the generic spec-driven resolver
    )


class Credit(models.Model):
    ...
    catalog_relationship_spec: ClassVar[CatalogRelationshipSpec] = CatalogRelationshipSpec(
        namespace="credit",
        subject=XorSubject(("model", "series")),
        resolver=resolve_credits,  # bespoke: XOR branch write
    )
```

### Design rule: identity is derived, not declared

The non-subject fields that compose the claim_key identity are always `UniqueConstraint.fields − subject.fks`. They are **not** declared on the spec; they are derived at `ready()` time from the model's `UniqueConstraint`(s) and cross-checked there. Declaring identity separately would just re-encode what the DB constraint already states and create a new drift surface between the two.

The `ready()`-time validator asserts:

1. Exactly one `UniqueConstraint` (or, for XOR subjects, exactly one conditional UC per subject branch) whose fields are a superset of the subject fields.
2. The non-subject residual is consistent across branches (XOR case).
3. All referenced field names resolve via `_meta`.

Any mismatch raises `ImproperlyConfigured` at startup.

### Fields

- **`namespace`** — the namespace string, often differs from the Django field name (`"gameplay_feature"` vs field `gameplayfeature`). `"abbreviation"` is shared across `TitleAbbreviation` and `MachineModelAbbreviation` — runtime lookup is keyed by `(namespace, subject_content_type)` for shared-namespace cases.
- **`subject`** — a tagged union declaring which FK(s) point to the parent/owner rather than the identity side. Django can't tell these apart, and self-parent through-models (`ThemeParent` after promotion) have two FKs to the same model that are only distinguishable semantically. Two variants:
  - **`SingleSubject(fk_name)`** — one FK names the subject, e.g. `SingleSubject("machinemodel")`. Covers the vast majority of through-models.
  - **`XorSubject((fk_a, fk_b))`** — exactly one of two nullable FKs is non-null per row (e.g. `Credit.model` XOR `Credit.series`). Validator requires both a matching pair of conditional `UniqueConstraint`s and a `CheckConstraint` enforcing the XOR.
  - Polymorphic subjects (`ContentType` + `object_id`) are **not** in the spec — the only catalog-app case would have been `EntityMedia`, which is out of scope.
- **`value_key_overrides`** — map from Django field name to JSON value_key when they differ.
- **`optional_value_fields`** — model fields that participate in the claim payload as optional keys (`count` on `MachineModelGameplayFeature` is the only current example) vs. pure model bookkeeping. Fields in this set are neither subject nor identity; they're non-identity stored state written from the claim payload.
- **`resolver`** — optional `Callable | None`, defaults to `None`. `None` means "use the generic spec-driven resolver" — the dispatcher reads the spec (subject, identity-from-UC, `optional_value_fields`) and does the standard claim-winners → through-rows sync. A non-`None` value is a bespoke resolver for cases the generic path can't express (e.g. `Credit`'s XOR branch write, `ModelAbbreviation`'s cross-table dedup against `TitleAbbreviation`). Bespoke resolvers take a canonical `(subject_ids: set[int] | None = None) -> None` signature.

Not currently a field: there's no `extra_value_fields` for claim-payload-only keys that aren't model fields. The original motivating example (`alias_display`) lives on alias models, which are out of scope. Reinstate if a real need emerges inside the through-model set.

There is also no `id_kwarg`. The current `_custom_dispatch` carries a per-resolver kwarg name (`model_ids` vs `entity_ids`) because today's bespoke resolvers were written without a naming convention. That indirection disappears once bespoke resolvers all take `subject_ids`.

## Prerequisite: promote self-parent M2Ms

Most M2Ms in this codebase already use explicit through-models (`MachineModelTheme`, `Credit`, `CorporateEntityLocation`, etc.). The only hidden auto-throughs are the self-parent M2Ms on `Theme.parents` and `GameplayFeature.parents`. For `CatalogRelationshipSpec` to hang off every claim-bearing relationship uniformly, those two need explicit through-models (`ThemeParent`, `GameplayFeatureParent`). Pre-launch and DB-resettable, so migration cost is essentially zero.

## Worked inventory

The full inventory of catalog-app through-models and their proposed `CatalogRelationshipSpec` literals has been sketched and cross-checked against current `UniqueConstraint`s. All ten (including the two self-parents after promotion) fit the spec shape above, with identity derivable from `UniqueConstraint` in every case. Credit's XOR validates by walking both conditional UCs and asserting the non-subject residual is consistent.

**One finding worth flagging separately:** Credit appears in `_entity_ref_targets` but not in `M2M_FIELDS` or `_custom_dispatch`. Its resolution path today may only cover MachineModel credits, not Series credits. Verify current behavior before claiming the new spec subsumes Credit — this is a pre-existing gap, not a spec-design issue, but it will surface when we cut over.

## Resolver strategy

A separate audit of all bespoke resolvers in `backend/apps/catalog/resolve/` showed that the apparent signature diversity is mostly cosmetic: `model_ids` vs `entity_ids` is pure naming; one unused stats-dict return can be dropped; entity-type hardcoding goes away once the dispatcher picks the spec by `(namespace, subject_content_type)`; self-referential column naming disappears once `Theme.parents` and `GameplayFeature.parents` are promoted to explicit through-models.

The stronger finding: **most bespoke resolvers disappear entirely** once the generic resolver reads the spec. Theme, tag, reward_type, corporate-entity-location, gameplay_feature (its `count` fits `optional_value_fields`), and the promoted parent through-models all collapse into one spec-driven generic resolver. The only remaining bespoke cases are those with internal semantic logic that can't be expressed declaratively:

- **`Credit`** — XOR subject write (which FK branch gets populated per row)
- **`ModelAbbreviation`** — cross-table dedup against `TitleAbbreviation` (a model abbreviation is suppressed if its title already has that abbreviation)

Possibly one or two more will surface during implementation. Those cases carry `resolver=…` on the spec; everything else defaults to `None` and goes through the generic path.

Cost: a bounded signature-refactor sweep (rename `entity_ids` → `subject_ids`, drop the one unused return, thread the spec into the generic resolver). `_custom_dispatch`, `_parent_dispatch`, and most of `M2M_FIELDS` go away.

## Open design questions

### App boundary: catalog vs. provenance

`AppBoundaries.md` keeps provenance peer-isolated from catalog. The current `_relationship_target_registry` mechanism preserves this via _inversion_: catalog's `ready()` calls `register_relationship_targets()` to push mappings into provenance; provenance never imports catalog.

A naïve reading of "validation reads derived schemas from model-owned specs" would break that boundary. The preserved design is:

1. Catalog app's `ready()` walks claim through-models, derives `RelationshipSchema` instances from each `CatalogRelationshipSpec` + `_meta`.
2. Catalog pushes those derived schemas into a narrow provenance-side registry API (same shape as today, narrower contract).
3. Provenance validates against its registry without importing catalog models.

The spec stays model-owned (what this doc argues for); provenance stays peer-isolated (what AppBoundaries.md requires). The boundary-preserving push pattern must stay — see the Implications section below for how it fits with ProvenanceValidationTightening's rewrite.

## Implications for ProvenanceValidationTightening.md

[ProvenanceValidationTightening.md](../types/ProvenanceValidationTightening.md) as currently designed proposes a unified `_relationship_schemas` registry — one registry to replace three. That's strictly better than the status quo, but per the umbrella principle, it's still the wrong shape.

Redesigned under this principle:

- No catalog-shaped `_relationship_schemas` registry inside provenance. A narrower provenance-side registry of `RelationshipSchema` instances remains — populated by catalog at `ready()` time, not hand-maintained — so the app boundary stays intact (see the "App boundary" open question above).
- Every claim through-model — including the newly-explicit `ThemeParent` and `GameplayFeatureParent` — declares a single `catalog_relationship_spec = CatalogRelationshipSpec(...)` class attr.
- Catalog's `ready()` walks claim through-models, derives `RelationshipSchema` instances from `_meta` + each declared `CatalogRelationshipSpec` (including deriving identity from `UniqueConstraint` − `subject.fks`), and pushes them into the provenance-side registry via a narrow API. Keyed by `(namespace, subject_content_type)` for shared-namespace cases like `abbreviation`.
- Catalog-side `ready()` validator asserts every claim through-model declares a `CatalogRelationshipSpec`, that referenced fields resolve via `_meta`, and that the declared subject matches the model's `UniqueConstraint` shape (one matching UC for `SingleSubject`; matching conditional UCs plus an XOR `CheckConstraint` for `XorSubject`).
- Provenance validates against its registry; same rejection conditions as currently specced. Provenance does not import catalog models.
- **Two small migrations** to promote `Theme.parents` and `GameplayFeature.parents` to explicit through-models (see "Prerequisite" above).

ProvenanceValidationTightening scope becomes: derive relationship schemas from model-owned `CatalogRelationshipSpec`s + tighten validation with the new derived schemas + the two promotion migrations. [CatalogResolveTyping.md](../types/CatalogResolveTyping.md)'s TypedDicts are still useful; the "consistency test" now compares TypedDict shapes against derived schemas (same idea, different source).

Net effect: one `CatalogRelationshipSpec` per through-model, two small migrations, **fewer** total new lines of code because the registry infrastructure disappears.

## Alternatives considered and rejected

### Abstract base classes

One alternative to `CatalogRelationshipSpec`-as-data is `CatalogRelationshipSpec`-as-type-hierarchy: `ClaimThroughModel(ABC)` with `EntityRefClaim`, `LiteralClaim`, `RelationshipClaim` subclasses, each enforcing its own shape via abstract methods. Appeal: shape mismatches become import-time errors rather than first-request, and shared-namespace / XOR cases become explicit subclasses rather than conditional logic in a generic resolver.

Rejected because:

- The declarative data object can do the same validation at `ready()` time — startup failure is close enough to import-time failure for this use case.
- Several through-models straddle categories (shared-namespace abbreviations are part literal, part entity-ref-ish), which would force either awkward multiple inheritance or a catch-all subclass that defeats the point.
- Inheritance imposes a taxonomy that will fight future claim shapes; a data object lets new fields be added without moving classes around.

Data object wins on flexibility; ABC hierarchy would lock in a taxonomy we don't yet trust.

### Consolidated relationship registry

Another alternative would be to accept the registry shape but consolidate the current scattered relationship metadata into a single richer registry. This was the direction proposed by [ProvenanceValidationTightening.md](../types/ProvenanceValidationTightening.md): replace `_entity_ref_targets`, `_literal_schemas`, and `_relationship_target_registry` with one authoritative `_relationship_schemas` structure.

Appeal: it is smaller than a model-owned metadata rewrite, reduces today's most obvious duplication, and gives validation/resolution/frontend metadata a single runtime schema to read.

Rejected because:

- It preserves the wrong ownership model. The registry would still be a second catalog schema beside the Django models.
- It improves the number of registries but not the core drift risk: adding or changing a relationship still requires remembering to update a separate map away from the model/through-model that actually defines the relationship.
- It would likely become attractive as a dumping ground for resolver and frontend behavior because it sits in the middle of many consumers.

This can still be useful as a temporary migration bridge if a direct model-owned rewrite is too large, but it should not be the final architecture.
