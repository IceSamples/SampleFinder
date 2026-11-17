-- COLDEX sample database — SQLite schema.
-- A faithful translation of the Supabase (Postgres) "coldex" schema.
--
--   uuid            -> TEXT   (new rows get a random uuid automatically)
--   date            -> TEXT   ('YYYY-MM-DD')
--   numeric/double  -> REAL
--   boolean         -> INTEGER (1 = true, 0 = false)
--
-- Foreign keys must be switched ON for each connection (DB Browser for SQLite does this
-- by default: Preferences > Database > "Foreign keys").

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------------
-- Cores
-- ---------------------------------------------------------------------------------
CREATE TABLE cores (
  core_uuid     TEXT NOT NULL PRIMARY KEY
                DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
                         substr(hex(randomblob(2)), 2) || '-' ||
                         substr('89ab', abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)), 2) ||
                         '-' || hex(randomblob(6)))),
  core_code     TEXT NOT NULL UNIQUE,
  site_name     TEXT,
  latitude_deg  REAL,
  longitude_deg REAL,
  elevation_m   REAL,
  drill_date    TEXT,
  pi            TEXT,
  drill_type    TEXT,
  oldest_age    REAL,
  notes         TEXT,
  "Maximum_Depth" REAL
);

-- The table the website's map and core pages read.
CREATE TABLE "cores_ALLALHILLS" (
  core_uuid     TEXT NOT NULL PRIMARY KEY
                DEFAULT (lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
                         substr(hex(randomblob(2)), 2) || '-' ||
                         substr('89ab', abs(random()) % 4 + 1, 1) || substr(hex(randomblob(2)), 2) ||
                         '-' || hex(randomblob(6)))),
  core_code     TEXT NOT NULL UNIQUE,
  site_name     TEXT,
  latitude_deg  REAL,
  longitude_deg REAL,
  elevation_m   REAL,
  "Year Drilled"   TEXT,
  pi            TEXT,
  drill_type    TEXT,
  oldest_age    REAL,
  notes         TEXT,
  "Maximum_Depth"  REAL,
  "Drill Diameter" INTEGER,
  "COLDEX"         INTEGER CHECK ("COLDEX" IN (0, 1))
);

-- ---------------------------------------------------------------------------------
-- Requests  (PRIVATE: contains names and emails — never exported to the website)
-- ---------------------------------------------------------------------------------
CREATE TABLE requests (
  request_id             TEXT NOT NULL PRIMARY KEY,
  requester_name         TEXT,
  institution            TEXT,
  contact_email          TEXT,
  requested_core_section TEXT,
  requested_depth_range  TEXT,
  purpose                TEXT,
  status                 TEXT
);

