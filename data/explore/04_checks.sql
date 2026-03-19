-- 04_checks.sql — Integrity checks on pinbase data.
-- Depends on: 02_raw.sql, 03_staging.sql
-- Aborts with non-zero exit code if any hard violations are found.

DROP TABLE IF EXISTS _violations;
DROP TABLE IF EXISTS _warnings;
CREATE TEMP TABLE _violations (category VARCHAR, check_name VARCHAR, detail VARCHAR);
CREATE TEMP TABLE _warnings (check_name VARCHAR, cnt BIGINT);

------------------------------------------------------------
-- Slug uniqueness and format
------------------------------------------------------------

INSERT INTO _violations
SELECT 'slugs', 'duplicate_model_slug', slug
FROM models GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'slugs', 'duplicate_title_slug', slug
FROM titles GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'slugs', 'duplicate_manufacturer_slug', slug
FROM manufacturers GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'slugs', 'duplicate_ce_slug', slug
FROM corporate_entities GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'slugs', 'duplicate_person_slug', slug
FROM people GROUP BY slug HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'slugs', 'invalid_slug_model', slug FROM models WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'slugs', 'invalid_slug_title', slug FROM titles WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'slugs', 'invalid_slug_manufacturer', slug FROM manufacturers WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'slugs', 'invalid_slug_ce', slug FROM corporate_entities WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';
INSERT INTO _violations
SELECT 'slugs', 'invalid_slug_person', slug FROM people WHERE slug != regexp_replace(slug, '[^a-z0-9-]', '', 'g') OR slug = '';

-- Slugs ending in a number (likely a dedup failure, e.g. linda-deal-2)
INSERT INTO _violations
SELECT 'slugs', 'person_slug_numbered_suffix', slug
FROM people WHERE slug ~ '-\d+$';
INSERT INTO _violations
SELECT 'slugs', 'manufacturer_slug_numbered_suffix', slug
FROM manufacturers WHERE slug ~ '-\d+$';
INSERT INTO _violations
SELECT 'slugs', 'ce_slug_numbered_suffix', slug
FROM corporate_entities WHERE slug ~ '-\d+$';

-- No empty names
INSERT INTO _violations
SELECT 'slugs', 'empty_name_model', slug FROM models WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'slugs', 'empty_name_title', slug FROM titles WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'slugs', 'empty_name_manufacturer', slug FROM manufacturers WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'slugs', 'empty_name_ce', slug FROM corporate_entities WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'slugs', 'empty_name_person', slug FROM people WHERE name IS NULL OR trim(name) = '';
INSERT INTO _violations
SELECT 'slugs', 'empty_name_theme', slug FROM themes WHERE name IS NULL OR trim(name) = '';

------------------------------------------------------------
-- External ID uniqueness and agreement
------------------------------------------------------------

INSERT INTO _violations
SELECT 'external_ids', 'duplicate_model_opdb_id', opdb_id
FROM models WHERE opdb_id IS NOT NULL
GROUP BY opdb_id HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'external_ids', 'duplicate_model_ipdb_id', CAST(ipdb_id AS VARCHAR)
FROM models WHERE ipdb_id IS NOT NULL
GROUP BY ipdb_id HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'external_ids', 'duplicate_title_opdb_group_id', opdb_group_id
FROM titles WHERE opdb_group_id IS NOT NULL
GROUP BY opdb_group_id HAVING count(*) > 1;

INSERT INTO _violations
SELECT 'external_ids', 'duplicate_ce_ipdb_manufacturer_id', CAST(ipdb_manufacturer_id AS VARCHAR)
FROM corporate_entities WHERE ipdb_manufacturer_id IS NOT NULL
GROUP BY ipdb_manufacturer_id HAVING count(*) > 1;

-- OPDB/Pinbase ipdb_id agreement
INSERT INTO _violations
SELECT 'external_ids', 'ipdb_id_disagreement',
  m.slug || ' pinbase=' || m.ipdb_id || ' opdb=' || om.ipdb_id
