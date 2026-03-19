-- 01_reference.sql — Hand-maintained reference tables, macros, and exception lists.
-- Domain knowledge that doesn't come from any data file.
-- Depends on: nothing

------------------------------------------------------------
-- Macros
------------------------------------------------------------

-- Normalize manufacturer names by stripping business suffixes.
-- Mirrors normalize_manufacturer_name() in bulk_utils.py.
-- Applied repeatedly to handle compound suffixes like "Sega Enterprises, Ltd."
CREATE OR REPLACE MACRO normalize_mfr_name(name) AS (
  lower(trim(
    regexp_replace(
      regexp_replace(
        regexp_replace(name,
          ',?\s+(?:Manufacturing|Electronics|Industries|Enterprises|Games|Pinball|Technologies|Company|Corporation|Incorporated|Limited|Inc\.?|Ltd\.?|Co\.?|LLC|GmbH|S\.?A\.?|s\.?p\.?a\.?|Kabushikigaisha|Automaten)\s*$',
          '', 'i'),
        ',?\s+(?:Manufacturing|Electronics|Industries|Enterprises|Games|Pinball|Technologies|Company|Corporation|Incorporated|Limited|Inc\.?|Ltd\.?|Co\.?|LLC|GmbH|S\.?A\.?|s\.?p\.?a\.?|Kabushikigaisha|Automaten)\s*$',
        '', 'i'),
      ',?\s+(?:Manufacturing|Electronics|Industries|Enterprises|Games|Pinball|Technologies|Company|Corporation|Incorporated|Limited|Inc\.?|Ltd\.?|Co\.?|LLC|GmbH|S\.?A\.?|s\.?p\.?a\.?|Kabushikigaisha|Automaten)\s*$',
      '', 'i')
  ))
);

------------------------------------------------------------
-- Geographic reference data
------------------------------------------------------------

-- US states: canonical name + aliases for IPDB typos/variants
CREATE OR REPLACE VIEW ref_us_states AS
SELECT * FROM (VALUES
  ('Alabama',        'Alabama'),
  ('Alaska',         'Alaska'),
  ('Arizona',        'Arizona'),
  ('Arkansas',       'Arkansas'),
  ('California',     'California'),
  ('Colorado',       'Colorado'),
  ('Connecticut',    'Connecticut'),
  ('Delaware',       'Delaware'),
  ('Florida',        'Florida'),
  ('Georgia',        'Georgia'),
  ('Hawaii',         'Hawaii'),
  ('Idaho',          'Idaho'),
  ('Illinois',       'Illinois'),
  ('Indiana',        'Indiana'),
  ('Iowa',           'Iowa'),
  ('Kansas',         'Kansas'),
  ('Kentucky',       'Kentucky'),
  ('Louisiana',      'Louisiana'),
  ('Maine',          'Maine'),
  ('Maryland',       'Maryland'),
  ('Massachusetts',  'Massachusetts'),
  ('Michigan',       'Michigan'),
  ('Minnesota',      'Minnesota'),
  ('Mississippi',    'Mississippi'),
  ('Missouri',       'Missouri'),
  ('Montana',        'Montana'),
  ('Nebraska',       'Nebraska'),
  ('Nevada',         'Nevada'),
  ('New Hampshire',  'New Hampshire'),
  ('New Jersey',     'New Jersey'),
  ('New Mexico',     'New Mexico'),
  ('New York',       'New York'),
  ('North Carolina', 'North Carolina'),
  ('North Dakota',   'North Dakota'),
  ('Ohio',           'Ohio'),
  ('Oklahoma',       'Oklahoma'),
  ('Oregon',         'Oregon'),
  ('Pennsylvania',   'Pennsylvania'),
  ('Rhode Island',   'Rhode Island'),
  ('South Carolina', 'South Carolina'),
  ('South Dakota',   'South Dakota'),
  ('Tennessee',      'Tennessee'),
  ('Texas',          'Texas'),
  ('Utah',           'Utah'),
  ('Vermont',        'Vermont'),
  ('Virginia',       'Virginia'),
  ('Washington',     'Washington'),
  ('West Virginia',  'West Virginia'),
  ('Wisconsin',      'Wisconsin'),
  ('Wyoming',        'Wyoming'),
  -- IPDB typos
  ('NewYork',        'New York'),
  ('SouthCarolina',  'South Carolina')
) AS t(state_name, canonical_name);

