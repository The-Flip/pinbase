"""Authz types — phase 1 ships only the Activity enum.

Phase 2 of the Authz rollout (see docs/plans/auth/Authz.md) extends this
module with `Decision`, `Allow`, `Deny`, `DenialCode`, and the
`PolicyUser` Protocol. Until then, this file is the minimal central
registry the route-inventory test reads.
"""

from __future__ import annotations

from enum import StrEnum


class Activity(StrEnum):
    """Closed enum of named editorial activities the policy gates.

    String values are pinned explicitly because they are wire- and
    log-load-bearing for phase 3 (denial-code context, audit logging).
    StrEnum's auto-derived values would normalize the member name to
    `"catalog_edit"`, not the dotted form the rest of the design uses.

    Add members during the inventory pass when a route surfaces a need
    not covered by these. Same pinning rule applies.
    """

    CATALOG_EDIT = "catalog.edit"
    CATALOG_CREATE = "catalog.create"
    CATALOG_DELETE = "catalog.delete"
    CLAIM_REVERT = "claim.revert"
    # Discovered during the phase-1 inventory pass — added per Authz.md's
    # "Add an activity when its call site is being built, not in advance".
    CHANGESET_UNDO = "changeset.undo"
    CITATION_EDIT = "citation.edit"
    MEDIA_EDIT = "media.edit"
    KIOSK_EDIT = "kiosk.edit"
