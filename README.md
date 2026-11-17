# COLDEX Sample Finder

A static website: `index.html` + `allan-hills-map.png` + `data/coldex-data.js`.
There is no server or live database connection. The page reads a snapshot of the
COLDEX database from `data/coldex-data.js` and does all searching in the browser.

## Updating the data

After the database is updated (new field season, CPL, etc.):

```bash
node scripts/export-data.mjs      # needs Node 18+; takes about a minute
git add data/coldex-data.js
git commit -m "Update data snapshot"
git push
```

The script reads through the same public database functions the site used to call,
so the snapshot contains only what was already public. The `requests` table and the
staging/temp tables are never read. The page shows the snapshot date at the bottom.

Request IDs are published as the bare request code only (e.g. `C_2026_015`). Anything
the database appends after the code (requester names, institutions, notes) is removed
by the export script, so it never reaches the public file. Keep your request tracking
in the database as before; only the `C_YYYY_NNN` part is ever published.

## Trying it locally

Open `index.html` in a browser. No server is needed.

## Adding a new core to the map

The orange/blue dots and hover zones are tied to the map image. A new core needs its
code added to the matching zone in `MAP_HOTSPOTS` (and `MAP_DOTS`) in `index.html`.
