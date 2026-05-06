# Custom User Model

This document proposes implementing a custom user model.

## Related work

This is the first step of an auth-hardening sequence. After this lands, follow-on plans build on the model shape defined here: [Webhooks.md](Webhooks.md) + [Verification.md](Verification.md), then [UserSelfManagement.md](UserSelfManagement.md).

## Problem

This project is pre-launch, and we've deferred the question of how to manage users until now. We're on Django's default `auth.User`, but Django's default `User` is starting to bend under our requirements:

- **No way to enforce email uniqueness cleanly.** `auth.User.email` is `blank=True, unique=False`. The matching logic in `get_or_create_django_user()` (`apps/accounts/api.py:111`) compensates, but only when there's exactly 0 or 1 match — 2+ matches silently create a duplicate user. We need a partial-unique constraint that the default model can't carry.
- **No user-editable URL slug.** With `USERNAME_FIELD = "email"` (proposed below), Django's `username` is freed from being the login identifier and becomes a stable internal handle — but we still need a separate user-editable slug for `/users/<...>` URLs, which the default user model has no clean way to provide.
- **The pending auth-hardening fields don't have a clean home.** [Verification.md](Verification.md) introduces `email_verified`; the provider-switching freshness signal `last_seen_at` needs somewhere to live too. With default `auth.User`, every such field has to land on the existing `UserProfile` sidecar — which makes every read of basic identity state go through `select_related("profile")`.

## Using a custom user model

Django's official guidance is to define a custom user model from day one of any project. Doing it later is famously painful — but the project hasn't launched, so we don't have to migrate; instead, we will drop the DB and re-ingest. The user has confirmed this is acceptable.

## Proposed model

A new `accounts.User(AbstractUser)` plus a small `accounts.SocialAccount` join table that records the underlying OAuth identities (Google `sub`, Apple `sub`, etc.) at login time. The existing `UserProfile` model is dropped; its two fields (`workos_user_id`, `priority`) move onto `User`.

### Prerequisites and project invariants

**BYO OAuth credentials for every social provider — no exceptions.** We register the OAuth client at Google / Apple / GitHub / Microsoft ourselves and hand the `client_id`/`secret` to WorkOS, rather than using WorkOS's default credentials. This is the load-bearing detail that makes `SocialAccount` worth populating: with our own client, the `sub` Google returns is scoped to _our_ OAuth app, not WorkOS's. When we eventually plug those same credentials into a different managed provider (or self-host), Google issues the _same_ `sub` for the same human, so our stored `(google, sub)` pairs match and the new provider can pre-link without forcing re-login.

If we ever switched to WorkOS-owned credentials (or used them for a new provider), the `sub` values we'd accumulate would be scoped to WorkOS's client and useless after a switch — silently undermining the migration story. So this isn't a one-time setup detail, it's a permanent project invariant: when adding any new social provider, register the OAuth app under our own account first.

Currently confirmed BYO: **Google** (registered under our Google Cloud project, configured in WorkOS).

**Spike before merge: confirm two fields are present in the WorkOS auth response.**

`SocialAccount` capture-on-login and the reactivation `email_verified` guard are both committed; the spike just informs _how_ we read the values, not whether the design is viable.

1. **Underlying OAuth `sub`** — three plausible shapes:
   - Inline on `auth_response.user` (simplest — read directly, populate at login).
   - On a separate `identities` field of the response (slightly different access pattern; same cost).
   - Not on the auth response, requires a per-user API call to WorkOS. If so, mitigate by only making the call on first-login-per-provider (cache via the `SocialAccount` existence check).
2. **`email_verified`** — verify it's present, named as expected, and reliable for both OAuth and email/password users. The reactivation guard refuses login if false, so we need to know it's surfaced consistently. Verification.md already references `auth_response.user.email_verified`; confirm rather than assume.

Confirm both before merging so the implementation details are settled, not so the design itself is contingent.

### `accounts.User`

