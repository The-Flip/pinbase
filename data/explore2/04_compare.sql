-- 04_compare.sql — Cross-source comparison views, gap analysis, and slug quality.
-- Depends on: 01_raw.sql, 02_staging.sql

------------------------------------------------------------
-- Cross-source: models vs OPDB (by opdb_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_models_opdb AS
SELECT
  m.slug,
  m.name AS pinbase_name,
  o.name AS opdb_name,
  m.name <> o.name AS name_differs,
  m.corporate_entity_slug AS pinbase_corporate_entity,
  ce.manufacturer_slug AS pinbase_manufacturer,
  o.manufacturer_name AS opdb_manufacturer,
  m.year AS pinbase_year,
  year(o.manufacture_date) AS opdb_year,
  m.year <> year(o.manufacture_date) AS year_differs,
  m.technology_generation_slug AS pinbase_tech_gen,
  o.technology_generation_slug AS opdb_tech_gen,
  m.technology_generation_slug <> o.technology_generation_slug AS tech_gen_differs,
  m.display_type_slug AS pinbase_display,
  o.display_type_slug AS opdb_display,
  m.display_type_slug <> o.display_type_slug AS display_differs,
  m.player_count AS pinbase_players,
  o.player_count AS opdb_players,
  m.opdb_id
FROM models AS m
INNER JOIN opdb_machines_staged AS o ON m.opdb_id = o.opdb_id
LEFT JOIN corporate_entities AS ce ON ce.slug = m.corporate_entity_slug;

------------------------------------------------------------
-- Cross-source: models vs IPDB (by ipdb_id)
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_models_ipdb AS
SELECT
  m.slug,
  m.name AS pinbase_name,
  i.Title AS ipdb_name,
  m.name <> i.Title AS name_differs,
  m.corporate_entity_slug AS pinbase_corporate_entity,
  ce.manufacturer_slug AS pinbase_manufacturer,
  i.ManufacturerShortName AS ipdb_manufacturer,
  m.year AS pinbase_year,
  TRY_CAST(i.DateOfManufacture AS INTEGER) AS ipdb_year,
  m.year <> TRY_CAST(i.DateOfManufacture AS INTEGER) AS year_differs,
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
-- Cross-source: titles vs OPDB groups (by opdb_group_id)
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
-- Cross-source: IPDB credits missing from Pinbase
-- Maps IPDB credit fields to pinbase person slugs via name/alias lookup,
-- then finds credits that exist in IPDB but not in Pinbase.
------------------------------------------------------------

CREATE OR REPLACE VIEW compare_credits_ipdb AS
WITH
-- Build a name→slug lookup from people + aliases
person_lookup AS (
  SELECT slug, LOWER(name) AS lookup_name FROM people
  UNION ALL
  SELECT slug, LOWER(UNNEST(aliases)) FROM people WHERE aliases IS NOT NULL
),
-- Flatten IPDB credit fields into (IpdbId, role, person_name) rows
ipdb_credits_raw AS (
  SELECT IpdbId, 'Design' AS role, TRIM(UNNEST(string_split(DesignBy, ','))) AS person_name FROM ipdb_machines WHERE DesignBy <> ''
  UNION ALL
  SELECT IpdbId, 'Art', TRIM(UNNEST(string_split(ArtBy, ','))) FROM ipdb_machines WHERE ArtBy <> ''
  UNION ALL
  SELECT IpdbId, 'Dots/Animation', TRIM(UNNEST(string_split(DotsAnimationBy, ','))) FROM ipdb_machines WHERE DotsAnimationBy <> ''
  UNION ALL
  SELECT IpdbId, 'Mechanics', TRIM(UNNEST(string_split(MechanicsBy, ','))) FROM ipdb_machines WHERE MechanicsBy <> ''
  UNION ALL
  SELECT IpdbId, 'Music', TRIM(UNNEST(string_split(MusicBy, ','))) FROM ipdb_machines WHERE MusicBy <> ''
  UNION ALL
  SELECT IpdbId, 'Sound', TRIM(UNNEST(string_split(SoundBy, ','))) FROM ipdb_machines WHERE SoundBy <> ''
  UNION ALL
  SELECT IpdbId, 'Software', TRIM(UNNEST(string_split(SoftwareBy, ','))) FROM ipdb_machines WHERE SoftwareBy <> ''
),
-- Filter out placeholder/sentinel names
ipdb_credits_filtered AS (
  SELECT * FROM ipdb_credits_raw
  WHERE LOWER(person_name) NOT IN (
    '(undisclosed)', 'undisclosed', 'unknown', 'missing', 'null', 'undefined',
    'n/a', 'none', 'tbd', 'tba', '?', ''
  )
    AND person_name NOT ILIKE '%(undisclosed)%'
    AND person_name NOT ILIKE '%unknown%'
),
-- Resolve person names to slugs
ipdb_credits AS (
  SELECT
    ic.IpdbId,
    ic.role,
    ic.person_name AS ipdb_person_name,
    pl.slug AS person_slug
  FROM ipdb_credits_filtered ic
  LEFT JOIN person_lookup pl ON LOWER(ic.person_name) = pl.lookup_name
)
SELECT
  m.slug AS model_slug,
  ic.role,
  ic.person_slug,
  ic.ipdb_person_name,
  ic.IpdbId
FROM ipdb_credits ic
JOIN models m ON m.ipdb_id = ic.IpdbId
WHERE ic.person_slug IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM pinbase_credits pc
    WHERE pc.model_slug = m.slug
      AND pc.person_slug = ic.person_slug
      AND pc.role = ic.role
  );

