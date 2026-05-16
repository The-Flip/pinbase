# Observability Rollout Plan

Also see:

- [Observability.md](Observability.md)
- [ObservabilityArchitecture.md](ObservabilityArchitecture.md)

## Phases

- [Prerequisites](#prerequisites)
- [ObservabilityBackendPlan.md](ObservabilityBackendPlan.md) — notify about server exceptions.
- [ObservabilityFrontendPlan.md](ObservabilityFrontendPlan.md) — notify about browser & SSR exceptions

Backend ships before frontend because frontend debug route depends on `Activity.OBSERVABILITY_DEBUG` being registered on the backend.

## Prerequisites

Done in Sentry and Railway dashboards before either the backend or frontend deploys; no PRs.

- Sentry org created; `flipcommons-backend` and `flipcommons-frontend` projects exist.
- Both founders invited as org members with per-recipient notification routing configured.
- Railway production env vars set: `SENTRY_DSN` (backend project DSN), `PUBLIC_SENTRY_DSN` (frontend project DSN), `SENTRY_AUTH_TOKEN` (org-scoped, secret), `SENTRY_ORG`, `SENTRY_PROJECT=flipcommons-frontend`.
- Local, CI, and test environments leave all of the above unset — the empty-DSN guard in [ObservabilityArchitecture.md § Environment separation](ObservabilityArchitecture.md#environment-separation) is the master switch.

## Post-deploy (one-time, out-of-band)

Done in the Sentry dashboard after both code PRs are deployed.

- Uptime monitor attached to `flipcommons-frontend`, hitting `/__health` on a 5-minute interval. The endpoint already exists; the architecture rationale is in [ObservabilityArchitecture.md § Uptime](ObservabilityArchitecture.md#uptime).
- Alert rules created in both projects: new issue, regression of resolved issue, uptime check failure. The spike-in-existing-issue rule is deferred until there's production data to tune the threshold against (per [ObservabilityArchitecture.md § Alerting](ObservabilityArchitecture.md#alerting)).
- Default issue assignment left as **unassigned** in both projects.

## Definition of Done

Rollout is complete when:

- Production backend exceptions appear in `flipcommons-backend` with the deployed `RAILWAY_GIT_COMMIT_SHA` as the release tag.
- Production frontend exceptions appear in `flipcommons-frontend` from both SSR and browser paths, with stack traces resolving to TypeScript source (not minified JS).
- A real event payload inspected in the Sentry UI confirms no cookies, no `Authorization` header, no CSRF token, no IP address, no email address. Authenticated events carry `{id, username}`; anonymous events carry no user.
- Uptime monitor reports green and pages both founders on a forced failure.
- New-issue and regression alerts route to both founders' configured destinations.
- Both `/api/sentry_test` and `/_sentry_test` return 403 to non-staff and trigger a Sentry event for staff.
- Local dev and CI runs produce zero Sentry events (verified by absence in the dashboard and by the `SENTRY_DSN`-unset guard test).
