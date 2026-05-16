# Analytics Typed Events Plan

This doc orchestrates the typed-events track of [AnalyticsPlan.md](AnalyticsPlan.md). Implementation lives in [AnalyticsTypedEventsBackendPlan.md](AnalyticsTypedEventsBackendPlan.md) and [AnalyticsTypedEventsFrontendPlan.md](AnalyticsTypedEventsFrontendPlan.md). Contracts live in [AnalyticsArchitecture.md](AnalyticsArchitecture.md).

The typed-events track answers product questions the pageview firehose can't — things like on-site search behavior, edit-flow drop-off, and the title-vs-model thesis check. Each event is a deliberate, named, typed call (`analytics.capture(...)`), not anything implicit.

This track has nothing to do with the launch. The launch is the untyped track ([AnalyticsUntypedEventsPlan.md](AnalyticsUntypedEventsPlan.md)). The typed-events track ships only when a specific product question makes it worth instrumenting a specific behavior.

## Prerequisites

- [AnalyticsUntypedEventsPlan.md](AnalyticsUntypedEventsPlan.md) — the SDK is up and the pageview firehose is flowing. Typed events ride on the same SDK.

## Phases

Strictly sequential:

1. Backend Pseudonym
2. Backend Events (the first transactional event adds pseudonym to the page payload)
3. Frontend Events (depends on pseudonym in payload)

### Phase: Backend Pseudonym

Stand up the pseudonym infrastructure so identified events can be attributed without leaking `User.id` to the vendor. No events fire yet.

Details in [AnalyticsTypedEventsBackendPlan.md § Skeleton](AnalyticsTypedEventsBackendPlan.md#phase-skeleton).

### Phase: Backend Events

Land server-side typed events. The first event also adds the pseudonym to the page payload so the frontend can `identify()` later.

Details in [AnalyticsTypedEventsBackendPlan.md § event 1 (transactional)](AnalyticsTypedEventsBackendPlan.md#phase-event-1-transactional), [§ event 2 (post-write)](AnalyticsTypedEventsBackendPlan.md#phase-event-2-post-write), and [§ Remaining events](AnalyticsTypedEventsBackendPlan.md#phase-remaining-events).

### Phase: Frontend Events

Land `identify()` / `reset()` and then client-side typed events. `identify()` consumes the pseudonym the backend put in the page payload during the previous phase.

Details in [AnalyticsTypedEventsFrontendPlan.md § identify() and reset()](AnalyticsTypedEventsFrontendPlan.md#phase-identify-and-reset) and [§ Client events](AnalyticsTypedEventsFrontendPlan.md#phase-client-events).

## What this doc does NOT cover

- SDK setup and the pageview firehose — see [AnalyticsUntypedEventsPlan.md](AnalyticsUntypedEventsPlan.md).
- DB-derived stats — see [AnalyticsDbStatsPlan.md](AnalyticsDbStatsPlan.md).
- Cross-cutting sequencing across all three tracks — see [AnalyticsPlan.md](AnalyticsPlan.md).
- Pseudonym mechanics, privacy lockdown, naming conventions — see [AnalyticsArchitecture.md](AnalyticsArchitecture.md).