------------------------------------------------------------
-- Slug quality: name faithfulness
-- Compares each model's slug to a mechanical slugification of its name.
-- Large edit distance or missing words signal a slug that doesn't
-- represent the name well.
------------------------------------------------------------

CREATE OR REPLACE VIEW slug_name_faithfulness AS
WITH slugified AS (
  SELECT
    slug,
    name,
    title_slug,
    -- Mechanical slug: lowercase, spaces to hyphens, strip non-alphanumeric
    regexp_replace(
      lower(replace(name, ' ', '-')),
      '[^a-z0-9\-]', '', 'g'
    ) AS name_as_slug
  FROM models
)
SELECT
  *,
  slug <> name_as_slug AS slug_differs_from_name,
  length(slug) - length(name_as_slug) AS slug_length_delta
FROM slugified
WHERE slug <> name_as_slug;

------------------------------------------------------------
-- Slug quality: prime slug conflicts
-- Finds cases where a model's slug matches another title's slug,
-- suggesting the "obvious" slug was taken by a different title group.
-- Ranks by IPDB production count and rating so you can see when
-- an obscure model holds the prime slug over a popular one.
------------------------------------------------------------

CREATE OR REPLACE VIEW slug_prime_conflicts AS
WITH
  -- Models whose slug differs from their title_slug: they didn't get the "home" slug
  displaced AS (
    SELECT
      m.slug AS model_slug,
      m.name AS model_name,
      m.title_slug,
      m.ipdb_id,
      m.corporate_entity_slug,
      m.year
    FROM models AS m
    WHERE m.slug <> m.title_slug
      AND m.title_slug IS NOT NULL
  ),
  -- The model that holds the title's "prime" slug (slug = title_slug)
  prime_holders AS (
    SELECT
      m.slug AS model_slug,
      m.name AS model_name,
      m.title_slug,
      m.ipdb_id,
      m.corporate_entity_slug,
      m.year
    FROM models AS m
    WHERE m.slug = m.title_slug
  )
SELECT
  d.title_slug,
  -- The displaced (potentially popular) model
  d.model_slug AS displaced_slug,
  d.model_name AS displaced_name,
  d.corporate_entity_slug AS displaced_corporate_entity,
  d.year AS displaced_year,
  di.ProductionNumber AS displaced_production,
  di.AverageFunRating AS displaced_rating,
  -- The model holding the prime slug
  p.model_slug AS prime_slug,
  p.model_name AS prime_name,
  p.corporate_entity_slug AS prime_corporate_entity,
  p.year AS prime_year,
  pi.ProductionNumber AS prime_production,
  pi.AverageFunRating AS prime_rating
FROM displaced AS d
LEFT JOIN prime_holders AS p ON d.title_slug = p.title_slug
LEFT JOIN ipdb_machines AS di ON d.ipdb_id = di.IpdbId
LEFT JOIN ipdb_machines AS pi ON p.ipdb_id = pi.IpdbId
WHERE p.model_slug IS NOT NULL
ORDER BY COALESCE(di.ProductionNumber, 0) DESC;

