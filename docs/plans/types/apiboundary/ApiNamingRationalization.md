# API Schema Naming Rationalization

## Context

The Django Ninja schema names that flow through OpenAPI into the
generated TypeScript types are inconsistent. Today the contract
carries:

- 117 names ending in `Schema` (the Ninja base class).
- 18 names that don't — split between intentional choices (`Ref`,
  `JsonBody`), divergent media-app conventions (`UploadOut`,
  `MediaAssetRefIn`, `RenditionUrlsOut`, `AttachmentMetaOut`), and
  generic Python-side leakage (`Input`, `SearchResponse`).
- Schemas with too-generic bare names that survive suffix removal
  poorly (`Variant`, `Source`, `Stats`, `Recognition`, `Create`).
- Schemas defined inline in endpoint files that don't follow the
  schema-module convention (out of scope for this plan; see
  follow-ups).

The OpenAPI contract is the shared vocabulary between Django, the
generated TypeScript types, ~88 frontend consumers, and any AI agent
reading the codebase. When the same role takes different suffixes
depending on which app a schema lives in, every contributor has to
learn the per-app convention before they can type anything correctly.
Generic names like `Input`, `Source`, `Stats` are worse: at the
OpenAPI component level they're ambiguous, and a frontend reader
can't tell what they refer to without grepping the backend.

We will rationalize the names at the source — in the backend Python
classes — so the OpenAPI contract, the generated `schema.d.ts`, and
the frontend imports all use the same vocabulary. The rule is
**every Ninja `Schema` subclass ends in `Schema`** (with two
deliberate exceptions, below). This matches Django Ninja's own
documentation, which adopts the `Schema` suffix specifically to
disambiguate wire shapes from Django models when the bare name would
collide. We have the same collision throughout `provenance` and
`citation` (`ChangeSet`, `Claim`, `CitationInstance`, `Source`, …
all exist as both ORM models and wire shapes), and the `Schema`
suffix is the cleanest way to keep them unambiguous in Python _and_
in cross-stack grep.

This doc is the rules-and-tables source for the rename. The
process — when, in what commit, with what codemod — lives in
[ApiSvelteBoundary.md](ApiSvelteBoundary.md).

## Naming convention

These rules apply to every Ninja schema class in `backend/apps/*`
and `backend/config/api.py`.

### Suffixes by role

| Role                                  | Suffix                | Example                                                   |
| ------------------------------------- | --------------------- | --------------------------------------------------------- |
| Output, full entity (detail)          | `…DetailSchema`       | `TitleDetailSchema`, `PersonDetailSchema`                 |
| Output, list/index page row           | `…ListItemSchema`     | `TitleListItemSchema`, `PersonListItemSchema`             |
| Output, grid view row                 | `…GridItemSchema`     | `PersonGridItemSchema`                                    |
| Output, paginated/wrapped list        | `…ListSchema`         | `ModelListSchema` _(if such a wrapper appears in future)_ |
| Output, minimal reference (name+slug) | `EntityRef` or `…Ref` | `EntityRef`, `TitleRef`, `ModelRef`                       |
| Input, full payload                   | `…InputSchema`        | `ChangeSetInputSchema`, `CreditInputSchema`               |
| Input, partial update                 | `…PatchSchema`        | `ClaimPatchSchema`, `TitleClaimPatchSchema`               |
| Input, create payload                 | `…CreateSchema`       | `SystemCreateSchema`                                      |

### Hard rules

1. **Every Ninja `Schema` subclass ends in `Schema`.** It marks
   "this is a wire shape," disambiguates from Django model classes
   that share the bare name, and gives the boundary test one rule
   to assert. Two exceptions:
   - **`*Ref` shapes are bare** (no `Schema` suffix). The `Ref`
     suffix already self-identifies the class as a wire-shape
     reference (`{name, slug}` and minor variants). Examples:
     `EntityRef`, `TitleRef`, `ModelRef`, `LocationAncestorRef`,
     `LocationChildRef`, `CorporateEntityLocationAncestorRef`,
     `GameplayFeatureRef`. This includes `…AncestorRef` /
     `…ChildRef` family members.
   - **`JsonBody` is exempt** — it is not a `Schema` subclass at
     all (PEP 695 type alias for arbitrary JSON objects). See
     §_Ghost-type fixes_.
