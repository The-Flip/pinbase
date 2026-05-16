# Small Team

Flipcommons is a volunteer-run, not-for-profit project. Our mission is to further pinball knowledge, not make money.

To survive, the system and the "organization", such as it is, must stay **lean**:

## Hosted over build-yourself

Generally owning a system is more complex than renting it.

## Cheap

We aren't making money on this. Prefer systems that are free -- we're open source OSS so that helps someimes. If we do have to pay, a few bucks a month. $10 is expensive. $20 is very expensive.

## Low ongoing maintenance

Nobody's manning this on a day-to-day basis so ongoing maintenance must be MINIMAL. For example:

- rotating HTTP certs manually is a no-no
- Automatic security patches to our packages is mandatory

## Not aimed at pro IT

Hosted systems must be runnable by **part-time developers without DevOps training**. For services like CDN, file sharing, auth, choose systems that are NOT aimed at professional IT.

### Easy to onboard

A new contributor should be productive on day one.

## Simple

Prefer boring, well-documented choices over clever ones.

Minimal moving parts.

## No single person failure

Volunteers, even founders, disappear. Ensure no one person has the keys to the kingdom.

### Hosted systems must be multi-admin

Hosted systems must support multiple admins. Each person gets their own login.

#### Hosted systems without master accounts

Strong preference for a hosted system not having a single master account. We don't want a shared password manager with a shared master account or password. Instead, prefer systems that have some sort of team structure where multiple people can be full co-equal admins.

#### Beware pricing tiers

If multi-user access is gated behind a pay tier that we can't justify at our scale, the vendor is disqualified.