FROM models AS m
JOIN opdb_machines AS om ON m.opdb_id = om.opdb_id
WHERE m.ipdb_id IS NOT NULL
  AND om.ipdb_id IS NOT NULL
  AND m.ipdb_id != om.ipdb_id;

-- CE ↔ IPDB manufacturer agreement
INSERT INTO _violations
SELECT 'external_ids', 'ce_ipdb_disagreement',
  m.slug || ' pinbase_ce=' || m.corporate_entity_slug
  || ' ipdb_mfr_id=' || im.ManufacturerId
  || ' ce_ipdb_id=' || COALESCE(CAST(ce.ipdb_manufacturer_id AS VARCHAR), 'NULL')
FROM models AS m
JOIN ipdb_machines AS im ON m.ipdb_id = im.IpdbId
LEFT JOIN corporate_entities AS ce ON ce.slug = m.corporate_entity_slug
WHERE m.corporate_entity_slug IS NOT NULL
  AND im.ManufacturerId != 328
  AND im.ManufacturerId != 0
  AND (ce.ipdb_manufacturer_id IS NULL OR ce.ipdb_manufacturer_id != im.ManufacturerId);

-- CE ↔ OPDB manufacturer agreement
INSERT INTO _violations
SELECT 'external_ids', 'ce_opdb_manufacturer_disagreement',
  m.slug || ' opdb_mfr_id=' || (om.manufacturer ->> 'manufacturer_id')
  || ' pinbase_mfr=' || mfr.slug
  || ' mfr_opdb_id=' || COALESCE(CAST(mfr.opdb_manufacturer_id AS VARCHAR), 'NULL')
FROM models AS m
JOIN opdb_machines AS om ON m.opdb_id = om.opdb_id
LEFT JOIN corporate_entities AS ce ON ce.slug = m.corporate_entity_slug
LEFT JOIN manufacturers AS mfr ON mfr.slug = ce.manufacturer_slug
WHERE m.corporate_entity_slug IS NOT NULL
  AND om.manufacturer IS NOT NULL
  AND (mfr.opdb_manufacturer_id IS NULL
    OR mfr.opdb_manufacturer_id != (om.manufacturer ->> 'manufacturer_id')::INT)
  AND NOT EXISTS (
    SELECT 1 FROM ref_opdb_manufacturer_exceptions ex
    WHERE ex.opdb_manufacturer_id = (om.manufacturer ->> 'manufacturer_id')::INT
      AND ex.manufacturer_slug = mfr.slug
  );

------------------------------------------------------------
-- Orphan references
------------------------------------------------------------

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_model_title', m.slug || ' -> ' || m.title_slug
FROM models AS m
WHERE m.title_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM titles AS t WHERE t.slug = m.title_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_title_franchise', t.slug || ' -> ' || t.franchise_slug
FROM titles AS t
WHERE t.franchise_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM franchises AS f WHERE f.slug = t.franchise_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_title_series', t.slug || ' -> ' || t.series_slug
FROM titles AS t
WHERE t.series_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM series AS s WHERE s.slug = t.series_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_model_corporate_entity', m.slug || ' -> ' || m.corporate_entity_slug
FROM models AS m
WHERE m.corporate_entity_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM corporate_entities AS ce WHERE ce.slug = m.corporate_entity_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_model_cabinet', m.slug || ' -> ' || m.cabinet_slug
FROM models AS m
WHERE m.cabinet_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM cabinets AS c WHERE c.slug = m.cabinet_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_model_technology_generation', m.slug || ' -> ' || m.technology_generation_slug
FROM models AS m
WHERE m.technology_generation_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM technology_generations AS tg WHERE tg.slug = m.technology_generation_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_model_display_type', m.slug || ' -> ' || m.display_type_slug
FROM models AS m
WHERE m.display_type_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM display_types AS dt WHERE dt.slug = m.display_type_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_model_system', m.slug || ' -> ' || m.system_slug
FROM models AS m
WHERE m.system_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM systems AS s WHERE s.slug = m.system_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_variant_of', m.slug || ' -> ' || m.variant_of
FROM models AS m
WHERE m.variant_of IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.variant_of);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_converted_from', m.slug || ' -> ' || m.converted_from
FROM models AS m
WHERE m.converted_from IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.converted_from);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_remake_of', m.slug || ' -> ' || m.remake_of
FROM models AS m
WHERE m.remake_of IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM models AS m2 WHERE m2.slug = m.remake_of);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_credit_person', c.model_slug || ' -> ' || c.person_slug
FROM pinbase_credits AS c
WHERE NOT EXISTS (SELECT 1 FROM people AS p WHERE p.slug = c.person_slug);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_credit_role', c.model_slug || ' -> ' || c.role
FROM pinbase_credits AS c
WHERE NOT EXISTS (SELECT 1 FROM credit_roles AS cr WHERE cr.name = c.role);

