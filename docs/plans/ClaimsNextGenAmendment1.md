# ClaimsNextGen Amendment 1: Push Validation to the Database

## Status

Proposed amendment for review. Extends the validation work referenced in
ClaimsNextGen (which inherits from
[ValidationFix.md](./ValidationFix.md) Component B) with database-level
constraint enforcement.

## Problem Statement

Pinbase has extensive Python-level validation on catalog model fields:
`MinValueValidator`, `MaxValueValidator`, `RegexValidator`, and custom
validators like `validate_no_mojibake`. These validators run at the
claim boundary (`validate_claim_value()`) and during form/API input, but
they are invisible to the database. Any write path that bypasses Python
validation — raw SQL, `QuerySet.update()`, `bulk_create()`, direct ORM
`save()` without `full_clean()` — can persist invalid data.

This is not a theoretical concern. The ClaimsNextGen plan identifies
direct ORM writes that bypass claims entirely. The apply layer uses
`bulk_create` for ChangeSets and Claims. Management commands use
`QuerySet.update()`. And the provenance system's own resolution layer
calls `save(update_fields=...)` on resolved model fields without
re-running validators.

The current validation architecture creates a false sense of safety:
validators exist on every field, but nothing enforces them at the
storage layer. The database accepts whatever it is given.

### The introspection complication

This is not a simple "add constraints" task. The codebase introspects
Django model validators at runtime to extract validation metadata and
serve it to other layers:

**`get_field_constraints()`** (`catalog/api/edit_claims.py:44-89`)
reads `field._validators` to find `MinValueValidator` and
`MaxValueValidator` instances, extracts their `limit_value`, and returns
a `{"year": {"min": 1800, "max": 2100, "step": 1}}` dict. This is
served via `/api/field-constraints/{entity_type}` and consumed by the
frontend (`field-constraints.ts`) to set `min`/`max`/`step` on form
inputs.

**`validate_claim_value()`** (`provenance/validation.py:110-166`)
iterates `field.validators` to run the Django validator chain at the
claim boundary — this is the central validation gate for both
interactive edits and bulk ingest.

**`_coerce()`** (`catalog/resolve/_helpers.py:92-128`) introspects
field types (`isinstance(field, models.IntegerField | ...)`) to coerce
claim values during resolution.

If validators are naively replaced with `CheckConstraint`, both
`get_field_constraints()` and `validate_claim_value()` lose their data
source. The frontend would have no min/max hints, and claim-boundary
validation would degrade to type coercion only, with range violations
surfacing as database errors instead of clean 422 responses.

## Concrete Examples

### 1. Range validators with no DB enforcement

Every numeric field uses Python-only range checking:

```python
# MachineModel
year = models.IntegerField(null=True, blank=True,
    validators=[MinValueValidator(1800), MaxValueValidator(2100)])
month = models.SmallIntegerField(null=True, blank=True,
    validators=[MinValueValidator(1), MaxValueValidator(12)])
player_count = models.SmallIntegerField(null=True, blank=True,
    validators=[MinValueValidator(1), MaxValueValidator(8)])
ipdb_rating = models.DecimalField(null=True, blank=True,
    validators=[MinValueValidator(0), MaxValueValidator(10)])

# Person — six date-component fields with the same pattern
birth_year = models.IntegerField(null=True, blank=True,
    validators=[MinValueValidator(1800), MaxValueValidator(2100)])
birth_month = models.SmallIntegerField(null=True, blank=True,
    validators=[MinValueValidator(1), MaxValueValidator(12)])
# ... birth_day, death_year, death_month, death_day

# CorporateEntity
year_start = models.IntegerField(null=True, blank=True,
    validators=[MinValueValidator(1800), MaxValueValidator(2100)])
year_end = models.IntegerField(null=True, blank=True,
    validators=[MinValueValidator(1800), MaxValueValidator(2100)])
```

A `MachineModel.objects.filter(...).update(year=9999)` succeeds
silently. So does `bulk_create` with `month=13`.

### 2. Cross-field invariants with no enforcement at all

These logical relationships exist only as human assumptions — no Python
validator, no DB constraint:

- **`CorporateEntity.year_start <= year_end`** — nothing prevents
  `year_start=2000, year_end=1950`