------------------------------------------------------------
-- Missing: IPDB machines not yet in Pinbase
-- Anti-join on ipdb_id to find machines we haven't imported.
------------------------------------------------------------

CREATE OR REPLACE VIEW missing_models_ipdb AS
SELECT
  i.IpdbId,
  i.Title,
  i.ManufacturerShortName AS ipdb_manufacturer,
  i.ManufacturerId AS ipdb_manufacturer_id,
  i.Type AS ipdb_type,
  i.TypeShortName AS ipdb_type_short,
  TRY_CAST(i.DateOfManufacture AS INTEGER) AS ipdb_year,
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
-- Distinct ManufacturerId values with no matching corporate entity.
-- IPDB's ManufacturerId maps to our corporate_entities (not manufacturers),
-- since one manufacturer brand can have multiple corporate entities.
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
-- Corporate entities that DO exist but whose manufacturer_slug
-- doesn't match any row in manufacturers.
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
-- Flattens all IPDB credit fields, resolves against people + aliases,
-- and returns names that don't match any known person.
------------------------------------------------------------

CREATE OR REPLACE VIEW missing_people_ipdb AS
WITH
person_lookup AS (
  SELECT slug, LOWER(name) AS lookup_name FROM people
  UNION ALL
  SELECT slug, LOWER(UNNEST(aliases)) FROM people WHERE aliases IS NOT NULL
),
ipdb_credits_raw AS (
  SELECT IpdbId, 'Design' AS role, TRIM(UNNEST(string_split(DesignBy, ','))) AS person_name FROM ipdb_machines WHERE DesignBy <> ''
  UNION ALL
  SELECT IpdbId, 'Art', TRIM(UNNEST(string_split(ArtBy, ','))) FROM ipdb_machines WHERE ArtBy <> ''
  UNION ALL
  SELECT IpdbId, 'Dots/Animation', TRIM(UNNEST(string_split(DotsAnimationBy, ','))) FROM ipdb_machines WHERE DotsAnimationBy <> ''
  UNION ALL
  SELECT IpdbId, 'Mechanics', TRIM(UNNEST(string_split(MechanicsBy, ','))) FROM ipdb_machines WHERE MechanicsBy <> ''
  UNION ALL
  SELECT IpdbId, 'Music', TRIM(UNNEST(string_split(MusicBy, ','))) FROM ipdb_machines WHERE MusicBy <> ''
  UNION ALL
  SELECT IpdbId, 'Sound', TRIM(UNNEST(string_split(SoundBy, ','))) FROM ipdb_machines WHERE SoundBy <> ''
  UNION ALL
  SELECT IpdbId, 'Software', TRIM(UNNEST(string_split(SoftwareBy, ','))) FROM ipdb_machines WHERE SoftwareBy <> ''
),
ipdb_credits_filtered AS (
  SELECT * FROM ipdb_credits_raw
  WHERE LOWER(person_name) NOT IN (
    '(undisclosed)', 'undisclosed', 'unknown', 'missing', 'null', 'undefined',
    'n/a', 'none', 'tbd', 'tba', '?', ''
  )
    AND person_name NOT ILIKE '%(undisclosed)%'
    AND person_name NOT ILIKE '%unknown%'
),
unresolved AS (
  SELECT
    ic.person_name,
    ic.role,
    ic.IpdbId
  FROM ipdb_credits_filtered ic
  LEFT JOIN person_lookup pl ON LOWER(ic.person_name) = pl.lookup_name
  WHERE pl.slug IS NULL
)
SELECT
  person_name,
  list(DISTINCT role ORDER BY role) AS roles,
  count(DISTINCT IpdbId) AS machine_count,
  list(DISTINCT IpdbId ORDER BY IpdbId)[:5] AS sample_ipdb_ids
FROM unresolved
GROUP BY person_name
ORDER BY machine_count DESC, person_name;

------------------------------------------------------------
-- File/media views — content auditing
------------------------------------------------------------

