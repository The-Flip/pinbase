# ValidationFix Amendment 1

## Status

Proposed amendment for review. This document does not replace
[ValidationFix.md](./ValidationFix.md) or
[IngestRefactor.md](./IngestRefactor.md) yet. It records a change in
direction for the ingest architecture based on the current pre-launch
operating model.

## Background

The current planning documents assume a future state in which Pinbase is
incrementally re-ingesting long-lived external sources and needs to decide,
during each ingest, whether facts that are absent from a source should be
retracted.

That assumption is not true today.

Today the project is still pre-launch. The normal workflow is to delete the
database and rebuild it from scratch by running a full ingest. We are not yet
running a long-lived incremental sync process against production data. We are
also not re-ingesting a permanent internal "Pinbase source" as an ongoing
source of truth. The current pinbase export exists to bootstrap the database;
it is not the final operational model.

This matters because the recent ingest design discussion introduced
`full_sync`, `partial_enrichment`, and related omission-based semantics as a
core architectural concept. Those concepts answer a real future question:

- if a source does not include a value in this run, should the old claim be
  retracted?

But they answer that question earlier than the project currently needs to.

At the moment, omission-based deletion behavior would be based on assumptions
about future source behavior, future ingestion patterns, and future domain
ownership rules that have not yet been validated in practice. That is a poor
fit for the current stage of the system.

## Diagnosis

The earlier documents correctly identified two separate problems:

1. Some facts still bypass claims entirely.
2. Claim validation was inconsistent across write paths.

Those remain real problems.

However, omission semantics are a third problem, and they are different:

- provenance coverage asks: "did this fact enter the system through a claim?"
- validation asks: "is this claim valid?"
- omission semantics asks: "what does source silence mean?"

The first two are current concrete problems. The third is mostly a future
operational problem.

Treating omission semantics as a first-class near-term architectural concern
adds complexity before the project actually needs that complexity:

- it introduces speculative policy categories (`full_sync`,
  `partial_enrichment`)
- it invites accidental assumptions that a source snapshot is complete when it
  may not be
- it makes the system harder to reason about before production ingest behavior
  has been established
- it couples "may this source assert this fact?" with "what does omission
  mean?", which are separate questions

In short: the current stage of the project needs a coherent claims-based write
path, not a complete omission-policy framework.

## Amendment

### Near-term ingest should be additive-only

For now, ingest should be modeled as a positive assertion process:

- match existing entities
- create new entities where needed
- assert claims for facts the source currently provides
- resolve materialized read models from those claims

Absence from a source payload should have no deletion semantics.

In other words:

- ingest says what a source sees
- ingest does not infer what a source has deleted

This means the near-term system should not retract claims merely because a
value is absent from an ingest payload.

### Deletion should be an explicit future mechanism

Retraction remains important, but it should be introduced when the product
actually needs it and when the evidence for deletion is explicit enough to be
trusted.

Examples of future deletion mechanisms:

- a source-provided changelog or tombstone feed
- an editorial/manual retraction action
- a future reconciliation job against a source that is explicitly treated as a
  complete authoritative snapshot for a declared scope

That future work is real, but it should be designed as explicit deletion or
reconciliation behavior, not inferred from absence by default in the initial
planner/applier architecture.

### Source permissions are separate from omission semantics

A source may be disallowed from asserting a category of facts even in an
additive-only system.

For example:

- OPDB may be a useful source of machine metadata but not of Pinbase-owned
  `Title` grouping or `variant_of` relationships
- manufacturer/company facts may belong on `CorporateEntity` rather than
  `Manufacturer`

These are source-permission and domain-ownership rules, not sync-mode rules.

The framework should keep those concerns separate:

- source permissions answer: "may this source assert claims in this category?"
- claim operations answer: "what claims is the source asserting or retracting?"

This separation is clearer than mixing both questions into a single "sync mode"
concept.

## Proposal

### 1. Keep the planner/applier split

