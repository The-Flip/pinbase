-- 06_gaps.sql — What's missing? Gap analysis and fandom cross-reference.
-- Depends on: 02_raw.sql, 03_staging.sql

------------------------------------------------------------
-- Missing: IPDB machines not yet in Pinbase
------------------------------------------------------------

CREATE OR REPLACE VIEW missing_models_ipdb AS
SELECT
  i.IpdbId,
  i.Title,
  i.ManufacturerShortName AS ipdb_manufacturer,
  i.ManufacturerId AS ipdb_manufacturer_id,
  i.Type AS ipdb_type,
  i.TypeShortName AS ipdb_type_short,
  EXTRACT(YEAR FROM TRY_CAST(i.DateOfManufacture AS DATE))::INTEGER AS ipdb_year,
  i.Players AS ipdb_players,
  i.ProductionNumber AS ipdb_production,
  i.AverageFunRating AS ipdb_rating,
  i.technology_generation_slug,
  i.system_slug
FROM ipdb_machines_staged AS i
LEFT JOIN models AS m ON m.ipdb_id = i.IpdbId
WHERE m.ipdb_id IS NULL
ORDER BY i.IpdbId;

------------------------------------------------------------
-- Missing: IPDB corporate entities not yet in Pinbase
------------------------------------------------------------

CREATE OR REPLACE VIEW missing_corporate_entities_ipdb AS
SELECT DISTINCT
  i.ManufacturerId AS ipdb_manufacturer_id,
  i.ManufacturerShortName AS ipdb_manufacturer_name,
  i.Manufacturer AS ipdb_manufacturer_full,
  count(*) OVER (PARTITION BY i.ManufacturerId) AS machine_count
FROM ipdb_machines_staged AS i
LEFT JOIN corporate_entities AS ce ON ce.ipdb_manufacturer_id = i.ManufacturerId
WHERE ce.slug IS NULL
  AND i.ManufacturerId IS NOT NULL
  AND i.ManufacturerId != 0
  AND i.Manufacturer IS NOT NULL
  AND i.Manufacturer != 'Unknown Manufacturer'
ORDER BY machine_count DESC, i.ManufacturerId;

------------------------------------------------------------
-- Missing: IPDB manufacturers (brands) not yet in Pinbase
------------------------------------------------------------

CREATE OR REPLACE VIEW missing_manufacturers_ipdb AS
SELECT DISTINCT
  ce.manufacturer_slug,
  ce.slug AS corporate_entity_slug,
  ce.name AS corporate_entity_name
FROM corporate_entities AS ce
LEFT JOIN manufacturers AS mfr ON mfr.slug = ce.manufacturer_slug
WHERE mfr.slug IS NULL
  AND ce.ipdb_manufacturer_id IS NOT NULL
ORDER BY ce.manufacturer_slug;

------------------------------------------------------------
-- Missing: IPDB credited people not yet in Pinbase
------------------------------------------------------------

CREATE OR REPLACE VIEW missing_people_ipdb AS
SELECT
  person_name,
  list(DISTINCT role ORDER BY role) AS roles,
  count(DISTINCT IpdbId) AS machine_count,
  list(DISTINCT IpdbId ORDER BY IpdbId)[:5] AS sample_ipdb_ids
FROM _ipdb_credits
WHERE person_slug IS NULL
GROUP BY person_name
ORDER BY machine_count DESC, person_name;

------------------------------------------------------------
-- Fandom cross-reference: people
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_people_fandom AS
WITH
  alias_map AS (
    SELECT unnest(aliases) AS alias_name, slug, name AS canonical_name
    FROM people
    WHERE aliases IS NOT NULL
  ),
  matched AS (
    SELECT
      fp.page_id AS fandom_page_id,
      fp.title AS fandom_name,
      fp.wikitext AS fandom_wikitext,
      COALESCE(p.slug, am.slug) AS person_slug,
      COALESCE(p.name, am.canonical_name) AS pinbase_name,
      CASE
        WHEN p.slug IS NOT NULL THEN 'name'
        WHEN am.slug IS NOT NULL THEN 'alias'
        ELSE NULL
      END AS match_method
    FROM fandom_persons AS fp
    LEFT JOIN people AS p ON lower(fp.title) = lower(p.name)
    LEFT JOIN alias_map AS am ON p.slug IS NULL AND lower(fp.title) = lower(am.alias_name)
  )
SELECT * FROM matched
ORDER BY match_method NULLS LAST, fandom_name;

CREATE OR REPLACE VIEW missing_people_fandom AS
SELECT fandom_page_id, fandom_name, fandom_wikitext
FROM compare_people_fandom
WHERE match_method IS NULL
ORDER BY fandom_name;