-- ---------------------------------------------------------------------------------
-- Samples (core sections)
-- ---------------------------------------------------------------------------------
CREATE TABLE samples (
  record_id      TEXT NOT NULL PRIMARY KEY,
  core_id        TEXT,
  section_number TEXT,
  top_depth_m    REAL,
  bottom_depth_m REAL,
  length_m       REAL,
  notes          TEXT,
  remaining_m    REAL,
  old_id         INTEGER UNIQUE,
  status         TEXT CHECK (status IS NULL OR status IN ('available', 'consumed')),
  -- Filled in automatically from core_id when left blank (see trigger below).
  core_uuid      TEXT REFERENCES cores (core_uuid) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX idx_samples_core_id ON samples (core_id);

-- ---------------------------------------------------------------------------------
-- Subsamples
-- ---------------------------------------------------------------------------------
CREATE TABLE subsamples (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  top_depth_m       REAL,
  bottom_depth_m    REAL,
  length_m          REAL,
  destination       TEXT,
  status            TEXT,
  date_sent         TEXT,
  purpose_notes     TEXT,
  request_id        TEXT REFERENCES requests (request_id) ON UPDATE CASCADE ON DELETE SET NULL,
  linked_shipment   TEXT,
  cut_shape         TEXT,
  parent_section_id TEXT REFERENCES samples (record_id) ON UPDATE CASCADE ON DELETE CASCADE,
  old_id            INTEGER UNIQUE,
  subsample_id      TEXT      -- built automatically by the triggers below; no need to type it
);
CREATE INDEX idx_subsamples_parent ON subsamples (parent_section_id);

-- ---------------------------------------------------------------------------------
-- Working tables carried over from Supabase (not used by the website)
-- ---------------------------------------------------------------------------------
CREATE TABLE subsamples_stage (
  top_depth_m       REAL,
  bottom_depth_m    REAL,
  length_m          REAL,
  destination       TEXT,
  status            TEXT,
  date_sent         TEXT,
  purpose_notes     TEXT,
  request_id        TEXT,
  linked_shipment   TEXT,
  cut_shape         TEXT,
  parent_section_id TEXT,
  old_id            INTEGER,
  id                INTEGER,
  subsample_id      TEXT
);

CREATE TABLE temp_available_samples (
  record_id TEXT NOT NULL PRIMARY KEY
);

-- ---------------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------------
CREATE VIEW v_samples AS
  SELECT s.record_id, s.core_uuid, s.section_number, s.top_depth_m, s.bottom_depth_m,
         s.length_m, s.notes, s.remaining_m, s.old_id, s.status, c.core_code AS core_id
  FROM samples s JOIN cores c ON c.core_uuid = s.core_uuid;

CREATE VIEW core_codes AS
  SELECT DISTINCT core_code FROM cores WHERE core_code IS NOT NULL ORDER BY core_code;

-- Open this in DB Browser to see records that look odd. It only reports; nothing is blocked.
CREATE VIEW v_data_checks AS
  SELECT 'sample has no depth' AS problem, record_id AS item, NULL AS detail
    FROM samples WHERE top_depth_m IS NULL OR bottom_depth_m IS NULL
  UNION ALL
  SELECT 'sample top is deeper than bottom', record_id, top_depth_m || ' > ' || bottom_depth_m
    FROM samples WHERE top_depth_m > bottom_depth_m
  UNION ALL
  SELECT 'sample core_id not found in cores', record_id, core_id
    FROM samples WHERE core_id IS NOT NULL AND core_id NOT IN (SELECT core_code FROM cores)
  UNION ALL
  SELECT 'sample core_uuid does not match its core_id', s.record_id, s.core_id || ' vs ' || c.core_code
    FROM samples s JOIN cores c ON c.core_uuid = s.core_uuid WHERE s.core_id <> c.core_code
  UNION ALL
  SELECT 'subsample top is deeper than bottom', COALESCE(subsample_id, CAST(id AS TEXT)), top_depth_m || ' > ' || bottom_depth_m
    FROM subsamples WHERE top_depth_m > bottom_depth_m
  UNION ALL
  SELECT 'subsample has no parent section', CAST(id AS TEXT), subsample_id
    FROM subsamples WHERE parent_section_id IS NULL
  UNION ALL
  SELECT 'subsample has no destination', COALESCE(subsample_id, CAST(id AS TEXT)), NULL
    FROM subsamples WHERE destination IS NULL OR trim(destination) = ''
  UNION ALL
  SELECT 'destination spelled in mixed case', destination, COUNT(*) || ' rows'
    FROM subsamples WHERE destination <> upper(destination) GROUP BY destination
  UNION ALL
  SELECT 'request code not in requests table', request_id, COUNT(*) || ' subsamples'
    FROM subsamples WHERE request_id IS NOT NULL AND request_id NOT IN (SELECT request_id FROM requests)
    GROUP BY request_id
  UNION ALL
  SELECT 'core has samples but is missing from cores_ALLALHILLS (no map or core page on the website)', core_id, COUNT(*) || ' samples'
    FROM samples WHERE core_id IS NOT NULL AND core_id NOT IN (SELECT core_code FROM "cores_ALLALHILLS")
    GROUP BY core_id
  UNION ALL
  SELECT 'core is in cores but missing from cores_ALLALHILLS', core_code, NULL
    FROM cores WHERE core_code NOT IN (SELECT core_code FROM "cores_ALLALHILLS");

-- ---------------------------------------------------------------------------------
-- Triggers
-- ---------------------------------------------------------------------------------

-- New samples: fill core_uuid from core_id when it was left blank.
CREATE TRIGGER trg_samples_core_uuid AFTER INSERT ON samples
WHEN NEW.core_uuid IS NULL
BEGIN
  UPDATE samples SET core_uuid = (SELECT core_uuid FROM cores WHERE core_code = NEW.core_id)
  WHERE record_id = NEW.record_id;
END;

-- subsample_id = parent-section id + top (mm) + bottom (mm) + cut shape, joined by "-",
-- skipping any blank part. Same rule as the original Postgres trigger fn_set_subsample_id().
CREATE TRIGGER trg_subsamples_subsample_id_ins AFTER INSERT ON subsamples
WHEN NEW.subsample_id IS NOT substr(
       CASE WHEN NEW.parent_section_id IS NOT NULL THEN '-' || NEW.parent_section_id ELSE '' END ||
       CASE WHEN NEW.top_depth_m       IS NOT NULL THEN '-' || CAST(round(NEW.top_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NEW.bottom_depth_m    IS NOT NULL THEN '-' || CAST(round(NEW.bottom_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NULLIF(NEW.cut_shape, '') IS NOT NULL THEN '-' || NEW.cut_shape ELSE '' END, 2)
BEGIN
  UPDATE subsamples SET subsample_id = substr(
       CASE WHEN NEW.parent_section_id IS NOT NULL THEN '-' || NEW.parent_section_id ELSE '' END ||
       CASE WHEN NEW.top_depth_m       IS NOT NULL THEN '-' || CAST(round(NEW.top_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NEW.bottom_depth_m    IS NOT NULL THEN '-' || CAST(round(NEW.bottom_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NULLIF(NEW.cut_shape, '') IS NOT NULL THEN '-' || NEW.cut_shape ELSE '' END, 2)
  WHERE id = NEW.id;
END;

CREATE TRIGGER trg_subsamples_subsample_id_upd
AFTER UPDATE OF parent_section_id, top_depth_m, bottom_depth_m, cut_shape, subsample_id ON subsamples
WHEN NEW.subsample_id IS NOT substr(
       CASE WHEN NEW.parent_section_id IS NOT NULL THEN '-' || NEW.parent_section_id ELSE '' END ||
       CASE WHEN NEW.top_depth_m       IS NOT NULL THEN '-' || CAST(round(NEW.top_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NEW.bottom_depth_m    IS NOT NULL THEN '-' || CAST(round(NEW.bottom_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NULLIF(NEW.cut_shape, '') IS NOT NULL THEN '-' || NEW.cut_shape ELSE '' END, 2)
BEGIN
  UPDATE subsamples SET subsample_id = substr(
       CASE WHEN NEW.parent_section_id IS NOT NULL THEN '-' || NEW.parent_section_id ELSE '' END ||
       CASE WHEN NEW.top_depth_m       IS NOT NULL THEN '-' || CAST(round(NEW.top_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NEW.bottom_depth_m    IS NOT NULL THEN '-' || CAST(round(NEW.bottom_depth_m * 1000) AS INTEGER) ELSE '' END ||
       CASE WHEN NULLIF(NEW.cut_shape, '') IS NOT NULL THEN '-' || NEW.cut_shape ELSE '' END, 2)
  WHERE id = NEW.id;
END;
