# Observability

We use **[Sentry.io](https://sentry.io)** to learn when production has problems before a user has to tell us. Error capture and alerting — nothing else. No tracing, no profiling, no session replay, no analytics.

In Sentry, we have two projects:

- `flipcommons-backend`: Python/Django
- `flipcommons-frontend`: JavaScript/SvelteKit — both SSR and browser report here

## Sentry config

For the Sentry-side configuration (env vars, scrubbing rules, alert rules), see [Hosting.md § Sentry](Hosting.md#sentry).

## The master switch: DSN presence

A **DSN** (Data Source Name) is Sentry's name for the per-project URL to posts events to. It identifies the project and authenticates the write — it's a public write-only key by design, not a secret. Each of our two projects has its own DSN.

Each runtime's SDK init runs only when its own DSN env var is non-empty: the backend gates on `SENTRY_DSN`, the frontend (SSR + browser) gates on `PUBLIC_SENTRY_DSN`. Local, CI, and test environments leave both unset and the init blocks no-op. There is no per-environment matrix and no runtime kill switch — disabling Sentry in prod means removing the DSN and redeploying.

## What we capture

- Unhandled backend exceptions (via `DjangoIntegration`).
- Unhandled SSR and browser exceptions (via `@sentry/sveltekit`).
- Explicit `sentry_sdk.capture_*` calls for swallowed-but-noteworthy cases.

## Things we don't capture

Some of the things we explicitly don't capture:

- **Backend**: validation errors, expected permission denials, expected 404s, structured 4xx errors (rate limits, etc.).
- **Frontend**: `ResizeObserver` notifications, navigation aborts, `ChunkLoadError`, non-Error throws.

## Logs ≠ alerts

`logger.info/warning/error` flows to stdout and stays there. To send to Sentry, code must call the Sentry SDK's `capture_*` API explicitly. On the backend, `LoggingIntegration(level=INFO, event_level=None)` attaches log records as breadcrumbs on real events but never promotes them to standalone Sentry events. This keeps authz denials, validation errors, and rate-limit hits out of the alert stream by construction.

## Privacy

Sentry **does not store**: emails, IPs, request bodies, cookies, session tokens. (Some never leave the app — the SDK is configured not to extract them. The rest are stripped server-side at ingest by Sentry's Advanced Data Scrubbing rules before storage.)

Sentry **does store**: route name, HTTP method, status code, exception type/message/stack trace, release SHA, environment, user id and username (authenticated requests only), `auth_state` tag (`"auth"`/`"anon"`), full User-Agent (plus `ua_family` tag for filtering).

Differnt bits of this enforcement live in different layers:

- Sentry SDK init options
- A Sentry-provided Python `EventScrubber`
- Sentry Advanced Data Scrubbing rules — see [Hosting.md § Sentry](Hosting.md#sentry) for the dashboard half.

## Release correlation

Events and uploaded sourcemaps are both tagged with `RAILWAY_GIT_COMMIT_SHA`, so production stack traces resolve to source and issues tie to a specific deploy in Sentry.
