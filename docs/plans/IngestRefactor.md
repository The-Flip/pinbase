# Ingest Architecture

## The Problem

Pinbase's ingest layer is a set of Django management commands that import catalog data from external sources (IPDB, OPDB, Fandom wiki, Wikidata) and from Pinbase's own editorial data (pindata JSON exports). Each command was written independently and evolved to handle its source's unique data shape.

The commands are fragile, hard to maintain, and a persistent source of bugs — especially for AI agents working on them. The root cause is not that the code is messy (though some of it is). The root cause is that the commands are imperative programs that mix several distinct responsibilities in one place: parsing, entity matching, claim-intent policy, direct ORM mutation, claim assertion, and resolver invocation. These concerns are interleaved in per-command control flow with no shared contracts or boundaries.

This makes it hard to answer basic questions about any given ingest write:

- Is this write provenance-backed?
- If the command fails halfway through, what state remains?
- If a source stops asserting a value, does the old claim get retracted?
- Should this source be asserting this field for this entity at all?

The answers are buried in per-command control flow, variable names, tuple positions, and comments. They are not represented in the type system or enforced by shared infrastructure.

### Concrete failure modes

**Non-atomic execution.** None of the individual ingest commands wrap their `handle()` in `transaction.atomic()`. (`ingest_all` wraps the full pipeline, but individual commands run without protection during development and debugging.) A command that fails after creating entity rows but before finishing claim assertion leaves partial state that is hard to diagnose and may not be safe to retry.

**Direct writes bypass claims.** Despite the project rule that all catalog fields are claims-based, ingest still has multiple direct-write paths: `QuerySet.update()` for title slugs, `save(update_fields=...)` for wikidata IDs (which are also asserted as claims — a dual-write), direct `opdb_id` rewrites in changelog processing, and `ManufacturerResolver.resolve_or_create()` which creates `Manufacturer` rows with no claim provenance at all.

**No scalar retraction.** Relationship claims use sweep semantics — a source declares its complete set, and anything it previously asserted but didn't include this time gets retracted. Scalar claims have no equivalent. If a source stops asserting a value, the old claim stays active forever. Whether omission means "retract" or "ignore" is inconsistent and always implicit.

**Snowflake claim collection.** The same conceptual operations (match or create entities, collect scalar claims, gate slug claims on source attribution, assert relationship claims with sweep) are reimplemented with different variable names, data structures, parameter conventions, and control flow in each command. During the slug migration, this caused an agent to assert slug claims for entities a source didn't create, a human reviewer to miss the same error for two entity types, and a tuple-arity change to break an unpack site that couldn't be found by grep.

**Implicit policy.** Whether a source should assert a slug claim, whether it should assert a name claim, whether it is authoritative enough to sweep, which anomalies are warnings vs. blocking errors — all of these are encoded as if-branches and local conventions rather than as named, auditable policy.

## Design Principles

**Separate planning from application.** Parsing, matching, and claim-intent decisions should happen before any database mutation. Database mutation should happen in one place, in one transaction, with no source-specific logic.

**Make sync semantics explicit.** Every source/field combination should declare whether missing data means "retract" or "ignore." The current asymmetry — relationships sweep, scalars don't — should be an explicit policy choice, not an accident of implementation history.

**One write path.** Every catalog fact enters the system through claims. No direct ORM writes to claim-controlled fields. Entity creation and claim persistence both happen in the apply layer's transaction — the planner never writes to the database.