-- Country name normalization (IPDB inconsistencies)
CREATE OR REPLACE VIEW ref_country_normalization AS
SELECT * FROM (VALUES
  ('England',        'United Kingdom'),
  ('Britain',        'United Kingdom'),
  ('UK',             'United Kingdom'),
  ('U.K.',           'United Kingdom'),
  ('West Germany',   'Germany'),
  ('Holland',        'Netherlands'),
  ('The Netherlands','Netherlands'),
  ('R.O.C.',         'Taiwan')
) AS t(raw_country, normalized_country);

-- IPDB location overrides for misformatted manufacturer strings.
-- These have missing commas, semicolons, multi-city HQs, etc.
CREATE OR REPLACE VIEW ref_ipdb_location_overrides AS
SELECT * FROM (VALUES
  -- "Chicago Illinois" — missing comma
  (532, 'Chicago',          'Illinois',  'USA'),
  -- "Long Island City, Queens, New York" — Queens is a borough, not a state
  (607, 'Long Island City',  'New York',  'USA'),
  -- "Lincoln, Nebraska; Des Moines, Iowa" — two cities
  (764, 'Lincoln',           'Nebraska',  'USA'),
  -- "Youngstown, Ohio and New York City" — two cities
  (696, 'Youngstown',        'Ohio',      'USA'),
  -- "Madrid" — just a city, no country
  (439, 'Madrid',            NULL,        'Spain'),
  -- "Marcoussis and Paris, France" — dual city, use primary (Marcoussis is a Paris suburb)
  (364, 'Marcoussis',        NULL,        'France'),
  -- "Avenza, Massa-Carrera, Toscana, Italy" — Massa-Carrara is an Italian province, not a state
  (135, 'Avenza',            NULL,        'Italy')
) AS t(ipdb_manufacturer_id, headquarters_city, headquarters_state, headquarters_country);

------------------------------------------------------------
-- Source-specific code mappings
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
-- OPDB manufacturer resolution
------------------------------------------------------------

-- OPDB manufacturer ID → pinbase manufacturer slug mapping.
-- For OPDB manufacturers whose name doesn't match a pinbase manufacturer
-- (renames, merges, different brand names).
CREATE OR REPLACE VIEW ref_opdb_manufacturer_aliases AS
SELECT * FROM (VALUES
  (25,  'alvin-g'),                -- Alvin G. & Co → Alvin G.
  (37,  'bell-coin-matics'),       -- Bell Coin Matic → Bell Coin Matics
  (149, 'bem'),                    -- Bigliardini Elettronici Milano → BEM
  (82,  'century-consolidated-industries-company'), -- Cisco
  (71,  'coffee-mat'),             -- Coffee Mat → Coffee-Mat
  (19,  'esco'),                   -- Exhibit → ESCO
  (65,  'fascination-int-incorporated'), -- Fascination Game
  (50,  'komplett-flipper'),       -- Geiger → Komplett Flipper
  (63,  'giorgio-massiero'),       -- Giorgio Massiniero → Giorgio Massiero
  (138, 'ice'),                    -- Innovative Concepts (ICE) → ICE
  (31,  'international-concepts'), -- International → International Concepts
  (104, 'christian-tabart'),       -- K.C. Tabart → Christian Tabart
  (55,  'komplett-flipper'),       -- Komplett → Komplett Flipper
  (44,  'mac-sa'),                 -- Maguinas / Mac Pinball → MAC S.A.
  (108, 'marsaplay'),              -- Marsa Play → MarsaPlay
  (28,  'mr-game'),                -- Mr Game → Mr. Game
  (113, 'pmi'),                    -- Pinball Manufacturing Inc. → PMI
  (66,  'playmec'),                -- Playmec Flippers → Playmec
  (56,  'the-valley-company-subsidiary-of-walter-kidde-company-incorporated'), -- Valley
  (94,  'viza-mfg-inc')           -- Viza Manufacturing → Viza Mfg., Inc.
) AS t(opdb_manufacturer_id, manufacturer_slug);

