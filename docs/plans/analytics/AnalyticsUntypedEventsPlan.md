# Analytics Untyped Events Plan

This doc covers the untyped-events track of [AnalyticsPlan.md](AnalyticsPlan.md). Contracts live in [AnalyticsArchitecture.md](AnalyticsArchitecture.md).

This is the launch path — "slap PostHog in and call it a day." It stands up the SDK with the locked-down privacy config and starts firing anonymous pageviews. No typed events, no backend involvement, no pseudonym, no identify. The PostHog firehose alone answers most of the high-level questions in [AnalyticsQuestions.md § Root questions](AnalyticsQuestions.md#root-questions) — see [AnalyticsPlan.md § Which phase answers which question](AnalyticsPlan.md#which-phase-answers-which-question) for the mapping.

## Phase: Skeleton

Stand up `frontend/src/lib/analytics/` with the module structure from [AnalyticsArchitecture.md § Module Layout](AnalyticsArchitecture.md#module-layout). No events fire yet.

**Deliverables:**

- `index.ts` — public API exporting the active adapter as `analytics`. `capture()`, `pageview()`, `identify()`, `reset()` per the [`Analytics` interface](AnalyticsArchitecture.md#the-abstraction-api).
- `posthog.ts` — PostHog adapter. The init config goes here, exactly as specified in [AnalyticsArchitecture.md § Privacy Enforcement](AnalyticsArchitecture.md#privacy-enforcement). Do not deviate.
- `noop.ts` — no-op adapter for tests, dev, and opt-out.
- `config.ts` — the literal init options object, imported by `posthog.ts`. Isolating it makes the integration test below trivial.
- `events.ts` — empty `EventRegistry` type, ready to grow.
- `PUBLIC_POSTHOG_KEY` wired through SvelteKit env. Document in `.env.example`.
- ESLint `no-restricted-imports` rule banning `posthog-js` outside `posthog.ts`.

**Verification:**

- An integration test (vitest) that imports `config.ts` and asserts every locked-down option matches the architecture doc. Weakening any option fails the test.
- The dev-mode default adapter is `noop`, not PostHog. Confirm in a dev-run by inspecting the network tab — no requests to `eu.posthog.com`.

## Phase: Pageviews

PostHog's auto-pageview is off (`capture_pageview: false`); pageviews fire from a SvelteKit `afterNavigate` hook in the root layout, so every CSR route change is captured — not just the initial SSR load.

**Deliverables:**

- `afterNavigate` hook in `frontend/src/routes/+layout.svelte`:

  ```svelte
  <script lang="ts">
    import { afterNavigate } from "$app/navigation";
    import { analytics } from "$lib/analytics";

    afterNavigate(({ from, to }) => {
      if (!to) return;
      analytics.pageview(to.url.pathname, {
        referrer: from?.url.pathname ?? null,
      });
    });
  </script>
  ```

  `afterNavigate` fires after the initial load **and** after every subsequent CSR navigation, so a single hook covers the whole SPA. Without this, the SPA would look like a one-page-per-visit site to PostHog — pages-per-session would always be 1, bounce rate would be 100%.

- No pageview fires from `+layout.server.ts`. Server-rendered HTML doesn't imply the user saw the page (bots, prefetches, etc.).

**Verification:**

- A vitest using `RecordingAnalytics` that simulates an initial load + two CSR navigations and asserts three pageview events with the expected pathnames and internal `referrer` properties.
- Staging spot-check: load the homepage, click through a few links, find the events in PostHog. Confirm `$referrer` and `$referring_domain` are present (set by PostHog at session start from `document.referrer`), distinct from the internal `referrer` property which holds the previous in-SPA pathname.

## Test patterns

The default adapter under vitest is `RecordingAnalytics`, which captures calls into an array and exposes them to assertions. The PostHog adapter is never exercised in unit tests. The Skeleton-phase integration test on `config.ts` is the one place that touches the real adapter, and it asserts the locked-down init config, not the network.

## What this doc does NOT cover

- The abstraction contract, privacy lockdown spec, naming conventions — those are architecture, see [AnalyticsArchitecture.md](AnalyticsArchitecture.md).
- Typed events (server- or client-side) — see [AnalyticsTypedEventsBackendPlan.md](AnalyticsTypedEventsBackendPlan.md) and [AnalyticsTypedEventsFrontendPlan.md](AnalyticsTypedEventsFrontendPlan.md).
- DB-derived stats — see [AnalyticsDbStatsPlan.md](AnalyticsDbStatsPlan.md).
- Cross-cutting sequencing — see [AnalyticsPlan.md](AnalyticsPlan.md).
