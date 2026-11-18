# COLDEX Sample Finder

A static website: `index.html` + `allan-hills-map.png` + `data/coldex-data.js`.
There is no server and no live database. The page loads a snapshot of the COLDEX data from
`data/coldex-data.js` and does all searching in the browser.

The **master database is a SQLite file on the data manager's computer** (`private/coldex.sqlite`).
The website's data file is generated from it.

## Updating the website

1. Edit the data in **DB Browser for SQLite** (open `private/coldex.sqlite`).
2. Click **Write Changes** (Cmd+S), then close DB Browser.
3. Double-click **`Update Website.command`** (or run `python3 scripts/update-site.py`).

The script then: checks the database → makes a verified backup → shows data-check warnings →
builds the new `data/coldex-data.js` → shows what changed → asks **"Publish?"** → commits only
that file and pushes it. GitHub Pages updates in a minute or two.

It stops without publishing if the database has unsaved edits, if the row count drops more than 5%,
or if the git identity isn't a GitHub no-reply address. Options: `--no-push` (prepare only),
`--yes` (don't ask), `--force` (skip the row-drop stop).

## Entering data (DB Browser tips)

- **New sample:** add a row to `samples`. `core_uuid` fills itself in from `core_id`.
- **New subsample:** add a row to `subsamples`; leave `id` and `subsample_id` blank (automatic).
- **New core:** add it to **both** `cores` and `cores_ALLALHILLS`, or it won't appear on the website.
  For the map it also needs a dot and hover zone (see below).
- After editing, open the **`v_data_checks`** view to see anything that looks wrong.
- `requests` holds names and emails. It is never read by the website export.

## Backups

`python3 scripts/backup-db.py` makes a dated, verified copy in `private/backups/`; the update script
does this automatically. To restore: close DB Browser, then copy a backup over `private/coldex.sqlite`.
**The database is the only master copy**, so also keep it in Time Machine or on another drive.
Everything under `private/` is private (request data) and is ignored by git. Never publish it.

## Scripts

| File | Purpose |
|---|---|
| `scripts/update-site.py` | The one-command update (above). |
| `scripts/export-from-sqlite.py` | Builds `data/coldex-data.js` from the database. Reads only `cores_ALLALHILLS`, `samples`, `subsamples`. |
| `scripts/backup-db.py` | Verified, dated backup. |
| `scripts/schema.sql` | The database blueprint (tables, rules, views, triggers). |
| `scripts/build-sqlite.py` | One-time builder that created the SQLite file from the Supabase export. |
| `scripts/legacy-export-from-supabase.mjs` | **Do not run.** Reads the old Supabase data; kept only until Supabase is deleted. |

Request IDs are published as the bare code only (e.g. `C_2026_015`); names and institutions that
the database appends are dropped by the export.

## Adding a new core to the map

The dots and hover zones are tied to the map image. Add the core's code to the matching zone in
`MAP_HOTSPOTS` (and `MAP_DOTS`) in `index.html`. A core with no spot on the map still appears in
the Sample Finder.

## Trying it locally

Open `index.html` in a browser. No server is needed.