INSERT INTO _violations
SELECT 'orphan_refs', 'orphan_ce_manufacturer', ce.slug || ' -> ' || ce.manufacturer_slug
FROM corporate_entities AS ce
WHERE ce.manufacturer_slug IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM manufacturers AS m WHERE m.slug = ce.manufacturer_slug);

------------------------------------------------------------
-- Entity structure
------------------------------------------------------------

-- Self-referential variant_of
INSERT INTO _violations
SELECT 'entities', 'self_variant_of', slug
FROM models WHERE variant_of = slug;

-- Chained variant_of (A -> B where B also has variant_of)
INSERT INTO _violations
SELECT 'entities', 'chained_variant_of', a.slug || ' -> ' || a.variant_of || ' -> ' || b.variant_of
FROM models AS a
JOIN models AS b ON a.variant_of = b.slug
WHERE b.variant_of IS NOT NULL;

-- Pinbase model references a non-physical OPDB record (physical_machine=0)
INSERT INTO _violations
SELECT 'entities', 'non_physical_opdb_ref', m.slug || ' (' || m.opdb_id || ')'
FROM models AS m
JOIN opdb_machines AS om ON m.opdb_id = om.opdb_id
WHERE om.physical_machine = 0;

-- Corporate entity: manufacturer_slug is required
INSERT INTO _violations
SELECT 'entities', 'ce_missing_manufacturer', slug
FROM corporate_entities WHERE manufacturer_slug IS NULL;

-- Every manufacturer must have at least one corporate entity
INSERT INTO _violations
SELECT 'entities', 'orphan_manufacturer', m.slug
FROM manufacturers AS m
WHERE NOT EXISTS (SELECT 1 FROM corporate_entities AS ce WHERE ce.manufacturer_slug = m.slug);

-- More corporate entities than manufacturers
INSERT INTO _violations
SELECT 'entities', 'fewer_ces_than_manufacturers',
  'corporate_entities=' || (SELECT count(*) FROM corporate_entities)
  || ' manufacturers=' || (SELECT count(*) FROM manufacturers)
WHERE (SELECT count(*) FROM corporate_entities) <= (SELECT count(*) FROM manufacturers);

-- No two corporate entities share the same (name, manufacturer_slug) pair
INSERT INTO _violations
SELECT 'entities', 'duplicate_ce_name_manufacturer', name || ' -> ' || manufacturer_slug
FROM corporate_entities
WHERE (name, manufacturer_slug) NOT IN (
  ('Automatic Games Company', 'automatic-games-company'),
  ('Shyvers Manufacturing Company', 'shyvers')
)
GROUP BY name, manufacturer_slug HAVING count(*) > 1;

-- All models must point at a title
INSERT INTO _violations
SELECT 'entities', 'model_missing_title', slug
FROM models WHERE title_slug IS NULL;

-- More models than titles
INSERT INTO _violations
SELECT 'entities', 'fewer_models_than_titles',
  'models=' || (SELECT count(*) FROM models)
  || ' titles=' || (SELECT count(*) FROM titles)
WHERE (SELECT count(*) FROM models) <= (SELECT count(*) FROM titles);

