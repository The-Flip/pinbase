# Media Hosting Provider Options

This doc evaluates specific storage and CDN providers against the requirements in [MediaHostingProviderRequirements.md](MediaHostingProviderRequirements.md). Requirements are referenced below by name (e.g. "the production-grade serving requirement", "the managed-TLS requirement") rather than by number, since the requirement order may change.

Storage and CDN are evaluated separately. Unbundling them is the industry norm past the smallest scale; combining them at the recommendation step is the reader's job. The recommendation at the end picks one of each.

Cloudflare and AWS options are excluded by the avoid-Cloudflare and avoid-AWS preferences and are not evaluated here.

## File Storage Options

All assume `django-storages` with the S3-compatible backend. `MEDIA_STORAGE_BUCKET`, `MEDIA_STORAGE_ENDPOINT`, etc. are already wired up in [backend/config/settings.py](../../../backend/config/settings.py).

### Backblaze B2

- **S3 API**: GA, mature, very well-trodden in `django-storages` setups.
- **US-East**: Yes — Reston, Virginia (`us-east-005`) added in 2024. Verify GA status before committing.
- **Cost**: $0.006/GB-month. No minimum charge — pure per-GB. At launch volume: pennies/month. Egress: 3× free egress per month relative to storage volume, then $0.01/GB. Bandwidth Alliance partnership has historically given free egress to Bunny CDN (verify current terms).
- **Cold-read perf**: HDD-backed tier for cost. Cold-read TTFB is the slowest of the candidates here — public benchmarks have shown 100–200ms higher first-byte than Wasabi for similar workloads. With CDN tiered caching in front this matters less for steady-state, but at low launch traffic where many images won't be cache-hot, it's perceptible.
- **Operational simplicity**: clean self-serve dashboard, application keys with bucket-scoped permissions. **Largest developer community of any candidate** — most tutorials, most Stack Overflow answers, deepest third-party docs.
- **Private origin**: yes — buckets can be private; CDN authenticates with application keys.
- **Viability**: publicly traded (NASDAQ: BLZE), founded 2007, ~$130M annual revenue. Audited financials. Strongest viability of the simple-vendor storage candidates.
- **Verdict**: best community/docs and strongest public-co viability, but slowest cold reads. Right pick if community size matters more than cold-read latency.

### DigitalOcean Spaces

- **S3 API**: GA, mature.
- **US-East**: `nyc3` (New York). ✓
- **Cost**: $5/month flat — includes 250 GB storage and 1 TB transfer. Floor is high relative to actual usage at launch.
- **Cold-read perf**: SSD-backed. Competitive with S3 for TTFB.
- **Operational simplicity**: friendliest self-serve UX of any candidate. Sign up, click Create Space, get keys.
- **Private origin**: yes — buckets can be private; access keys for CDN.
- **Note on Spaces CDN**: their bundled CDN is **not** considered here. Spaces CDN fails the managed-TLS requirement when DNS isn't hosted at DigitalOcean. As pure storage behind a different CDN, that issue doesn't apply.
- **Viability**: publicly traded (NYSE: DOCN), ~$700M annual revenue, profitable, founded 2011. Solid.
- **Verdict**: solid storage candidate, especially for operational simplicity. $5/month floor is the only real downside.

### Wasabi

- **S3 API**: GA, well-trodden. Multiple production `django-storages` users.
- **US-East**: `us-east-1` (Virginia) and `us-east-2` (Virginia). ✓
- **Cost**: $0.007/GB-month effective ($6.99/TB/month). **1 TB minimum charge** — pay ~$7/month even when storing a few GB. Egress free under "fair use" (egress ≤ monthly storage volume).
- **Cold-read perf**: SSD-forward architecture. Wasabi explicitly markets fast read latency as a differentiator and has independent benchmarks supporting it. Fast cold reads relative to B2 (~50–100ms TTFB in typical conditions).
- **Operational simplicity**: clean dashboard, standard S3-style access keys. Account signup is heavier than B2 (asks for more business info upfront). Smaller developer community than B2.
- **Private origin**: yes.
- **Quirks**: 90-day minimum retention — files deleted within 90 days still bill for the full 90 days. Not relevant for our access pattern.
- **Viability**: privately held, founded 2017 by David Friend (co-founder of Carbonite). $250M+ raised, claims profitability. No public financials. Established storage business; smaller brand presence in the developer sphere than B2.
- **Verdict**: fast cold reads, simple operations, well-known in the production storage space. Trade-off vs. B2: faster perf, smaller community, private vs. public.

### iDrive e2

