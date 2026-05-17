# Analytics Typed Events Frontend Plan

This doc covers the frontend side of the typed-events track of [AnalyticsPlan.md](AnalyticsPlan.md).

Contracts live in [AnalyticsArchitecture.md](AnalyticsArchitecture.md). The SDK skeleton, locked-down init, and the pageview firehose are covered in [AnalyticsUntypedEventsPlan.md](AnalyticsUntypedEventsPlan.md) — this doc assumes that work is done.

Specific events have not yet been designed; the candidate event names below are illustrative.

## Prerequisites

- [AnalyticsUntypedEventsPlan.md](AnalyticsUntypedEventsPlan.md) — the SDK and pageview firehose ship from there first.
- [AnalyticsTypedEventsBackendPlan.md](AnalyticsTypedEventsBackendPlan.md) — `identify()` consumes the pseudonym the backend puts in the page payload, so the backend must ship its first transactional event before this doc's identify phase can run.

## Phase: identify() and reset()

Connects authenticated journeys to the backend-derived pseudonym. Depends on the backend exposing pseudonym in the page payload — see [AnalyticsTypedEventsBackendPlan.md § event 1](AnalyticsTypedEventsBackendPlan.md#phase-event-1-transactional).

**Deliverables:**

- Root layout calls `analytics.identify(pseudonym)` once auth state hydrates and confirms the user is logged in. The pseudonym comes from the page payload, not a separate fetch.
- Logout calls `analytics.reset()`, clearing PostHog's in-memory `distinct_id`.
- Default aliasing behavior is accepted: when `identify()` fires after login within the same SPA instance, PostHog aliases the anonymous heap-bound `distinct_id` to the pseudonym, retroactively attributing pre-login browsing to the user. The user has consented to authenticated use; aliasing is bounded to one SPA instance because anonymous ids never persist past document replacement.

**Verification:**

- A vitest using `RecordingAnalytics` that captures a pageview, then calls `identify(p)`, then captures another pageview. Assert both events end up under the same id post-identify (the aliasing behavior).
- A vitest for logout: `identify(p)` → `reset()` → capture. Assert the post-reset event is anonymous (new heap-bound id, not `p`).
- Staging spot-check: log in. In PostHog, confirm the pre-login pageviews are now attributed to the logged-in pseudonym (aliasing succeeded), and the pseudonym is not a recognizable encoding of `user.id`.

## Phase: Client events

Land client-side events as the features that emit them get built. Illustrative candidates (pending taxonomy review):

- Reading: information-need search, optionally a separate zero-result event (see the search-event discussion in the taxonomy review notes).
- Contribution lifecycle: edit-start, edit-abandon. Abandonment is the easiest to forget instrumenting because it has no obvious "user clicked submit" moment — likely fires on navigate-away or tab-close.
- Page-level: machine-page view (only if the pageview event doesn't already cover the question).

**Deliverables (per event):**

- A `TypedDict`-equivalent shape in `events.ts`.
- A call through `analytics.capture()` — never `posthog.capture()` directly. The lint rule forbids it.

**Verification:**

- A vitest per event using `RecordingAnalytics`. Drive the UI to the state that should fire the event, assert exactly one event with the expected properties.

## Test patterns

The default adapter under vitest is `RecordingAnalytics`, which captures calls into an array and exposes them to assertions. Test shape (illustrative):

```ts
test("the action records the expected event", () => {
  const a = new RecordingAnalytics();
  // ... drive the UI through the action ...
  expect(a.events).toEqual([
    { event: "...", properties: { ... } },
  ]);
});
```

The PostHog adapter itself isn't exercised here; the config-lockdown integration test lives in [AnalyticsUntypedEventsPlan.md § Skeleton](AnalyticsUntypedEventsPlan.md#phase-skeleton).

## What this doc does NOT cover

- The abstraction contract, privacy lockdown spec, pseudonymization model, naming conventions — those are architecture, see [AnalyticsArchitecture.md](AnalyticsArchitecture.md).
- SDK setup and pageviews — see [AnalyticsUntypedEventsPlan.md](AnalyticsUntypedEventsPlan.md).
- Backend work — see [AnalyticsTypedEventsBackendPlan.md](AnalyticsTypedEventsBackendPlan.md).
- DB-derived stats — see [AnalyticsDbStatsPlan.md](AnalyticsDbStatsPlan.md).
- Cross-cutting sequencing — see [AnalyticsPlan.md](AnalyticsPlan.md).
