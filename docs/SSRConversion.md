# SSR Conversion

This document is a practical guide for converting an existing SvelteKit route subtree from CSR to SSR in Pinbase.

It is not the canonical source for SSR philosophy or API design rules. Read [Svelte.md](Svelte.md) and [WebApiDesign.md](WebApiDesign.md) for those. This doc is the implementation checklist.

## When To Use This

Use this workflow when:

- a public page currently ships an app shell and fetches content client-side
- the initial HTML should contain meaningful content
- the page is important for SEO, sharing, or first-load usability

Do not use this workflow blindly for authenticated or highly interactive app surfaces.

## Standard Pattern

For a typical detail page conversion:

1. add a page-oriented backend endpoint under `/api/pages/...`
2. tag it `tags=["private"]`
3. reuse existing serializer/query logic when the existing resource endpoint already returns the right page model
4. replace `+layout.ts` or `+page.ts` with `+layout.server.ts` or `+page.server.ts`
5. use `createServerClient(fetch, url)` from `$lib/api/server`
6. audit every child route before removing inherited `ssr = false`
7. add backend and frontend SSR tests
8. regenerate API types

## Backend Checklist

When adding the page endpoint:

- put it in the app that owns the domain, usually `apps.catalog`
- do not put catalog-specific page endpoints in `apps.core`
- place it under `/api/pages/...`
- tag it `tags=["private"]`
- prefer reusing existing detail querysets and serializers when they already match the page model
- do not create a second serializer just to rename a resource endpoint into a page endpoint if the shape is already correct
- register the router by adding a `("/pages/", pages_router)` tuple to the app's `routers` list in `__init__.py` — `config/api.py` autodiscovers it from there

Examples:

- `/api/pages/title/{slug}`
- `/api/pages/manufacturer/{slug}`

## Frontend Loader Checklist

When converting the route loader:

- replace `+page.ts` with `+page.server.ts`, or `+layout.ts` with `+layout.server.ts`
- remove browser `client` usage from the server load path
- use `createServerClient(fetch, url)` from `$lib/api/server`
- `$lib/api/server` imports `$env/dynamic/private` and can only be used in server-side files (`+page.server.ts`, `+layout.server.ts`) — importing it from a universal `+page.ts` will error
- fetch one backend endpoint that already matches the page
- return the page model directly to the route

Pattern:

```ts
import { error } from "@sveltejs/kit";
import { createServerClient } from "$lib/api/server";
import type { LayoutServerLoad } from "./$types";

export const load: LayoutServerLoad = async ({ fetch, url, params }) => {
  const client = createServerClient(fetch, url);
  const { data, response } = await client.GET("/api/pages/title/{slug}", {
    params: { path: { slug: params.slug } },
  });

  if (!data) {
    if (response?.status === 404) throw error(404, "Not found");
    throw error(response.status || 500, "Failed to load page");
  }

  return { title: data };
};
```

## Child Route Audit

This is the most common source of mistakes.

When a parent route switches from CSR to SSR, all children inherit SSR unless they explicitly opt out.

Before deleting `ssr = false` from the parent:

- list every child route in the subtree
- classify each child as SSR content or CSR app surface
- add `export const ssr = false` in a child `+page.ts` for routes that must stay client-only

Children usually need explicit `ssr = false` when they:

- import the browser `client` default export
- read `auth.isAuthenticated` or other browser-only state at render time
- are edit, upload, or mutation-heavy routes
- depend on app-like interaction more than initial HTML

Children can usually inherit SSR when they:

- only render data from the parent layout/page load
- are public content pages
- do not mutate data directly

Do not assume a child “stays CSR” just because it has no loader today.

## Tests Required

An SSR conversion should usually add or update these tests:

- backend endpoint test for the new `/api/pages/...` route
- frontend server-load test for the new `+page.server.ts` or `+layout.server.ts`
- frontend server-load test for any converted child route like `edit-history/+page.server.ts`
- at least one render proof that meaningful content reaches initial HTML

The render proof does not need to cover every part of the route shell. It should prove that the server-rendered output contains real page content, not just a shell.

## Manual Verification

For a converted page, manually verify:

1. `make dev`
2. open the converted route
3. view source and confirm meaningful content is present in initial HTML
4. open any converted public child routes and confirm the same
5. open any explicitly CSR children and confirm they still work
6. verify 404 behavior for a nonexistent slug

## Common Gotchas

- putting page endpoints in the wrong Django app and violating app boundaries
- using generic resource endpoints when the page really needs a page-oriented endpoint
- forgetting `tags=["private"]` on page endpoints
- forgetting to regenerate OpenAPI types
- converting the parent route to SSR and accidentally dragging edit/upload children into SSR
- keeping stale comments like `// Data loaded in +layout.ts` after the loader moved to `+layout.server.ts`
- adding only backend tests and forgetting frontend SSR tests
- proving only the data fetch path, but not that meaningful HTML is actually rendered
- wondering why the new `/api/pages/...` path doesn't type-check — `schema.d.ts` is gitignored and must be regenerated locally with `make api-gen` before the typed client sees the new endpoint

## Definition Of Done

A route subtree is cleanly converted when:

- the backend exposes one page-oriented endpoint under `/api/pages/...`
- the SSR route uses `createServerClient`
- child routes are explicitly classified as SSR or CSR
- tests cover the endpoint and SSR load path
- manual verification confirms meaningful initial HTML
- generated types and docs are updated if needed

## Scope: Detail Pages vs. List Pages

This checklist is written around detail page conversions: one slug, one page endpoint, one response. Most detail pages follow this pattern directly — the existing resource endpoint often already returns the right page model.

List and browse pages (e.g. `/titles/`, `/manufacturers/`) are a different shape. A list page that loads the entire dataset client-side and filters in the browser cannot simply move that load to `+layout.server.ts` — the server would serialize the same large payload into HTML, and the full dataset would still need to hydrate into the browser for client-side filtering.

For list pages, SSR conversion usually requires rethinking the data strategy:

- server-side filtering with query params instead of client-side facet engines
- paginated responses instead of full dataset dumps
- server-computed facet counts instead of browser-computed counts
- filter state encoded in the URL so SSR can render the correct filtered page

The standard pattern section above still applies to the backend and frontend loader mechanics. The difference is in the endpoint design: a list page endpoint accepts filter and pagination params and returns one page of results plus facet metadata, rather than the full dataset.
