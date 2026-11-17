#!/usr/bin/env python3
"""Make a dated, verified backup of the SQLite master database.

    python3 scripts/backup-db.py
    python3 scripts/backup-db.py --db private/coldex.sqlite --dir private/backups

Uses SQLite's own online-backup call, so it is safe even if the database is open in DB Browser
(though unsaved edits in the app are not included until you click "Write Changes").
The copy is checked (integrity + row counts) before it is kept. Backups are never deleted
automatically.

Backups hold private request data (names, emails): keep them out of git and out of anything public.
"""
import argparse
import datetime
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def counts(con):
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in sorted(tables)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "private", "coldex.sqlite"))
    ap.add_argument("--dir", default=os.path.join(ROOT, "private", "backups"))
    args = ap.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"Database not found: {args.db}")
    os.makedirs(args.dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    final = os.path.join(args.dir, f"coldex-{stamp}.sqlite")
    tmp = final + ".partial"

    src = sqlite3.connect(f"file:{os.path.abspath(args.db)}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp)
    src.backup(dst)
    dst.close()

    check = sqlite3.connect(tmp)
    ok = check.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    same = counts(check) == counts(src)
    check.close()
    src.close()
    if not (ok and same):
        os.remove(tmp)
        sys.exit("Backup FAILED verification and was discarded.")
    os.replace(tmp, final)
    print(f"Backup saved: {final}  ({os.path.getsize(final) / 1024:.0f} KB, verified)")
    n = len([f for f in os.listdir(args.dir) if f.endswith('.sqlite')])
    print(f"{n} backup(s) in {args.dir}")


if __name__ == "__main__":
    main()