2. **No `In`/`Out` abbreviations.** Inputs use `…InputSchema` (or
   `…PatchSchema` / `…CreateSchema`). Outputs drop the direction
   marker entirely — the role suffix already implies output. The
   media app's current `In`/`Out` names are migrated.
3. **No bare entity names.** Where an entity's "bare" schema today
   is actually a list-item shape (e.g., today's `PersonSchema`,
   `ManufacturerSchema`), it gets renamed to `…ListItemSchema`.
   The bare name slot stays vacant; a future pass can decide
   whether to alias `Person` → `PersonDetail` or leave them
   distinct.
4. **Generic names get scoped.** `Variant`, `Source`, `Stats`,
   `Recognition`, `Create`, and `SearchResponse` are too generic at
   the OpenAPI component level. Each is renamed to an
   entity-scoped name.

### Page-vs-resource note

[docs/ApiDesign.md](../../../ApiDesign.md) draws a sharp distinction
between resource APIs (`/api/<entity>/...`) and page APIs
(`/api/pages/<entity>/...`), with page endpoints returning
"page models." In practice, every `*DetailSchema` in the codebase
today is shared between the two — the page endpoint returns the
same shape as the resource detail endpoint. This plan does not
attempt to separate them. The rename preserves whatever sharing
exists; if a future pass splits page models from resource shapes,
it will introduce new `…PageSchema` schemas alongside the
`…DetailSchema` ones.

## Decisions baked into the rename table

These are settled in this plan; the per-app rename tables below
apply them mechanically.

