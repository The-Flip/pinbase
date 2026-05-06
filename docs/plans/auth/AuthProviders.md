# Auth Provider Options

## Requirements

See [Auth.md](Auth.md).

## Options

Note: we also need to choose an email provider. See [AuthMail.md](AuthMail.md).

### Managed Service: Auth0

Auth0 is third-party hosted IdP service. All properties redirect to Auth0 for login. Auth0 provides a "Universal Login" page that can be themed to match your branding, hosted on a custom domain like `auth.theflip.museum`.

At ~30 users (growing to perhaps a few hundred with public registration), this falls well within Auth0's free tier (25,000 MAU). The free tier includes unlimited social login providers and 1 custom domain.

**Pros:**

- Registration, forgot password, email verification, social login, account linking, rate limiting, and session management all come out of the box
- OIDC client libraries (e.g. Authlib) exist for every framework in our stack
- Custom user metadata (e.g. `is_museum_staff`) supported natively
- OIDC is a standard — if Auth0 ever becomes a problem, you can migrate to another OIDC provider without changing your apps' integration code
- GDPR account deletion and user self-service profile management available
- Supports bulk user import with PBKDF2 password hashes on the free tier. Django's `pbkdf2_sha256$iterations$salt$hash` format would need a conversion script to Auth0's PHC format, but existing Flipfix users could keep their passwords.
- Password hash export is available (requires a support ticket; may not be available on the free tier), which reduces vendor lock-in for password-based users
- Attack protection for signup and login flows is built in
- 1 custom domain on the free tier means we can host login at something like `auth.theflip.museum`

**Cons:**

- **Session lifetime on free tier is short** — max 3-day idle timeout and 30-day absolute session lifetime. A user who doesn't visit for 4 days gets logged out. We want sessions lasting months. Longer sessions require Enterprise pricing (~$30k/year). This is a significant UX concern for a casual wiki-style site like this project.
- **MFA is not available on the free tier.** Essentials plan ($35/mo B2C) gets basic TOTP; Professional ($240/mo) adds SMS/email/push.
- **Custom email templates need more verification** — Auth0 definitely requires an external email provider for production email and branded transactional email, but it is not yet clear from the docs whether template customization itself is gated behind a paid plan.
- Login UI is hosted by Auth0 (customizable, but not fully yours)
- Still requires us to configure an external email provider for production email sending; Auth0's built-in email provider is for testing only
- True OIDC back-channel logout exists, but Auth0 documents it as an Enterprise feature, so we should not count on that for v1
- User data lives on Auth0's servers (US or EU region selectable)

Auth0 also has startup and nonprofit programs, which may matter if we later need paid features.

However, this does not solve the session-lifetime problem. Auth0's public nonprofit discount is 50% off paid plans, which would bring Essentials to about $17.50/mo and Professional to about $120/mo. But the long-session capability appears to require Enterprise, and Enterprise would therefore still cost more than Professional and remain out of budget.

### Managed Service: WorkOS AuthKit

WorkOS AuthKit is a third-party hosted auth platform with hosted login/signup flows, password auth, social login, MFA, email verification, user management, and a branded authentication UI. Free tier covers up to 1 million MAU.

At the currently expected scale, cost is not a meaningful factor. If we have roughly 20 monthly active users in month 1, 100 in month 2, and 500 by month 6, the monthly WorkOS AuthKit charge still appears to be $0 unless we opt into paid add-ons like custom domains.

WorkOS sends auth emails itself by default (from `workos-mail.com`), which eliminates the need for a separate email provider — unless we want a custom sending domain.

WorkOS exposes standard OIDC/OAuth2 endpoints, so we can integrate with any OIDC library (`mozilla-django-oidc`, `authlib`, etc.) — not locked into their SDK.

**Pros:**

