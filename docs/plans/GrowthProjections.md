# Growth Projections

Numbers are rough order-of-magnitude guesstimates of how the user base, traffic, and stored content will grow.

## Registered Users

| Horizon | Monthly active registered users |
| ------- | ------------------------------- |
| Month 1 | 20                              |
| Month 2 | 100                             |
| Month 6 | 200                             |
| Year 1  | 400                             |

Two distinct user profiles:

- **Readers** (museum visitors, casual fans, collectors): unauthenticated reads dominate and aren't in the table above.
- **Contributors** (historians, museum-connected enthusiasts): the registered-user count above is essentially this group. Initial cohort is a known group of museum-connected pinball enthusiasts.

## Traffic

The MAU counts above are editors. Anonymous readers dominate actual page-load traffic, and the right scale to anchor against is similar pinball sites:

| Site (Similarweb, Apr 2026) | Visits/mo | Pages/visit | Implied pageviews/mo |
| --------------------------- | --------- | ----------- | -------------------- |
| Pinside.com                 | ~420k     | ~8          | ~3.3M                |
| IPDB.org                    | ~98k      | ~5.5        | ~540k                |

Pinside is the engagement ceiling (forum + marketplace, not a reference site); IPDB is a direct comparable and a plausible target.

Back-of-envelope assumptions:

- **Reader-to-editor ratio**: ramps from ~25× at launch (word-of-mouth and museum-kiosk only) to ~200× by Year 1 (SEO mass, reputation, IPDB displacement). Below Wikipedia's ~25,000:1; in line with what current IPDB traffic implies for its contributor base.
- **Pages per visit**: ~5. In line with IPDB; below Pinside because Flipcommons is reference-shaped, not forum-shaped.
- **Peak-hour multiplier**: ~5× the 24h average. US-evening + weekend skew.

| Horizon | Editors | Ratio | Visits/mo | Pageviews/mo |
| ------- | ------- | ----- | --------- | ------------ |
| Month 1 | 20      | 25×   | ~500      | ~2,500       |
| Month 2 | 100     | 50×   | ~5,000    | ~25,000      |
| Month 6 | 200     | 100×  | ~20,000   | ~100,000     |
| Year 1  | 400     | 200×  | ~80,000   | ~400,000     |

## Media uploads

Working assumption for capacity sizing:

- **5,000 uploaded images** (near-term reference point).
- **3 stored objects per upload** (`original`, `thumb`, `display`).
- **60 image reads/hour** on average.

Resulting total stored bytes, given an average size per image set (original + thumb + display):

| Avg stored size per image set | Total stored |
| ----------------------------- | ------------ |
| 1.4 MB                        | ~7.0 GB      |
| 3.4 MB                        | ~16.8 GB     |
| 5.4 MB                        | ~26.5 GB     |
| 10.4 MB                       | ~50.9 GB     |

The long-term capacity driver is total stored bytes, especially originals and any future video assets — not image-serving request volume.

Upload-volume shape: expect a small number of **super-uploaders** (the museum's own collection plus a few museum-connected enthusiasts uploading whole personal collections) rather than a long tail of one-off uploads. Batch upload and bulk tagging are core needs.

Per-image upload size cap is currently 20 MB. Video is deferred.

## Catalog content (system-generated, not user-uploaded)

Seed catalog size:

| Entity               | Files  |
| -------------------- | ------ |
| Models               | 6,829  |
| Titles               | 6,224  |
| Manufacturers        | 774    |
| Themes               | 597    |
| People               | 585    |
| Franchises           | 128    |
| Corporate Entities   | 90     |
| Systems              | 73     |
| Taxonomy (all types) | 78     |
| **Total**            | 15,366 |
