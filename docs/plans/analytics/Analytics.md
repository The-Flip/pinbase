# Analytics

## Purpose

Analytics in this project should support two narrow jobs:

1. Understanding **who visits the site and how they got here**, so we can grow reach and improve discovery.
2. Understanding **how contributors use the product**, so we can fix friction and prioritize improvements.

A third downstream surface — [public dashboards](PublicDashboardIdeas.md) — reuses the same data to celebrate preservation work and coordinate community effort.

Analytics is **not** observability. See [Operational Telemetry](#operational-telemetry) below.

## Audiences

- **Maintainers** — the [small team](../../SmallTeam.md) running the project. Primary consumers of product analytics.
- **Contributors** — community members, via [public dashboards](PublicDashboardIdeas.md). Consumers of curated aggregates only, never raw events.
- **Visitors** — the public, via the same dashboards.

No internal access tier above "maintainer"; no third-party data sharing.

## Capabilities

### Visitor Traffic Analytics

Aggregate, mostly-anonymous web traffic data.

- pageviews and uniques
- referral sources (search engines, social, direct, inbound links)
- popular content
- aggregate discovery trends

### Product Analytics

Event-based data about how authenticated and anonymous users interact with product surfaces. Grouped to match the [event taxonomy](EventTaxonomy.md):

- **Discovery** — search success and failure, what content gets found, what doesn't.
- **Contribution** — edit and upload flows, where contributors drop off, time-to-first-contribution.
- **Community** — onboarding paths, retention of contributors over time.

Event scope is deliberately narrow; see [EventTaxonomy.md](EventTaxonomy.md) for the "intentional, not just-in-case" philosophy.

### Public Dashboards

Curated, aggregate-only views built on top of the above. See [PublicDashboardIdeas.md](PublicDashboardIdeas.md).

## Constraints

### Privacy

- Privacy-respectful by default; see [Privacy.md](../../Privacy.md) for the project's overall stance.
- No ad-tech, no behavioral fingerprinting, no cross-site tracking, no advertising profiles.
- Analytics sets no cookies. The only cookies on the site are functional (auth session, CSRF).

#### Identifiability

- **Visitor traffic** is anonymous. No persistent identifier.
- **Product analytics for logged-in users** are linked via a per-user pseudonym, not the user's identity record. This decouples analytics data from the authoritative user table.
- **Product analytics for anonymous visitors** are not linked across sessions. Anonymous search events are explicitly wanted — they tell us what content to add or improve.
- **Raw search queries are stored.** The "content gaps" use case is the point of search analytics.

#### Retention

Analytics data is retained indefinitely. The pseudonymization posture above is what makes long retention privacy-safe — the data isn't directly joinable to user accounts.

### Operational

- **Low maintenance**. Maintainable by a [small team](../../SmallTeam.md) of volunteer developers.
- **Managed/hosted service**. We do not want to operate an analytics service ourselves.
- **Cost ceiling**: no more than $10/month, ideally free while the project is small.
- **Vendor-neutral integration**: code calls our own abstraction, not a vendor SDK directly. See [AnalyticsArchitecture.md](AnalyticsArchitecture.md).

## Non-Goals

We intentionally avoid:

- ad-tech ecosystems and ad-supported analytics providers
- behavioral fingerprinting and cross-site tracking
- advertising profiles or audience segmentation for marketing
- engagement-addiction metrics, manipulative retention analytics, predictive behavioral scoring
- operational telemetry (see below) — different system, different retention, different access

## Operational Telemetry

Operational telemetry is a separate concern with different purposes, retention policies, and access controls. It is **not** part of this analytics system.

Examples of operational telemetry:

- server logs
- performance metrics
- error tracking
- abuse detection
- security auditing
