# COLDEX Sample Finder

A static website: `index.html` + `allan-hills-map.png` + `data/coldex-data.js`.
There is no server and no live database. The page loads a snapshot of the COLDEX data from
`data/coldex-data.js` and does all searching in the browser.

The **master database is a SQLite file on the data manager's computer** (`private/coldex.sqlite`).
The website's data file is generated from it.

## Two sites, two folders

| | GitHub repo (remote) | Web address | Local folder |
|---|---|---|---|
| **Live site** (everyone sees it) | `IceSamples/SampleFinder` (`live`) | icesamples.github.io/SampleFinder | this folder, branch `main` |
| **Test site** (only for trying things) | `IceSamples/SampleFinder-dev` (`dev`) | icesamples.github.io/SampleFinder-dev | `Website Sample Finder SANDBOX`, branch `sandbox` |

- **Data updates** go to the live site from **this** folder (next section).
- **Design experiments** are done in the **SANDBOX folder**, so the live site can't be affected by half-finished work.

## Updating the website

1. Edit the data in **DB Browser for SQLite** (open `private/coldex.sqlite`).
2. Click **Write Changes** (Cmd+S), then close DB Browser.
3. Double-click **`Update Website.command`** (or run `python3 scripts/update-site.py`).

The script then: checks the database → makes a verified backup → shows data-check warnings →
builds the new `data/coldex-data.js` → shows what changed → asks **"Publish to the LIVE site?"** →
commits only that file and pushes it to the **live** repo. GitHub Pages updates in a minute or two.

It stops without publishing if the database has unsaved edits, if the row count drops more than 5%,
if the git identity isn't a GitHub no-reply address, if you're in the SANDBOX folder, or if the live
site has changes this folder doesn't have yet. Options: `--no-push` (prepare only),
`--yes` (don't ask), `--force` (skip the row-drop stop).

## Trying design changes safely (the SANDBOX folder)

1. Open `Website Sample Finder SANDBOX` and edit `index.html` (open it in a browser to look; nothing is public).
2. Double-click **`Preview on Dev Site.command`**: it saves your changes as a snapshot, brings in any new data
   from the live site, and sends the result to the **test site**. The live site is not touched.
3. Happy with it? Double-click **`Go Live.command`**: it shows exactly what will change, asks first, then
   publishes to the **live site** and updates this folder to match.

Unhappy with an experiment? Ask Claude to reset the sandbox to the live version.
Each launcher stops if it is run from the wrong folder.

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
| `scripts/update-site.py` | The one-command data update (above). Live site, from the main folder only. |
| `scripts/sandbox.py` | `preview` (to the test site) and `golive` (to the live site), run from the SANDBOX folder. |
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
