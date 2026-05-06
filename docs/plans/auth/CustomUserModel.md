# Custom User Model

## Problem

We're on Django's default `auth.User`. That decision was load-bearing back when the project was going to share an identity stack with The Flip's other properties (Flipfix, Juice, theflip.museum) — a custom user model under one app would have been awkward to share. Flipcommons has since evolved into its own thing on its own domain, and Django's default `User` is starting to bend under our requirements:

- **No way to enforce email uniqueness cleanly.** `auth.User.email` is `blank=True, unique=False`. The matching logic in `get_or_create_django_user()` (`apps/accounts/api.py:111`) compensates, but only when there's exactly 0 or 1 match — 2+ matches silently create a duplicate user. We need a partial-unique constraint that the default model can't carry.
- **`UserProfile` is becoming an identity sidecar.** The proposed fields across [Verification.md](Verification.md), [Webhooks.md](Webhooks.md), and [UserSelfManagement.md](UserSelfManagement.md) (`workos_user_id`, `email_verified`, `is_banned`, `last_seen_at`, `deactivated_at`, `display_name_override`) are mostly identity, not preferences. The 1-1 split with `auth.User` is starting to feel arbitrary, and every read needs `select_related("profile")`.
- **`username` is auto-derived from email and not user-editable.** With `USERNAME_FIELD = "email"` (proposed below), `username` loses its login-identifier role and is free to take over as the user-editable URL slug — but the default user model gives us no clean way to expose it for editing.
- **Django's official guidance** is to define a custom user model from day one of any project. Doing it later is famously painful — but the project hasn't launched, so the migration cost is just "drop the dev DB and re-ingest," which the user has confirmed is acceptable.

This doc proposes the custom user model, the field split between `User` and `UserProfile`, and the migration path.

## Proposed model

A new `accounts.User(AbstractUser)`. The split below assumes we're keeping `UserProfile` as a thinner sidecar — identity and auth state on `User`, display preferences on `UserProfile`.

### `accounts.User`

Identity, auth state, anything that gates access:

```python
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    # AbstractUser already provides:
    #   username, first_name, last_name, email,
    #   is_active, is_staff, is_superuser, last_login, date_joined, password
    #
    # `username` is repurposed: with USERNAME_FIELD = "email" it's no longer the
    # login identifier, so we use it as the user-editable URL slug
    # (/users/<username>). Defaulted from the email prefix at first login,
    # editable later from the settings page.

    # Override to enforce uniqueness and require non-empty.
    email = models.EmailField(unique=False)  # uniqueness enforced via partial constraint below

    # Identity link to the auth provider. Stays here (not UserProfile)
    # because it gates which user a sign-in maps to.
    workos_user_id = models.CharField(max_length=64, null=True, blank=True, unique=True)

    # Mirrored from the provider on every login + via webhook.
    email_verified = models.BooleanField(default=False)

    # Local moderation / lifecycle state. Owned by us, not the provider.
    is_banned = models.BooleanField(default=False)
    banned_at = models.DateTimeField(null=True, blank=True)
    banned_reason = models.CharField(max_length=255, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)

    # Request-time freshness signal (see ProviderSwitching.md).
    last_seen_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # createsuperuser will prompt for email + password only.

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(is_active=True),
                name="unique_active_user_email",
            ),
        ]
```

Notes on the choices:

