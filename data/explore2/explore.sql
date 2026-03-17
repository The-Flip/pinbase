-- View definitions for data/explore2/explore2.duckdb
-- Rebuild: scripts/rebuild_explore2.sh

.read 'data/explore2/01_raw.sql'
.read 'data/explore2/02_staging.sql'
.read 'data/explore2/03_checks.sql'
.read 'data/explore2/04_compare.sql'
