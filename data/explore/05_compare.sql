-- 05_compare.sql — Cross-source comparison: do sources agree?
-- Depends on: 02_raw.sql, 03_staging.sql

------------------------------------------------------------
-- Models vs OPDB (by opdb_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_models_opdb AS
SELECT
  m.slug,
  m.name AS pinbase_name,
  o.name AS opdb_name,
  m.name IS DISTINCT FROM o.name AS name_differs,
  m.corporate_entity_slug AS pinbase_corporate_entity,
  ce.manufacturer_slug AS pinbase_manufacturer,
  o.manufacturer_name AS opdb_manufacturer,
  m.year AS pinbase_year,
  year(o.manufacture_date) AS opdb_year,
  m.year IS DISTINCT FROM year(o.manufacture_date) AS year_differs,
  m.technology_generation_slug AS pinbase_tech_gen,
  o.technology_generation_slug AS opdb_tech_gen,
  m.technology_generation_slug IS DISTINCT FROM o.technology_generation_slug AS tech_gen_differs,
  m.display_type_slug AS pinbase_display,
  o.display_type_slug AS opdb_display,
  m.display_type_slug IS DISTINCT FROM o.display_type_slug AS display_differs,
  m.player_count AS pinbase_players,
  o.player_count AS opdb_players,
  m.opdb_id
FROM models AS m
INNER JOIN opdb_machines_staged AS o ON m.opdb_id = o.opdb_id
LEFT JOIN corporate_entities AS ce ON ce.slug = m.corporate_entity_slug;

------------------------------------------------------------
-- Models vs IPDB (by ipdb_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_models_ipdb AS
SELECT
  m.slug,
  m.name AS pinbase_name,
  i.Title AS ipdb_name,
  m.name IS DISTINCT FROM i.Title AS name_differs,
  m.corporate_entity_slug AS pinbase_corporate_entity,
  ce.manufacturer_slug AS pinbase_manufacturer,
  i.ManufacturerShortName AS ipdb_manufacturer,
  m.year AS pinbase_year,
  EXTRACT(YEAR FROM TRY_CAST(i.DateOfManufacture AS DATE))::INTEGER AS ipdb_year,
  m.year IS DISTINCT FROM EXTRACT(YEAR FROM TRY_CAST(i.DateOfManufacture AS DATE))::INTEGER AS year_differs,
  m.technology_generation_slug AS pinbase_tech_gen,
  i.technology_generation_slug AS ipdb_tech_gen,
  m.player_count AS pinbase_players,
  i.Players AS ipdb_players,
  i.AverageFunRating AS ipdb_rating,
  i.ProductionNumber AS ipdb_production,
  m.ipdb_id
FROM models AS m
INNER JOIN ipdb_machines_staged AS i ON m.ipdb_id = i.IpdbId
LEFT JOIN corporate_entities AS ce ON ce.slug = m.corporate_entity_slug;

------------------------------------------------------------
-- Titles vs OPDB groups (by opdb_group_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_titles_opdb AS
SELECT
  t.slug,
  t.name AS pinbase_name,
  g.name AS opdb_name,
  t.name <> g.name AS name_differs,
  t.opdb_group_id
FROM titles AS t
INNER JOIN opdb_groups AS g ON t.opdb_group_id = g.opdb_id;

------------------------------------------------------------
-- IPDB credits missing from Pinbase
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_credits_ipdb AS
SELECT
  m.slug AS model_slug,
  ic.role,
  ic.person_slug,
  ic.person_name AS ipdb_person_name,
  ic.IpdbId
FROM _ipdb_credits ic
JOIN models m ON m.ipdb_id = ic.IpdbId
WHERE ic.person_slug IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM pinbase_credits pc
    WHERE pc.model_slug = m.slug
      AND pc.person_slug = ic.person_slug
      AND pc.role = ic.role
  );
