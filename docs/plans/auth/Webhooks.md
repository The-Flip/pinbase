# Webhook-Driven Sync from the Auth Provider

## Problem

Today we only refresh local user state inside `get_or_create_django_user()` (`backend/apps/accounts/api.py:111`), which runs on login. Anything that changes at the auth provider _between_ logins is invisible to us until that user signs in again — which for an active session could be days or weeks.

The events we currently miss:

- **Email change.** A user updates their email at WorkOS. We keep showing the old one, and our email-fallback re-link branch (`api.py:129`) compares against stale data.
- **Email verification flips.** A user clicks the verification link mid-session. They're still blocked from editing on our side until their session expires and they sign in fresh.
- **Admin ban at the provider.** Once we mirror Clerk's `banned` flag (see [EmailVerification.md](EmailVerification.md)), this matters even more — a banned user with a live Django session cookie keeps editing until the cookie expires, because Clerk only refuses _new_ sign-ins.
- **Account deletion.** A user closes their account at the provider. We have no way to know, so their email/identity stays in our DB indefinitely. That's a GDPR / data-hygiene problem the moment we go live.
- **Profile updates.** Name, picture URL, etc. — low stakes, but trivially fixable.

Login-driven sync is fine for steady-state UX but wrong for moderation, security, and account-lifecycle concerns. The right fix is to let the provider _push_ state changes to us.

## Proposed Solution

Add a single webhook endpoint that receives provider events, verifies the signature, and updates `UserProfile` accordingly. Keep it provider-agnostic enough that swapping WorkOS for Clerk or Auth0 changes only the verifier and the event-name mapping.

### 1. The endpoint

```
POST /api/auth/webhooks/
```

Public (no session auth), but every request must carry a valid provider signature. Unsigned or mis-signed requests get a `401` and are not processed. The view is CSRF-exempt because the caller is the provider, not a browser.

WorkOS signs webhook bodies with HMAC-SHA256 using a configured `WORKOS_WEBHOOK_SECRET`. The SDK exposes `client.webhooks.verify_event(payload, sig_header, secret)`. Clerk uses Svix-signed webhooks; their SDK has the equivalent verifier. The verifier is the only provider-specific piece in the request path.

### 2. Events we care about

| Provider event (WorkOS naming)  | Local effect                                                                                                         |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `user.updated`                  | Refresh `email`, `first_name`, `last_name`, `email_verified`, profile picture URL on the local user / `UserProfile`. |
| `user.deleted`                  | Soft-delete the local user (`is_active = False`, clear `workos_user_id`, keep content attribution).                  |
| `email_verification.created`    | (If Clerk) flip `UserProfile.email_verified = True` and lift the edit gate immediately.                              |
| `user.banned` / `user.unbanned` | (Clerk-specific) flip `user.is_active` (false on ban, true on unban); on ban, also flush the user's Django sessions. |

We **don't** handle `user.created` from the webhook. Local user creation stays login-driven — we only want to materialize a Django user when they actually arrive on our site, not when they're just sitting in the auth provider's DB. If we ever receive an updated/deleted event for a user we've never seen locally, we log and skip.

### 3. Handler shape

Dispatch on event type to small, named functions:

```python
def handle_user_updated(provider_user) -> None: ...
def handle_user_deleted(provider_user) -> None: ...
def handle_user_banned(provider_user) -> None: ...
```

Each function looks the user up by `workos_user_id` (the durable link), updates the relevant fields, and saves with explicit `update_fields=[...]`. Last-write-wins is fine for everything except deletion, which is a one-way transition.

Reuse logic between the webhook handlers and `get_or_create_django_user()` where it makes sense — both paths ultimately do "given a provider user object, update our local mirror." Extracting a `_sync_profile_from_provider(profile, provider_user)` helper keeps the two code paths from drifting.

### 4. Account deletion — soft-delete, don't drop the row

When `user.deleted` arrives, we can't `DELETE` the local user: their `id` is referenced by `ChangeSet.user`, `Claim.user`, and the entire contribution history. Cascading would erase the audit trail.

Instead:

- `user.is_active = False` — Django's auth middleware already refuses login for inactive users.
- `user.workos_user_id = None` — breaks the provider link so a returning user can re-bind to this row with a new `workos_user_id` (see [CustomUserModel.md](CustomUserModel.md) on reactivation).
- **Do not clear `email`.** The reactivation path matches by email; clearing it would strand the user's contribution history forever. Same for `first_name` / `last_name` — keep them so the row stays recognizable. If we ever get a hard GDPR-erasure request, that's a separate management-command path that fully purges the row.
- (`updated_at` on `User` already records "when the row last changed," which is enough audit for v1. A dedicated `deleted_at` timestamp can be added later if we need it.)

We can layer a "fully purge" management command on top later if we ever get a hard erasure request.

### 5. Session invalidation on ban

When a `user.banned` event arrives (Clerk only, today), in addition to setting `user.is_active = False`, walk Django's `Session` table and delete any session whose `auth_user_id` equals this user. That's the difference between "banned" being meaningful in five seconds vs. five days.

For v1 we treat ban and provider-deletion identically on our side — both set `is_active=False`. The semantic difference (banned users shouldn't be able to re-register with the same email; deleted users can) doesn't matter until we have actual abusive users. See the note in [CustomUserModel.md](CustomUserModel.md).

Helper:

```python
from django.contrib.sessions.models import Session

def flush_user_sessions(user) -> int:
    count = 0
    for session in Session.objects.iterator():
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == str(user.pk):
            session.delete()
            count += 1
    return count
```

Linear in active session count; fine at our scale, revisit if it ever isn't.

### 6. Idempotency and out-of-order delivery

Providers retry webhooks on non-2xx responses, sometimes for hours. The handler must be safe to run twice.

- Each event from WorkOS / Clerk has a unique `id`. Persist `(provider, event_id)` in a small `WebhookEvent` table on first successful processing; on duplicate IDs, return `200` and skip.
- All field updates are last-write-wins, so out-of-order delivery is benign except for `user.deleted` — once we soft-delete, we ignore subsequent `user.updated` for the same `workos_user_id`.

### 7. Provider portability

The shape is deliberately:

```
[provider HTTPS POST] → [verify signature] → [normalise event] → [dispatch] → [update UserProfile]
```

Swapping providers replaces the first two steps. The dispatch table and handler functions stay identical because they only know about `UserProfile` fields, not WorkOS or Clerk concepts. This is the same portability story as the rest of the auth code: keep provider-specifics in `accounts/workos_client.py` and the webhook view, and don't let provider names leak into models or downstream code.

### 8. Configuration

Add to settings:

- `WORKOS_WEBHOOK_SECRET` — HMAC secret from the WorkOS dashboard.
- Webhook URL configured on the provider side (`https://flipcommons.org/api/auth/webhooks/`).

Local dev: providers can deliver to a `cloudflared` / `ngrok` tunnel, or we stub the verifier and POST events with `httpie` for testing. Tests use a fake verifier and exercise each handler directly.

### 9. Tests to write

- Signature verification: valid, invalid, missing — only valid passes.
- Each handler: `user.updated`, `user.deleted`, `user.banned`, `user.unbanned` — given a mock event and a fixture user, the right fields change.
- Idempotency: same event ID twice processes once.
- Unknown user: `user.updated` for a `workos_user_id` we've never seen logs and returns 200 (don't make the provider retry forever).
- Session flush on ban: a user with two active sessions has both gone after a ban event.

## Open questions

- **Do we ever want webhook-driven user _creation_?** Probably no. Pre-creating a Django row for someone who's signed up at WorkOS but hasn't visited us pollutes the user list and complicates `username` generation (we currently derive it from email at first login).
- **Replay attack window?** WorkOS's signature includes a timestamp; reject events with timestamps more than ~5 minutes old. Same for Clerk via Svix.
- **Do we need a dead-letter queue?** Not at our scale. If the handler raises, return `500` and let the provider retry. If it fails repeatedly, that's a bug to fix, not a queue to drain.

## Non-goals

- **Bidirectional sync.** We don't push local state to the provider. If we ban someone on our side, that's local-only — the provider doesn't need to know, and reaching back would couple our domain to their API.
- **Full audit log of provider events.** We persist `WebhookEvent` rows for idempotency, not for forensics. Use the provider's dashboard for full event history.
- **Real-time streaming / SSE to the SPA.** Webhooks update the DB; the SPA picks up changes on the next request like any other state. No push to clients.