**Source-specific complexity stays source-specific.** Parsing, matching heuristics, encoding fixes, entity-creation decisions (e.g. IPDB's corporate entity derivation) — these are inherently per-source. The architecture should not try to force them into a shared abstraction. It should give them a clear place to live and keep them out of the apply layer.

**Idempotency.** Running the same ingest with the same input data twice should produce identical database state. No new rows, no retractions, no side effects. The current `bulk_assert_claims` already achieves this (unchanged claims are detected and skipped). The full-sync diff preserves this property — a snapshot that matches prior claims produces zero writes. This must remain true in the redesign; it is an explicit design goal, not an emergent property.

## Architecture

### Two phases: Plan and Apply

Every ingest run has two phases with an explicit boundary between them.

**Plan** — the source adapter reads raw data, matches it to existing entities, applies source-specific policy, and produces a change plan. The planner does not mutate the database. It references entities that need to be created by including `PlannedEntityCreate` operations in the plan, not by writing rows directly.

**Apply** — the framework creates planned entities (capturing PKs), patches PKs into associated claims, validates the plan, computes diffs for full-sync categories, persists all changes in one transaction, resolves affected entities, and emits a run report. The applier contains no source-specific logic.

This separation is the core of the design. Everything else follows from it. The boundary must be strict: the planner produces data, the applier performs writes. If the planner is allowed to "just create a bootstrap row," the separation unravels — dry-run is no longer side-effect-free, and the transaction boundary leaks.

### Source adapters

Each source implements three concerns:

**Parse.** Load raw data, convert to typed source records. This is already extracted into per-source record types (`IpdbRecord`, `OpdbRecord`, etc.) and mostly works well today.

**Reconcile.** Match source records to existing entities. Output is a list of `MatchResult` objects:

```python
@dataclass
class MatchResult[R]:
    entity: Model | None   # existing entity, or None if new
    record: R              # typed source record
    created_by_source: bool
    # possibly: match_type (exact_id, name, heuristic, ambiguous)
```

For new entities (no match found), the reconciler does not create database rows. Instead, the claim collection step emits a `PlannedEntityCreate` alongside the claims for that entity. Claims reference the planned entity by a temporary handle (e.g. an index into the plan's create list, or the source-specific identity values). The apply layer creates the row, captures the PK, and patches it into the associated claims before persisting them.

This is more machinery than "just create the row in the reconciler," but it is what makes the planner genuinely non-mutating. Without it, dry-run would still write rows, the transaction boundary would leak, and the plan/apply separation would be nominal rather than real.

Each source's matching logic is different (IPDB matches by `ipdb_id`, OPDB by `opdb_id`, Fandom by name) and that is fine. The architecture does not try to unify matching strategies. It requires that matching produces structured output rather than silently falling through into row creation as a side effect of a lookup helper.

**Collect claims.** Given reconciled results, produce the set of claims this source wants to assert. Source-specific policy is explicit here:

- Slug gating: assert only when `created_by_source` (cross-source invariant)
- Name policy: per-source, per-entity (IPDB skips name for matched machine models due to encoding corruption; Fandom always asserts name to prevent resolver blanking; OPDB asserts name unconditionally)
- Field mappings: which source fields become which claim field names
- Encoding transforms: HTML entity decoding, mojibake handling
- Relationship claims: credits, themes, gameplay features, etc.

Simple policy (slug gating, sync mode declarations) should be data. Complex policy (IPDB's CE derivation from manufacturer data, Fandom's near-duplicate person detection) will remain procedural code. The goal is not to make all policy declarative — it is to give policy a named, auditable location rather than embedding it in general-purpose control flow.

Claim value validation is not a concern of the source adapter. The apply layer runs `validate_claims_batch()` on all planned claims — the same claim-boundary validation established by [ValidationFix.md](ValidationFix.md) Component B. Source adapters produce claims; the framework validates them.

### Sync modes

Every source/field combination operates in one of three sync modes:

**`full_sync`** — the source owns the complete set for this field or relationship category. The plan contains a snapshot of everything the source currently asserts. The apply layer diffs it against the source's prior active claims and computes creates, unchanged, and retractions. If the source didn't include a value in this run, the framework retracts it.

This is how relationship sweep already works today. The design extends it to scalars where appropriate.

**`partial_enrichment`** — the source contributes values when present but does not own the complete set. Missing values are ignored, not retracted. The plan contains targeted assertions only.

This is the right mode for Wikidata (adds `wikidata_id` and descriptions but doesn't own name or slug), Fandom manufacturer enrichment (adds website and description but doesn't own the entity), and any source that supplements rather than defines.

**`append_only`** — the source adds facts that are never automatically retracted. Useful for historical or additive data.

Sync mode is chosen **per source/field-category**, not per source. A single source is often authoritative for some fields and only a partial enricher for others. IPDB is `full_sync` for machine model scalars and credits, but only `partial_enrichment` for person names. OPDB is `full_sync` for its relationship categories (gameplay features, reward types, tags) but does not own titles or variant_of. Fandom is `partial_enrichment` almost everywhere. Making sync mode a source-level default would invite accidental retractions — exactly the class of error this design is meant to prevent.

The key insight: the current codebase already implements `full_sync` for relationships (via `sweep_field` + `authoritative_scope`) and `partial_enrichment` for scalars (via "skip if empty"). But which mode applies where is an accident of implementation shape, not an explicit choice. Making it explicit and per-field-category is what turns ad-hoc retraction behavior into a principled system.

#### Full-sync scope

For `full_sync` categories, the apply layer needs to know the **authoritative scope** — which entities did this source provide data for in this run? The diff retracts prior claims only within that scope.

This matters because sources do not necessarily provide data for every entity they have ever touched. If IPDB removes a machine from its dump, should IPDB's claims for that machine be retracted? The answer depends on why it was removed:

- If IPDB's dump is a complete export and the machine is gone, retraction is correct.
- If the dump is a partial extract or the source had a data error, retraction would destroy good data.

The source adapter must declare the authoritative scope explicitly as part of the plan — it cannot be inferred from the input alone. This is the same `authoritative_scope` concept that the current relationship sweep machinery already uses. The redesign generalises it to cover scalars too, but the responsibility stays the same: the source declares what it is authoritative over, and the framework handles the diff within that scope.

#### Validation failure is not omission

The apply layer validates planned claims before diffing (step 2b before 2c). Batch validation logs and skips invalid claims rather than failing the run. This creates a dangerous interaction with full_sync: if a planned claim is rejected by validation, the diff must not treat that as the source omitting the field — otherwise a tightened validator could retract a previously-good claim.

The rule: **a claim rejected by validation is excluded from the diff entirely.** The diff only considers claims that passed validation or were not attempted. "Source included this field but validation rejected it" (preserve prior claim, log warning) is a different outcome from "source did not include this field" (retract under full_sync). The rejected claim's prior value stays active; the warning surfaces in the run report.

### Ingest runs and change sets ✓ (data models implemented)

Ingest provenance is recorded at two levels:

**IngestRun** — one record per source invocation. This is the run-level audit trail:

- source (FK to Source, on_delete=PROTECT)
- start/end timestamps
- input fingerprint (CharField)
- git SHA (CharField)
- counts (JSONField: parsed, matched, created, asserted, retracted, rejected)
- status (running, success, partial, failed)
- warnings and errors (JSONField lists)

**ChangeSet** — one per target entity touched in the run. Groups all claims the source asserted about that entity (scalar claims, relationship claims) into a coherent unit. Each ChangeSet has a nullable FK to its IngestRun (on_delete=CASCADE — deleting a run deletes its ChangeSets). User-edit ChangeSets have a null ingest_run.

Retractions are linked to the ChangeSet so entity history shows the complete picture — what was added, what was changed, and what was removed in a given run. Claim has a nullable `retracted_by_changeset` FK (on_delete=SET_NULL). When the diff deactivates a claim, the apply layer sets `is_active=False` and sets `retracted_by_changeset` to the current entity's ChangeSet. Entity history can then show both "these claims were asserted" (ChangeSet → claims) and "these claims were retracted" (ChangeSet → retracted claims via reverse FK).

"Per target entity" means grouped by the object the claims are about, not by the source record that triggered them. When IPDB processes one machine record, it may assert claims against the MachineModel, create or update a CorporateEntity, and assert claims against Persons for credits. That is three ChangeSets (one per target entity), not one. This is the right granularity because entity history is viewed per entity — a user looking at Medieval Madness's history sees the claims about Medieval Madness, not about the CorporateEntity that was also updated in the same source record.

Claims already have an optional FK to ChangeSet. The IngestRun is reachable through ChangeSet — claims don't need a direct FK to IngestRun.

This gives two natural query levels:

- "Show me everything IPDB said about Medieval Madness in this run" — that's the ChangeSet
- "Show me everything that happened in the March 28 IPDB run" — that's the IngestRun

ChangeSet is reused exactly as designed: a thin grouping of related claims from one actor. For user edits, the actor is a user and the ChangeSet groups a handful of manual changes. For ingest, the actor is a source and the ChangeSet groups everything a source said about one entity. The single-actor invariant holds in both cases. The scale is right — dozens of claims per entity, not thousands.

**Single-actor enforcement.** A `CheckConstraint` on ChangeSet enforces that `user` and `ingest_run` are mutually exclusive (user XOR ingest_run, or neither for legacy/system). `assert_claim()` additionally checks that source-attributed claims with a changeset require `changeset.ingest_run.source == source`. Note: the apply layer uses `bulk_create` for ChangeSets and Claims, which bypasses `assert_claim()`. Source consistency on the bulk path is maintained by construction — the apply layer creates each ChangeSet from the IngestRun, then creates claims with the same source. Implementers must maintain this invariant explicitly.

**Visibility.** IngestRun is an admin/system-level concept. Admins can browse runs across all sources — inspecting counts, timing, failures, and warnings. Regular users see entity history through ChangeSets, not run records. A user viewing the history of Medieval Madness sees "IPDB updated these fields on March 28" (the ChangeSet), not "IPDB run #47 processed 4,000 machines" (the IngestRun). The IngestRun is reachable from the ChangeSet for admin drill-down, but it is not part of the user-facing entity history.

### Apply layer

The apply layer is source-agnostic. Its responsibilities:

1. **Create IngestRun** (before transaction) — record source, start time, input fingerprint, status=`running`
2. **Open transaction:**
   a. **Create entities** — execute `PlannedEntityCreate` operations, capture PKs, patch them into associated claims
   b. **Validate** — run `validate_claims_batch` on new/changed claims (see [ValidationFix.md](ValidationFix.md) Component B)
   c. **Diff** — for `full_sync` categories, compare the plan's claim snapshot against prior active claims from this source within the declared authoritative scope; compute creates, unchanged, and retractions
   d. **Persist** — bulk-create a ChangeSet per target entity, bulk-create new claims linked to their ChangeSet, deactivate retracted claims (set `is_active=False` and `retracted_by_changeset` to the entity's ChangeSet). A single ingest run can touch thousands of entities, so ChangeSet creation must be batched (`bulk_create`), not one `create()` per entity in a loop
   e. **Resolve** — materialise affected entities (same resolution layer as today)
3. **Finalise IngestRun** (after transaction) — update counts, status, end time

The IngestRun record is created and updated **outside** the apply transaction. If the transaction rolls back on failure, the IngestRun still survives with status=`failed` and error details — which is exactly when you most want the audit record. ChangeSets and claims are created **inside** the transaction, so partial ingest state never persists on failure.

Source adapters never open transactions or write to the database. The data models (IngestRun, ChangeSet.ingest_run FK, Claim.retracted_by_changeset FK) are implemented. The database will be deleted and migrations reset to `0001` as part of the remaining work, so no backfill or data migration is needed.

### Run reports

The IngestRun record is the persisted form of the run report. In dry-run mode the same report is produced as an in-memory data structure but not written to the database. Either way, the report should make it possible to answer "what happened?", "what changed?", "what was skipped?", and "what needs human curation?" without reading logs or re-running the import.

### Dry run

Because the planner is fully non-mutating, dry run is straightforward: parse, reconcile, collect claims, validate, diff against current state (read-only), emit report, apply nothing. No rollback transactions needed. The plan and diff are the same objects whether or not they get applied.

### Testing

The most valuable tests target the plan boundary: given these source records and this database state, what change plan is produced? This directly exposes source-attribution decisions, sync mode behavior, and claim-intent policy without requiring end-to-end command execution. Integration tests still matter but sit on top of a more inspectable model.

### Domain ownership enforcement

The architecture cannot decide which model owns a fact — that is a domain decision humans make. But it can make that decision **enforceable** once made.

Today nothing prevents a source adapter from attaching company facts to `Manufacturer` instead of `CorporateEntity`. That's how the Fandom and Wikidata TODOs happened: both sources target `Manufacturer` for company metadata that should live on `CorporateEntity`, and nothing in the system caught or prevented it.

Source policy declarations should include which models and fields a source is permitted to assert claims against. The apply layer can then reject claims that target a model/field combination the source hasn't declared. This turns "emit claims against the right model" from a convention that source authors must remember into a constraint the framework enforces.

The architecture does not decide that company metadata belongs on `CorporateEntity` rather than `Manufacturer`. It makes that decision — once made — hard to violate accidentally.

## `ingest_pinbase` is a special case

The plan/apply model fits IPDB, OPDB, Fandom, and Wikidata naturally. Each is an external source that focuses on one or two entity types per run. `ingest_pinbase` is fundamentally different.

`ingest_pinbase` is the editorial source that seeds the entire catalog. It processes 12 entity types in dependency order (taxonomy, themes, gameplay features, manufacturers, corporate entities, systems, people, series, titles, models), each with its own matching logic, claim shapes, and resolution steps. Later phases depend on rows created by earlier phases (e.g. titles reference manufacturers and systems that were ingested in prior phases).

This does not fit cleanly into "one source adapter produces one plan, the apply layer executes it."

The right approach is a **compound plan**: the pinbase adapter produces a plan with ordered sub-plans, one per entity type (or logical group). The apply layer executes them sequentially within one transaction, making each sub-plan's entities available to the next.

This is the only option that preserves full atomicity naturally — if any phase fails, the entire pinbase ingest rolls back. The alternatives (multiple independent plan/apply cycles, or a hybrid that applies each phase independently) reintroduce the non-atomicity problem unless wrapped in an outer transaction, which negates the benefit of separate cycles.

The compound plan also maps most closely to the current phase structure, making migration straightforward: each `_ingest_*` method becomes a sub-plan builder rather than an imperative mutate-as-you-go method. The apply layer handles entity creation, claim persistence, and resolution for each sub-plan in sequence. Each sub-plan must not have direct ORM writes to claim-controlled fields, and entity creation must be explicit and provenance-backed.

## What This Does Not Solve

**Domain modeling decisions.** The architecture enforces domain ownership but does not decide it. Which model owns which facts is a domain decision that must be made separately. The existing Fandom and Wikidata TODOs (targeting `Manufacturer` when they should target `CorporateEntity`) are domain fixes that the architecture would then enforce.

**Source-specific parsing complexity.** IPDB's gameplay feature extraction with multiball special-casing, Fandom's wiki fetching and near-duplicate detection, IPDB's encoding corruption handling — these are essential complexity that no architecture can remove. The architecture gives them a clear home (the source adapter) and keeps them out of the apply layer, but they remain code that must be written and maintained per source.

## What Stays Source-Specific

- Parsing raw data into typed records
- Matching/reconciliation logic and fallback strategies
- Field mappings
- Name and encoding policy
- Entity creation decisions
- Complex claim-intent policy that cannot be expressed as data

## What Stops Being Source-Specific

- Transaction management
- Claim persistence and retraction
- Sync mode enforcement (full_sync diffing, partial_enrichment passthrough)
- Resolution orchestration
- Run reporting
- The "collect into a list, then bulk_assert, then resolve" boilerplate that every command currently reimplements

## Relationship to ValidationFix

[ValidationFix.md](ValidationFix.md) established the claim boundary as the place where validation happens and built the machinery (`validate_claim_value()`, `validate_claims_batch()`, `classify_claim()`). This plan reuses that machinery in the apply layer — it does not replace or duplicate it.

The two plans address different layers of the same problem:

- **ValidationFix** answers: "given a claim, is it valid?" (claim-content validation at the boundary)
- **IngestRefactor** answers: "should this claim exist at all, and how does it get to the boundary?" (claim-intent policy, sync semantics, transaction management)

ValidationFix step 7 adds a field validator audit to ensure model fields carry adequate validators. This complements the ingest redesign — the apply layer's validation step is stronger when the fields carry adequate validators, but the refactor does not depend on it. The two can proceed in parallel.

## Non-Goals

This document defines the target architecture. It does not:

- Prescribe a migration order for the existing code
- Define every dataclass or module in final detail
- Choose a storage format for planned entity identities or run metadata
- Decide exact package layout beyond the architectural split into source adapters and apply layer
