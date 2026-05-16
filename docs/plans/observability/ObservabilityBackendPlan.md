# Observability Backend Plan

This doc covers backend implementation of [ObservabilityPlan.md](ObservabilityPlan.md). Contracts live in [ObservabilityArchitecture.md](ObservabilityArchitecture.md).

## Phase: SDK

Stand up the Sentry SDK in the Django process. Events flow for unhandled exceptions; no user attribution yet.

**Deliverables:**

- `sentry-sdk[django]` added to backend dependencies.
- `config/settings.py` initializes the SDK exactly per [ObservabilityArchitecture.md § Backend integration](ObservabilityArchitecture.md#backend-integration), gated on a non-empty `SENTRY_DSN`. Init runs once per process.
- `config/sentry_scrubber.py` implements `scrub_event` per [ObservabilityArchitecture.md § Privacy enforcement](ObservabilityArchitecture.md#privacy-enforcement). Strips cookies, `Authorization`, CSRF token + form field, password fields, fields containing `token`/`secret`/`key`, request body by default, email addresses, IP addresses.
- `LoggingIntegration(level=logging.INFO, event_level=None)` is wired so log records become breadcrumbs but never standalone events (see [ObservabilityArchitecture.md § Logging integration](ObservabilityArchitecture.md#logging-integration)).
- `.env.example` documents `SENTRY_DSN` as unset for local/CI.

**Verification:**

- Unit test asserting that when `SENTRY_DSN` is unset, the init block is a no-op (no `sentry_sdk.init` call, no client attached). Weakening the guard fails this test.
- Unit test for `scrub_event`: feeds a representative event with cookies, `Authorization`, a password field, a `csrfmiddlewaretoken`, an email in `extra`, and an IP. Asserts each is stripped, and that route/method/status/exception/release are preserved.
- Manual: deploy with `SENTRY_DSN` set, force an exception from a staff-only debug shell or existing endpoint, confirm it appears in `flipcommons-backend` tagged with the current `RAILWAY_GIT_COMMIT_SHA` and no PII.

## Phase: User attribution

Attach `{id, username}` to the Sentry scope for authenticated requests so events can be grouped by user.

**Deliverables:**

- Middleware registered after `AuthenticationMiddleware` that calls `sentry_sdk.set_user({"id": ..., "username": ...})` for authenticated requests and leaves the scope untouched for anonymous ones. No email, no IP — usernames are public on this project; the others are not (see [Privacy.md](../../Privacy.md)).

**Verification:**

- Unit test that runs an authenticated request through the middleware and asserts the Sentry scope carries `{id, username}` and nothing else.
- Unit test that runs an anonymous request and asserts the scope user is unset.

## Phase: Debug route

Add an on-demand exception trigger so the verification checklist in [ObservabilityArchitecture.md § First-event verification](ObservabilityArchitecture.md#first-event-verification) is repeatable.

**Deliverables:**

- `Activity.OBSERVABILITY_DEBUG` registered in [apps/core/authz/rules.py](../../../backend/apps/core/authz/rules.py) with predicates `is_authenticated, is_staff`. Mirrors the existing `DJANGO_ADMIN_ACCESS`/`RATE_LIMIT_EXEMPT` pattern.
- `/api/sentry_test` (Django Ninja, `tags=["private"]`), decorated `@requires(Activity.OBSERVABILITY_DEBUG)`, raises an exception when hit.

**Verification:**

- API test: anonymous request → 401/403; non-staff authenticated → 403; staff → 500 with the exception captured. Assert via Sentry's test transport (or a recording client) that exactly one event was captured with the expected exception type.
- Manual post-deploy: hit `/api/sentry_test` from a staff account, confirm the event lands in `flipcommons-backend` with correct release tag within 30 seconds.

## Test patterns

The Sentry SDK ships a transport that can be swapped for an in-memory recorder in tests. Backend tests that need to assert "an event was captured" use this transport via a fixture; the real HTTPS transport is never exercised in unit tests. The SDK-phase init test is the only place that touches the real init code path, and it asserts the guard, not the network.

## What this doc does NOT cover

- The init shape, scrubber spec, scope of capture, environment separation — those are architecture, see [ObservabilityArchitecture.md](ObservabilityArchitecture.md).
- Frontend work — see [ObservabilityFrontendPlan.md](ObservabilityFrontendPlan.md).
- Cross-cutting sequencing, dashboard setup, alert rules — see [ObservabilityPlan.md](ObservabilityPlan.md).