The plan/apply architecture remains directionally correct and should stay:

- the planner/reconciler should produce a side-effect-free plan
- the applier should own transactions, validation, persistence, and resolution

This amendment changes the omission/deletion semantics, not the basic
plan/apply direction.

### 2. Remove omission-based sync modes from the near-term design

The near-term design should not model `full_sync` and `partial_enrichment` as
core ingest behaviors.

Instead, the default and only normal ingest behavior should be:

- additive assertion of observed facts

This keeps the model smaller and more honest:

- sources assert what they currently provide
- the system does not infer deletions from silence

### 3. Keep room for future explicit retraction

The apply layer should still be designed so that explicit retraction can be
added later without redesigning the whole system.

That means retraction should be represented as an explicit operation type when
it arrives, not as implicit behavior tied to absence.

### 4. Treat "replace a set" as a derived workflow, not a primitive

The earlier vocabulary included operations like `replace_claim_set`. That is
useful as a future reconciliation concept, but it should not be treated as a
primitive write verb.

"Replace this set of claims for this scope" is a higher-level workflow that can
be compiled into lower-level explicit operations:

- assert these claims
- retract those claims

That composition is clearer than baking omission semantics into the primitive
operation vocabulary from the start.

## Proposed Operation Verbs

The system should have a small set of primitive write operations.

### Primitive operations

- `entity_create`
- `claim_assert`
- `claim_retract`

These are intentionally narrow:

- `entity_create` creates a new entity row
- `claim_assert` records a positive source- or user-attributed fact
- `claim_retract` explicitly withdraws a previously active claim

These names are more symmetric and composable than mixing a collection-level
operation like `replace_claim_set` alongside single-claim operations.

If more human-readable names are preferred in prose, the equivalent terms are:

- create entity
- assert claim
- retract claim

### Derived operations

These should not be treated as primitives. They are planner/applier workflows
built on top of the primitive operations:

- `scope_reconcile`
- `claim_set_reconcile`
- `entity_merge`

For example, a future authoritative-snapshot ingest might use
`claim_set_reconcile` internally, but that workflow should compile down to
`claim_assert` and `claim_retract` during apply.

This keeps the core system simpler while leaving room for richer future jobs.

## Why This Is Not Hard To Add Later

If the system starts with:

- side-effect-free planning
- transactional apply
- explicit primitive operations
- claims as the only truth-affecting write path

then later deletion support is additive:

- add `claim_retract` to the plan when there is explicit deletion evidence
- later add reconciliation jobs that compute `claim_assert` + `claim_retract`
  from an authoritative snapshot

That is not a fundamental redesign. It is an extension of the apply-layer
operation set.

What would be invasive is the opposite direction: building omission-based
retraction into the core ingest semantics now, then trying to remove or narrow
it later after production behavior proves the assumptions wrong.

## Effect On Existing Documents

This amendment changes the near-term recommendation in two places:

### ValidationFix

ValidationFix should continue to focus on:

- closing provenance coverage gaps
- enforcing claim-boundary validation consistently

It should not assume that omission-based deletion semantics are part of the
near-term ingest rollout.

### IngestRefactor

IngestRefactor should keep:

- planner/applier separation
- non-mutating planning
- explicit source policy
- one transactional apply layer
- run reporting and audit trails

But it should defer:

- omission-based `full_sync` / `partial_enrichment` as core ingest policy
- source-silence-driven retraction behavior

Those can return later as explicit reconciliation features, once the system is
live and the actual operational requirements are known.

## Review Questions

1. Is additive-only ingest the most honest model for the current pre-launch
   stage of the project?
2. Should source-permission rules be documented separately from future
   retraction/reconciliation policy?
3. Are `entity_create`, `claim_assert`, and `claim_retract` the right
   primitive operation names, or should a different naming scheme be used?
4. Should future reconciliation remain explicitly out of scope for the first
   planner/applier implementation?
