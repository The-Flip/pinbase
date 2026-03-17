-- 04_checks.sql — Integrity checks on pinbase data.
-- Depends on: 01_raw.sql, 02_staging.sql
-- Aborts with non-zero exit code if any hard violations are found.

CREATE TEMP TABLE IF NOT EXISTS _violations (check_name VARCHAR, detail VARCHAR);
CREATE TEMP TABLE IF NOT EXISTS _warnings (check_name VARCHAR, cnt BIGINT);

------------------------------------------------------------
-- Hard failures (structural integrity)
------------------------------------------------------------

-- Duplicate slugs
INSERT INTO _violations
SELECT 'duplicate_model_slug', slug
FROM models GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_title_slug', slug
FROM titles GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_manufacturer_slug', slug
FROM manufacturers GROUP BY slug HAVING count(*) > 1;

-- Duplicate external IDs
INSERT INTO _violations
SELECT 'duplicate_model_opdb_id', opdb_id
FROM models WHERE opdb_id IS NOT NULL
GROUP BY opdb_id HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_model_ipdb_id', CAST(ipdb_id AS VARCHAR)
FROM models WHERE ipdb_id IS NOT NULL
GROUP BY ipdb_id HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'duplicate_title_opdb_group_id', opdb_group_id
FROM titles WHERE opdb_group_id IS NOT NULL
GROUP BY opdb_group_id HAVING count(*) > 1;

-- Orphan references: model -> title
INSERT INTO _violations
SELECT 'orphan_model_title', m.slug || ' -> ' || m.title_slug
FROM models AS m
WHERE m.title_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM titles AS t WHERE t.slug = m.title_slug);

-- Orphan references: title -> franchise
INSERT INTO _violations
SELECT 'orphan_title_franchise', t.slug || ' -> ' || t.franchise_slug
FROM titles AS t
WHERE t.franchise_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM franchises AS f WHERE f.slug = t.franchise_slug);

-- Orphan references: title -> series
INSERT INTO _violations
SELECT 'orphan_title_series', t.slug || ' -> ' || t.series_slug
FROM titles AS t
WHERE t.series_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM series AS s WHERE s.slug = t.series_slug);

-- Orphan references: model -> manufacturer
INSERT INTO _violations
SELECT 'orphan_model_manufacturer', m.slug || ' -> ' || m.manufacturer_slug
FROM models AS m
WHERE m.manufacturer_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM manufacturers AS mfr WHERE mfr.slug = m.manufacturer_slug);

-- Orphan references: model -> system
INSERT INTO _violations
SELECT 'orphan_model_system', m.slug || ' -> ' || m.system_slug
FROM models AS m
WHERE m.system_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM systems AS s WHERE s.slug = m.system_slug);

-- Orphan references: variant_of -> model
INSERT INTO _violations
SELECT 'orphan_variant_of', m.slug || ' -> ' || m.variant_of
FROM models AS m
WHERE m.variant_of IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.variant_of);

-- Orphan references: converted_from -> model
INSERT INTO _violations
SELECT 'orphan_converted_from', m.slug || ' -> ' || m.converted_from
FROM models AS m
WHERE m.converted_from IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.converted_from);

-- Orphan references: remake_of -> model
INSERT INTO _violations
SELECT 'orphan_remake_of', m.slug || ' -> ' || m.remake_of
FROM models AS m
WHERE m.remake_of IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.remake_of);

-- Self-referential variant_of
INSERT INTO _violations
SELECT 'self_variant_of', slug
FROM models WHERE variant_of = slug;

-- Chained variant_of (A -> B where B also has variant_of)
INSERT INTO _violations
SELECT 'chained_variant_of', a.slug || ' -> ' || a.variant_of || ' -> ' || b.variant_of
FROM models AS a
JOIN models AS b ON a.variant_of = b.slug
WHERE b.variant_of IS NOT NULL;

-- Pinbase model references a non-physical OPDB record (physical_machine=0)
INSERT INTO _violations
SELECT 'non_physical_opdb_ref', m.slug || ' (' || m.opdb_id || ')'
FROM models AS m
JOIN opdb_machines AS om ON m.opdb_id = om.opdb_id
WHERE om.physical_machine = 0;

-- Source dump integrity: every OPDB record must have an opdb_id
INSERT INTO _violations
SELECT 'opdb_record_missing_id', name
FROM opdb_machines WHERE opdb_id IS NULL;

-- Source dump integrity: every IPDB record must have an IpdbId
INSERT INTO _violations
SELECT 'ipdb_record_missing_id', Title
FROM ipdb_machines WHERE IpdbId IS NULL;

------------------------------------------------------------
-- Soft warnings (data quality)
------------------------------------------------------------

-- Pinbase references external IDs not in our (possibly stale) dumps
INSERT INTO _warnings
SELECT 'pinbase_opdb_id_not_in_dump', count(*)
FROM models AS m
WHERE m.opdb_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM opdb_machines AS o WHERE o.opdb_id = m.opdb_id);

INSERT INTO _warnings
SELECT 'pinbase_ipdb_id_not_in_dump', count(*)
FROM models AS m
WHERE m.ipdb_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM ipdb_machines AS i WHERE i.IpdbId = m.ipdb_id);

INSERT INTO _warnings
SELECT 'models_missing_manufacturer', count(*)
FROM models WHERE manufacturer_slug IS NULL;

INSERT INTO _warnings
SELECT 'models_missing_title', count(*)
FROM models WHERE title_slug IS NULL;

INSERT INTO _warnings
SELECT 'titles_missing_opdb_group', count(*)
FROM titles WHERE opdb_group_id IS NULL;

INSERT INTO _warnings
SELECT 'conversion_without_source', count(*)
FROM models WHERE is_conversion AND converted_from IS NULL;

------------------------------------------------------------
-- Report
------------------------------------------------------------

SELECT 'WARNING: ' || check_name || ' (' || cnt || ' rows)'
FROM _warnings WHERE cnt > 0;

SELECT CASE
  WHEN count(*) > 0
  THEN error(count(*) || ' contract violation(s) found. Run: SELECT * FROM _violations')
  ELSE 'All checks passed'
END FROM _violations;
