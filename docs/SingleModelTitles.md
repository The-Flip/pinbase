# Single-Model Titles

This doc describes how the system handles **single-Model Titles** -- that is, Titles that contain exactly one Model with no variants.

## The Background

Most pinball sites don't have the concept of Title; instead, they only have Models (like Godzilla Pro & Godzilla Premium are separate models). This is because most pinball sites are developed by and for enthusiasts and collectors who think in those terms. This site, however, is run by a museum and aims to be inclusive of the broader public, who doesn't think at that level of detail. To the public, the machine is simply "Godzilla".

This creates a UX problem: most older machines only have one single model. For single-Model Titles, we don't want to force the user to click on the Title, then click on the Model to see all the info. So the title route ( /titles/doctor-who ) shows all the information, and we don't link to the model route.

Editor users are different; we can reasonably expect them to think in terms of distinct models. Regardless, for ease of editing, we made the decision to collapse the edit UX of single-Model Titles as well: you edit them from the Title page. However, each individual Editor dialog only edits Title info or Model info -- we never create a ChangeSet that changes multiple records.

## Information asymmetry

Almost all editable content lives on the Model. The Title row carries only identity-and-grouping fields:

- `name`, abbreviations, `franchise`, `series`, `description` (dormant when single-Model — see below)

Everything else — manufacturer, year, technology, features, people, media,
related models, external IDs — lives on the Model.

A single-Model Title's Model therefore carries the large majority of the
catalog content and edit history. The Title row is a thin shell.

## Single-to-Multi-Model Titles

Single-Model Titles _can_ and _do_ become multi-Model:

- Every new multi-Model Title passes through single-Model during creation, because an editor must create the Title first with no Models, then add Models one at a time.
- Remakes (e.g. Medieval Madness 2025) with many years of edit history promote established single-Model Titles into multi-Model ones.

## Collapse rule

When `len(active_models) == 1` and that Model has no variants, the UI
**collapses** the Title and Model into one page. This rule fires in three
places and must stay consistent across them:

- API: `TitleDetailSchema.model_detail` is populated inline — see
  [titles.py:609-613](../backend/apps/catalog/api/titles.py#L609-L613).
- Read view: the Title page renders the Model's content inline — see
  [+page.svelte](../frontend/src/routes/titles/[slug]/+page.svelte).
- Edit view: the section-edit menu interleaves Title-tier and Model-tier
  sections via `combinedSectionsFor(isSingleModel)` —
  see [combined-edit-sections.ts](../frontend/src/lib/components/editors/combined-edit-sections.ts).

The collapse is UI-only. The data model is unchanged: two entities, two sets
of claims, two ChangeSet histories.

## Which entity each editor section targets

In the single-Model Title edit menu, as in every other edit menu, each editor section targets exactly one entity. Every section save is single-entity. No ChangeSet ever spans both Title and Model.

### Field overlap: Description

Both `Title` and `MachineModel` have a `description` field.

For single-Model Titles, we use the **Model's** description; the read view shows the **Model's** description and the edit menu's Overview section edits the **Model's** description. The Title's
description is dormant.

We use the Model's description for single-Model Titles because it stays correct after
promotion to multi-Model; it still describes that Model. The Title's description is expected to be used for copy about the collection of Models that only makes sense once multiple Models exist.

### Field overlap: Name & Slug

Both `Title` and `MachineModel` have `name` and `slug` fields.

The single-Model Title edit menu uses the Title's version for both, because the Title is the public identity of the collapsed record.

### Field overlap: Abbreviations

Both `Title` and `MachineModel` have abbreviation records. The collapsed Name editor edits the **Title's** abbreviations; the Model's are dormant.

This is because, even if the Title becomes multi-model, those abbreviations will identify the Title, not the Model.

### Field overlap: External IDs

The fields don't literally overlap one-to-one — Title has `opdb_id` and `fandom_page_id`; Model has `ipdb_id`, `opdb_id`, and `pinside_id` — but they're conceptually the same kind of data. The collapsed edit menu surfaces **both** sections side by side ("External Data" for the Model, "External Data - Title" for the Title), since each entity legitimately owns IDs the other doesn't.

## Edit history and sources

The Edit History and Sources pages are unaware of single-Model Titles; their job is to display the edit history / sources of a single catalog record. Each ChangeSet targets exactly one entity, so `/edit-history` and `/sources` filter strictly by entity.

The single-Model Title page surfaces links to both the title _AND_ model Edit History and Sources routes.
