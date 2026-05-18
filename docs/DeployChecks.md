# Deployment Preflight Checks

This documents how to add production preflight checks via Django's system check framework. For the operator-facing view (what `preDeployCommand` does, how failures surface in Railway), see [Hosting.md](Hosting.md).

These checks are not to be confused with a runtime liveness/readiness endpoint (e.g. `/healthz`). These checks run once at deploy time, in-process, before the new container takes traffic — they do not probe a running service.

## Design philosophy

### One service, one env

Backend and frontend ship in the same Railway container, with the same env-var scope. Anything Railway sets on the service is visible to both Django at runtime and SvelteKit at build + runtime. There is no per-process env separation to work around.

### Frontend checks belong in Python

Because the backend and frontend share an env, every env var the frontend needs is readable from `os.environ` in Django. There is no separate frontend preflight.

When a new `PUBLIC_*` var becomes required in production, the assertion goes in `apps/<name>/checks.py`, not in `vite.config.ts`, `instrumentation.server.ts`, or `hooks.client.ts`.

### Checks gate promotion; there is no rollback

The checks run via `preDeployCommand` (`manage.py check --deploy && manage.py migrate`).

These checks run **before** the new container takes traffic. If it fails, Railway does not promote the new deploy; the old container keeps serving. There is no "deploy rolled back" state to worry about — there is only "the new version never went live."

Migrations are part of the same gate: a failing `migrate` step blocks promotion exactly like a failing check. Treat schema changes with the same care — there is no in-place rollback path.

### These checks are our automation frontline

We are a [small team of volunteers](SmallTeam.md); there's no professional IT, nobody looking at logs. Everything must be automated. Prefer failing a check to logging a potential problem.

We deploy automatically on merges to `main`; nobody's looking at log warnings or checking the site thoroughly after deploy.

### Check aggressively

Deploy checks should be aggressive. A failed check means "stay on the old version," not "page someone at 2am.". Prefer raising the bar (Error) over hoping someone reads the logs (Warning).

### Error vs Warning

- **Error** — the deploy is broken without this. Block promotion. Examples: missing `SENTRY_DSN` in production, misconfigured storage credentials.
- **Warning** — operator should notice, but the service still works. Surface in logs without blocking. Example: `core.W001` (`RATE_LIMIT_TRUST_PROXY_HEADERS` off in non-DEBUG — IP rate limiters degrade silently but the site still runs).

When in doubt, prefer Error.

### Assert env-var shape, don't probe services

Deploy checks run in-process during `preDeployCommand`. They can read `settings` and `os.environ` cheaply, but they are the wrong place to open sockets, hit S3/R2, or query the DB. Network probes are slow, flaky, and turn a deploy gate into a dependency-availability gate — a transient blip in an upstream service blocks promotion of an unrelated change.

Assert that env vars are **present and well-formed** (correct prefix, parseable URL, expected length). "Can we actually reach the bucket" is a runtime-readiness concern, not a deploy-gate concern. We don't have a runtime readiness endpoint yet; if we add one, that's where connectivity probes would go.

## Adding a check

Checks live in `apps/<name>/checks.py` and are imported from the app's `AppConfig.ready()`. Two decorator shapes:

```python
from collections.abc import Sequence
from typing import Any

from django.apps.config import AppConfig
from django.core.checks import CheckMessage, Error, Tags, Warning, register

# Always runs (under `manage.py check` and at server boot).
@register(Tags.models)
def check_something(
    app_configs: Sequence[AppConfig] | None,
    **kwargs: Any,  # noqa: ANN401
) -> list[CheckMessage]:
    _ = app_configs, kwargs
    ...

# Only runs under `manage.py check --deploy` — i.e., in production preflight.
@register(Tags.security, deploy=True)
def check_prod_env(
    app_configs: Sequence[AppConfig] | None,
    **kwargs: Any,  # noqa: ANN401
) -> list[CheckMessage]:
    _ = app_configs, kwargs
    ...
```

`**kwargs: Any` is required by Django's check-framework signature (it may carry forward-compatible options like `databases`); the `noqa: ANN401` is the documented escape hatch. The `_ = app_configs, kwargs` line marks them as intentionally unread.

Pick a tag from `django.core.checks.Tags` that matches the domain (`security`, `models`, `database`, etc.). Return a list of `Error` / `Warning` with a stable `id` like `core.E101` or `core.W001` — the id is what operators grep for in logs.

See [`apps/core/checks.py`](../backend/apps/core/checks.py) for the full shape and `check_rate_limit_proxy_trust` as a worked deploy-gated example.

### Running deploy checks locally

`--deploy` checks are skipped under `DEBUG=True`, so reproducing what Railway runs requires faking a production-shaped env:

```sh
DEBUG=false \
RATE_LIMIT_TRUST_PROXY_HEADERS=false \
SECRET_KEY=dummy123456789012345678901234567890123456789012345 \
  uv run python manage.py check --deploy
```

Flip the var your check inspects to confirm it actually fires; flip it back to confirm it goes quiet.

### Testing

Every deploy-gated check should have a unit test that sets the relevant `settings`/env state and asserts the check returns (or doesn't return) the expected message id. The id is the contract — operators search logs for `core.W001`, not for the human-readable message — so pin it in the test.
