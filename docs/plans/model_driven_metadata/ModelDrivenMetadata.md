# Model-Driven Metadata

## Principle: the model is the source of truth

**The Django model is the source of truth. Derive metadata from Django introspection whenever possible; declare only the minimum that Django can't express — and declare it as a class attribute on the model itself.**

Consequence: parallel hand-maintained registries for things Django already knows are an anti-pattern. When we encounter one, the fix is to replace it with introspection + (at most) a small class-level attr on the owning model.

This principle is the umbrella. It applies to _any_ purpose — claim serialization, link/URL construction, resolver dispatch, media behavior, frontend edit affordances, validation — not just claims. What it does **not** permit is a single grab-bag class attr that accumulates everything; that would just relocate the drift surface onto the model.

### Why

Every registry that duplicates model metadata becomes a drift surface. Adding a new catalog model today touches many places because we maintain parallel views of what's already on the model. The current inventory, grouped analytically into four clusters, lives in [ModelDrivenMetadataViolations.md](ModelDrivenMetadataViolations.md).

## One axis, one typed spec

The rule: each orthogonal concern gets its own **typed, narrowly-scoped** class attr. A concern earns a spec when it is consumed by a well-defined subsystem (the claim resolver, the link builder, the media pipeline, etc.) and has a stable shape.

### Already in the codebase

- `claim_fk_lookups` — per-model FK lookup override ("use `slug`, not `pk`").
- `MEDIA_CATEGORIES` — media-supported models only.
- `entity_type` — `LinkableModel` public identifier.

### Proposed by this doc

#### Catalog Relationships

`CatalogRelationshipSpec` — describes how a through-model maps to a claim namespace + payload; consumed by the claim resolver, provenance validation, and (eventually) frontend edit metadata.

Design: [ModelDrivenCatalogRelationshipMetadata.md](ModelDrivenCatalogRelationshipMetadata.md).

### Evaluated and deferred

#### Citation Sources

A `CitationSourceSpec` was considered for unifying citation-source-family metadata (IPDB, OPDB, Fandom). Deferred — revisit when a 3rd structured-parser source family is imminent. Two reasons, detailed in [ModelDrivenCitationSourceMetadata.md](ModelDrivenCitationSourceMetadata.md):

- **Not the same shape as `CatalogRelationshipSpec`.** Citation source families aren't models; they're rows in `CitationSource` with per-family behavior (a URL regex and a callable builder). The right pattern is a class-per-family behavior registry with a sidecar data table, not model-owned metadata. It reuses the Shape 3 machinery but isn't an instance of this doc's umbrella principle.
- **Scale doesn't warrant it yet.** Only 2 structured-parser source families exist today (IPDB, OPDB), and the backend extractor registry already absorbed part of the drift surface. A field audit against the ≥2-consumers rule shrinks the spec to `identifier_key` + `display_name` + URL-recogniser methods — real but narrow ROI.

### Possible future axes

- `edit_spec` — if/when frontend edit metadata outgrows derivation from `CatalogRelationshipSpec`.
- `link_spec` — if URL construction needs more than `entity_type` + slug.
- `media_attachment_spec` — would live in `apps.media`, not catalog. `EntityMedia`'s polymorphic `content_type` + `object_id` attachment doesn't fit `CatalogRelationshipSpec` (different app, different shape); give it its own axis in the media app if and when it earns one.

### Avoiding axis drift

Guard against dumping-ground drift: if you want to add a field to an existing spec, ask whether the consumer is the same subsystem the spec was built for. If not, it's a new axis and deserves its own attr. If a field could plausibly live in two specs, put it in the narrower one and let the broader consumer read through.

A related temptation: when frontend editing or page behavior gets complicated, it can look attractive to define a per-entity **profile object** that bundles API names, edit affordances, relationship sections, etc. into one UI-facing structure. That is fine _only_ if the profile is a derived view composed from the underlying specs + `_meta`, and stays a narrow UI/API concern. It must not become a second hand-maintained catalog registry. Defer introducing any such layer until the duplication it would eliminate is real, not speculative.

## How derivation works

### Derivation shapes