| Current name               | New name                              | Why                                                                                                                                                                                                                         |
| -------------------------- | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VariantSchema`            | `ModelVariantSchema`                  | Bare `Variant` is too generic; the user reserves "variant" for machine-model variants specifically. `MachineModel` is reserved for the Django model class and never appears in wire vocabulary; the wire side uses `Model`. |
| `SourceSchema`             | `CitationSourceSchema`                | Bare `Source` is too generic and collides with the `apps.citation.models.CitationSource` model name.                                                                                                                        |
| `StatsSchema`              | `SiteStatsSchema`                     | Bare `Stats` is too generic. The schema lives in `config/api.py` and reports site-wide totals.                                                                                                                              |
| `RecognitionSchema`        | `CitationRecognitionSchema`           | Bare `Recognition` is too generic; clearly a citation-domain schema.                                                                                                                                                        |
| `Ref`                      | `EntityRef`                           | Bare `Ref` is too generic at the OpenAPI level. `EntityRef` makes the role explicit; stays bare under the `*Ref` exception.                                                                                                 |
| `Input` (auto)             | (already fixed as `PaginationParams`) | Renamed to `PaginationParamsSchema` here for the universal-`Schema` rule (see §Ghost-type fixes).                                                                                                                           |
| `JsonBody`                 | (kept as-is)                          | Intentional shared name for arbitrary JSON-object fields; not a `Schema` subclass. See §_Ghost-type fixes_.                                                                                                                 |
| `UploadOut`                | `UploadSchema`                        | Drop redundant `Out`; outputs don't carry a direction marker.                                                                                                                                                               |
| `MediaAssetRefIn`          | `MediaAssetInputSchema`               | Expand `In` → `Input`; add `Schema`. (`MediaAssetRef` is not the trailing token, so the `*Ref` exception doesn't apply.)                                                                                                    |
| `AttachmentMetaOut`        | `AttachmentMetaSchema`                | Drop redundant `Out`.                                                                                                                                                                                                       |
| `RenditionUrlsOut`         | `RenditionUrlsSchema`                 | Drop redundant `Out`.                                                                                                                                                                                                       |
| `BatchCitationInstanceOut` | `CitationInstanceBatchSchema`         | Drop redundant `Out`.                                                                                                                                                                                                       |
| `CitationInstanceCreateIn` | `CitationInstanceCreateSchema`        | Drop redundant `In` — `Create` already implies input.                                                                                                                                                                       |
| `CreditInput`              | `CreditInputSchema`                   | Add `Schema` for consistency.                                                                                                                                                                                               |
| `GameplayFeatureInput`     | `GameplayFeatureInputSchema`          | Add `Schema` for consistency.                                                                                                                                                                                               |
| `EditCitationInput`        | `CitationReferenceInputSchema`        | Add `Schema` for consistency.                                                                                                                                                                                               |
| `EditOptionItem`           | `EditOptionSchema`                    | Drop redundant `Item`; add `Schema`.                                                                                                                                                                                        |
| `CreateSchema`             | `EntityCreateInputSchema`             | Currently a base class for entity creates in `catalog/api/schemas.py`. Scoped name avoids collision with per-entity `…CreateSchema` names.                                                                                  |
| `SearchResponse`           | `CitationSourceSearchResponseSchema`  | `Response` suffix is rare; scope it to its entity since `SearchResponse` is too generic.                                                                                                                                    |
| `DeletePreviewBase`        | `DeletePreviewBaseSchema`             | Add `Schema` for consistency (it's a Schema subclass used as a mixin).                                                                                                                                                      |
| `FieldConstraint`          | `FieldConstraintSchema`               | Add `Schema` for consistency.                                                                                                                                                                                               |
| `PaginationParams`         | `PaginationParamsSchema`              | Already-shipped ghost-type fix; rename to satisfy the universal `Schema` rule.                                                                                                                                              |
| `TitleRefSchema`           | `TitleRef`                            | Strip `Schema` to align with the `*Ref` exception.                                                                                                                                                                          |
| `ModelRefSchema`           | `ModelRef`                            | Strip `Schema` to align with the `*Ref` exception.                                                                                                                                                                          |
| `GameplayFeatureSchema`    | `GameplayFeatureRef`                  | This schema is `Ref + count`; renaming clarifies role and lands it under the `*Ref` exception (no `Schema`).                                                                                                                |

Names that already conform pass through unchanged: every existing
`…Schema` not listed above (e.g., `TitleDetailSchema`,
`AuthStatusSchema`, `ChangeSetSchema`, `ClaimSchema`,
`CitationInstanceSchema`, …), plus the existing bare-`*Ref` family
(`LocationAncestorRef`, `LocationChildRef`,
`CorporateEntityLocationAncestorRef`, etc.).

## Per-app rename tables

Apps are listed smallest first, matching the commit sequence in
[ApiSvelteBoundary.md](ApiSvelteBoundary.md). Apps with **zero**
renames under the new rules (`accounts`, `core`) are omitted —
their existing names already conform.

### `core` (1 rename)

| Current                     | New                    |
| --------------------------- | ---------------------- |
| `LinkTargetsResponseSchema` | `LinkTargetListSchema` |

(Wraps `list[LinkTargetSchema]`; `Response` is rare across the
codebase and the `…ListSchema` wrapper convention says it more
clearly.)

### `media` (4 renames)

| Current             | New                     |
| ------------------- | ----------------------- |
| `AttachmentMetaOut` | `AttachmentMetaSchema`  |
| `MediaAssetRefIn`   | `MediaAssetInputSchema` |
| `RenditionUrlsOut`  | `RenditionUrlsSchema`   |
| `UploadOut`         | `UploadSchema`          |

(`MediaRenditionsSchema` and `UploadedMediaSchema` already conform.)

### `citation` (5 renames)

| Current                 | New                                  |
| ----------------------- | ------------------------------------ |
| `ExtractDraftSchema`    | `CitationExtractDraftSchema`         |
| `ExtractRequestSchema`  | `CitationExtractInputSchema`         |
| `ExtractResponseSchema` | `CitationExtractResultSchema`        |
| `RecognitionSchema`     | `CitationRecognitionSchema`          |
| `SearchResponse`        | `CitationSourceSearchResponseSchema` |

(`Extract` is too generic at the OpenAPI level — could be extracting
anything. Scope all three to `CitationExtract*`. `Request` →
`Input` per our convention; `Response` → `Result` reads more
naturally for the operation's output. All other
`CitationSource*Schema` names already conform.)

### `provenance` (5 renames)

| Current                    | New                            |
| -------------------------- | ------------------------------ |
| `BatchCitationInstanceOut` | `CitationInstanceBatchSchema`  |
| `CitationInstanceCreateIn` | `CitationInstanceCreateSchema` |
| `EditCitationInput`        | `CitationReferenceInputSchema` |
| `SourceSchema`             | `CitationSourceSchema`         |
| `FieldConstraint`          | `FieldConstraintSchema`        |

(All other `…Schema` names already conform.)

### `catalog` (~25 renames)

Grouped by sub-area for readability. Entries that already conform
are not listed.

#### Top-level (`apps/catalog/api/schemas.py`)

| Current                 | New                       |
| ----------------------- | ------------------------- |
| `CreateSchema`          | `EntityCreateInputSchema` |
| `CreditInput`           | `CreditInputSchema`       |
| `DeletePreviewBase`     | `DeletePreviewBaseSchema` |
| `EditOptionItem`        | `EditOptionSchema`        |
| `GameplayFeatureSchema` | `GameplayFeatureRef`      |
| `Ref`                   | `EntityRef`               |
| `TitleRefSchema`        | `TitleRef`                |

#### Titles (`apps/catalog/api/titles.py`)

| Current                     | New                       |
| --------------------------- | ------------------------- |
| `TitleListSchema`           | `TitleListItemSchema`     |
| `TitleMachineSchema`        | `TitleModelSchema`        |
| `TitleMachineVariantSchema` | `TitleModelVariantSchema` |

(`TitleListSchema` → `TitleListItemSchema` rather than left bare:
it's the row shape, not a wrapper around a list. `TitleMachine*` →
`TitleModel*` purges another `Machine` leak; the `<Parent><Child>`
shape stays intact, distinct from the standalone `ModelSchema`
family.)

#### Machine models (`apps/catalog/api/machine_models.py`)

| Current                    | New                   |
| -------------------------- | --------------------- |
| `MachineModelDetailSchema` | `ModelDetailSchema`   |
| `MachineModelGridSchema`   | `ModelGridItemSchema` |
| `MachineModelListSchema`   | `ModelListItemSchema` |
| `ModelRefSchema`           | `ModelRef`            |
| `VariantSchema`            | `ModelVariantSchema`  |

#### People (`apps/catalog/api/people.py`)

| Current            | New                    |
| ------------------ | ---------------------- |
| `PersonSchema`     | `PersonListItemSchema` |
| `PersonGridSchema` | `PersonGridItemSchema` |

#### Manufacturers / corporate entities / locations

| Current                     | New                                 |
| --------------------------- | ----------------------------------- |
| `CorporateEntityListSchema` | `CorporateEntityListItemSchema`     |
| `CorporateEntitySchema`     | `ManufacturerCorporateEntitySchema` |
| `ManufacturerGridSchema`    | `ManufacturerGridItemSchema`        |
| `ManufacturerSchema`        | `ManufacturerListItemSchema`        |
| `SystemSchema`              | `ManufacturerSystemSchema`          |

`SystemSchema` and `CorporateEntitySchema` are both renamed to
`Manufacturer*` names following the `<Parent><Child>` pattern
already used for `ManufacturerPersonSchema` and
`LocationManufacturerSchema`. Both are embedded sub-shapes inside
`ManufacturerDetailSchema`. Per
[ApiDesign.md](../../../ApiDesign.md), naming a list-item shape
preserves a future expansion point that collapsing to `Ref` would
foreclose.

`ManufacturerCorporateEntitySchema` is genuinely distinct in shape
from `CorporateEntityListItemSchema` — the embedded form lacks
`manufacturer` and `model_count`. A future consolidation of those
two shapes (if the field divergence isn't load-bearing) is tracked
in
[ApiSvelteBoundaryFollowups.md](ApiSvelteBoundaryFollowups.md).

#### Systems (`apps/catalog/api/systems.py`)

| Current            | New                    |
| ------------------ | ---------------------- |
| `SystemListSchema` | `SystemListItemSchema` |

#### Series, themes, franchises, gameplay features, taxonomy

| Current                          | New                                  |
| -------------------------------- | ------------------------------------ |
| `DisplayTypeListSchema`          | `DisplayTypeListItemSchema`          |
| `FranchiseListSchema`            | `FranchiseListItemSchema`            |
| `GameplayFeatureInput`           | `GameplayFeatureInputSchema`         |
| `GameplayFeatureListSchema`      | `GameplayFeatureListItemSchema`      |
| `SeriesListSchema`               | `SeriesListItemSchema`               |
| `TechnologyGenerationListSchema` | `TechnologyGenerationListItemSchema` |
| `ThemeListSchema`                | `ThemeListItemSchema`                |

### `config/api.py` (1 rename)

| Current       | New               |
| ------------- | ----------------- |
| `StatsSchema` | `SiteStatsSchema` |

### Already-shipped touch-up

| Current            | New                      |
| ------------------ | ------------------------ |
| `PaginationParams` | `PaginationParamsSchema` |

The orphan-pagination fix landed in commit `fd9e02b5a` named the
new schema `PaginationParams` (no suffix). The universal-`Schema`
rule means it should be `PaginationParamsSchema`. Bundle this
one-class rename into whichever app PR touches it most naturally
(`core`, since it lives in `apps/core/pagination.py`).

## Ghost-type fixes

Some OpenAPI components don't come from explicit Ninja schema
classes — Ninja auto-generates them from internal class names
inside its `@paginate` machinery. They need source-side fixes
analogous to (and following the pattern of) the already-shipped
`PaginationParams` fix.

### Pagination query params — DONE

- **`Input` (Ninja-auto-named pagination query model)** — replaced
  by `PaginationParams` in `apps/core/pagination.py` (commit
  `fd9e02b5a`). Will be renamed to `PaginationParamsSchema` along
  with the per-app sweep above.

### `Paged*Schema` wrappers — TODO

Four components in the OpenAPI doc are auto-named by Ninja's
`@paginate` decorator from the inner row-schema class name:

- `PagedMachineModelListSchema` (wraps `MachineModelListSchema`)
- `PagedManufacturerSchema` (wraps `ManufacturerSchema`)
- `PagedPersonSchema` (wraps `PersonSchema`)
- `PagedTitleListSchema` (wraps `TitleListSchema`)

After the renames in this plan, the auto-generated names degrade
to confusing forms like `PagedManufacturerListItemSchema` — mixing
the "wrapper" prefix `Paged` with the "row" suffix `ListItem`.

**Fix** (mirrors `NamedPageNumberPagination`): introduce a
`NamedPaginatedResponseSchema` base — a Ninja-`Schema` subclass
parameterized by the row type — and apply it at the four
`@paginate(...)` sites so each wrapper gets a stable, intentional
name. Goal:

| Auto-generated today          | After ghost fix          |
| ----------------------------- | ------------------------ |
| `PagedMachineModelListSchema` | `ModelListSchema`        |
| `PagedManufacturerSchema`     | `ManufacturerListSchema` |
| `PagedPersonSchema`           | `PersonListSchema`       |
| `PagedTitleListSchema`        | `TitleListSchema`        |

(After the row-rename, the `…ListSchema` wrapper slot is free —
e.g., `TitleListSchema` → `TitleListItemSchema` opens up
`TitleListSchema` for the wrapper.)

This is its own small PR, sequenced **after** the per-app renames
that free up the wrapper slot names.

### `JsonBody` — not a ghost

`JsonBody` also surfaces as an OpenAPI component without a Ninja
`Schema` subclass, but it is **not** a ghost-type fix: the PEP 695
`type JsonBody = dict[str, object]` alias in
[apps/core/types.py](../../../../backend/apps/core/types.py) is the
project-wide name for "an arbitrary JSON object," used pervasively
in the backend. Pydantic correctly registers it as a single named
component that every JSON-shaped field `$ref`s. Leave it alone — do
not rename, inline, or wrap it in a `Schema` subclass.
