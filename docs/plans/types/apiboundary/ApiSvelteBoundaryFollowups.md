# API Boundary Followups

## Context

Items deferred until after the API boundary work in
[ApiSvelteBoundary.md](ApiSvelteBoundary.md) lands. They either
depend on the rename being settled, or are surfaced by doing the
boundary work and only become tractable once it's done.

This doc starts thin. Most items will be added as the boundary work
surfaces them — collision resolutions in the rename pass that reveal
real shape duplication, naming inconsistencies the rationalization
table couldn't fully resolve, page-vs-resource shape divergences the
rename couldn't predict, and so on.

## Resolve underlying shape duplication surfaced by rename collisions

[ApiNamingRationalization.md](ApiNamingRationalization.md) flags two
collision pairs that resolve per-commit during the rename:

- `CorporateEntitySchema` vs `CorporateEntityListSchema` — both want
  `CorporateEntityListItem`.
- `SystemSchema` vs `SystemListSchema` — both want `SystemListItem`.

If the pre-flight investigation reveals these are near-identical
shapes, the per-commit resolution may pick distinct names rather
than consolidate, leaving the underlying duplication in place. After
the rename lands, decide whether to consolidate the shapes — by then
the names are stable and the call sites are visible against the
renamed contract.

## Split schema per-tag

If after the boundary work lands, `frontend/src/lib/api/schema.d.ts`
still feels unwieldy for AI/human reading, split it per Ninja tag so
working in catalog code only requires reading
`schema.catalog.d.ts` (~2–3k lines) instead of all 10k.

Requires build-tooling work: filter the OpenAPI doc per tag and run
`openapi-typescript` N times. The barrel from
[ApiSvelteBoundary.md](ApiSvelteBoundary.md) means consumers don't
change.

Skip this entirely if the file no longer feels like a problem after
the rename and barrel land.

## Page-model vs resource-canonical schema split

[docs/ApiDesign.md](../../../ApiDesign.md) draws a sharp distinction
between resource APIs (`/api/<entity>/...`) and page APIs
(`/api/pages/<entity>/...`), with page endpoints returning page
models. In practice, every `*Detail` schema today is shared between
the two — the page endpoint returns the same shape as the resource
detail endpoint. Splitting them is an architectural question, not a
naming one, and is explicitly out of scope for the rename.

After the boundary work lands and the names are settled, decide
whether to actually split them. The decision should be made per
page, not as a sweeping policy: most pages probably don't need a
distinct shape, and the conceptual cleanliness doesn't justify a
parallel schema family without concrete divergence. When divergence
shows up — a page wants a field the resource detail doesn't, or vice
versa — that's the point at which a `…Page` schema earns its name.
