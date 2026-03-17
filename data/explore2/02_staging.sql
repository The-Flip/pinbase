-- 02_staging.sql — Per-source transforms.
-- Makes each source independently queryable with normalized slugs.
-- No cross-source joins.
-- Depends on: 01_raw.sql

------------------------------------------------------------
-- Reference lookup tables (static mappings)
------------------------------------------------------------

-- OPDB type code -> technology generation slug
CREATE OR REPLACE VIEW ref_opdb_technology_generation AS
SELECT * FROM (VALUES
  ('em', 'electromechanical'),
  ('ss', 'solid-state'),
  ('me', 'pure-mechanical')
) AS t(opdb_type, slug);

-- OPDB display code -> display type slug
CREATE OR REPLACE VIEW ref_opdb_display_type AS
SELECT * FROM (VALUES
  ('reels',        'score-reels'),
  ('lights',       'backglass-lights'),
  ('alphanumeric', 'alphanumeric'),
  ('cga',          'cga'),
  ('dmd',          'dot-matrix'),
  ('lcd',          'lcd')
) AS t(opdb_display, slug);

-- IPDB TypeShortName/Type -> technology generation slug
CREATE OR REPLACE VIEW ref_ipdb_technology_generation AS
SELECT * FROM (VALUES
  ('EM', NULL,                    'electromechanical'),
  ('SS', NULL,                    'solid-state'),
  (NULL, 'Pure Mechanical (PM)',  'pure-mechanical')
) AS t(type_short_name, type_full, slug);

------------------------------------------------------------
-- OPDB staged
------------------------------------------------------------

-- Add technology/display slugs and extract manufacturer name
CREATE OR REPLACE VIEW opdb_machines_staged AS
SELECT
  om.*,
  (om.manufacturer ->> 'name') AS manufacturer_name,
  tg.slug AS technology_generation_slug,
  dt.slug AS display_type_slug
FROM opdb_machines AS om
LEFT JOIN ref_opdb_technology_generation AS tg ON om."type" = tg.opdb_type
LEFT JOIN ref_opdb_display_type AS dt ON om.display = dt.opdb_display;

-- Distinct manufacturers from OPDB
CREATE OR REPLACE VIEW opdb_manufacturers AS
SELECT DISTINCT
  om.manufacturer.manufacturer_id AS opdb_manufacturer_id,
  (om.manufacturer ->> 'name') AS "name",
  (om.manufacturer ->> 'full_name') AS full_name
FROM opdb_machines AS om
WHERE om.manufacturer IS NOT NULL
ORDER BY "name";

-- Unnested keywords per machine
CREATE OR REPLACE VIEW opdb_keywords AS
SELECT opdb_id, "name", unnest(keywords) AS keyword
FROM opdb_machines
WHERE len(keywords) > 0;

------------------------------------------------------------
-- IPDB staged
------------------------------------------------------------

-- Add technology generation slug and system/subgeneration via MPU match
CREATE OR REPLACE VIEW ipdb_machines_staged AS
SELECT
  im.*,
  COALESCE(tg1.slug, tg2.slug) AS technology_generation_slug,
  ps.slug AS system_slug,
  ps.technology_subgeneration_slug
FROM ipdb_machines AS im
LEFT JOIN ref_ipdb_technology_generation AS tg1
  ON im.TypeShortName = tg1.type_short_name AND tg1.type_short_name IS NOT NULL
LEFT JOIN ref_ipdb_technology_generation AS tg2
  ON im."Type" = tg2.type_full AND tg2.type_full IS NOT NULL
LEFT JOIN systems AS ps
  ON list_contains(ps.mpu_strings, im.MPU);

-- Distinct manufacturers from IPDB
CREATE OR REPLACE VIEW ipdb_manufacturers AS
SELECT DISTINCT
  ManufacturerId AS ipdb_manufacturer_id,
  Manufacturer AS "name",
  ManufacturerShortName AS short_name
FROM ipdb_machines
WHERE Manufacturer IS NOT NULL
ORDER BY "name";

------------------------------------------------------------
-- Pinbase staged
------------------------------------------------------------

-- Flat credits: one row per model + person + role
CREATE OR REPLACE VIEW pinbase_credits AS
SELECT
  m.slug AS model_slug,
  m.title_slug,
  unnest(m.credit_refs).person_slug AS person_slug,
  unnest(m.credit_refs)."role" AS "role"
FROM models AS m
WHERE m.credit_refs IS NOT NULL AND len(m.credit_refs) > 0;