```python
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import field_not_blank


SLUG_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9-]+$",
    message="May contain only lowercase letters, digits, and hyphens.",
)


class User(AbstractUser):
    # AbstractUser already provides:
    #   username, first_name, last_name, email,
    #   is_active, is_staff, is_superuser, last_login, date_joined, password
    #
    # `username` stays as Django's stable internal identifier — never
    # user-editable, defaulted from the email prefix at first login. Used by
    # admin labels, log lines, and any third-party Django package that assumes
    # `username` is identity-shaped. The slug validator keeps it from carrying
    # `@` or `.` (which the default UnicodeUsernameValidator permits) since
    # those would still leak into log identifiers and admin URLs even though
    # `username` is no longer the public URL slug.
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[SLUG_VALIDATOR],
    )

    # User-editable URL slug. /users/<handle>. Separate from `username` so that
    # renames don't make log lines ambiguous and so third-party packages that
    # treat `username` as stable identity keep working. Defaulted from the same
    # email-prefix derivation at first login (so first-login URLs match the
    # internal username), then user-editable on the settings page (per
    # UserSelfManagement.md).
    handle = models.CharField(
        max_length=150,
        unique=True,
        validators=[SLUG_VALIDATOR],
    )

    # Uniqueness is case-insensitive (enforced via the functional index in Meta
    # below); the field itself preserves the user's casing so we display what
    # they typed. Soft-deleted users keep their email for reactivation lookup
    # (see notes below).
    email = models.EmailField()

    # --- Identity / auth-state (gates access) ---

    # Pointer to the WorkOS-side user row — the managed-provider link. Distinct
    # from SocialAccount, which captures the underlying OAuth provider sub
    # (Google, Apple, etc.). When we switch managed providers, this column
    # becomes legacy; SocialAccount rows survive the switch unchanged.
    #
    # null=True only for the soft-delete window: the Webhooks.md user.deleted
    # handler clears workos_user_id (so a returning user can re-bind to this
    # row at reactivation time, see notes below). Active and never-active rows
    # both carry a value. The nullability is load-bearing for the soft-delete
    # contract, not an open invariant.
    workos_user_id = models.CharField(max_length=64, null=True, blank=True, unique=True)

    # Moderation marker. NULL = not banned. Set when an admin (or future
    # Clerk-style provider ban event) bans the user; we also flip is_active=False
    # at the same time. The reactivation path on signup explicitly refuses rows
    # with banned_at IS NOT NULL — without this column, banning is a sign-out-and
    # -sign-back-in away from being undone (see "Reactivation gates" below).
    banned_at = models.DateTimeField(null=True, blank=True)

    # Who issued the ban. NULL = never banned, or banned by a provider event,
    # or banner has since been deleted. SET_NULL because audit records outlive
    # the actor.
    banned_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bans_issued",
    )

    # Request-time freshness signal (see ProviderSwitching.md).
    last_seen_at = models.DateTimeField(null=True, blank=True)

    # --- On-site profile ---

    # Wikipedia-style attribution priority (existing field, moved off UserProfile).
    priority = models.PositiveSmallIntegerField(default=10000)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # createsuperuser will prompt for email + password only.

    class Meta:
        constraints = [
            # Case-insensitive unique email — Alice@... and alice@... collide.
            # Functional index works on PostgreSQL and modern SQLite.
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_unique_email_ci",
            ),
            # Email must be non-empty.
            field_not_blank("email"),
            # workos_user_id may be NULL, but if set, may not be empty string.
            field_not_blank("workos_user_id"),
            # username and handle: not blank and lowercase, enforced at the DB
            # so bulk writes / raw SQL / migrations can't bypass. The full slug
            # shape (only [a-z0-9-]) is enforced by SLUG_VALIDATOR at the app
            # layer — DataModeling.md forbids regex in CHECK constraints, and
            # an explicit character-class LIKE would need 36 NOT-LIKE clauses.
            #
            # The lowercase check uses Lower() (a SQL function, portable across
            # PostgreSQL and SQLite) rather than the existing field_lowercase()
            # helper, which uses __regex internally and contradicts the
            # DataModeling.md "no regex in CHECK" rule. Fixing field_lowercase()
            # itself is a separate cleanup; this PR doesn't perpetuate the bug.
            field_not_blank("username"),
            field_not_blank("handle"),
            models.CheckConstraint(
                condition=Q(username=Lower("username")),
                name="accounts_user_username_lowercase",
            ),
            models.CheckConstraint(
                condition=Q(handle=Lower("handle")),
                name="accounts_user_handle_lowercase",
            ),
            # Ban consistency: a banned user must not be active. Catches the
            # admin-flips-is_active=True-while-banned_at-is-set footgun even
            # though the admin UI funnels through actions; per DataModeling.md
            # "validate in the database."
            models.CheckConstraint(
                condition=Q(banned_at__isnull=True) | Q(is_active=False),
                name="accounts_user_banned_implies_inactive",
            ),
        ]
```