There are three derivation shapes, in increasing structure. Pick the smallest one that fits; don't reach for a typed spec when a `_meta` walk will do.

| Need                                                 | Shape             | Canonical example                                            |
| ---------------------------------------------------- | ----------------- | ------------------------------------------------------------ |
| Filter or transform of fields Django already exposes | Shape 1           | [`get_claim_fields`](../../backend/apps/core/models.py#L281) |
| One datum per model, one consumer                    | Shape 2           | `MEDIA_CATEGORIES`                                           |
| Structured metadata, multiple consumers              | Shape 3           | `CatalogRelationshipSpec`                                    |
| Metadata consumed outside Python                     | Shape 3 + codegen | `catalog-meta.ts` generator                                  |

### Shape 1 — Pure `_meta` walks (optional class-attr inputs)

When the answer is a filter or transform of information Django already carries. May also read small Shape 2 class attrs as per-model inputs (`claims_exempt` is the canonical case). Common idioms:

- **Field shape** (name, type, nullability, unique, default) → `_meta.get_field(name)`.
- **FK target + lookup** → `field.related_model` + convention ("pk" unless overridden).
- **M2M through-models** → `Model.m2m_attr.through` or explicit `through="..."` declarations.
- **Reverse relations** → `_meta.get_fields()` / attribute access.

Canonical example in the codebase: [`get_claim_fields(model)`](../../backend/apps/core/models.py#L281) — walks `_meta.get_fields()`, filters by field type and per-model `claims_exempt`, returns a dict. No registry, no caching (cheap enough to recompute), no base class. Hand-maintained lists like the cache-invalidation signal list and `_SOURCE_FIELDS` are the natural targets for this shape.

### Shape 2 — Single-purpose class attr, ad-hoc read

When one extra datum per model is enough and a single consumer reads it directly. Template:

```python
class Location(CatalogModel):
    claim_fk_lookups: ClassVar[dict[str, str]] = {"parent": "location_path"}
```

Consumers do `getattr(model, "claim_fk_lookups", {})`. Minimal ceremony, good for narrow needs (`MEDIA_CATEGORIES`, `claim_fk_lookups`, `claims_exempt`). **Not appropriate when multiple subsystems consume the same metadata** — that's the Shape 3 case.

Rules:

- Always use `ClassVar[...]` typing on the attr.
- Default via `getattr(..., default)` so models don't have to opt in.
- No registry, no discovery helper — consumers read per-model on demand.

### Shape 3 — Typed spec + registry-via-introspection

When a structured piece of metadata is consumed by multiple subsystems, or when its absence should fail at startup rather than at first request. This is the pattern proposed for `CatalogRelationshipSpec`.

#### Why one typed spec object and not N separate class attrs

- Single import to grep for.
- Single schema to evolve.
- One `ready()`-time validator asserts every member of the target set has a well-formed spec.
- Retrofitting a consolidation later would mean touching every affected model twice.

#### Canonical template

Rank-ordering the existing "correct examples" surfaced inconsistencies; this is the composite best-of:

| Concern               | Do this                                                                                                         | Why                                                                                                                             |
| --------------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Identity              | Declared class attr, typed `ClassVar[Spec]`                                                                     | Convention-based identity (e.g. deriving a namespace from `_meta.verbose_name`) is fragile; explicit declaration doesn't drift. |
| Discovery             | Recursive `__subclasses__()` walk of an abstract base, skipping `_meta.abstract == True`                        | Matches [`core/entity_types.py`](../../backend/apps/core/entity_types.py). No hand-maintained list.                             |
| Cache                 | `functools.lru_cache(maxsize=1)` on the build function                                                          | Cleaner than a module-level `None`-init global; no `global` keyword, no nullable type.                                          |
| Readiness guard       | Explicit `apps.check_apps_ready()` at the top of the build function                                             | Relying on a docstring ("must be called after app registry is ready") is how bugs ship.                                         |
| Build-time validation | Raise `ImproperlyConfigured` on: missing spec, duplicate identity, referenced fields not resolvable via `_meta` | Fails at startup instead of at first request.                                                                                   |
| Return type           | Typed `NamedTuple` or `@dataclass(frozen=True)` of derived schemas                                              | Avoids callers indexing into raw dicts.                                                                                         |
| Public API            | Single lookup function, e.g. `get_relationship_schema(namespace, content_type=None)`                            | Internals stay module-private; consumers don't know about the walk.                                                             |

#### Existing examples, ranked

- **Gold — [`core/entity_types.py`](../../backend/apps/core/entity_types.py)** — class attr + subclass walk + cache + `check_apps_ready()` + duplicate validation + typed return + tight API. Closest template to copy.
- **Silver — [`_alias_registry.py`](../../backend/apps/catalog/_alias_registry.py)** — same shape, cleaner caching (`lru_cache`), `NamedTuple` return. But derives identity from `_meta.verbose_name` (fragile) and lacks the explicit `check_apps_ready()` guard. Copy the `lru_cache` + `NamedTuple` ideas; don't copy the verbose_name convention.
- **Don't copy:** `MEDIA_CATEGORIES` + `MediaSupported` (no discovery helper, no validator); `claim_fk_lookups` (untyped ad-hoc `getattr`); `export_catalog_meta` (different axis — codegen/distribution).

#### Worked example

One Shape 3 spec is proposed, in its own sibling doc holding the concrete dataclass, per-model declarations, and derivation function:

- `CatalogRelationshipSpec` → [ModelDrivenCatalogRelationshipMetadata.md](ModelDrivenCatalogRelationshipMetadata.md) (claim-relationship metadata).

A second candidate (`CitationSourceSpec`) was evaluated and deferred — see "Evaluated and deferred" above.

## Distribution to non-Python consumers

Shapes 1/2/3 cover how Django exposes model metadata to Python runtime consumers. A separate concern: **how does that metadata reach consumers that can't import Python** — the SvelteKit frontend, the OpenAPI schema, external tools, any sibling service. Codegen is the answer; any of the three shapes can feed it.

The canonical example already in the codebase: `export_catalog_meta` generates `frontend/src/lib/api/catalog-meta.ts` from Django models. The rules generalize to any upstream shape → any downstream artifact:

- Generators read models + specs + `_meta`. They never invert the dependency.
- Generated artifacts are derived and not hand-edited; checking them into git is fine but they stay clearly downstream.
- Each generator carries a parity test that fails when the upstream shape drifts from the emitted artifact.

Reuse this pattern when a new spec has to reach another language or runtime. Do not build a parallel hand-maintained schema on the consumer side.

## Alternatives considered and rejected

### Rejected alternative: catalog metadata DSL

An alternative would be to define catalog entities, claim-controlled fields, relationship shapes, resolver behavior, API metadata, and frontend-facing metadata in a separate domain-specific schema, then generate Django models and derived code from that schema.

Appeal: one intentionally-designed source of truth could describe the whole catalog surface, including things Django cannot express. In theory, adding a new model or relationship would mean editing one schema entry and regenerating the rest.

Rejected because:

- It would create a second modeling layer above Django. We would still need to understand and debug the generated Django models, migrations, ContentTypes, admin behavior, ORM relations, and type-checking output.
- The project already has working Django model introspection patterns. Replacing those with generation would throw away useful native framework semantics instead of leaning on them.
- Code generation has its own drift surface: generator logic, generated files, migration output, handwritten escape hatches, and review diffs all become part of the maintenance burden.
- The hard cases here are not field declarations. They are semantic ownership questions: claim identity, subject side, shared namespaces, payload-only keys, resolver dispatch, and polymorphic attachments. A DSL would still need declarations for those; it would only move them farther from the models they describe.
- Retrofitting a generator into an active Django app is a large architectural commitment. The current pain can be addressed incrementally by moving small declarations onto model classes and deriving runtime schemas from `_meta`.

The model-owned metadata approach gets most of the centralization benefit while preserving Django as the actual persistence and relationship authority.

## Planning

For the current plan-of-record — ordering, dependencies, open questions ready to be worked — see [ModelDrivenMetadataPlanning.md](ModelDrivenMetadataPlanning.md). This doc stays time-invariant reference.