-- Every title must have at least one model
INSERT INTO _violations
SELECT 'entities', 'orphan_title', t.slug
FROM titles AS t
WHERE NOT EXISTS (SELECT 1 FROM models AS m WHERE m.title_slug = t.slug);

-- Model year is reasonable (1850–2030)
INSERT INTO _violations
SELECT 'entities', 'model_year_out_of_range', slug || ' year=' || year
FROM models WHERE year IS NOT NULL AND (year < 1850 OR year > 2030);

-- Model month is 1–12 when present
INSERT INTO _violations
SELECT 'entities', 'model_month_out_of_range', slug || ' month=' || month
FROM models WHERE month IS NOT NULL AND (month < 1 OR month > 12);

-- Production quantity is positive when present
INSERT INTO _violations
SELECT 'entities', 'model_negative_production', slug || ' qty=' || production_quantity
FROM models WHERE production_quantity IS NOT NULL AND TRY_CAST(production_quantity AS INTEGER) <= 0;

-- Models missing CE where an external source has manufacturer data
INSERT INTO _violations
SELECT 'entities', 'model_missing_ce_with_external_mfr', m.slug
FROM models m
LEFT JOIN ipdb_machines i ON m.ipdb_id = i.IpdbId
LEFT JOIN opdb_machines om ON m.opdb_id = om.opdb_id
WHERE m.corporate_entity_slug IS NULL
  AND (
    (i.ManufacturerId IS NOT NULL AND i.ManufacturerId != 0 AND i.ManufacturerId != 328)
    OR om.manufacturer.name IS NOT NULL
  );

------------------------------------------------------------
-- Credits and people
------------------------------------------------------------

-- Pinbase credit count must match IPDB credit count
INSERT INTO _violations
SELECT 'credits', 'credit_count_mismatch_ipdb',
  m.slug || ' pinbase=' || COALESCE(pb.cnt, 0) || ' ipdb=' || ipdb.cnt
FROM models AS m
JOIN (
  SELECT IpdbId, count(*) AS cnt FROM _ipdb_credits GROUP BY IpdbId
) AS ipdb ON m.ipdb_id = ipdb.IpdbId
LEFT JOIN (
  SELECT model_slug, count(*) AS cnt FROM pinbase_credits GROUP BY model_slug
) AS pb ON pb.model_slug = m.slug
WHERE COALESCE(pb.cnt, 0) <> ipdb.cnt;

-- People with no credits (orphaned person records)
INSERT INTO _violations
SELECT 'credits', 'person_without_credits', p.slug
FROM people AS p
WHERE NOT EXISTS (SELECT 1 FROM pinbase_credits AS c WHERE c.person_slug = p.slug);

-- Duplicate credit on a model (same person+role twice)
INSERT INTO _violations
SELECT 'credits', 'duplicate_credit', model_slug || ' ' || person_slug || ' ' || role
FROM pinbase_credits
GROUP BY model_slug, person_slug, role HAVING count(*) > 1;

-- Person alias duplicated on same person
INSERT INTO _violations
SELECT 'credits', 'duplicate_person_alias', slug || ' alias "' || a || '"'
FROM (
  SELECT slug, UNNEST(aliases) AS a
  FROM people WHERE aliases IS NOT NULL
)
GROUP BY slug, a HAVING count(*) > 1;

-- Duplicate person names (different slugs, same name)
INSERT INTO _violations
SELECT 'credits', 'duplicate_person_name', p1.slug || ' & ' || p2.slug || ' = ' || p1.name
FROM people AS p1
JOIN people AS p2 ON LOWER(p1.name) = LOWER(p2.name) AND p1.slug < p2.slug;

-- Person alias collides with another person's canonical name
INSERT INTO _violations
SELECT 'credits', 'person_alias_collides_with_name',
  p1.slug || ' alias "' || alias || '" matches name of ' || p2.slug
FROM people AS p1, UNNEST(p1.aliases) AS t(alias)
JOIN people AS p2 ON LOWER(alias) = LOWER(p2.name) AND p1.slug != p2.slug;

