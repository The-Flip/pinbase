# Surviving an Auth Provider Switch

## Problem

This project uses WorkOS as an auth providers today. We may not always. Reasons we'd switch include pricing changes, feature gaps, an outage with poor remediation, or just finding a better fit (Clerk's free tier, Auth0's enterprise features, eventually self-hosted OIDC).

If we switch, we need it to be possible and not have our user accounts held hostage.

Failures we want to avoid:

1. **Not knowing who our users are**. If the only place we know a user's email / verified status / linked Google account is the old provider, we can't even hook up our existing users to a new provider. Unacceptable.
2. **Forcing users to re-enter their password**
3. **Dropping users MFA enrollment**
4. **Requiring users to log in again.**

This doc captures what to store, _now_.

Some of it overlaps with [Verification.md](Verification.md) and [Webhooks.md](Webhooks.md) — the goal here is to look at the same data through the migration lens and call out the gaps.

## What we already plan to store

Already covered in other docs, summarised here so the picture is whole:

| Data                             | Source                             | Doc             | Why it helps a migration                                                                                       |
| -------------------------------- | ---------------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------- |
| `workos_user_id`                 | Today                              | —               | The current link. Becomes "legacy provider ID" on switch.                                                      |
| Email, first / last name         | Today                              | —               | Primary re-link key (verified-email match against the new provider).                                           |
| `email_verified`                 | [Verification.md](Verification.md) | Verification.md | New provider may distrust unknown users; we know they were verified.                                           |
| Profile picture URL              | [Verification.md](Verification.md) | Verification.md | Continuity — UI doesn't go blank during the cutover.                                                           |
| `(provider, provider_sub)` pairs | [Verification.md](Verification.md) | Verification.md | Stable Google/GitHub/Apple `sub` survives provider switches; re-link by `(google, sub)` even if email changed. |
| `is_banned` (local)              | Webhooks.md                        | Webhooks.md     | Moderation state owned by us, not the provider — survives any switch.                                          |
| Webhook-driven freshness         | Webhooks.md                        | Webhooks.md     | All of the above stay current between logins, so the migration snapshot is recent.                             |

If those three docs land before any switch, the local `User` + `UserProfile` already carries every field we'd need to map a user to a new provider _by identity_. That's the easy half.

## What else to capture (the new gaps)

Small additions specifically for migration ergonomics:

### `provider_account_created_at` on the external-identity row

When we add the `ExternalIdentity(provider, provider_sub, ...)` table from [Verification.md](Verification.md), include a `provider_account_created_at` field populated from the provider's `created_at`. Two uses:

- **Migration prioritisation.** During lazy migration (below), we can prioritise long-tenured users for early cutover and more aggressive notification.
- **Trust signals.** A "this Google identity has been linked since 2024-03" datum is genuinely useful for anti-abuse independent of any switch.

### `last_seen_at` on `UserProfile` — **local-only, not from the provider**

Source: us, not the auth provider. The provider's `last_sign_in_at` is auth-time, and we already get an equivalent for free in Django's `User.last_login` (updated by `login()`). Neither captures "the user is actively using the site" — only "the user authenticated."

For migration planning we want "active in the last 30 days" populated from request-time. A small middleware updates `UserProfile.last_seen_at` on authenticated requests (debounced to once per hour per user to keep write traffic minimal). No provider call, no webhook dependency — just our own session-level signal. Use it during a switch to:

- Identify the active cohort (the people who'll feel a forced re-login).
- Skip lazy-migration steps for accounts that haven't been seen in years.
- Eventually purge accounts that have been dormant past some threshold.

### A snapshot-on-write pattern, not a snapshot table

We _don't_ want a `ProviderSnapshot` table that tries to mirror every provider field "just in case." That's how mirrors get stale and contradict the live system. The webhook-driven sync from [Webhooks.md](Webhooks.md) already keeps `UserProfile` fresh; that's the snapshot, and it's keyed on the fields we actually use.

## Password hashes — the special case

This is the part the user feels. If we get this wrong, every user re-enters their password (or worse, can't, and clicks "forgot password"). If we get it right, most users notice nothing.

### We can't store hashes ourselves

In an OAuth/OIDC flow, **our backend never sees the password.** The user types it into the provider's hosted UI. We receive a code, exchange it for tokens, and never see plaintext or hash. There is no "capture password hash on login" pattern available to us — that would require us to host the login form, which is the thing we explicitly don't want to do.

So password hash continuity has to be solved at migration time, not pre-staged in our DB.

### Three strategies, in order of user-friendliness

1. **Bulk hash export → bulk hash import.** The best path. Old provider exports each user's bcrypt/scrypt/argon2 hash; new provider imports it in a compatible format. Users authenticate against the new provider with their original password — no reset, no friction. Whether this is possible depends entirely on whether _both_ providers support it:

   | Provider      | Exports password hashes? | Imports external hashes?         |
   | ------------- | ------------------------ | -------------------------------- |
   | Auth0         | Yes (bcrypt)             | Yes (bcrypt, scrypt, argon2)     |
   | Clerk         | Yes (bcrypt + others)    | Yes (bulk user import API)       |
   | WorkOS        | Yes, on request          | Yes (bulk user import API)       |
   | Firebase Auth | Yes (custom scrypt)      | Yes                              |
   | AWS Cognito   | **No**                   | Yes (with hashes from elsewhere) |
   | Okta          | Limited                  | Yes                              |

   **Action: when we evaluate any new auth provider, "supports bcrypt hash export and re-import" is a hard requirement.** Cognito is on this list as a cautionary footnote; we shouldn't pick a provider that traps us.

2. **Lazy migration.** When (1) isn't possible, the new provider runs a custom auth function: on first login, it checks credentials against the _old_ provider's API; if valid, it hashes locally and disables the old account. Over a few weeks, the active cohort silently migrates without any user-visible reset. Inactive users eventually get a "please reset" email. Auth0 calls this an "import users from external DB" hook; Clerk has the equivalent. Operationally heavier than bulk import but invisible to users.

3. **Force-reset everyone.** Always works. Always feels bad. Reserved for either (a) a security incident where we can't trust the old hashes, or (b) a switch where neither (1) nor (2) is available. At our scale and tone, this is the option of last resort.

### What we should write down now

Not code; constraints. Add to the auth README / this doc:

- "Any new auth provider must support bcrypt-format hash export and import."
- "Migration plans assume hashes will be moved, not regenerated."

## Session continuity — surprisingly free

The thing the user actually asked about ("so users don't have to log in again") has a partial easy answer that's independent of password hashes:

**Django sessions are ours.** The `django_session` table is keyed on our local `User.id`, set by `login()` in `auth_callback` (`apps/accounts/api.py:234`). The auth provider issued the session indirectly, but the cookie itself doesn't reference the provider at all.

That means at migration time, **we do not flush the session table.** Every user with an active session stays logged in to Flipcommons and keeps editing while we cut over. They only encounter the new provider when their session cookie next expires (default Django setting: 2 weeks). The migration shifts from "everyone is logged out on day 0" to "everyone gets a new login experience the next time they would have logged in anyway." That's the cheapest possible blast radius.

This is true regardless of the password-hash story. Hash continuity matters for the _next_ login; session continuity matters for the active session. Both should hold.

## MFA, passkeys, and other irreducible losses

Some things don't migrate, and we should be honest about that up front rather than discover it on day 0:

- **TOTP secrets.** Most providers refuse to export them (sharing a TOTP secret is by definition a compromise). Users will need to re-enrol their authenticator app at the new provider.
- **Passkeys / WebAuthn credentials.** These are cryptographically bound to the provider's Relying Party ID. There is no migration path. Users re-register passkeys on the new provider.
- **Backup codes.** Regenerated.

We don't currently use any of these, so today this is theoretical. If we enable MFA in the future, the migration playbook needs a "tell users to re-enrol" communication step. There's no engineering fix.

## Migration playbook (high level)

Concrete enough to be useful, vague enough to be revised when the time comes:

1. **T-30 days:** confirm new provider supports hash import and webhook-driven sync. Run a smoke test importing a single test user.
2. **T-14 days:** parallel-create users in the new provider's staging env from a recent webhook-driven snapshot. Verify identity matches by email and `(provider, sub)`.
3. **T-7 days:** internal cutover — staff accounts switch first, validate edit gating, profile rendering, banned propagation, ChangeSet attribution.
4. **T-1 day:** request password-hash export from old provider (Auth0/Clerk/WorkOS — whichever we're leaving). Import to new provider preserving original user IDs where the API allows.
5. **T-0:**
   - Update `WORKOS_*` settings to the new provider's equivalents.
   - Swap the SDK / verifier in `accounts/workos_client.py` and `auth_callback`.
   - Deploy.
   - **Do not flush `django_session`.**
6. **T+0 to T+14:** monitor failed logins. Provide a clear "reset your password" path for the long tail. Communicate MFA re-enrolment if applicable.
7. **T+30:** decommission the old provider's tenant.

The point of all the upfront mirroring is that step 2 has nothing left to discover — we already know who our users are, what's verified, who's banned, which Google accounts they linked. Step 4 is the only step that can fail _because of_ provider choice, which is why hash-export support is a hard requirement up front.

## What this means for naming on `UserProfile`

A small but real consideration: today the field is called `workos_user_id`. Two choices when we switch:

- **Add a new column** (`clerk_user_id` etc.) and keep `workos_user_id` populated for the legacy read path. Fits the user's stated preference for provider-specific names. Migration code reads from `workos_user_id`, writes into the new column.
- **Generalise into the `ExternalIdentity` table** from [Verification.md](Verification.md). This is where we'd land anyway once we want to track Google/GitHub/Apple `sub`s individually. The old WorkOS ID becomes one row among many.

Recommendation: do the second one, but only when there's a reason to (a second provider becomes real, or the migration is actually scheduled). Adding the table speculatively is YAGNI; having the design ready in this doc is not.

## Open questions

- **Do we want a "download my data" feature for users?** GDPR-adjacent but separate from provider switching. Worth a separate doc when it becomes relevant.
- **Are we comfortable letting Django sessions outlive the old provider's existence?** Yes — the session is just a row pointing to our local `User`. The provider is only re-consulted on the next sign-in.
- **What's the threshold for "dormant, force-reset rather than lazy-migrate"?** Probably 12 months unseen, but defer until we have the data.

## Non-goals

- **Capturing password hashes locally.** Impossible in an OAuth flow; ruled out by architecture, not by policy.
- **Building our own auth backend.** Whole point of the provider story is to not own this; switching providers is the escape valve, not a return to in-house auth.
- **Pre-mirroring every provider field "just in case."** Mirror what we use; trust the provider for the rest. The webhook keeps the mirrored fields fresh.
- **Cross-provider MFA continuity.** Not solvable; document and communicate at switch time.