- **`Person.birth_year <= death_year`** — same gap
- **month/day require year** — `Person` and `MachineModel` can have
  `month=6` with `year=NULL`, which is meaningless

### 3. Regex validators with no DB enforcement

`Manufacturer.wikidata_id` and `Person.wikidata_id` use
`RegexValidator(r'^Q\d+$')` — Python only. A raw write of
`wikidata_id='not-a-wikidata-id'` is accepted by the database.
Note: regex `CheckConstraint` enforcement is Postgres-only — SQLite
(the dev database) does not support regex in `CHECK` constraints. The
Python `RegexValidator` remains the enforcement layer in dev.

### 4. Non-blank invariants beyond slugs

`slug_not_blank()` adds a `CheckConstraint` ensuring `slug != ''` on
every slugged model. But other `CharField(blank=False)` fields (like
`name` on most catalog entities) only get `blank=False` enforcement at
the form layer. A raw insert with `name=''` succeeds.

### 5. `unique_together` still in use

Six models use the deprecated `unique_together` instead of
`UniqueConstraint`:

- `RecordReference` — `[["source_type", "source_id", "target_type", "target_id"]]`
- `MachineModelGameplayFeature` — `[("machinemodel", "gameplayfeature")]`
- `CorporateEntityLocation` — `[("corporate_entity", "location")]`
- `ModelAbbreviation` — `[("machine_model", "value")]`
- `TitleAbbreviation` — `[("title", "value")]`
- `SourceFieldLicense` — `[("source", "field_name")]`

These produce the same SQL `UNIQUE` index but miss `UniqueConstraint`
features: `condition`, `include`, `nulls_distinct`,
`violation_error_message`.

### 6. Timestamps without `db_default`

`TimeStampedModel.created_at` and `updated_at` use Django's Python-side
`auto_now_add`/`auto_now`. A row inserted outside the ORM gets
`NULL` timestamps. Django 5.0+ `db_default=Now()` puts the default in
the DDL.

## Options

### Option A: Keep both — add CheckConstraints alongside existing validators

Add `CheckConstraint` for every range, cross-field, regex, and non-blank
invariant. Keep the existing validators unchanged. Both layers enforce
the same rules independently.

**Pros:**

- Zero changes to `get_field_constraints()`, `validate_claim_value()`,
  or the frontend
- Validators continue to produce clean error messages at the claim
  boundary
- CheckConstraints catch anything that slips past Python
- Smallest diff, lowest risk

**Cons:**

- Every range is defined twice — once in the validator, once in the
  constraint — with no compile-time guarantee they match
- Over time, one side drifts (someone updates a validator limit but
  forgets the constraint, or vice versa)
- Tests must assert both layers independently

### Option B: Centralize ranges as constants, reference everywhere

Define range constants (e.g. `YEAR_MIN = 1800`, `YEAR_MAX = 2100`) on
each model or in a shared module. Reference those constants in
validators, `CheckConstraint` conditions, and optionally in
`get_field_constraints()`.

```python
class MachineModel(TimeStampedModel):
    YEAR_MIN, YEAR_MAX = 1800, 2100
    MONTH_MIN, MONTH_MAX = 1, 12

    year = models.IntegerField(null=True, blank=True,
        validators=[MinValueValidator(YEAR_MIN), MaxValueValidator(YEAR_MAX)])

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(year__gte=YEAR_MIN, year__lte=YEAR_MAX)
                         | Q(year__isnull=True),
                name="machinemodel_year_range",
            ),
        ]
```

`get_field_constraints()` can continue reading from `field._validators`
(no change needed) — the constants just ensure both sources agree.

**Pros:**

- Single source of truth for every range
- Both layers always agree by construction
- `get_field_constraints()` and `validate_claim_value()` need zero changes
- Constants are greppable and testable

**Cons:**

- Moderate diff — every model with range validators needs to extract
  constants and add constraints
- Naming convention must be established (per-model constants vs. shared
  module)

### Option C: Replace validators with constraints, rewrite introspection

Remove `MinValueValidator`/`MaxValueValidator` from fields. Add
`CheckConstraint` for all ranges. Rewrite `get_field_constraints()` to
parse constraint conditions (or read from a declarative registry) and
rewrite `validate_claim_value()` to not depend on field validators for
range checking.

