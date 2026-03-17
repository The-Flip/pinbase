-- 01_raw.sql — Raw tables from all JSON data files.
-- No transforms, no joins. Just flatten top-level wrappers where needed.
-- Tables (not views) so JSON is parsed once at build time.

------------------------------------------------------------
-- Pinbase Markdown-sourced data (via pinbase_export)
------------------------------------------------------------

CREATE OR REPLACE TABLE cabinets AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/cabinet.json');

CREATE OR REPLACE TABLE corporate_entities AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/corporate_entity.json');

CREATE OR REPLACE TABLE credit_roles AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/credit_role.json');

CREATE OR REPLACE TABLE display_subtypes AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/display_subtype.json');

CREATE OR REPLACE TABLE display_types AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/display_type.json');

CREATE OR REPLACE TABLE franchises AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/franchise.json');

CREATE OR REPLACE TABLE game_formats AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/game_format.json');

CREATE OR REPLACE TABLE gameplay_features AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/gameplay_feature.json');

CREATE OR REPLACE TABLE manufacturers AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/manufacturer.json');

CREATE OR REPLACE TABLE models AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/model.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE TABLE people AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/person.json', (union_by_name = CAST('t' AS BOOLEAN)));

CREATE OR REPLACE TABLE series AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/series.json');

CREATE OR REPLACE TABLE systems AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/system.json');

CREATE OR REPLACE TABLE tags AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/tag.json');

CREATE OR REPLACE TABLE technology_generations AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/technology_generation.json');

CREATE OR REPLACE TABLE technology_subgenerations AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/technology_subgeneration.json');

CREATE OR REPLACE TABLE themes AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/theme.json');

CREATE OR REPLACE TABLE titles AS
SELECT * FROM read_json_auto('data/explore/pinbase_export/title.json', (union_by_name = CAST('t' AS BOOLEAN)));

------------------------------------------------------------
-- External source dumps (data/dump1/)
------------------------------------------------------------

-- Fandom wiki exports
CREATE OR REPLACE TABLE fandom_games AS
SELECT d.*
FROM (SELECT unnest(games) AS d FROM read_json_auto('data/dump1/fandom_games.json'));

CREATE OR REPLACE TABLE fandom_manufacturers AS
SELECT d.*
FROM (SELECT unnest(manufacturers) AS d FROM read_json_auto('data/dump1/fandom_manufacturers.json'));

CREATE OR REPLACE TABLE fandom_persons AS
SELECT d.*
FROM (SELECT unnest(persons) AS d FROM read_json_auto('data/dump1/fandom_persons.json'));

-- Pinball Map API exports
CREATE OR REPLACE TABLE pinballmap_machines AS
SELECT d.*
FROM (SELECT unnest(machines) AS d FROM read_json_auto('data/dump1/pinballmap_machines.json'));

CREATE OR REPLACE TABLE pinballmap_machine_groups AS
SELECT d.*
FROM (SELECT unnest(machine_groups) AS d FROM read_json_auto('data/dump1/pinballmap_machine_groups.json'));

-- OPDB (Open Pinball Database) exports
CREATE OR REPLACE TABLE opdb_groups AS
SELECT * FROM read_json_auto('data/dump1/opdb_export_groups.json');

CREATE OR REPLACE TABLE opdb_machines AS
SELECT
  opdb_id,
  split_part(opdb_id, '-', 1) AS group_id,
  split_part(opdb_id, '-', 2) AS machine_id,
  CASE
    WHEN split_part(opdb_id, '-', 3) = '' THEN NULL
    ELSE split_part(opdb_id, '-', 3)
  END AS alias_id,
  is_machine,
  is_alias,
  "name",
  common_name,
  shortname,
  physical_machine,
  ipdb_id,
  manufacture_date,
  manufacturer,
  "type",
  display,
  player_count,
  features,
  keywords,
  description,
  created_at,
  updated_at,
  images
FROM read_json_auto('data/dump1/opdb_export_machines.json');

-- IPDB (Internet Pinball Database) export
CREATE OR REPLACE TABLE ipdb_machines AS
SELECT d.*
FROM (
  SELECT unnest("Data") AS d
  FROM read_json_auto('data/dump1/ipdbdatabase.json', (maximum_object_size = 67108864))
);