- 1 million MAU on the free tier (vastly more generous than Auth0's 25k)
- Password auth, social login, email verification, forgot password, MFA, and account linking all included on the free tier (Auth0 charges $35/mo for MFA alone)
- WorkOS sends auth emails itself by default — no separate email provider to configure
- Standard OIDC/OAuth2 — not SDK-locked like Clerk; works with any OIDC client library
- Hosted UI supports logo and brand color customization on the free tier
- Session configuration is available on the free tier. In the dashboard we verified:
  - Maximum session length can be set to 365 days
  - Access token duration defaults to 5 minutes and the UI appears to allow much longer values
  - Inactivity timeout defaults to 2 days and we successfully increased it to 100 days
- Supports bulk user import with PBKDF2 password hashes. Django 5.1+ (which the Flipfix system was born on) uses 870,000 iterations, which is within WorkOS's accepted range (600k–1M). Requires a format conversion script from Django's format to PHC format. Import is one API call per user (no bulk endpoint).
- User metadata for custom attributes (e.g. `is_museum_staff`) supported
- If we later decide to bring our own email provider, WorkOS supports SES, Mailgun, Postmark, Resend, and SendGrid

**Cons:**

- **No password hash export** — WorkOS does not allow exporting password hashes. If we migrate away, every password-based user must reset their password. (WorkOS imports hashes willingly but won't give them back.) Social login users are unaffected since their identity is anchored to the external provider.
- **Custom domains (auth UI + email sending) are $99/mo** — a single bundle that covers auth domain, admin portal domain, and email sending domain. Without this, the login UI lives on WorkOS's domain and emails come from `workos-mail.com`.
- **Email customization is limited compared to a full template editor** — WorkOS supports branding assets, brand colors, localized copy, and custom email-provider integrations, but if we need full control over email HTML/text we may still need to disable WorkOS emails and send our own.

If we relax the custom domain requirement, WorkOS's free tier is significantly more capable than Auth0's for our use case — MFA, generous MAU limits, built-in email sending, and long-lived sessions that can be configured up to 365 days.

### Managed Service: Clerk

Clerk is a hosted auth and user-management platform with passwords, social login, automatic account linking, user metadata, hosted UI components, and a free tier that includes a custom domain.

Its pricing is attractive: free for small apps, custom domain included, unlimited applications, and up to 50,000 monthly retained users per app. If this were a pure Next.js or React estate, it would be a stronger contender.

**Pros:**

- Custom domain available on Pro plan ($20–25/mo)
- Unlimited applications on one account
- Password auth, social login, automatic account linking, usernames, and user metadata are all supported
- Device/session management is built in
- Shared auth across subdomains is a first-class Clerk concept
- Clerk can act as an OAuth/OIDC identity provider for external apps
- Self-service password hash export from the dashboard (CSV), no support ticket needed — the most migration-friendly option

**Cons:**

- **OIDC discovery is non-standard** — Clerk publishes `/.well-known/oauth-authorization-server` (RFC 8414), not `/.well-known/openid-configuration` (the OIDC standard). Libraries like `mozilla-django-oidc` and `authlib` expect the latter and won't auto-discover Clerk's endpoints. You'd need to manually configure each endpoint URL.
- **No standard Django integration path** — every Django + Clerk integration in the wild uses Clerk-specific JWT verification, not standard OIDC. Clerk has a Python SDK (`clerk-backend-api`) and a community `clerk-django` package, but both are vendor-specific. There are zero documented examples of anyone using a generic OIDC library with Clerk on Django.
- Clerk is much more SDK- and component-centric than OIDC-centric; its sweet spot is Next.js / React, whereas our estate is a mix of Django, SvelteKit, Next.js, and Python
- MFA, custom email templates, and custom session lifetime are paid features
- **Free-tier session lifetime is fixed at 7 days** (re-verified against Clerk's session-options docs in 2026). Production customization requires the Pro plan; only development mode allows changes on the free tier. Pro plan max is undocumented (practical ceiling is Chrome's 400-day cookie limit).
- Multi-domain and advanced shared-session docs are heavily oriented around Clerk-managed frontend apps, which makes this feel like a less natural fit for Flipfix and Juice than a more conventional OIDC provider

Clerk is interesting on price, but looks less aligned with our mixed-stack, standards-first integration needs than Auth0.

### Managed Service: Kinde

Kinde is a hosted auth, billing, and access-management platform aimed at modern SaaS products. Free-forever pricing with no card required, 10,500 MAU on the free tier, and a number of features (custom domain, MFA, customizable session duration, self-serve hash export) that competitors put behind paid plans.

**Pros:**

- **Custom domain on the free tier** — matches Auth0, beats WorkOS's $99/mo, beats Clerk's $20/mo. We could host login at `auth.theflip.museum` without paying.
- **One year (?) session duration on the free tier** — beats Auth0 (Enterprise-only) and Clerk (Pro-only); matches WorkOS. I signed up to Kinde and managed to set it to 1 year (31536000 seconds); dunno if the Kinde system will actually honor that.
- **MFA on the free tier** — supports authenticator apps and email; SMS is gated to 10 messages/month. Beats Auth0 ($35/mo) and Clerk ($20/mo); matches WorkOS.
- **10,500 MAU on the free tier** — comfortable headroom for our scale (more than Auth0's 25k is overkill, less than WorkOS's 1M, but plenty for a pinball wiki).
- **Self-serve password hash export** — supports bcrypt, sha256, md5, crypt, and wordpress hashes. Export file is encrypted with AES-256-CTR. Best-in-class for migration portability; matches Clerk's self-serve story without Clerk's OIDC oddities.
- **Self-serve bulk import** via CSV/JSON, with documented hash formats. Importing existing Flipfix users with their PBKDF2 hashes would still need a conversion script (PBKDF2 isn't in Kinde's natively-supported list — you'd contact support to add it, or use a "lazy migration" hook).
- **Customizable email content and sender on the free tier**.
- Pricing is honest: free forever for MAU; only direct cost is a 0.7% transaction fee if we ever use Kinde's billing features (we won't).

**Cons:**

- **No standard OIDC discovery confirmed** — Kinde's docs don't surface a `/.well-known/openid-configuration` endpoint or auto-discovery story. ID tokens are JWTs with standard `iss`/`sub`/`exp` claims, suggesting OIDC underneath, but we'd need to verify that `mozilla-django-oidc` or `authlib` can integrate cleanly. Worth a 30-minute spike before committing.
- **Official Django integration is via the vendor-specific `kinde-python-sdk`**, not standard OIDC libraries. Same architectural smell as Clerk: `KindeApiClient` instances managed per-session, vendor-specific token-fetch and user-detail calls. The Kinde tutorial is an explicit "use our SDK" pattern, not a "drop in any OIDC client" pattern.
- Official SDK examples and docs lean Flask / FastAPI; Django is supported but not first-class.
- Smaller community than Auth0 / WorkOS / Clerk. Less battle-tested at scale, fewer Stack Overflow answers when something breaks.
- Free tier MAU (10,500) is much smaller than WorkOS (1M) — we'd need to upgrade as growth happens. Paid plans aren't priced as a bare MAU rate (see Kinde pricing page); plan cost depends on which paid features you light up.
- Email deliverability: Kinde sends auth emails on the free tier from a Kinde-owned domain (verifiable by inspecting the dashboard). Whether bringing a custom sending domain requires a paid tier is not clearly documented.

Kinde looks attractive on the feature matrix — arguably the most generous free tier of any of the four if you weight custom-domain + MFA + long sessions equally — but the same standards-vs-SDK concern that ruled out Clerk applies here too. If we're already willing to live with a vendor SDK, Kinde's free-tier feature set is materially better than Clerk's. If standards-based integration is a hard requirement, both Kinde and Clerk fall behind WorkOS and Auth0.

### Rejected Options

#### Managed Service: Amazon Cognito

Rejected because I already know from experience that Cognito is difficult to work with, hard to debug, hard to configure, and I do not want to bring AWS complexity into this project.

#### Managed Service: Descope

Rejected because custom domain support starts at the Pro plan, and Descope Pro starts at `$249/mo`, which is too expensive.

#### Self-Hosted IdP: Authentik

Rejected because I do not want to run an auth service ourselves.

Authentik is a self-hosted identity provider. We'd run it ourselves on Railway alongside our existing services. Authentik is built on Django under the hood, so it's culturally familiar. It provides a full admin UI, OIDC/OAuth2/SAML support, social login, email verification, MFA, and user management.

**Pros:**

- Full control over all auth infrastructure and user data
- No vendor dependency or pricing risk
- Feature-rich: social login, MFA, email verification, forgot password, account linking, user self-service, admin UI
- Built on Django/Python — familiar stack for debugging and customization
- Supports custom attributes for the "museum staff" flag
- No limits on social providers or login customizations
- Can be themed to match your branding completely

**Cons:**

- Another Railway service to host, monitor, update, and back up
- You still need to configure SMTP for transactional email (e.g. Postmark, Mailgun, SES) — email deliverability is your problem
- More moving parts: Authentik needs a database, Redis, and a worker process
- Operational burden on a small team — security patches, version upgrades, etc.
- More initial setup and configuration compared to a managed service

#### Build It Ourselves: django-allauth

allauth is the mature batteries-included Django auth library — using it is "buy" in the sense of "drop in a debugged library," not "write auth from scratch." For a 100-user volunteer-led wiki, the operational and feature surface is genuinely small. So the rejection needs a real reason, not a category-level "I don't want to build auth."

**The actual reason: ongoing email-deliverability monitoring.**

Auth that doesn't reliably deliver email isn't auth — verification links, password resets, MFA codes all become silent failures. With allauth that means:

- Setting up SPF / DKIM / DMARC (a one-time afternoon)
- Picking a transactional provider — Postmark, SES, Mailgun (a one-time decision plus ~$15/mo)
- Designing and maintaining branded email templates (one-time, then drift)
- **Ongoing bounce/spam monitoring** — this is the killer. Inbox-placement decay, gradual sender-reputation erosion, "your mail is going to Promotions/Spam at the big providers" detection. WorkOS handles this entirely. We'd add a recurring operational concern that has nothing to do with the wiki.

WorkOS sending from `workos-mail.com` removes that ongoing surface entirely. At our scale and with our staffing model (volunteer-led, no dedicated ops), that's the trade that decides it.

**Reasons that look like rejections but aren't, on closer inspection:**

- ~~OAuth credential management.~~ We'd have to register Google/Apple/GitHub OAuth apps eventually anyway if we ever migrate users to a new provider. Not a real allauth-specific cost.
- ~~3am operational responsibility.~~ WorkOS is roughly as likely to break at 3am as our own Django stack — and if our Django stack is down, the wiki is down regardless of where auth lives. Auth being on the same failure domain as the rest of the site is a feature, not a bug, since the user-visible outcome is the same either way.
- ~~Login UI lives at a Django route (brief detour from SvelteKit).~~ Acceptable UX cost. SvelteKit-routed-everything isn't a hard requirement.

**Pros if we ever revisit:**

- Stays entirely within our existing tech stack — it's just Django
- Maximum control and customization over every flow and UI element
- No vendor costs at any scale
- The "must be able to migrate to a new auth provider" hard requirement evaporates — there's nothing to migrate from
- Long-lived sessions are trivial (`SESSION_COOKIE_AGE`); no juggling free-tier session limits

**Reconsider when:** WorkOS pricing changes pinch us, or we already have working transactional-email infrastructure (e.g., shared from Flipfix) that absorbs the ongoing monitoring cost.

## How they Integrate

Regardless of which option we pick, the integration pattern is the same for each property:

- **this project**: User clicks login → redirect to IdP → authenticate → redirect back → Django creates session. Fits your existing same-origin proxy architecture perfectly.
- **Flipfix**: Switches from being the OAuth provider to being an OAuth client. django-allauth or mozilla-django-oidc on the client side. Existing ~30 users migrated to the new IdP.
- **Juice**: Swaps Flipfix's OAuth endpoint for the new IdP's. Minimal change.
- **www**: No change now. If needed later, NextAuth.js speaks OIDC natively.

### The "Museum Staff" Flag

The requirement for optionally knowing "this person is museum staff" across properties maps cleanly to OIDC claims or user metadata. All three options support this — the IdP stores a custom attribute like is_museum_staff: true, and each property can read it from the token and decide what to do with it locally. It's not complex in any of the options.

## Comparison

Only the four actively considered managed services are compared. ✅ = included on free tier, 💰 = paid, ❌ = not available.

|                                                                         | Auth0             | WorkOS AuthKit    | Clerk                              | Kinde                                 |
| ----------------------------------------------------------------------- | ----------------- | ----------------- | ---------------------------------- | ------------------------------------- |
| [Standard OIDC/OAuth2](Auth.md#ease-of-integration)                     | ✅                | ✅                | ❌❌❌ SDK-only, no OIDC discovery | ⚠️ JWT-based but SDK-first; verify    |
| [Forgot password](Auth.md#forgot-password)                              | ✅                | ✅                | ✅                                 | ✅                                    |
| [Email verification](Auth.md#email-verification)                        | ✅                | ✅                | ✅                                 | ✅                                    |
| [Social login](Auth.md#social-login)                                    | ✅                | ✅                | ✅                                 | ✅                                    |
| [Account linking](Auth.md#email--social-logins-work-seamlessly)         | ✅                | ✅                | ✅                                 | ✅                                    |
| [MFA](Auth.md#security)                                                 | 💰 $35/mo         | ✅                | 💰 $20/mo                          | ✅ (SMS limited to 10/mo)             |
| [Long-lived sessions](Auth.md#sessions)                                 | 💰 Enterprise     | ✅ up to 365 days | 💰 $20/mo (free = 7 days)          | ✅ customizable on free               |
| [User metadata / staff flag](Auth.md#museum-staff-identity-across-apps) | ✅                | ✅                | ✅                                 | ✅                                    |
| [GDPR account deletion](Auth.md#user-initiated-deleting)                | ✅                | ✅                | ✅                                 | ✅                                    |
| [Rate limiting](Auth.md#security)                                       | ✅                | ✅                | ✅                                 | ✅                                    |
| [Hosted vendor](Auth.md#dont-build-it-ourselves)                        | ✅                | ✅                | ✅                                 | ✅                                    |
| [Cost](Auth.md#cost)                                                    | Free (25k MAU)    | Free (1M MAU)     | Free (50k MAU)                     | Free (10.5k MAU)                      |
| [Initial user migration](Auth.md#initial-user-migration)                | PBKDF2 import ✅  | PBKDF2 import ✅  | PBKDF2 import ✅                   | bcrypt/sha256/md5; PBKDF2 via support |
| [Password hash export](Auth.md#ease-of-migrating-off)                   | 💰 support ticket | ❌                | ✅ self-service                    | ✅ self-service (AES-256 encrypted)   |
| Custom domain                                                           | ✅ (free tier)    | 💰 $99/mo         | 💰 $20/mo                          | ✅ (free tier)                        |
| Built-in email sending                                                  | ❌ testing only   | ✅                | ✅                                 | ✅                                    |
| Custom email templates                                                  | unclear           | Limited           | 💰 $20/mo                          | ✅                                    |