**Pros:**

- No redundancy — each rule exists in exactly one place (the DB)
- Claim-boundary errors become `IntegrityError` caught by the
  transaction, matching the "DB is the source of truth" philosophy

**Cons:**

- `Q` objects are not designed for introspection — parsing
  `CheckConstraint.condition` to extract min/max is fragile and
  undocumented
- Claim-boundary validation degrades: instead of clean
  `ValidationError("year must be >= 1800")`, users get raw
  `IntegrityError` from the DB or a generic constraint-violation message
- Requires a parallel declarative registry to feed the frontend, which
  is effectively the same as Option B but with more moving parts
- Largest diff, highest risk

## Recommendation

**Option B.** It is the only option that eliminates the drift risk
(ranges defined once, used everywhere) without degrading the
claim-boundary validation UX or requiring fragile constraint
introspection. The constants are straightforward, the migration is
mechanical, and neither `get_field_constraints()` nor
`validate_claim_value()` requires changes.

Cross-field invariants (year ordering, month-requires-year) and
non-blank constraints do not have the introspection complication — they
are purely additive CheckConstraints with no existing consumer to break.
These can be added regardless of which option is chosen for range
validators.

## Scope

### Phase 1: Cross-field invariants and non-blank constraints (no introspection impact)

These are pure additions — no existing code reads them:

1. `CorporateEntity`: `year_start <= year_end` (when both non-null)
2. `Person`: `birth_year <= death_year` (when both non-null)
3. `Person`: `birth_month` requires `birth_year`; `birth_day` requires
   `birth_month` (and same for death fields)
4. `MachineModel`: `month` requires `year`
5. Non-blank `CheckConstraint` on `name` for all catalog entities that
   have `blank=False` on name

### Phase 2: Range constants + CheckConstraints (Option B)

1. Define range constants on each model class
2. Reference constants in existing validators (update `MinValueValidator(1800)`
   to `MinValueValidator(YEAR_MIN)`)
3. Add `CheckConstraint` for each range using the same constants
4. Add a test that asserts validator limits match constraint conditions
   (drift detection)

### Phase 3: Mechanical cleanup

1. Migrate `unique_together` to `UniqueConstraint`
2. Add `db_default=Now()` on `created_at` fields only. `updated_at`
   stays Python-managed (`auto_now`) — true DB-managed update timestamps
   would require triggers, which is a separate concern.
3. Add `db_default` on `IngestRun.status` (already has it) and any other
   fields with meaningful defaults
4. Regex `CheckConstraint` for `wikidata_id` fields — **Postgres-only**.
   SQLite remains the dev database and does not support regex in
   `CHECK` constraints. These constraints should use Django's
   `CheckConstraint(..., condition=...)` and will only be enforced in
   production (Postgres). The Python `RegexValidator` remains the
   enforcement layer in dev.

### Phase 4: Review and trim

After Phases 1-3, review `validate_catalog` and resolver coercions
(as noted in ClaimsNextGen) to identify checks that are now redundant
with DB-level enforcement.

## Relationship to ClaimsNextGen

ClaimsNextGen's apply layer uses `bulk_create` for Claims and
ChangeSets, which bypasses `full_clean()` and field validators. The
apply layer calls `validate_claims_batch()` before persisting, so
claim-boundary validation still runs. But any bug in that call path —
a claim that skips validation, a code path that calls `bulk_create`
directly — would persist invalid data without DB constraints.

DB constraints are the safety net beneath the claim-boundary validation.
They do not replace it (claim-boundary validation produces better error
messages and runs before the transaction), but they guarantee that
invalid data never reaches the storage layer regardless of the write
path.

This is fully additive to the ClaimsNextGen architecture. No changes to
the plan/apply split, operation primitives, or source adapter design.

## Non-Goals

- Replacing the claim-boundary validation layer — CheckConstraints are a
  safety net, not a replacement for `validate_claim_value()`
- Adding constraints that require procedural checks (e.g. cycle
  detection in Location hierarchy — that stays in Python)
- `GeneratedField` for computed columns — valuable but a separate
  concern from validation enforcement