- **`USERNAME_FIELD = "email"`.** Aligns with how OIDC actually works — every provider returns email as the canonical identifier. Email becomes both the login key and the natural human identifier.
- **`username` is the URL slug.** With `USERNAME_FIELD = "email"`, `username` loses its login-identifier role and becomes a plain slug field that we use for `/users/<username>` URLs and wiki-style links. Continues to be defaulted from the email prefix at first login (existing `_generate_username()` keeps doing what it does), and becomes user-editable on the settings page (per [UserSelfManagement.md](UserSelfManagement.md)). One slug field instead of two — no parallel `handle`. Django admin labels still read "username," which is fine semantically since that's still what it is.
- **`workos_user_id` moves from `UserProfile` to `User`.** It's identity, not preference — it determines which row a sign-in maps to. The `(provider, sub)` external-identity table from [Verification.md](Verification.md) eventually replaces this single column, but for v1 a column on `User` is fine.
- **Partial unique on email.** The constraint allows multiple soft-deleted users to share a freed email, while preventing two active users from sharing one. Plays correctly with the soft-delete pattern in [Webhooks.md](Webhooks.md) — when we set `is_active=False`, the row drops out of the constraint and the email becomes available for a new account.
- **Email normalization.** Django's `EmailField` does not lowercase emails. Override `save()` (or use a manager) to normalize to lowercase before insert; otherwise `Foo@example.com` and `foo@example.com` slip past the unique constraint.

### `accounts.UserProfile` (slimmer)

Display preferences and on-site profile data only — nothing that gates access:

```python
class UserProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # Wikipedia-style attribution priority (existing field).
    priority = models.PositiveSmallIntegerField(default=10000)

    # From UserSelfManagement.md.
    display_name_override = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    avatar_source = models.CharField(
        max_length=16,
        choices=[("PROVIDER", "Provider"), ("UPLOADED", "Uploaded"), ("INITIALS", "Initials")],
        default="PROVIDER",
    )
    avatar_uploaded = models.ImageField(null=True, blank=True, upload_to="avatars/")

    # Privacy toggles.
    show_real_name_on_edits = models.BooleanField(default=True)

    # Notification preferences (forward-looking; minimum viable shape).
    email_notifications_enabled = models.BooleanField(default=True)
```

The split rule of thumb: **if it gates access, it's on `User`. If it's a display knob, it's on `UserProfile`.** Banning is on `User`. Bio is on `UserProfile`. Email-verification is on `User` because it gates the edit path. Avatar choice is on `UserProfile` because it's purely cosmetic.

## What this lets us delete

Things that exist today only because we don't have a custom user model:

- The `matches.count() == 1` ambiguity branch in `get_or_create_django_user()` (api.py:129). Becomes impossible by construction with the partial-unique-email constraint — `.get()` instead of conditional logic. (`_generate_username()` itself stays — `username` is now the editable URL slug, and the email-prefix default is still the right starting value.)
- The `_get_profile()` helper (api.py:107). The `User.profile` related-name is enough; if we ever want eager loading, callers add `select_related`.
- `from django.contrib.auth.models import User as DjangoUser` (api.py:13). Replace with `from apps.accounts.models import User`.
- `from django.contrib.auth.models import User` in `apps/media/tests/test_upload_api.py:9`. Replace with `get_user_model()` (this one's an existing bug — should never have referenced the model directly).

## Migration

The user has confirmed dropping the prod DB and re-running `make pull-ingest && make ingest` is acceptable. That makes this a green-field migration in everything but name.

### Steps

1. **Audit existing FK references.** Most of the codebase already uses `settings.AUTH_USER_MODEL` (good) or `get_user_model()` (good). The grep that needs fixing:
   - `apps/media/tests/test_upload_api.py:9` — direct `from django.contrib.auth.models import User` import. Change to `get_user_model()`.
   - `apps/accounts/api.py:13` — direct import of `User as DjangoUser`. Change to import from `apps.accounts.models`.
2. **Create `apps/accounts/models.py: User(AbstractUser)`** as specified above.
3. **Set `AUTH_USER_MODEL = "accounts.User"`** in `config/settings.py`.
4. **Remove existing migrations from a clean slate.** Since we're dropping the DB:
   - Delete every app's `migrations/00*.py` files (keep `__init__.py`).
   - Run `make migrate-fresh` (or equivalent) to regenerate all migrations against the new user model.
   - Re-run `make ingest` to repopulate catalog data.
5. **Custom `UserManager`** with a `create_user(email, password=None, **extra)` that lowercases email and generates a default `handle`. Required because `AbstractUser`'s default manager keys on `username`.
6. **Update `apps/accounts/admin.py`** to register the custom user model with a custom `UserAdmin` (Django requires this; the default `auth.UserAdmin` has hardcoded references to `username` as the login field).
7. **Update `apps/accounts/api.py`:**
   - `_generate_username` keeps doing what it does today — its output now seeds the user-editable URL slug rather than a login identifier, but the derivation logic is identical.
   - `get_or_create_django_user` simplifies — drop the `count() == 1` ambiguity path.
   - `auth_me` and `user_profile_page` continue to use `username` (now interpreted as a URL slug, not a login identifier).
8. **Update `apps/accounts/signals.py`** if it has a `post_save` profile-creation hook — should still work, but verify it sees the new model.
9. **Update tests.** Anything that does `User.objects.create_user(username="...")` needs to switch to `email=...`. Anything that asserts on `user.username` may need `user.handle`.
10. **Update `apps/accounts/test_factories.py`** (and provenance test factories) to construct users via the new manager.

### Migration is one-way

We're not building a backwards path. Once migrations regenerate and the dev DB is re-seeded, there's no "switch back to `auth.User`" scenario worth supporting. Branch this work, prove it green, merge.

### Coordinating with other open auth plans

Several in-flight plan docs assume the old shape. After landing this:

- **[Verification.md](Verification.md)** — `email_verified` field moves from `UserProfile` to `User`. Update the doc when implementation lands.
- **[Webhooks.md](Webhooks.md)** — references to `profile.workos_user_id` and `profile.is_banned` become `user.workos_user_id` and `user.is_banned`. The flush-sessions helper still works (it walks `_auth_user_id`).
- **[ProviderSwitching.md](ProviderSwitching.md)** — `last_seen_at` moves to `User`. The provider-switching playbook is otherwise unaffected.
- **[UserSelfManagement.md](UserSelfManagement.md)** — the Field-by-Field Proposal table needs updating: the proposed `UserProfile.handle` becomes `User.username` (the existing field, repurposed as the user-editable URL slug now that `USERNAME_FIELD = "email"`); `User.first_name/last_name` (unchanged); `UserProfile.display_name_override` (unchanged). The "Why the username / handle split" section in that doc is obsolete and should be replaced with a short note that `username` plays both roles cleanly under the custom user model.

We don't need to update those docs in lockstep with this one — they describe the target shape, and once the custom user lands, the field locations drift in the obvious way. A single follow-up commit can sweep them.

## Open questions

- **Should ban / deactivation also move to `UserProfile`?** Argument for: keeps `User` minimal. Argument against: these gate access, and Django's `is_active` is the canonical "can this user log in" signal — pairing our extra flags next to it on `User` keeps the access-control surface in one place. Going with the latter.
- **Full consolidation into `User`, drop `UserProfile`?** Considered and rejected above. Keeping the split because `User` is something Django itself reaches into (admin, auth middleware, permissions); `UserProfile` is a plain model we can iterate freely without worrying about whether some Django internal expects a particular attribute.
- **Move `workos_user_id` to a future `ExternalIdentity(provider, provider_sub)` table?** Yes eventually, per [Verification.md](Verification.md). Not in this PR. Single column for v1 is the right amount of premature.

## Non-goals

- **Roles / permissions / trust tiers.** This doc adds the model; the authorization design is its own future doc.
- **Account merge for the same human across two providers.** Future doc.
- **Custom `AbstractBaseUser` (vs. `AbstractUser`).** The smaller leap; we lose nothing by keeping `AbstractUser`'s built-ins.
- **Username/handle history table for 301 redirects.** Mentioned in UserSelfManagement.md as a future concern; out of scope here.
- **Mass user import from any existing data source.** There isn't a meaningful existing user base — Flipcommons hasn't launched. Re-ingest creates no users; users are created at first login.