- **S3 API**: GA.
- **Chicago**: There's a Chicago data center!
- **US-East**: Multiple regions including Virginia and Maryland. ✓
- **Cost**: ~$0.004/GB-month — cheapest in the field. No minimum on pay-as-you-go pricing. Egress: 3× storage free, then $0.01/GB.
- **Cold-read perf**: marketed as performance-oriented and reportedly comparable to Wasabi. Less independent benchmarking than B2 or Wasabi.
- **Operational simplicity**: reasonable self-serve dashboard, standard S3-style access keys. **Smallest developer community** of the three S3-clone candidates — fewer tutorials and SO answers when stuck.
- **Private origin**: yes.
- **Viability**: privately held by iDrive Inc. (originally Pro Softnet), founded 1995. 30+ years operating. Long-running consumer-backup business; less brand recognition in the object-storage developer space than Wasabi or B2.
- **Verdict**: cheapest at scale, perf in the same class as Wasabi. Smallest developer community of the candidates. Good choice if cost matters; Wasabi is similar with better community presence.

### Akamai Object Storage

- **S3 API**: GA (formerly Linode Object Storage; Linode acquired by Akamai in 2022).
- **US-East**: Newark and Washington DC. ✓
- **Cost**: ~$5/month for 250 GB storage + 1 TB transfer. Similar shape to DO Spaces.
- **Cold-read perf**: competitive with DO Spaces and Wasabi. SSD-backed.
- **Operational simplicity**: the Linode-origin storage dashboard is self-serve and reasonable. Complexity arrives if paired with Akamai CDN (Property Manager) — see CDN section.
- **Private origin**: yes.
- **Note on built-in custom-domain feature**: Akamai Object Storage's own custom-domain UI requires BYO TLS cert (manual upload, manual renewal). That fails the managed-TLS requirement. Pairing this storage with a different CDN (Bunny, Fastly) avoids the issue — the CDN handles TLS instead.
- **Viability**: publicly traded (NASDAQ: AKAM), ~$4B revenue, founded 1998. **Strongest viability of any candidate.**
- **Verdict**: solid storage with the strongest viability story. Pair with a non-Akamai CDN to dodge Property Manager.

### Fastly Object Storage

- **S3 API**: announced 2024; **verify current GA status and regional availability before committing**. My information here is less certain than for the other options.
- **US-East**: NY and Virginia (verify which regions are GA for Object Storage specifically).
- **Cost**: verify current pricing. Free egress to Fastly CDN within the Fastly ecosystem.
- **Cold-read perf**: well-positioned given Fastly's edge infrastructure and the free internal egress to their CDN.
- **Operational simplicity**: Fastly's services/origins concepts apply to storage too.
- **Private origin**: yes.
- **Viability**: publicly traded (NYSE: FSLY), ~$500M revenue, founded 2011. Solid.
- **Verdict**: potentially compelling if GA — especially paired with Fastly CDN. GA-status verification required before treating as a real candidate.

### Bunny Edge Storage

- **Status**: **Fails the S3-compatible API requirement.** As of 2026-04-30, Bunny's S3-compatible API is invite-only preview. Their GA API is a proprietary HTTP interface, not S3-compatible.
- **Verdict**: out for the launch decision. Reopen if/when their S3 API hits GA — at that point Bunny all-in (storage + CDN + Optimizer + Stream) becomes the strongest single-vendor candidate for our future capabilities.

## CDN Options

All CDN options assume the storage provider exposes an S3-compatible HTTPS origin and the CDN is configured as a pull zone with that origin.

### Bunny CDN

- **PoPs**: ~120+ globally. Chicago PoP: yes. Strong in EU/Asia, good in US.
- **Managed TLS**: free Let's Encrypt for custom hostnames via ACME HTTP-01 against the CDN endpoint. No DNS-on-Bunny required. Automatic renewal. ✓
- **Operational simplicity**: **the simplest of the three.** Create pull zone, set origin, attach custom hostname, click issue cert. ~15 minutes from zero for a volunteer with no Bunny background.
- **Cache features**: tiered caching free and on by default — edge miss falls to a regional cache before going to origin. **Perma-Cache** is a paid add-on that keeps long-tail content cached in Bunny's permanent storage even after edge eviction; useful for low-traffic sites where the long tail is mostly cold.
- **Cost**: ~$0.005–$0.01/GB egress depending on region. No minimum.
- **Viability**: privately held (BunnyWay d.o.o., Slovenia), founded 2015. Self-described profitable, ~70 employees, 100K+ customers. Smallest of the CDN candidates by a meaningful margin, but the CDN is swappable so the risk is bounded.
- **Verdict**: best operational simplicity. Right CDN for a volunteer-run setup unless viability concerns dominate.

### Fastly CDN

