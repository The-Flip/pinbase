# Model-Driven Citation Source Metadata

Sibling doc to [ModelDrivenMetadata.md](ModelDrivenMetadata.md). The umbrella doc establishes the principle ("Django model is source of truth; one axis, one typed spec"). This doc is the design for the `citation_source_spec` axis — the typed spec that unifies the citation-source identity metadata currently scattered across extractor code, Django model fields, CHECK constraints, and seed data.

## Scope

`citation_source_spec` describes a citation source family — IPDB, OPDB, Fandom, etc. Consumed by:

- URL recognition (extractors)
- Ingest adapters (1:1 with source families)
- The `Citation` model + `identifier_key_valid` CHECK constraint
- Seed data
- Source-priority ranking (claim conflict resolution)
- Display / branding in the UI

The "citation" qualifier is deliberate: "source" is overloaded in this codebase — ingest sources, claim sources, data sources. `CitationSourceSpec` names the specific concept without collision.

This doc does **not** redesign the extractor, the `Citation` model, or ingest adapters — those are downstream consumers. It also does not design `catalog_relationship_spec`; that's a separate axis with its own sibling doc ([ModelDrivenCatalogRelationshipMetadata.md](ModelDrivenCatalogRelationshipMetadata.md)).

## What this replaces

One Cluster 2 violation from [ModelDrivenMetadataViolations.md](ModelDrivenMetadataViolations.md), plus partial overlap with Cluster 4:

- **Cluster 2 (row 7) — `identifier_key` touch-points.** Four hand-maintained locations today: the `EXTRACTORS` dict in `citation/extractors.py`, the `IdentifierKey` `TextChoices` enum in `citation/models.py`, the `identifier_key_valid` CHECK constraint, and the website seed data. Adding a new source family requires coordinated updates across all four.
- **Cluster 4 (row 10) — adapter `resolve_hooks`.** Not a pure Cluster 2 violation — each adapter picks a subset of resolvers based on what it actually writes — but the _available set_ of resolvers per source is metadata this spec can own. Revisit once `CitationSourceSpec` and `CatalogRelationshipSpec` both exist.

### Migration story: the CHECK constraint is not runtime-derivable

A realistic constraint on the "one source of truth" promise: `identifier_key_valid` is a Django migration artifact. Its allowed-values list is baked into SQL, not read from code at runtime. Adding a new source family therefore cannot be _just_ declaring a new subclass — the CHECK still needs a generated migration.

What the registered set realistically owns:

- Runtime-only consumers (extractor registration, URL recognition, seed data filter, UI display) derive directly from the registered subclasses at `ready()` time.
- Migration-state consumers (the `IdentifierKey` `TextChoices` values and the `identifier_key_valid` CHECK constraint) are _driven_ by the registered set via `makemigrations` — the migration author regenerates them from the current registered set rather than hand-editing either location.

Net effect: four touch points collapse to two (subclass declaration + `makemigrations` run) rather than one. Still a meaningful improvement; the doc should say so precisely rather than overclaim a fully-runtime-derived constraint.

## Open design question: where does the spec live?

The spec's consumers span multiple layers (extractor code, Django model, DB constraints, seed data, UI), so the ownership choice is non-trivial. Three candidates, not yet decided:

1. **On the adapter class.** Each ingest adapter is 1:1 with a source family; colocating the spec with URL-recognition code keeps related logic together. But the `Citation` model and the CHECK constraint can't cleanly import adapters (layering).
2. **On `CitationSource` Django model rows.** Best fits the "model is source of truth" principle — citation-source data lives as data. But `recognize_url` is code, not data, so it can't live here. Splits the spec across data + code boundaries awkwardly.
3. **On a registered `CitationSource` class (new).** A class-based registry where each source family subclasses a common abstract base. The Django `CitationSource` model is auto-populated from the registered set. Keeps code and data together; matches the Shape 3 canonical template (class attr + `__subclasses__()` walk) exactly.

Option 3 reads best but this is a structural decision about how the citation subsystem's layering works, not a naming tweak. Defer until `CatalogRelationshipSpec` is settled — both specs want the same `ready()`-validator and derivation-helper machinery, and using the second axis as a sanity check on that machinery before committing is the point.

## Prerequisites

- `CatalogRelationshipSpec` design settled in [ModelDrivenCatalogRelationshipMetadata.md](ModelDrivenCatalogRelationshipMetadata.md). The Shape 3 machinery (`ready()`-time validator, derivation helper, canonical build pattern) gets prototyped there first; this axis reuses it.
