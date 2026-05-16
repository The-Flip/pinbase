# Personas

This doc names the kinds of people who use the system.

These are not roles in the authorizations; instead, auth uses [Activities](Authz.md).

## The Personas

### Reader

People who come to read. They browse pages, look up models, follow links, search.

This is by far the largest group, and the audience whose experience most of the public surface must first be optimized for - if we don't have Readers, we won't have Contributors either.

See [below](#reader-profile) for their motivational picture.

### Contributor

People who add to and improve the site. They write descriptions and essays, upload photos and documents, edit catalog records, and steward the pages they care about.

See [below](#contributor-profile) for their motivational picture.

### Maintainer

A member of the [small team](../SmallTeam.md) running the project. They operate the site, respond to incidents, review activity, and shape the data and the product.

## Future Personas

Anticipated but not implemented:

- **Moderator** — a Contributor with elevated privileges and responsibilities, that might police less-privileged contributors.

## Aliases

Other docs predate this one and use varying terms:

| Role        | Aliases found elsewhere             |
| ----------- | ----------------------------------- |
| Reader      | Visitor, "casual fan", "the public" |
| Contributor | Editor, Writer, "logged-in user"    |
| Maintainer  | Admin, Staff, Superuser             |

## Commonality among all personas

The core user is someone driven by curiosity and love of the subject, not by a transactional need. They're not here to price a machine or manage a route — they're here because pinball history is interesting and they want to go deeper. The tagline of The Flip museum is "Preserving the love of pinball for future generations" and this project is a plank of that.

This doc names the three personas in the system — **Reader**, **Contributor**, **Maintainer** — and describes who they are and what draws them in. Other docs should use these names.

These are descriptive labels, not authorization primitives; backend gates use [Activities](../../Authz.md).

## Who They Are

- Historians/archivists who care about preservation for its own sake.
- People just getting into pinball and wanting the authoritative encyclopedia of all the concepts.
- Casual fans who just played something cool at a bar and want to know more.
- Collectors wanting to learn more about the history of their machines, their significance, the industry context, ideas for other machines to collect.
- The general public of the museum, which is probably mostly casual fans, wanting to explore more about what they've seen, are seeing at the moment (via a kiosk at the museum or their phone) or are about to see before they come.

## Who They Might Be In The Future

- Restorers looking for specs, schematics, parts info. We already have a public read-only version of the Flipfix maintenance site that we hope to grow into a deep resource of repair information for the particular models that the museum owns: the entire maintenance history and conversations around maintenance are public. So there's deep interest from the museum in supporting this community. Adding specs, schematics, parts info to this project would absolutely be right in the museum's mission. Dunno, though, whether we can improve on existing sites around this.

## Who They Are Not

- Tournament players who care about rules, competition data.
- Collectors wanting to value what they own.
- Operators managing routes and tracking machine performance.

## Reader Profile

"I just played Medieval Madness and now I want to fall down a rabbit hole about Williams in the 90s." The casual fan, the museum visitor, the person just getting into pinball.

Readers come to read — they browse pages, look up models, follow links, search. Often arriving from search engine results, almost always unauthenticated. The largest group, and the audience whose experience most of the public surface is designed around.

## Contributor Profile

"I know things about pinball history that aren't captured anywhere, and I want to help build the definitive record." The historian/archivist and the museum-connected enthusiast.

Contributors write descriptions and essays, upload photos and documents, edit catalog records, and steward the pages they care about. They must have an account.

### The opportunity

We suspect there's pent-up demand among amateur pinball writers and historians becuase IPDB, the existing major encyclopedia, has been difficult to work with for years.

This is this project's contributor acquisition strategy: give frustrated IPDB contributors a better home.

### What they contribute

Two distinct activities that attract different people and need different recognition:

**Writing** — original descriptions, historical context, essays on gameplay features (like the evolution of star rollovers), histories of manufacturers, titles, series, people, and places. This is creative, high-effort, high-reward work. It's what makes a page great. A 2,000-word history of Williams' System 11 platform needs to feel like that author's contribution to a shared project, not something that disappeared into the site.

**Uploading** — photos, documents, media. The museum has its own collection of high-quality photos, and people attached to the museum have personal collections. Expect super-uploaders who will upload their entire collection if given an easy way to do so, rather than one-off uploads from random owners. Lower effort per item than writing, more mechanical, but still valuable. Batch upload and bulk tagging are core needs, not nice-to-haves. These people may enjoy having more control over how their photos are presented, giving them more control over layouts... just a hypothesis. We know some of these people and can both ask them and user-test features with them.

Contributors probably won't enter that much structured catalog data — that's already fairly complete for historical models. This may be the way that new models get entered, or we may automate scraping manufacturer sites to get this information.

### What makes it meaningful to them

Both ownership and reputation matter:

- **Stewardship**: The Wikipedia model. "I am the person who maintains the article on Bally Manufacturing, and that matters." The identity comes first; game mechanics (edit counts, awards) reinforce it. Contributors need to feel like stewards of a shared project, not data entry workers for someone else's site.
- **Visibility**: The Pinside model. Contributors are recognized community members. Their name appears on their work, they build a visible contribution history, and the community acknowledges their expertise.

The museum director's background at Wikipedia informs the approach: knowledge as a side-product of well-designed incentives, with stewardship as the foundation and reputation mechanics as reinforcement.

## Maintainer

The [small team](../../SmallTeam.md) running the project. Not a target user — Maintainers are us, the operators. They run the site, respond to incidents, review activity, and shape the data and the product.

Maintainers receive production alerts (see [Observability.md](../observability/Observability.md#recipients)) and consume raw analytics and operational telemetry.

## Aliases

Other docs predate this one and use varying terms:

| Persona     | Aliases found elsewhere                                                                 |
| ----------- | --------------------------------------------------------------------------------------- |
| Reader      | Visitor (Analytics, Observability), Explorer (older drafts), "casual fan", "the public" |
| Contributor | Editor, Writer, Uploader, "logged-in user"                                              |
| Maintainer  | Admin, Staff, Superuser, "the small team"                                               |

New docs should use the canonical names. Existing docs will be reconciled opportunistically.

## Future Personas

Anticipated but not yet present:

- **Moderator** — a Contributor with elevated review/revert capabilities, short of full Maintainer access. See [Authz.md](../../Authz.md) for the planned predicate hooks (moderator role, account age, reputation, abuse flag).
- **Bot / Service account** — non-human Contributors for automated ingest or integrations.