-- Approved OPDB↔pinbase manufacturer disagreements.
-- Cases where OPDB attributes a model to one manufacturer but pinbase
-- correctly uses a different one (verified by research).
-- (opdb_manufacturer_id, pinbase_manufacturer_slug, reason)
CREATE OR REPLACE VIEW ref_opdb_manufacturer_exceptions AS
SELECT * FROM (VALUES
  -- Segasa (15) vs Sonic: OPDB uses "Segasa" for post-rebrand games that
  -- were actually branded "Sonic" (Segasa d.b.a. Sonic). IPDB is correct.
  (15, 'sonic', 'OPDB uses parent name Segasa for Sonic-branded games'),
  -- Geiger (50) vs Komplett Flipper: Geiger-Automatenbau GmbH = A.H. Geiger Co.
  -- = Komplett Flipper brand. OPDB uses company name, pinbase uses brand.
  (50, 'komplett-flipper', 'OPDB uses Geiger for Komplett Flipper brand'),
  -- Geiger (50) vs Professional Pinball: OPDB misattributes Challenger to Geiger
  (50, 'professional-pinball', 'OPDB misattributes to Geiger; IPDB says Professional Pinball'),
  -- Spooky Pinball (95) vs The Pinball Company: Jetsons was designed by
  -- The Pinball Company and manufactured by Spooky. IPDB credits designer.
  (95, 'the-pinball-company', 'Collaboration: designed by TPC, manufactured by Spooky'),
  -- Brunswick (40) vs Briarwood: Briarwood was a division of Brunswick.
  -- OPDB uses parent company name.
  (40, 'briarwood', 'OPDB uses parent Brunswick for Briarwood division games'),
  -- Midway (14) vs Bally: some Bally games manufactured by Midway.
  -- OPDB uses Midway, IPDB credits Bally.
  (14, 'bally', 'OPDB uses Midway for Bally-branded game'),
  -- Gottlieb (2) vs Alben: Alben was a French manufacturer/licensee.
  -- OPDB uses Gottlieb, IPDB credits Alben.
  (2, 'alben', 'OPDB uses Gottlieb for Alben-manufactured game'),
  -- Bell Games (20) vs Bell Coin Matics: related companies.
  (20, 'bell-coin-matics', 'OPDB uses Bell Games for Bell Coin Matics game'),
  -- Chicago Coin (3) vs Chicago Gaming: different eras of Chicago-based companies.
  (3, 'chicago-gaming', 'OPDB uses Chicago Coin for Chicago Gaming game'),
  -- Cic Play (4) vs Sentinel: related companies.
  (4, 'sentinel', 'OPDB uses Cic Play for Sentinel game'),
  -- Allied Leisure (49) vs LAI: LAI = Leisure & Allied Industries (Australian).
  (49, 'lai', 'OPDB uses Allied Leisure for LAI game'),
  -- Joctronic (90) vs Jocmatic: related Spanish companies.
  (90, 'jocmatic-sa', 'OPDB uses Joctronic for Jocmatic game'),
  -- Taito (73) vs Mecatronics: Brazilian Taito division.
  (73, 'mecatronics-aka-taito-brazil-a-division-of-taito', 'OPDB uses Taito for Brazilian division')
) AS t(opdb_manufacturer_id, manufacturer_slug, reason);

------------------------------------------------------------
-- Quality/tag cross-reference mappings
------------------------------------------------------------

-- OPDB feature string → pinbase tag slug
CREATE OR REPLACE VIEW ref_feature_tag AS
SELECT * FROM (VALUES
  ('Home model',      'home-use'),
  ('Widebody',        'widebody'),
  ('Remake',          'remake'),
  ('Conversion kit',  'conversion-kit'),
  ('Export edition',  'export')
) AS t(feature, tag_slug);