------------------------------------------------------------
-- Fandom cross-reference: manufacturers
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_manufacturers_fandom AS
SELECT
  fm.page_id AS fandom_page_id,
  fm.title AS fandom_name,
  fm.wikitext AS fandom_wikitext,
  COALESCE(m_exact.slug, m_norm.slug, ce.manufacturer_slug) AS manufacturer_slug,
  COALESCE(m_exact.name, m_norm.name, m_ce.name) AS pinbase_name,
  CASE
    WHEN m_exact.slug IS NOT NULL THEN 'name'
    WHEN m_norm.slug IS NOT NULL THEN 'normalized'
    WHEN ce.manufacturer_slug IS NOT NULL THEN 'corporate_entity'
    ELSE NULL
  END AS match_method
FROM fandom_manufacturers AS fm
LEFT JOIN manufacturers AS m_exact
  ON lower(fm.title) = lower(m_exact.name)
LEFT JOIN (
  SELECT slug, name, normalize_mfr_name(name) AS norm_name
  FROM manufacturers
  WHERE normalize_mfr_name(name) != ''
  QUALIFY count(*) OVER (PARTITION BY normalize_mfr_name(name)) = 1
) AS m_norm
  ON m_norm.norm_name = normalize_mfr_name(fm.title)
  AND m_exact.slug IS NULL
LEFT JOIN (
  SELECT slug, name, manufacturer_slug, normalize_mfr_name(name) AS norm_name
  FROM corporate_entities
  WHERE normalize_mfr_name(name) != ''
  QUALIFY count(*) OVER (PARTITION BY normalize_mfr_name(name)) = 1
) AS ce
  ON ce.norm_name = normalize_mfr_name(fm.title)
  AND m_exact.slug IS NULL AND m_norm.slug IS NULL
LEFT JOIN manufacturers AS m_ce
  ON m_ce.slug = ce.manufacturer_slug
ORDER BY match_method NULLS LAST, fm.title;

CREATE OR REPLACE VIEW missing_manufacturers_fandom AS
SELECT fandom_page_id, fandom_name, fandom_wikitext
FROM compare_manufacturers_fandom
WHERE match_method IS NULL
ORDER BY fandom_name;

------------------------------------------------------------
-- Fandom cross-reference: games
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_games_fandom AS
WITH
  name_matches AS (
    SELECT
      fg.page_id AS fandom_page_id,
      fg.fandom_name,
      fg.manufacturer AS fandom_manufacturer,
      fg.year AS fandom_year,
      fg.production AS fandom_production,
      fg.wikitext AS fandom_wikitext,
      t.slug AS title_slug,
      t.name AS pinbase_name
    FROM fandom_games_staged AS fg
    LEFT JOIN titles AS t ON lower(fg.fandom_name) = lower(t.name)
  ),
  title_mfr_counts AS (
    SELECT
      m.title_slug,
      mfr.name AS manufacturer_name,
      count(*) AS model_count
    FROM models AS m
    JOIN corporate_entities AS ce ON ce.slug = m.corporate_entity_slug
    JOIN manufacturers AS mfr ON mfr.slug = ce.manufacturer_slug
    WHERE m.corporate_entity_slug IS NOT NULL
    GROUP BY m.title_slug, mfr.name
  ),
  title_manufacturers AS (
    SELECT title_slug, manufacturer_name
    FROM title_mfr_counts
    QUALIFY row_number() OVER (PARTITION BY title_slug ORDER BY model_count DESC) = 1
  ),
  scored AS (
    SELECT
      nm.*,
      tm.manufacturer_name AS pinbase_manufacturer,
      (lower(nm.fandom_manufacturer) = lower(tm.manufacturer_name)
        OR normalize_mfr_name(nm.fandom_manufacturer) = normalize_mfr_name(tm.manufacturer_name)
      ) AS manufacturer_matches,
      count(*) OVER (PARTITION BY nm.fandom_page_id) AS candidate_count
    FROM name_matches AS nm
    LEFT JOIN title_manufacturers AS tm ON nm.title_slug = tm.title_slug
  )
SELECT
  fandom_page_id,
  fandom_name,
  fandom_manufacturer,
  fandom_year,
  fandom_production,
  fandom_wikitext,
  title_slug,
  pinbase_name,
  pinbase_manufacturer,
  CASE
    WHEN title_slug IS NULL THEN NULL
    WHEN candidate_count = 1 THEN 'name'
    WHEN manufacturer_matches THEN 'name+manufacturer'
    ELSE 'ambiguous'
  END AS match_method
FROM scored
ORDER BY match_method NULLS LAST, fandom_name;

CREATE OR REPLACE VIEW missing_games_fandom AS
SELECT fandom_page_id, fandom_name, fandom_manufacturer, fandom_year, fandom_wikitext
FROM compare_games_fandom
WHERE match_method IS NULL
ORDER BY fandom_name;
