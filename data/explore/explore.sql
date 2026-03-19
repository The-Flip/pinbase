-- Table and view definitions for data/explore/explore.duckdb
-- Rebuild: scripts/rebuild_explore.sh

.read 'data/explore/01_reference.sql'
.read 'data/explore/02_raw.sql'
.read 'data/explore/03_staging.sql'
.read 'data/explore/04_checks.sql'
.read 'data/explore/05_compare.sql'
.read 'data/explore/06_gaps.sql'
.read 'data/explore/07_quality.sql'
