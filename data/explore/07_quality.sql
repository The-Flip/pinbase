-- 07_quality.sql — What needs cleanup? Slug quality, themes, files, backfills.
-- Depends on: 01_reference.sql, 02_raw.sql, 03_staging.sql

------------------------------------------------------------
-- Slug quality: name faithfulness
------------------------------------------------------------

CREATE OR REPLACE VIEW slug_name_faithfulness AS
WITH slugified AS (
  SELECT
    slug,
    name,
    title_slug,
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
------------------------------------------------------------

CREATE OR REPLACE VIEW slug_prime_conflicts AS
WITH
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
  d.model_slug AS displaced_slug,
  d.model_name AS displaced_name,
  d.corporate_entity_slug AS displaced_corporate_entity,
  d.year AS displaced_year,
  di.ProductionNumber AS displaced_production,
  di.AverageFunRating AS displaced_rating,
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
-- File/media views
------------------------------------------------------------

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
-- Theme/tag cross-reference
------------------------------------------------------------

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

CREATE OR REPLACE VIEW missing_tags_opdb AS
SELECT
  f AS opdb_feature,
  count(DISTINCT om.opdb_id) AS machine_count
FROM opdb_machines AS om, unnest(om.features) AS t(f)
WHERE NOT EXISTS (SELECT 1 FROM ref_feature_tag AS rft WHERE rft.feature = f)
GROUP BY f
ORDER BY machine_count DESC;

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

CREATE OR REPLACE VIEW missing_themes AS
SELECT name, in_ipdb, in_opdb
FROM compare_themes
WHERE NOT in_pinbase
ORDER BY name;

------------------------------------------------------------
-- Proposed backfill: corporate_entity_slug on models
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
ipdb_ce AS (
  SELECT t.slug AS model_slug, ce.slug AS ce_slug
  FROM target_models t
  JOIN ipdb_machines i ON t.ipdb_id = i.IpdbId
  JOIN corporate_entities ce ON i.ManufacturerId = ce.ipdb_manufacturer_id
),
parent_ce AS (
  SELECT t.slug AS model_slug, parent.corporate_entity_slug AS ce_slug
  FROM target_models t
  JOIN models parent ON t.variant_of = parent.slug
  WHERE parent.corporate_entity_slug IS NOT NULL
),
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
