# API Schema Refactors (follow-up)

## Consolidate name/slug pairs into Ref schema

The detail schemas have ~15 `*_name`/`*_slug` flat field pairs (e.g.,
`manufacturer_name`/`manufacturer_slug`, `technology_generation_name`/
`technology_generation_slug`). These should be consolidated into a
`Ref(Schema)` with `name` and `slug` fields.

This is a separate refactor from the licensing work — it affects every
detail and list endpoint, every frontend consumer, and many tests.