-- OPDB machine images: flattened from the nested images array
CREATE OR REPLACE VIEW opdb_machine_images AS
SELECT
  om.opdb_id,
  om.name AS machine_name,
  img.title AS image_title,
  img."primary" AS is_primary,
  img."type" AS image_type,
  img.urls.small AS url_small,
  img.urls.medium AS url_medium,
  img.urls."large" AS url_large,
  img.sizes.small.width AS small_width,
  img.sizes.small.height AS small_height,
  img.sizes.medium.width AS medium_width,
  img.sizes.medium.height AS medium_height,
  img.sizes."large".width AS large_width,
  img.sizes."large".height AS large_height
FROM opdb_machines AS om, unnest(om.images) AS t(img)
WHERE len(om.images) > 0;

-- IPDB machine files: all file types flattened into a single view
CREATE OR REPLACE VIEW ipdb_machine_files AS
SELECT
  IpdbId AS ipdb_id,
  Title AS machine_name,
  f.Url AS file_url,
  f."Name" AS file_name,
  category
FROM ipdb_machines, (
  SELECT unnest(ImageFiles) AS f, 'image' AS category
  UNION ALL SELECT unnest(Documentation), 'documentation'
  UNION ALL SELECT unnest(Files), 'file'
  UNION ALL SELECT unnest(RuleSheetUrls), 'rule_sheet'
  UNION ALL SELECT unnest(ROMs), 'rom'
  UNION ALL SELECT unnest(ServiceBulletins), 'service_bulletin'
  UNION ALL SELECT unnest(MultimediaFiles), 'multimedia'
);

-- Combined file/media view across both sources, keyed to pinbase models
CREATE OR REPLACE VIEW model_files AS
(SELECT
  m.slug AS model_slug,
  m.opdb_id,
  m.ipdb_id,
  'image' AS category,
  oi.image_type,
  oi.is_primary,
  oi.image_title AS file_name,
  CAST(NULL AS VARCHAR) AS file_url,
  oi.url_small,
  oi.url_medium,
  oi.url_large,
  'opdb' AS "source"
FROM opdb_machine_images AS oi
INNER JOIN models AS m ON oi.opdb_id = m.opdb_id)
UNION ALL
(SELECT
  m.slug AS model_slug,
  m.opdb_id,
  m.ipdb_id,
  imf.category,
  CAST(NULL AS VARCHAR) AS image_type,
  CAST(NULL AS BOOLEAN) AS is_primary,
  imf.file_name,
  imf.file_url,
  CAST(NULL AS VARCHAR) AS url_small,
  CAST(NULL AS VARCHAR) AS url_medium,
  CAST(NULL AS VARCHAR) AS url_large,
  'ipdb' AS "source"
FROM ipdb_machine_files AS imf
INNER JOIN models AS m ON imf.ipdb_id = m.ipdb_id);

-- Media coverage summary per model
CREATE OR REPLACE VIEW model_files_summary AS
SELECT
  model_slug,
  count(*) FILTER (WHERE source = 'opdb') AS opdb_file_count,
  count(*) FILTER (WHERE source = 'ipdb') AS ipdb_file_count,
  count(*) FILTER (WHERE category = 'image') AS image_count,
  count(*) FILTER (WHERE category = 'documentation') AS doc_count,
  count(*) FILTER (WHERE category = 'rom') AS rom_count,
  count(*) FILTER (WHERE category = 'rule_sheet') AS rule_sheet_count,
  count(*) FILTER (WHERE category = 'service_bulletin') AS service_bulletin_count,
  count(*) FILTER (WHERE category = 'multimedia') AS multimedia_count
FROM model_files
GROUP BY model_slug;

------------------------------------------------------------
-- Theme cross-reference
------------------------------------------------------------

-- OPDB feature → pinbase tag slug mapping
CREATE OR REPLACE VIEW ref_feature_tag AS
SELECT * FROM (VALUES
  ('Home model',      'home-use'),
  ('Widebody',        'widebody'),
  ('Remake',          'remake'),
  ('Conversion kit',  'conversion-kit'),
  ('Export edition',  'export')
) AS t(feature, tag_slug);

-- OPDB features mapped to pinbase tags, per model
CREATE OR REPLACE VIEW compare_tags_opdb AS
SELECT
  m.slug AS model_slug,
  m.opdb_id,
  rft.tag_slug,
  tg.name AS tag_name,
  rft.feature AS opdb_feature