-- Person alias collides with another person's alias
INSERT INTO _violations
SELECT 'credits', 'person_alias_collision',
  x.slug1 || ' & ' || x.slug2 || ' share alias "' || x.a1 || '"'
FROM (
  SELECT p1.slug AS slug1, p2.slug AS slug2, a1
  FROM (SELECT slug, UNNEST(aliases) AS a1 FROM people WHERE aliases IS NOT NULL) AS p1
  JOIN (SELECT slug, UNNEST(aliases) AS a2 FROM people WHERE aliases IS NOT NULL) AS p2
    ON LOWER(p1.a1) = LOWER(p2.a2) AND p1.slug < p2.slug
) AS x;

-- Person alias matches own canonical name (redundant)
INSERT INTO _violations
SELECT 'credits', 'person_alias_matches_own_name', p.slug || ' alias "' || alias || '"'
FROM people AS p, UNNEST(p.aliases) AS t(alias)
WHERE LOWER(alias) = LOWER(p.name);

-- IPDB person name does not resolve to any Pinbase person
INSERT INTO _violations
SELECT 'credits', 'ipdb_person_unresolved', person_name || ' (' || count(*) || ' credits)'
FROM _ipdb_credits
WHERE person_slug IS NULL
GROUP BY person_name;

------------------------------------------------------------
-- Source dump integrity
------------------------------------------------------------

INSERT INTO _violations
SELECT 'source_dumps', 'opdb_record_missing_id', name
FROM opdb_machines WHERE opdb_id IS NULL;

INSERT INTO _violations
SELECT 'source_dumps', 'ipdb_record_missing_id', Title
FROM ipdb_machines WHERE IpdbId IS NULL;

-- Every IPDB machine has a pinbase model
INSERT INTO _violations
SELECT 'source_dumps', 'ipdb_machine_missing_model', CAST(i.IpdbId AS VARCHAR) || ' ' || i.Title
FROM ipdb_machines AS i
WHERE NOT EXISTS (SELECT 1 FROM models AS m WHERE m.ipdb_id = i.IpdbId);

-- Every OPDB physical machine has a pinbase model
INSERT INTO _violations
SELECT 'source_dumps', 'opdb_machine_missing_model', om.opdb_id || ' ' || om.name
FROM opdb_machines AS om
WHERE om.is_machine = true AND om.physical_machine = 1
  AND NOT EXISTS (SELECT 1 FROM models AS m WHERE m.opdb_id = om.opdb_id);

------------------------------------------------------------
-- Soft warnings (data quality, not regressions)
------------------------------------------------------------

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
SELECT 'models_missing_corporate_entity', count(*)
FROM models m
WHERE m.corporate_entity_slug IS NULL
  AND NOT EXISTS (
    SELECT 1 FROM ipdb_machines i
    WHERE m.ipdb_id = i.IpdbId
      AND i.ManufacturerId IS NOT NULL AND i.ManufacturerId != 0 AND i.ManufacturerId != 328
  )
  AND NOT EXISTS (
    SELECT 1 FROM opdb_machines om
    WHERE m.opdb_id = om.opdb_id
      AND om.manufacturer.name IS NOT NULL
  );

INSERT INTO _warnings
SELECT 'titles_missing_opdb_group', count(*)
FROM titles WHERE opdb_group_id IS NULL;

INSERT INTO _warnings
SELECT 'conversion_without_source', count(*)
FROM models WHERE is_conversion AND converted_from IS NULL;

------------------------------------------------------------
-- Results
------------------------------------------------------------

SELECT 'WARNING: ' || check_name || ' (' || cnt || ' rows)'
FROM _warnings WHERE cnt > 0;

-- Per-category violation summary
SELECT category, count(*) AS violations
FROM _violations GROUP BY category ORDER BY category;

SELECT CASE
  WHEN count(*) > 0
  THEN error(count(*) || ' contract violation(s) found. Run: SELECT * FROM _violations')
  ELSE 'All checks passed'
END FROM _violations;
