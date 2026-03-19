# DuckDB Explore Database

The best way to explore the data in Pinbase is via DuckDB.

The project contains a read-only DuckDB database for validating pinbase data, comparing it against
external sources (OPDB, IPDB, Fandom), and finding gaps.

DuckDB is purely an audit and exploration tool; Pinbase markdown is the source of truth.

## Using it

```bash
make explore                        # rebuild (runs JSON export + SQL layers)
duckdb data/explore/explore.duckdb  # query interactively
```

The database is a build artifact (gitignored). Rebuild whenever pinbase markdown
or source dumps change. The build **fails** if integrity checks don't pass —
query `SELECT * FROM _violations` for details.

## SQL layers

Files in `data/explore/` load in numeric order:

| File               | Purpose                                              |
| ------------------ | ---------------------------------------------------- |
| `01_reference.sql` | Hand-maintained reference tables, macros, exceptions |
| `02_raw.sql`       | Turn pinbase & external JSON into tables             |
| `03_staging.sql`   | Per-source normalization (no cross-source joins)     |
| `04_checks.sql`    | Integrity checks. Hard violations abort the build    |
| `05_compare.sql`   | Cross-source comparison: do sources agree?           |
| `06_gaps.sql`      | Gap analysis: what's missing from pinbase?           |
| `07_quality.sql`   | Slug quality, media audit, backfill proposals        |

## Related scripts

- `scripts/apply_markdown_updates.py` — applies backfills to markdown files
- `scripts/generate_missing_ipdb_data.py` — creates markdown for missing IPDB entities
