# Analytics Untyped Events Plan

This doc covers the untyped-events track of [AnalyticsPlan.md](AnalyticsPlan.md). Contracts live in [AnalyticsArchitecture.md](AnalyticsArchitecture.md).

This is the launch path. It stands up the SDK with the locked-down privacy config and starts firing anonymous pageviews. No typed events, no backend involvement, no pseudonym, no identify. The PostHog firehose alone answers most of the high-level questions in [AnalyticsQuestions.md § Root questions](AnalyticsQuestions.md#root-questions) — see [AnalyticsPlan.md § Which phase answers which question](AnalyticsPlan.md#which-phase-answers-which-question) for the mapping.

## Phase: Skeleton

Stand up `frontend/src/lib/analytics/` with the module structure from [AnalyticsArchitecture.md § Module Layout](AnalyticsArchitecture.md#module-layout). No events fire yet.

**Deliverables:**

- `index.ts` — public API exporting the active adapter as `analytics`. Selects `noop` when `import.meta.env.DEV` **or** `PUBLIC_POSTHOG_KEY` is empty; the PostHog adapter otherwise. The key-presence check means staging/preview/CI builds without a key fall back to noop instead of crashing at init. `capture()`, `pageview()`, `identify()`, `reset()` per the [`Analytics` interface](AnalyticsArchitecture.md#the-api). All four are no-ops on every adapter at this phase; bodies land in later phases (`pageview()` next phase, `identify()`/`reset()` in typed-events).
- `posthog.ts` — PostHog adapter. Imports the locked-down options from `config.ts` and calls `posthog.init()` guarded by `browser` from `$app/environment` so the SDK never touches `window` during SSR. At this phase the four interface methods are empty bodies.
- `noop.ts` — no-op adapter for tests, dev, and opt-out.
- `config.ts` — the literal init options object, imported by `posthog.ts`. Isolating it makes the integration test below trivial. Specified in [AnalyticsArchitecture.md § Frontend init lockdown](AnalyticsArchitecture.md#frontend-init-lockdown); do not deviate.
- `events.ts` — empty `EventRegistry` type, ready to grow.
- `PUBLIC_POSTHOG_KEY` wired through SvelteKit env via `$env/static/public` (build-time constant; lets the DEV/noop branch tree-shake the SDK out of dev bundles entirely). Document in `.env.example`.
- ESLint `no-restricted-imports` rule banning `posthog-js` outside `posthog.ts`.

**Verification:**

- An integration test (vitest) that imports `config.ts` and asserts every locked-down option matches the architecture doc. Weakening any option fails the test.
- A vitest covering adapter selection across three cases: (a) `DEV=true` → noop, (b) `DEV=false` + empty key → noop, (c) `DEV=false` + key set → PostHog adapter. Use `vi.stubEnv` to drive `import.meta.env`. Confirm in a dev-run by inspecting the network tab — no requests to `eu.posthog.com`.
- A vitest asserting that importing `index.ts` in a non-browser environment (the vitest default) does not import `posthog-js` — the `browser` guard keeps SSR safe.

## Phase: Pageviews

PostHog's auto-pageview is off (`capture_pageview: false`); pageviews fire from a SvelteKit `afterNavigate` hook in the root layout, so every CSR route change is captured — not just the initial SSR load.

**Deliverables:**

- `afterNavigate` hook in `frontend/src/routes/+layout.svelte`:

  ```svelte
  <script lang="ts">
    import { afterNavigate } from "$app/navigation";
    import { analytics } from "$lib/analytics";

    afterNavigate(({ to }) => {
      if (!to) return;
      analytics.pageview(to.url.pathname);
    });
  </script>
  ```

  `afterNavigate` fires on client-side hydration after the initial SSR load **and** after every subsequent CSR navigation, so a single hook covers the whole SPA. Without this, the SPA would look like a one-page-per-visit site to PostHog — pages-per-session would always be 1, bounce rate would be 100%.

- Only the pathname is captured (`to.url.pathname`), not the query string or hash. Deliberate: keeps URL cardinality bounded and avoids leaking search terms or other query-encoded state into the firehose. Typed events (next phases) carry meaningful query-derived properties explicitly.
- No pageview fires from `+layout.server.ts`. Server-rendered HTML doesn't imply the user saw the page (bots, prefetches, etc.) — and since `afterNavigate` is client-only, a bot or `curl` that never hydrates produces no pageview, which is the intended behavior.
- Extend `posthog.ts`: track the previously-captured pathname in a module-level variable, attach it to each `$pageview` event as `internal_referrer` (the SPA's prior pathname, distinct from PostHog's `$referrer`, which reflects the external referring document). `reset()` clears it. `identify()` remains a no-op until typed-events.

**Verification:**

- A vitest using `RecordingAnalytics` that simulates an initial load + two CSR navigations and asserts three pageview events with the expected pathnames.
- A vitest on the PostHog adapter with `posthog-js` mocked at the module boundary: drive three `pageview()` calls and assert the mocked `posthog.capture` is invoked with `$pageview` and `internal_referrer` values of `null`, then the first path, then the second path. A fourth call after `reset()` asserts `internal_referrer: null` again.
- Staging spot-check: load the homepage, click through a few links, find the events in PostHog. Confirm `$referrer` and `$referring_domain` are present (set by PostHog at session start from `document.referrer`), distinct from `internal_referrer`, which is attached by our adapter and holds the previous in-SPA pathname.

## Test patterns

The default adapter under vitest is `RecordingAnalytics`, which captures calls into an array and exposes them to assertions. The PostHog adapter is never exercised in unit tests. The Skeleton-phase integration test on `config.ts` is the one place that touches the real adapter, and it asserts the locked-down init config, not the network.

## What this doc does NOT cover

- The abstraction contract, privacy lockdown spec, naming conventions — those are architecture, see [AnalyticsArchitecture.md](AnalyticsArchitecture.md).
- Typed events (server- or client-side) — see [AnalyticsTypedEventsBackendPlan.md](AnalyticsTypedEventsBackendPlan.md) and [AnalyticsTypedEventsFrontendPlan.md](AnalyticsTypedEventsFrontendPlan.md).
- DB-derived stats — see [AnalyticsDbStatsPlan.md](AnalyticsDbStatsPlan.md).
- Cross-cutting sequencing — see [AnalyticsPlan.md](AnalyticsPlan.md).