FROM opdb_machines AS om, unnest(om.features) AS t(f)
INNER JOIN ref_feature_tag AS rft ON f = rft.feature
INNER JOIN models AS m ON om.opdb_id = m.opdb_id
LEFT JOIN tags AS tg ON rft.tag_slug = tg.slug;

-- OPDB features with no corresponding pinbase tag
CREATE OR REPLACE VIEW missing_tags_opdb AS
SELECT
  f AS opdb_feature,
  count(DISTINCT om.opdb_id) AS machine_count
FROM opdb_machines AS om, unnest(om.features) AS t(f)
WHERE NOT EXISTS (SELECT 1 FROM ref_feature_tag AS rft WHERE rft.feature = f)
GROUP BY f
ORDER BY machine_count DESC;

-- Cross-source theme view: IPDB themes + OPDB keywords
CREATE OR REPLACE VIEW compare_themes AS
WITH
  ipdb_themes AS (
    SELECT DISTINCT Theme AS name
    FROM ipdb_machines
    WHERE Theme IS NOT NULL AND Theme <> ''
  ),
  opdb_kw AS (
    SELECT DISTINCT unnest(keywords) AS name
    FROM opdb_machines
    WHERE len(keywords) > 0
  ),
  all_sources AS (
    (SELECT name, true AS in_ipdb, false AS in_opdb FROM ipdb_themes)
    UNION ALL
    (SELECT name, false AS in_ipdb, true AS in_opdb FROM opdb_kw)
  ),
  merged AS (
    SELECT name, bool_or(in_ipdb) AS in_ipdb, bool_or(in_opdb) AS in_opdb
    FROM all_sources
    GROUP BY name
  )
SELECT
  m.*,
  th.slug AS pinbase_slug,
  (th.slug IS NOT NULL) AS in_pinbase
FROM merged AS m
LEFT JOIN themes AS th ON lower(m.name) = lower(th.name);

-- Themes/keywords in external sources but not yet in pinbase
CREATE OR REPLACE VIEW missing_themes AS
SELECT name, in_ipdb, in_opdb
FROM compare_themes
WHERE NOT in_pinbase
ORDER BY name;

------------------------------------------------------------
-- Fandom cross-reference
------------------------------------------------------------

-- People: fandom wiki linkage via name/alias resolution
CREATE OR REPLACE VIEW compare_people_fandom AS
WITH
  alias_map AS (
    SELECT unnest(aliases) AS alias_name, slug, name AS canonical_name
    FROM people
    WHERE aliases IS NOT NULL
  ),
  -- Match fandom persons to pinbase people by canonical name or alias
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

-- Fandom persons not matched to any pinbase person
CREATE OR REPLACE VIEW missing_people_fandom AS
SELECT fandom_page_id, fandom_name, fandom_wikitext
FROM compare_people_fandom
WHERE match_method IS NULL
ORDER BY fandom_name;

-- Manufacturers: fandom wiki linkage
-- Matches by exact name, then normalized name, then corporate entity name.
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

-- Fandom manufacturers not matched to any pinbase manufacturer
CREATE OR REPLACE VIEW missing_manufacturers_fandom AS
SELECT fandom_page_id, fandom_name, fandom_wikitext
FROM compare_manufacturers_fandom
WHERE match_method IS NULL
ORDER BY fandom_name;

-- Games: fandom wiki linkage to pinbase titles.
-- When multiple titles share a name, disambiguates by matching the fandom
-- page's manufacturer against the title's models' manufacturer.
CREATE OR REPLACE VIEW compare_games_fandom AS
WITH
  -- All name-based matches (may be 1:many for same-name titles)
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
  -- For each title, find its primary manufacturer (most common across models)
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
  -- Score each match: manufacturer agreement is the tiebreaker
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
-- When ambiguous, only keep the manufacturer-confirmed match
WHERE candidate_count = 1
   OR manufacturer_matches
   OR title_slug IS NULL
ORDER BY match_method NULLS LAST, fandom_name;

------------------------------------------------------------
-- Proposed backfill: corporate_entity_slug on models
-- Models missing CE where an external source has manufacturer data.
-- Resolution priority: IPDB CE match > variant parent > OPDB mfr ID > OPDB mfr name (most-used CE)
------------------------------------------------------------

