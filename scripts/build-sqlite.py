#!/usr/bin/env python3
"""Build the SQLite master database from a Supabase export.

    python3 scripts/build-sqlite.py private/supabase-export.json
    python3 scripts/build-sqlite.py private/supabase-export.json --out private/coldex.sqlite

The export is a single JSON object: {"cores": [...rows...], "samples": [...], ...} produced by
the query in the migration instructions (one `to_jsonb(row)` per table row). A .csv file that
holds that JSON in its single cell (what the Supabase SQL editor downloads) also works.

Safety:
  * It REFUSES to overwrite an existing database (that file is your master). Use a new name,
    or pass --force only when you are certain.
  * It builds in a temporary file and only moves it into place if every check passes.

Checks after loading: row counts match the export, foreign keys and integrity are clean, and
every subsample_id rebuilt by the new trigger equals the one that came from Supabase.
"""
import argparse
import csv
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Parents before children, so foreign keys are satisfied while loading.
TABLE_ORDER = ["cores", "cores_ALLALHILLS", "requests", "samples", "subsamples",
               "subsamples_stage", "temp_available_samples"]


def load_export(path):
    csv.field_size_limit(sys.maxsize)
    if path.lower().endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        if len(rows) < 2 or not rows[1]:
            sys.exit(f"{path}: expected a header row and one data row")
        text = rows[1][0]
    else:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    data = json.loads(text)
    if not isinstance(data, dict):
        sys.exit("The export must be a JSON object with one array per table.")
    return data


def to_sqlite_value(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("export", help="Supabase export (.json, or the .csv the SQL editor downloads)")
    ap.add_argument("--out", default=os.path.join(ROOT, "private", "coldex.sqlite"))
    ap.add_argument("--schema", default=os.path.join(HERE, "schema.sql"))
    ap.add_argument("--force", action="store_true", help="overwrite an existing database file")
    args = ap.parse_args()

    if os.path.exists(args.out) and not args.force:
        sys.exit(f"Refusing to overwrite {args.out}\n"
                 f"That file may be your master database. Choose another --out name.")

    data = load_export(args.export)
    unknown = [t for t in data if t not in TABLE_ORDER]
    if unknown:
        sys.exit(f"Export contains tables this script doesn't know about: {unknown}")

    tmp = args.out + ".building"
    for p in (tmp, tmp + "-journal"):
        if os.path.exists(p):
            os.remove(p)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    con = sqlite3.connect(tmp)
    con.executescript(open(args.schema, encoding="utf-8").read())
    con.execute("PRAGMA foreign_keys = ON")

    problems = []
    expected = {}
    for table in TABLE_ORDER:
        rows = data.get(table)
        if rows is None:
            problems.append(f"export has no '{table}' table")
            continue
        cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
        extra = sorted({k for r in rows for k in r} - set(cols))
        if extra:
            problems.append(f"{table}: export has columns the schema lacks: {extra}")
            continue
        if not rows:                       # nothing to load (e.g. an empty staging table)
            expected[table] = 0
            continue
        used = [c for c in cols if any(c in r for r in rows)]
        sql = f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in used)}) ' \
              f'VALUES ({", ".join("?" for _ in used)})'
        try:
            with con:
                con.executemany(sql, [[to_sqlite_value(r.get(c)) for c in used] for r in rows])
        except sqlite3.Error as e:
            problems.append(f"{table}: load failed: {e}")
            continue
        expected[table] = len(rows)

    # ---- verification -------------------------------------------------------------------
    print(f"{'table':26s} {'in export':>10s} {'in sqlite':>10s}")
    for table in TABLE_ORDER:
        n = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        ok = expected.get(table) == n
        print(f"{table:26s} {expected.get(table, '-'):>10} {n:>10}  {'ok' if ok else 'MISMATCH'}")
        if not ok:
            problems.append(f"{table}: row count differs")

    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        problems.append(f"{len(fk)} foreign-key violations, e.g. {fk[:3]}")
    integ = con.execute("PRAGMA integrity_check").fetchone()[0]
    if integ != "ok":
        problems.append(f"integrity_check: {integ}")

    if "subsamples" in data:
        original = {r["id"]: r.get("subsample_id") for r in data["subsamples"]}
        diff = [(i, original[i], s) for i, s in con.execute("SELECT id, subsample_id FROM subsamples")
                if original.get(i) != s]
        print(f"\nsubsample_id rebuilt by trigger vs Supabase: {len(diff)} differences")
        if diff:
            problems.append(f"{len(diff)} subsample_ids differ, e.g. {diff[:3]}")

    print("\nData checks (informational, from v_data_checks):")
    for problem, n in con.execute("SELECT problem, COUNT(*) FROM v_data_checks GROUP BY problem ORDER BY 2 DESC"):
        print(f"  {n:6d}  {problem}")

    con.close()
    if problems:
        print("\nNOT SAVED. Problems:")
        for p in problems:
            print("  -", p)
        sys.exit(1)

    if os.path.exists(args.out):
        os.remove(args.out)
    os.replace(tmp, args.out)
    print(f"\nBuilt {args.out}  ({os.path.getsize(args.out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