Notes on the choices:

- **`USERNAME_FIELD = "email"`.** The OIDC canonical identifier is `sub`, not email — but `sub` is opaque and provider-scoped, so we link it via `workos_user_id`, not as the login key. Email is the human-readable identifier every provider returns and the natural login key on our side.
- **`username` and `handle` are split.** `username` is Django's stable internal identifier (admin labels, log lines, third-party packages that treat `username` as identity-shaped) — defaulted from the email prefix via `_generate_username()`, never user-editable. `handle` is the user-editable URL slug (`/users/<handle>`) — defaulted to the same email-derived value at first login (so URLs match `username` initially), then editable from the settings page (per [UserSelfManagement.md](UserSelfManagement.md)). Both use the same `SLUG_VALIDATOR` (`[a-z0-9-]+`); `_generate_username()` already normalizes (`dean.moses@example.com` → `dean-moses`). The split decouples log identity from URL slug: when a user renames, `username` doesn't move, so `username=alice` in a log line keeps meaning the same person, and packages assuming `username` is stable (allauth, django-debug-toolbar, audit log libs) keep working.
- **`workos_user_id` is on `User`.** It's identity, not preference — it determines which row a sign-in maps to. Distinct from `SocialAccount` (see below), which captures the underlying OAuth identities; `workos_user_id` is the managed-provider pointer, `SocialAccount` rows are the OAuth-layer identifiers.
- **Full-unique email + reactivation on signup.** One row per email, ever. When a returning user signs in via WorkOS — they got a new `workos_user_id` because they closed and recreated their auth account — `get_or_create_django_user()` matches the soft-deleted row by email and reactivates it (`is_active=True`, re-bind `workos_user_id`, update `last_seen_at`). They keep their contribution history; we don't silently fork their identity into a second row. The alternative (partial-unique on `is_active`) was considered and rejected: it lets the new signup quietly create a fresh row, stranding the old contributions on the soft-deleted row.
- **Reactivation gates — required from day one.** Reactivation is a privilege escalation in disguise (it inherits the prior user's contribution history), so it must be gated. Three checks:
  1. **`auth_response.user.email_verified` must be true.** Without this, an attacker registers victim@oldcompany.com via the email/password path and inherits Alice's history before WorkOS sends the verification email. We don't need the local `email_verified` field yet (that's deferred to [Verification.md](Verification.md)) — the inbound login already carries the verified flag on the WorkOS user object. Read it live; don't reactivate if false.
  2. **`banned_at` must be NULL.** Otherwise banning is reversible by signing out and back in: ban → `is_active=False` → reactivation path flips it back to `True` and re-binds. The `banned_at` column is added in this PR specifically to make reactivation safe; without it, `is_active` is overloaded as both ban and provider-soft-delete and the two are indistinguishable on next login.
  3. **OAuth `sub` must match (when present).** If the user has any `SocialAccount` rows and the inbound login carries an OAuth `sub`, the inbound `(provider, sub)` must match one of them. A mismatch means "different human, don't reactivate" — this is the principled fix for the corporate-email-reassignment case. When the inbound login is email/password (no provider sub) and the user has only an email/password history (no `SocialAccount` rows), this check is a no-op; verified email is the only signal we have, and we accept it.

  Concretely, the reactivation predicate is `is_active=False AND banned_at IS NULL AND inbound.email_verified=True AND (no sub mismatch with existing SocialAccount rows)`. If any clause fails, fall through to "create new account" or "refuse" — never silently reactivate.

- **Soft-delete preserves email.** The [Webhooks.md](Webhooks.md) `user.deleted` handler sets `is_active=False` and clears `workos_user_id`, but **does not** clear `email` — clearing it would make reactivation impossible (no key to match on). If we ever get a hard GDPR-erasure request, that's a separate management-command path that fully purges the row.
- **Email normalization — domain only, RFC-respecting.** The custom `UserManager` (Migration step 4) calls `BaseUserManager.normalize_email()` from Django, which lowercases the _domain_ but preserves the _local-part_. RFC 5321 says the local-part is technically case-sensitive — no real mail provider honors this, but preserving casing means we display `Alice.Smith@example.com` the way she typed it. Uniqueness is enforced case-insensitively by the `Lower("email")` functional index in `Meta`, so `Alice@...` still collides with `alice@...` at the constraint level. Reactivation lookup uses `email__iexact` for the same reason — case-insensitive matching against stored case-preserved values. Per the [DataModeling.md](../../DataModeling.md) "validate in the database" principle, the functional index is the DB-level enforcement that bulk-insert / `update()` / raw SQL / migrations can't bypass.
- **`banned_at` distinguishes bans from provider-soft-deletes; everything else stays on `is_active`.** `is_active` is Django's canonical login gate (admin shows it, `ModelBackend.user_can_authenticate()` honors it). For both moderation bans and provider-`user.deleted` events we set `is_active=False`. The two are distinguished by whether `banned_at` is set — that's enough for the reactivation guard above. We deliberately don't add a separate `is_banned` boolean: the timestamp's nullness is the flag, and there's no second source of truth to drift. `banned_reason` is deferred until we actually have abusive users to annotate; the failure mode without it is a missing audit detail, not a correctness gap.
- **No generic `updated_at` for v1.** Considered and dropped — every event we'd want to capture already has a more specific timestamp (`last_login`, `last_seen_at`, `date_joined`, `banned_at`), and the user-editable fields whose "last touched" would warrant a generic column (bio, avatar, display name) are deferred to UserSelfManagement.md. Add `updated_at` then, when there's something worth tracking generically.

### `accounts.SocialAccount`

Records each OAuth identity linked to a local user — the underlying Google `sub`, Apple `sub`, etc. The shape is just the natural OIDC mirror: provider id, the `sub` claim, when it was linked, when it was last used, and the full claims payload for forensics. Field names are chosen for clarity in our context, not to track any particular library.

```python
class SocialAccount(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_accounts",
    )

    # OAuth provider id. "google", "apple", "github", "microsoft", etc.
    # No choices — the set grows as we enable providers.
    provider = models.CharField(max_length=64)

    # The OIDC `sub` claim from the underlying provider. Stable for a given
    # human-at-provider across managed-auth-provider switches.
    provider_sub = models.CharField(max_length=255)

    # When this identity was first linked to this user.
    linked_at = models.DateTimeField(auto_now_add=True)

    # When this identity was last used to sign in. Distinct from User.last_login
    # (which records any login, regardless of which identity was used).
    last_used_at = models.DateTimeField(auto_now=True)

    # Allowlisted OIDC claims we extracted from the inbound auth response.
    # Allowlist (not deny-list) so adding new keys is an explicit decision
    # rather than passively persisting whatever the provider chose to send.
    # Populated by the auth callback via OAUTH_PAYLOAD_ALLOWED_KEYS; the
    # save() override is a defense-in-depth strip in case a caller passes
    # a wider dict.
    oauth_payload = models.JSONField(default=dict)

    # Keys we intentionally keep from the inbound payload. Everything else
    # is dropped before persistence. Standard OIDC claims plus a couple of
    # forensic non-PII fields (issued-at, issuer).
    OAUTH_PAYLOAD_ALLOWED_KEYS = frozenset({
        "sub",
        "email",
        "email_verified",
        "name",
        "given_name",
        "family_name",
        "picture",
        "iat",
        "iss",
    })

    def save(self, *args, **kwargs):
        if isinstance(self.oauth_payload, dict):
            self.oauth_payload = {
                k: v for k, v in self.oauth_payload.items()
                if k in self.OAUTH_PAYLOAD_ALLOWED_KEYS
            }
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_sub"],
                name="accounts_socialaccount_unique_provider_sub",
            ),
            field_not_blank("provider"),
            field_not_blank("provider_sub"),
        ]
```

Notes:

- **OAuth users only.** Email/password sign-ups don't get a `SocialAccount` row — there's no underlying provider `sub`, only a WorkOS-side password hash. They're anchored to `User.workos_user_id` until we switch managed providers, at which point they need the password-reset path described in [ProviderSwitching.md](ProviderSwitching.md).
- **`(provider, provider_sub)` is globally unique.** A given Google account can be linked to at most one local user. Attempting to link an already-claimed Google account raises and the SPA shows "this account is already linked to another user."
- **CASCADE on `user`.** If a row is hard-deleted (a future GDPR purge command), its identities go too. Soft-delete (`is_active=False`) leaves the rows intact — they're needed for reactivation disambiguation.
- **Allowlist, not deny-list, in `save()`.** "Don't persist `access_token`/`refresh_token`/`id_token`" is the kind of rule that gets forgotten in a future code path, and id_token specifically embeds PII (email, name, picture URL) inside a JWT that anyone with DB read access can decode. Rather than a strip-list that has to grow when providers add claims, we keep an `OAUTH_PAYLOAD_ALLOWED_KEYS` allowlist of decoded claims we actually use. The `save()` override filters to that allowlist as defense in depth — even if a caller passes the raw inbound payload, only the allowed keys land in the column. Bypass paths (`bulk_create`, queryset `update`) exist but aren't in our planned write paths; the rule for any future caller is "go through `save()` or filter explicitly."
- **Why we capture from launch, not later.** Same accumulation argument as `last_seen_at`. Backfilling from WorkOS at switch-time means depending on WorkOS's API to be working _during the migration we're doing because WorkOS isn't working_. The migration scenarios where we'd need this data are exactly the scenarios where the API is least trustworthy. Capturing on every login means by year-end every active user's durable identity is on our side, not theirs.

## What this lets us delete

Things that exist today only because we don't have a custom user model:

- **`UserProfile` itself.** Drop the model, the related-name lookups, the inline in `accounts/admin.py`, the schema in `accounts/api.py`. Every reference to `user.profile.X` becomes `user.X`.
- The `_get_profile()` helper (`api.py:107`) — gone with `UserProfile`.
- The `matches.count() == 1` ambiguity branch in `get_or_create_django_user()` (`api.py:129`). Becomes impossible by construction with the full-unique email constraint — at most one row matches; reactivate it if soft-deleted, otherwise create. (`_generate_username()` itself stays — its output now seeds both `username` and `handle` at first login, but the derivation logic is identical.)
- `from django.contrib.auth.models import User as DjangoUser` (`api.py:13`). Replace with `from apps.accounts.models import User`.
- `from django.contrib.auth.models import User` in `apps/media/tests/test_upload_api.py:9`. Replace with `get_user_model()` (this one's an existing bug — should never have referenced the model directly).

## Migration

The user has confirmed dropping the prod DB and re-running `make pull-ingest && make ingest` is acceptable. That makes this a green-field migration in everything but name.

### Steps

Note on intermediate states: this is a single-PR migration. The tree won't compile at every intermediate step — some imports reference classes that don't exist yet, and `AUTH_USER_MODEL` isn't set until step 3. The end state compiles; that's what matters. Don't try to land these as separate commits expecting each to be green.

1. **Create `apps/accounts/models.py: User(AbstractUser)` and `SocialAccount`** as specified above. Delete the existing `UserProfile` model in the same change. (Done first because subsequent steps reference the new classes.)
2. **Set `AUTH_USER_MODEL = "accounts.User"`** in `config/settings.py`.
3. **Custom `UserManager`** with a `create_user(email, password=None, **extra)` that calls `self.normalize_email(email)` (Django's built-in — lowercases domain, preserves local-part) and seeds both `username` and `handle` from `_generate_username()`. Required because `AbstractUser`'s default manager keys on `username` and won't know about `handle`.
4. **Audit and rewrite every direct `auth.models.User` reference.** Most of the codebase uses `settings.AUTH_USER_MODEL` or `get_user_model()` (good); the rest will silently keep referring to the _old_ `auth.User` after the swap and produce confusing test failures. Don't enumerate by hand — run the grep:

   ```bash
   rg -n "from django\.contrib\.auth\.models import.*\bUser\b|django\.contrib\.auth\.models\.User|auth\.models\.User" backend/
   ```

   At time of writing this hits ~10 files across `apps/accounts/`, `apps/provenance/`, `apps/core/`, and `apps/media/`. Rewrite each:
   - In `apps/accounts/models.py` (the new home): leave alone — the new `User` class lives here.
   - In application code: replace with `from apps.accounts.models import User` (preferred when type-annotating model FKs / signals) or `get_user_model()` (preferred at module-level helpers and tests).
   - In `models.py` files anywhere: never import the model directly for FKs — use `settings.AUTH_USER_MODEL` as a string. The grep should come up clean for FKs after this pass.
   - Re-run the grep after the rewrite to confirm zero hits outside `apps/accounts/models.py`.

5. **Remove existing migrations from a clean slate.** Since we're dropping the DB:
   - **First, audit for `RunPython` / `RunSQL` operations.** Grep `backend/apps/*/migrations/` for non-trivial data migrations — default-row inserts, backfills, constraint repair, anything that encodes behavior the schema alone doesn't carry. `provenance`, `catalog`, and `core` are the likely sites. Port any such logic into a fresh data migration before deleting the originals; otherwise it's lost silently.
   - Delete every app's `migrations/00*.py` files (keep `__init__.py`).
   - Run `make migrate-fresh` (or equivalent) to regenerate all migrations against the new user model.
   - Re-run `make ingest` to repopulate catalog data.
6. **Update `apps/accounts/admin.py`** to register the custom user model with a custom `UserAdmin` (Django requires this; the default `auth.UserAdmin` has hardcoded references to `username` as the login field). Drop the `UserProfileInline`. Add `ban_users` / `unban_users` admin actions that flip `is_active`, `banned_at`, and `banned_by` together — `ban_users` sets `banned_at=now`, `banned_by=request.user`, `is_active=False`; `unban_users` clears `banned_at`/`banned_by` and sets `is_active=True`. Put `banned_at` and `banned_by` in `readonly_fields` so the actions are the _only_ path that can mutate them. Without that, an admin could set one without the others and produce a half-banned state. `is_active` itself stays editable — temporarily disabling a staff account is a legitimate use, and the worst an admin can do by accident is produce a soft-delete (a real distinct state), never a half-ban. Also register `SocialAccount` with a read-only admin (rows are written by the auth flow at login, not by hand — read-only prevents an admin from accidentally creating a row that would let someone log in as another user).
7. **Update `apps/accounts/api.py`:**
   - `_generate_username` derives from the email prefix as today, but normalizes to the new slug shape: lowercase, replace `.` / `_` / `+` with `-`, strip anything outside `[a-z0-9-]`, collapse repeated hyphens, trim leading/trailing hyphens. Same function seeds both `username` and `handle` at first login. Wrap the existing `.exists()` collision loop with a single retry-on-`IntegrityError` (TOCTOU race: two concurrent first-logins both pick `alice`, one fails the unique index — re-run the loop once with a fresh `.exists()` check, which will now find the winner's row and pick the next suffix). If the retry also fails, propagate.
   - `get_or_create_django_user` simplifies and gains gated reactivation. The inbound payload is `auth_response.user`; for OAuth logins, also extract the underlying `(provider, provider_sub)` (exact path TBD per the prerequisite spike). Four branches:
     1. **Lookup by `workos_user_id`.** If found and `is_active=True` and `banned_at IS NULL` → refresh mirrored fields (see below), upsert any inbound `(provider, provider_sub)` into `SocialAccount`, return. If found but banned or inactive → refuse the login (allowing a session here would let a banned user keep editing simply because their `workos_user_id` is still bound).
     2. **Else lookup by `email__iexact`** (active or soft-deleted). If found and reactivation guards all pass — `is_active=False` _and_ `banned_at IS NULL` _and_ `inbound.email_verified=True` _and_ no `(provider, provider_sub)` mismatch against existing `SocialAccount` rows — reactivate (`is_active=True`, re-bind `workos_user_id`, refresh mirrored fields, upsert inbound `(provider, provider_sub)`, save) and return.
     3. **Else if found by email but a guard failed** (banned, unverified inbound email, or `(provider, provider_sub)` mismatch) → refuse the login with a clear error; do not silently create a new row, since that would orphan the old contributions.
     4. **Else create a new user** via the manager and write the inbound `(provider, provider_sub)` as the first `SocialAccount` row. Wrap in `IntegrityError` retry-by-re-lookup: two simultaneous first-logins for the same email both miss the lookup, both `INSERT`, one wins the unique index — the loser re-runs the lookup and proceeds via branches 1–3. The same handler also catches the "two WorkOS accounts claim the same local user" case: a `workos_user_id` collision on insert means we tried to bind an `id` that's already on a different active row. Log at error level ("two WorkOS accounts claim same local user, refusing login until admin resolves") and refuse — surface it loudly so a human can untangle.

     Drop the `count() == 1` ambiguity path and the `_get_profile()` call.

   - **Mirrored fields, explicitly.** "Refresh mirrored fields" means: `email`, `first_name`, `last_name` — copied verbatim from `auth_response.user`. That's the v1 list; `email_verified` joins it when [Verification.md](Verification.md) lands. Save with `update_fields=["email", "first_name", "last_name"]` so `last_login` (handled by Django's signal) and any future `updated_at` aren't disturbed.
   - **`SocialAccount` upsert — not `get_or_create`, not `update_or_create`.** Both have hazards: `get_or_create` doesn't refresh the existing row, so `last_used_at` (auto_now) freezes at link-time and `oauth_payload` never reflects later claim changes. `update_or_create` would silently re-bind a row to a new user when the same `(provider, provider_sub)` pair exists under a different `user_id` — that's exactly the "different local user already claims this account" case we want to refuse loudly. So:

     ```python
     try:
         sa = SocialAccount.objects.get(provider=p, provider_sub=s)
     except SocialAccount.DoesNotExist:
         SocialAccount.objects.create(user=user, provider=p, provider_sub=s, oauth_payload=claims)
     else:
         if sa.user_id != user.id:
             raise SocialAccountConflict(...)  # different local user owns this Google/Apple/etc. account
         sa.oauth_payload = claims
         sa.save(update_fields=["oauth_payload", "last_used_at"])
     ```

     `last_used_at` _must_ appear in `update_fields` even though it's `auto_now=True` — when `update_fields` is specified, Django writes only the listed columns, and auto_now-on-save only takes effect for columns that will actually be written. Easy to miss; spell it out.

     `oauth_payload` is reassigned (not mutated in place) so `SocialAccount.save()`'s allowlist filter runs on the new payload, stripping any new bearer tokens or unrecognized claims the provider added since the row was created.

   - **Email-change re-verification.** When a webhook (or a future settings-page edit) changes a user's email, `email_verified` flips back to false until the new address is re-verified. Owned by [Verification.md](Verification.md); flagged here so it doesn't fall through.
   - `UserProfileSchema` and any `user.profile.X` reads collapse to fields on `user`.
   - `auth_me` and `user_profile_page` route by `handle`, not `username` — `handle` is the public URL slug. `user_profile_page` accepts a `handle` URL kwarg and looks up by that field.

8. **Update `apps/accounts/signals.py`** if it has a `post_save` profile-creation hook — delete it; there's no profile to create.
9. **Update `apps/accounts/backends.py: WorkOSBackend.get_user()`** to refuse banned and inactive users. Replace the body so the lookup filters them out:

   ```python
   def get_user(self, user_id):
       try:
           return User.objects.get(pk=user_id, is_active=True, banned_at__isnull=True)
       except User.DoesNotExist:
           return None
   ```

   Defense in depth: the login path (`get_or_create_django_user`) refuses banned users, but `get_user()` runs on every authenticated request via `AuthenticationMiddleware`. Filtering here means a freshly-banned user with a live session cookie stops being authenticated on the very next request, with no need to flush sessions.

10. **Add a middleware to populate `last_seen_at`.** Without a writer, the column stays NULL forever and provides no value at provider-switch time — the whole point is to have the value accumulating now. Shape:
    - **Guard on `request.user.is_authenticated` first.** For unauthenticated requests `request.user` is `AnonymousUser`, which has no `last_seen_at` attribute and would `AttributeError`. Skip the rest of the middleware in that case.
    - **Debounce to once per day per user, using the stored field value as the debounce state** — read `request.user.last_seen_at` (already loaded by `AuthenticationMiddleware` for authenticated users, no extra SELECT) and skip the UPDATE if it's within the last 24h.
    - Don't keep an in-memory `{user_id: last_write}` cache: that resets on every server restart and would spike a write per active user at boot.
    - Wire the middleware into `MIDDLEWARE` in `config/settings.py` after `AuthenticationMiddleware`.
    - Leave a `# TODO(perf):` at the UPDATE call site noting that under traffic this should move off the request path (`transaction.on_commit` or a queue). At v1 scale it's fine; the TODO is for future-grep when it isn't.
11. **Update tests.** Anything that does `User.objects.create_user(username="...")` needs to switch to `email=...`. Anything that asserts on `user.profile.X` becomes `user.X`.
12. **Update `apps/accounts/test_factories.py`** (and provenance test factories) to construct users via the new manager and drop `UserProfile` factory usage.

### Migration is one-way

We're not building a backwards path. Once migrations regenerate and the dev DB is re-seeded, there's no "switch back to `auth.User`" scenario worth supporting. Branch this work, prove it green, merge.

### Coordinating with other open auth plans

Several in-flight plan docs assume the old shape (default `auth.User` + `UserProfile` sidecar). After landing this:

- **[Verification.md](Verification.md)** — proposed `UserProfile.email_verified` lands as `User.email_verified`. The field is added by the Verification.md PR itself, not this one — it's read live from the provider on each login, so there's no accumulation reason to add it early. The `(provider, provider_sub)` external-identity table that Verification.md also proposed lands here instead, in this PR, populated continuously from launch — see the `SocialAccount` model above.
- **[Webhooks.md](Webhooks.md)** — `profile.workos_user_id` collapses to `user.workos_user_id`. The proposed `is_banned` mirroring (Clerk-only `user.banned`/`user.unbanned` events) folds into setting `user.is_active=False` for v1, with the same session-flush behavior. Revisit when we actually have abusive users. The flush-sessions helper still works (it walks `_auth_user_id`).
- **[ProviderSwitching.md](ProviderSwitching.md)** — `last_seen_at` lands on `User`. The provider-switching playbook is otherwise unaffected.
- **[UserSelfManagement.md](UserSelfManagement.md)** — the Field-by-Field Proposal table needs updating: the proposed `UserProfile.handle` lands as `User.handle` (added in this PR, separate from the internal `User.username`). All other proposed fields (`display_name_override`, `bio`, avatar fields, notification/privacy toggles) are out of scope for this PR — they land on `User` when UserSelfManagement.md actually ships, paired with the settings-page UI that consumes them. The "Why the username / handle split" section in that doc still applies, just with the field locations confirmed (both on `User`, not on a sidecar).

We don't need to update those docs in lockstep with this one — they describe the target shape, and once the custom user lands, the field locations drift in the obvious way. A single follow-up commit can sweep them.

## Open questions

- **Drop `workos_user_id` once `SocialAccount` is in v1?** Considered. Keeping it because it serves a different purpose: `workos_user_id` is the managed-provider pointer (the WorkOS-row primary key, used for fast lookup at login), while `SocialAccount` captures the underlying OAuth identities (Google `sub`, Apple `sub`). They sit at different layers — when we switch managed providers, `workos_user_id` becomes legacy and a new `clerk_user_id` (or generalized column) takes its place; `SocialAccount` rows survive unchanged. Email/password users have a `workos_user_id` but no `SocialAccount` rows; OAuth users have both. Drop `workos_user_id` only when we generalize it to a `(managed_provider, managed_provider_user_id)` shape — out of scope here.
- **When (if ever) does a sidecar earn its keep?** Not now. The trigger would be a real role distinction (`MuseumStaff`, `Volunteer`, `Editor` with permissions) — at which point we'd add a Flipfix-`Maintainer`-style model alongside `User`, not split user fields out of it.

## Non-goals

- **Roles / permissions / trust tiers.** This doc adds the model; the authorization design is its own future doc.
- **Account merge for the same human across two providers.** Future doc.
- **Custom `AbstractBaseUser` (vs. `AbstractUser`).** The smaller leap; we lose nothing by keeping `AbstractUser`'s built-ins.
- **Handle history table for 301 redirects.** Mentioned in UserSelfManagement.md as a future concern; out of scope here.
- **Mass user import from any existing data source.** There isn't a meaningful existing user base — Flipcommons hasn't launched. Re-ingest creates no users; users are created at first login.