CREATE OR REPLACE VIEW proposed_ce_backfill AS
WITH target_models AS (
  SELECT DISTINCT m.slug, m.name, m.ipdb_id, m.opdb_id, m.variant_of
  FROM models m
  LEFT JOIN ipdb_machines i ON m.ipdb_id = i.IpdbId
  LEFT JOIN opdb_machines om ON m.opdb_id = om.opdb_id
  WHERE m.corporate_entity_slug IS NULL
    AND (
      (i.ManufacturerId IS NOT NULL AND i.ManufacturerId != 0 AND i.ManufacturerId != 328)
      OR om.manufacturer.name IS NOT NULL
    )
),
-- Direct IPDB manufacturer ID -> CE
ipdb_ce AS (
  SELECT t.slug AS model_slug, ce.slug AS ce_slug
  FROM target_models t
  JOIN ipdb_machines i ON t.ipdb_id = i.IpdbId
  JOIN corporate_entities ce ON i.ManufacturerId = ce.ipdb_manufacturer_id
),
-- Inherit from variant parent
parent_ce AS (
  SELECT t.slug AS model_slug, parent.corporate_entity_slug AS ce_slug
  FROM target_models t
  JOIN models parent ON t.variant_of = parent.slug
  WHERE parent.corporate_entity_slug IS NOT NULL
),
-- OPDB manufacturer ID -> pinbase manufacturer -> most-used CE
opdb_id_ce AS (
  SELECT t.slug AS model_slug, pop.ce_slug
  FROM target_models t
  JOIN opdb_machines om ON t.opdb_id = om.opdb_id
  JOIN manufacturers mfr ON mfr.opdb_manufacturer_id = (om.manufacturer ->> 'manufacturer_id')::INT
  JOIN (
    SELECT ce.manufacturer_slug, m2.corporate_entity_slug AS ce_slug
    FROM models m2
    JOIN corporate_entities ce ON m2.corporate_entity_slug = ce.slug
    GROUP BY ce.manufacturer_slug, m2.corporate_entity_slug
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ce.manufacturer_slug ORDER BY count(*) DESC) = 1
  ) pop ON pop.manufacturer_slug = mfr.slug
  WHERE om.manufacturer IS NOT NULL
),
-- OPDB manufacturer name -> pinbase manufacturer -> most-used CE (fallback)
opdb_name_ce AS (
  SELECT t.slug AS model_slug, pop.ce_slug
  FROM target_models t
  JOIN opdb_machines om ON t.opdb_id = om.opdb_id
  JOIN manufacturers mfr ON LOWER(mfr.name) = LOWER(om.manufacturer.name)
  JOIN (
    SELECT ce.manufacturer_slug, m2.corporate_entity_slug AS ce_slug
    FROM models m2
    JOIN corporate_entities ce ON m2.corporate_entity_slug = ce.slug
    GROUP BY ce.manufacturer_slug, m2.corporate_entity_slug
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ce.manufacturer_slug ORDER BY count(*) DESC) = 1
  ) pop ON pop.manufacturer_slug = mfr.slug
  WHERE om.manufacturer.name IS NOT NULL
)
SELECT
  t.slug AS model_slug,
  t.name AS model_name,
  COALESCE(
    ipdb_ce.ce_slug,
    parent_ce.ce_slug,
    opdb_id_ce.ce_slug,
    opdb_name_ce.ce_slug
  ) AS proposed_ce_slug,
  CASE
    WHEN ipdb_ce.ce_slug IS NOT NULL THEN 'ipdb_direct'
    WHEN parent_ce.ce_slug IS NOT NULL THEN 'variant_parent'
    WHEN opdb_id_ce.ce_slug IS NOT NULL THEN 'opdb_mfr_id'
    WHEN opdb_name_ce.ce_slug IS NOT NULL THEN 'opdb_mfr_name'
    ELSE 'unresolved'
  END AS resolution_method
FROM target_models t
LEFT JOIN ipdb_ce ON t.slug = ipdb_ce.model_slug
LEFT JOIN parent_ce ON t.slug = parent_ce.model_slug
LEFT JOIN opdb_id_ce ON t.slug = opdb_id_ce.model_slug
LEFT JOIN opdb_name_ce ON t.slug = opdb_name_ce.model_slug;
SELECT fandom_page_id, fandom_name, fandom_manufacturer, fandom_year, fandom_wikitext
FROM compare_games_fandom
WHERE match_method IS NULL
ORDER BY fandom_name;
