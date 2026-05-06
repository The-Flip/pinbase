# SSO

This describes the authentication and authorization requirements for this project.

This project is an interactive, collaborative wiki-style catalog of all the pinball machines in existence. It hasn't gone live yet. It has public read-only access, public user registration, trusted museum staff roles, and Django superuser admin roles.

- Lives at https://flipcommons.org/
- I'd like the login page to be hosted at https://auth.flipcommons.org
- **Django + Sveltekit**. Built in Django on the back end and Sveltekit on the front end
- **Hosted on Railway**. It's currently hosted on Railway, which we like well enough, though we don't want to make decisions that lock us in to Railway.

## Requirements

### Social Login

Register/login using your Google/Apple/Facebook/etc identity.

#### Email & social logins work seamlessly

When someone registers with email/password, then later tries to log in with Google using the same email, that should be treated as the same account, and work seamlessly.

They can they still log in with their password.

### Forgot password

Forgot password is a must.

We have not yet built Forgot Password functionality for Flipfix. For one, we haven't hooked up an email server to send the forgot password messages. I know from past experience that it can be difficult to not be classified as junk mail, so I'm skittish. And then customizing the email HTML so that it displays nicely on all browsers is notoriously tricky. We've already had users forget their password, so it'd be nice to have this, but not critical.

### Email verification

Verify that the person registering owns the email address. Otherwise you get spam accounts and people squatting on addresses. This is a must-have.

If we're doing a system where people can also register with phone numbers, we'd need to verify the phone number. But I don't think we are... seems difficult?

### Banning

#### Admin-initiated banning

Admins should be able to ban abusive users. Need to think through this, such as how to prevent re-registering?

#### User-initiated deleting

We'd like to support GDPR-style "delete my account", but that may not be in scope for v1. Depends on how hard it is.

### Authorization / Roles

#### Newly registered public user

Newly registered users should not be able to make any changes until at least their email address is verified. Probably more. We need to think through this.

### Security

- Rate limiting on registration: yes
- CAPTCHA: no
- Password policy: I guess some sort of minimum complexity, I don't feel strongly on this.
- Multi-factor authentication: nice to have, depends on how hard it is

#### Sessions

- **Session Duration**. Ideally sessions last months, unless that's really a security no-no
- **User-initiated session revocation**. Users being able to see all of their login sessions and being able to revoke is a nice to have. Probably not for v1.

### Non-functional Requirements

#### Don't build it ourselves

Building an auth system sounds complicated; it's not our core competency; it's yet another service to keep running. My bias is to use a vendor for this, unless there's a good reason not to, or maybe unless there's an off-the-shelf system that is SUPER easy to run.

#### Cost

Ideallly for the first year of perhaps 10,000 users, we want a vendor with a free tier or maybe $5-10/mo. The Flip is a registered nonprofit and all the software that SSO would integrate with is open source, if that changes the cost structure that vendors charge.

#### Ease of Migrating to Another Auth Provider

It's a non-negotiable hard requirement: we MUST be able migrate to a new auth provider. We MUST be able carry all our users to the new auth provider, hopefully without them having to log in again.

#### Ease of integration

How easy is it to wire up each property?

We prefer a provider that exposes standard OIDC/OAuth2 endpoints (including `/.well-known/openid-configuration` discovery) so that our backend can integrate with a generic OIDC library (`mozilla-django-oidc`, `authlib`, etc.) rather than a vendor-specific SDK.

Our architecture is session-based: the frontend redirects to the IdP, the IdP redirects back, and Django creates a server-side session. This is a standard OIDC authorization code flow. A provider that requires its own JavaScript SDK on the frontend — replacing the redirect flow with client-side JWT verification on every API call — would be a poor fit because:

- It changes our auth model from server-side sessions to per-request JWT verification
- It couples the frontend to the vendor (Clerk components, Clerk API calls) instead of a simple redirect
- The backend needs vendor-specific token verification code instead of standard OIDC middleware

#### Hosting location

The website is hosted in US/East. The museum and many editors and end users are in US/Chicago, I'd prefer a SSO system that has services that work well with these regions, because perf/lantency.

### Non-Requirements

- **Data residency**
- **Uptime**. These are not mission-critical systems.

## The Options

See [AuthProviders.md](AuthProviders.md)

## Provisional Decision

I don't want to run an auth service ourselves:

- I don't want to build it and own that code
- I don't want to occupy us with the ongoing hosting of it

This pushes us to a hosted vendor.

After reviewing the hosted vendors (see [AuthProviders.md](AuthProviders.md)), WorkOS AuthKit is the leading candidate.

The key reason is sessions. We want users to stay signed in for months. Auth0's self-service plans cap sessions at 3 days idle and 30 days absolute, and the longer session limits appear to require Enterprise pricing, which is out of budget even with nonprofit discounts. By contrast, in a real WorkOS AuthKit account we verified that:

- Maximum session length can be set to 365 days
- Inactivity timeout defaults to 2 days and can be increased to at least 100 days
- Access token duration is configurable

WorkOS also remains strong on the other important requirements:

- Hosted vendor, not self-hosted
- Standard OIDC/OAuth2 integration
- Email/password, social login, email verification, forgot password, MFA, and account linking on the free tier
- Built-in auth email sending, so we do not need a separate email provider for v1 unless we want a custom sending domain

On current pricing, the expected monthly cost is still effectively zero at our projected scale. Even if this project grows from 20 users in month 1 to 100 users in month 2 and 500 users by month 6, that is still far below WorkOS AuthKit's free-tier limit of 1 million monthly active users.

The main downside is branding: custom auth and email domains cost $99/mo. At this point, I would rather give up custom domains than long-lived sessions, so that tradeoff appears acceptable.

So the current direction is:

- Choose WorkOS AuthKit as the SSO provider
- Accept WorkOS-hosted auth and email domains for v1
- Revisit custom domains later only if they become important enough to justify the extra cost