- **PoPs**: ~70, each typically very large. Chicago PoP: very strong. Performance benchmarks consistently rank Fastly among the fastest globally.
- **Managed TLS**: Fastly TLS service issues and renews managed certs via ACME, DNS-host-agnostic. ✓
- **Operational simplicity**: well-designed but more concepts to learn — services, origins, backends, optional VCL/rule snippets, configuration versions, activations. Volunteer onboarding requires real reading.
- **Cost**: free tier covers most launch traffic; past that, ~$0.12/GB egress (closer to AWS than Bunny). Wasabi has an explicit Fastly partnership — Wasabi → Fastly origin egress is free under their alliance.
- **Viability**: publicly traded (NYSE: FSLY), ~$500M revenue, founded 2011. Solid.
- **Verdict**: best raw perf (slightly), best public-company CDN viability, but operationally heavier than Bunny — cost is paid every time anyone touches the config.

### Akamai CDN (Property Manager)

- **PoPs**: ~4000+, the largest CDN network in the world. Chicago PoP: strong. Best for global reach to underserved regions.
- **Managed TLS**: Default DV certs, ACME-provisioned, DNS-host-agnostic via `_acme-challenge` CNAME. ✓
- **Operational simplicity**: **the heaviest of the three.** Property Manager is the enterprise CDN configuration apparatus: properties, behaviors, rule trees, CP codes, configuration versions and activations to staging and production networks. Same family of complexity as AWS CloudFront — well-designed but requires real expertise to configure.
- **Cost**: bundled with Akamai Object Storage's basic tier; larger Akamai-CDN-only contracts are enterprise-quoted.
- **Viability**: publicly traded (NASDAQ: AKAM), ~$4B revenue. Strongest viability of any CDN candidate.
- **Verdict**: best CDN reach and viability, worst operational simplicity. Right pick only if someone is willing to learn Property Manager.

## Decision

**Storage: iDrive e2 (US-East).**
**CDN: Bunny CDN.**

Decided 2026-05-01. `media.flipcommons.org` is live and serving a test file through Bunny CDN with iDrive e2 as the origin.

### Why iDrive e2 for storage

#### Chicago data center

Fastest for cold reads in the Chicago area

#### Performance

IDrive e2 is consistently faster than Backblaze B2 and Wasabi in terms of Time to First Byte (TTFB). It uses SSDs, avoids B2's HDD-tier latency.

#### Operational simplicity

I got it running very quicly. Clean self-serve dashboard, standard S3-style access keys.

#### No "90-Day Deletion" Trap

This is the biggest advantage over Wasabi.

    The Wasabi Problem: If you upload a 1GB video and delete it 5 minutes later, Wasabi charges you for that 1GB for the next 89 days.

    The IDrive Win: If a volunteer makes a mistake and deletes/replaces a file, the charge stops immediately. It’s much more forgiving for a dev environment.

#### Predictable "Flat" Pricing

    IDrive e2 costs $0.004 per GB/month.

##### No egress fees

    Unlike AWS S3, there are no egress fees (bandwidth costs) from IDrive. Since you’ve connected it to Bunny.net, IDrive won't charge you a penny for the data moving from their bucket to your CDN. You only pay for what you store.

##### No 1 TB minimum

No $5/month floor like DO Spaces. Costs scale to actual usage.

#### Modern "Virtual Hosted" Support

Supports modern Virtual Hosted-Style URLs. This makes it 100% compatible with boto3 and Bunny.net’s security signatures. It’s built on a newer architecture than some of the older "Legacy" S3 clones.

#### Team Management

IDrive’s "Users" dashboard is much simpler for a volunteer board to understand than AWS IAM.

    You can invite other museum board members as Admins.

    They get their own logins.

    No one has to share a "Master Password."

#### Viability

iDrive is a privately held but established since 1995, long-running consumer-backup business.

#### Trade-off accepted: smaller developer community

Smaller developer community than B2 or Wasabi.

### Why Bunny for CDN

#### CDN Operational simplicity

I tried it out and it was dead simple to set up.

#### Managed TLS

Managed TLS\*\* via free Let's Encrypt — no DNS migration needed.

#### CDN Performance

Perf is good for our type of content (immutable images served to mostly-US viewers).

#### Chicago PoP

Bunny has Chicago presence, which matters for museum-adjacent cold/warm reads.

#### Supports S3 Private Origin

Bunny supports S3-style origin authentication fields, so it can pull from private S3-compatible buckets depending on the storage provider. Confirmed it works with iDrive E2.

#### Cache features

- Tiered cache free and on by default.

#### Cold cache features

- Perma-Cache available if cold-cache prevalence becomes a problem at low launch traffic, to keep long-tail files warm if normal edge cache eviction causes too many cold origin reads.
