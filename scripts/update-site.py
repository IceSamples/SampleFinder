#!/usr/bin/env python3
"""Update the website from the SQLite master database — one command.

    python3 scripts/update-site.py            # does everything, asks before publishing
    python3 scripts/update-site.py --no-push  # prepare the new data file, don't commit or push
    python3 scripts/update-site.py --yes      # don't ask before publishing

What it does, in order:
  1. Checks the database is saved (no pending edits in DB Browser) and healthy.
  2. Makes a verified backup (private/backups/).
  3. Shows the data-check warnings (informational).
  4. Builds the new website data (data/coldex-data.js) from the database.
  5. Shows exactly what changed compared with the data currently on the website.
  6. Asks "Publish?" and then commits ONLY data/coldex-data.js and pushes it to the LIVE site
     (the GitHub repo named "live"). Run it from the main project folder (branch "main"), not
     from the SANDBOX folder.

It stops, changing nothing public, if something looks wrong (for example, a big drop in rows,
or a git identity that is not a GitHub no-reply address).
"""
import argparse
import collections
import datetime
import json
import os
import sqlite3
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA_FILE = os.path.join(ROOT, "data", "coldex-data.js")
PUBLISH_REMOTE = "live"      # the real site: github.com/IceSamples/SampleFinder
PUBLISH_BRANCH = "main"


def say(msg=""):
    print(msg, flush=True)


def step(n, title):
    say(f"\n[{n}/6] {title}")


def die(msg):
    say(f"\nSTOPPED: {msg}")
    sys.exit(1)


def git(*args, check=True):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        die(f"git {' '.join(args)} failed:\n{r.stderr.strip() or r.stdout.strip()}")
    return r.stdout.strip()


def load_snapshot(path=None, text=None):
    """Read a coldex-data.js file (or its text) back into Python."""
    raw = text if text is not None else open(path, encoding="utf-8").read()
    body = raw[raw.index("window.COLDEX_DATA = ") + len("window.COLDEX_DATA = "):].rstrip().rstrip(";")
    for k in ("generated", "cores", "samples", "subsamples"):
        body = body.replace(f"\n  {k}:", f'\n  "{k}":')
    return json.loads(body)


def canon(o):
    return json.dumps(o, sort_keys=True)


def compare(old, new):
    """Return a list of printable summary lines and whether anything changed."""
    lines, changed = [], False
    for table, key in (("cores", "core_code"), ("samples", "record_id")):
        a = {r[key]: canon(r) for r in old[table]}
        b = {r[key]: canon(r) for r in new[table]}
        added = [k for k in b if k not in a]
        removed = [k for k in a if k not in b]
        edited = [k for k in a if k in b and a[k] != b[k]]
        if added or removed or edited:
            changed = True
        lines.append(f"  {table:11s} {len(a):5d} -> {len(b):5d}   +{len(added)} new, -{len(removed)} removed, {len(edited)} edited")
        for label, ks in (("new", added), ("removed", removed), ("edited", edited)):
            if ks:
                shown = ", ".join(sorted(ks)[:6]) + (f", … ({len(ks)} total)" if len(ks) > 6 else "")
                lines.append(f"                {label}: {shown}")
    a = collections.Counter(canon(r) for r in old["subsamples"])
    b = collections.Counter(canon(r) for r in new["subsamples"])
    plus, minus = sum((b - a).values()), sum((a - b).values())
    if plus or minus:
        changed = True
    lines.append(f"  {'subsamples':11s} {len(old['subsamples']):5d} -> {len(new['subsamples']):5d}   "
                 f"{plus} new/changed rows, {minus} removed/replaced rows")
    return lines, changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=os.path.join(ROOT, "private", "coldex.sqlite"))
    ap.add_argument("--no-push", action="store_true", help="prepare the data file but don't commit or push")
    ap.add_argument("--yes", action="store_true", help="publish without asking")
    ap.add_argument("--force", action="store_true", help="skip the 'big drop in rows' safety stop")
    args = ap.parse_args()

    say("COLDEX website update")
    say("=" * 60)

    # ---- 0. right place? (publishing is only done from the main folder) --------------------
    if not args.no_push:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        if branch != PUBLISH_BRANCH:
            main_dir = ""
            for block in git("worktree", "list", "--porcelain").split("\n\n"):
                if f"branch refs/heads/{PUBLISH_BRANCH}" in block:
                    main_dir = block.splitlines()[0].replace("worktree ", "", 1)
            die(f"This folder is on the '{branch}' branch (the SANDBOX copy), not the live one.\n"
                "Data updates are published from the main project folder" +
                (f":\n  {main_dir}" if main_dir else ".") +
                "\nUse 'Preview on Dev Site' / 'Go Live' here for design experiments.")
        if subprocess.run(["git", "remote", "get-url", PUBLISH_REMOTE], cwd=ROOT, capture_output=True).returncode != 0:
            die(f"No git remote named '{PUBLISH_REMOTE}' (the live site) is set up in this folder.")

    # ---- 1. database saved and healthy -----------------------------------------------------
    step(1, "Checking the database")
    if not os.path.exists(args.db):
        die(f"Database not found: {args.db}")
    for suffix in ("-journal", "-wal"):
        if os.path.exists(args.db + suffix):
            die("The database has changes that aren't saved yet (DB Browser is probably open with edits).\n"
                "In DB Browser click 'Write Changes' (Cmd+S), or close the app, then run this again.")
    con = sqlite3.connect(f"file:{os.path.abspath(args.db)}?mode=ro", uri=True)
    if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        die("The database failed its integrity check. Restore a backup from private/backups/.")
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    if fk:
        die(f"{len(fk)} records point at something that doesn't exist (e.g. {fk[:2]}). Fix these first.")
    say("  database is saved, healthy, and all links between tables are valid")

    # ---- 2. backup -----------------------------------------------------------------------------
    step(2, "Backing up")
    r = subprocess.run([sys.executable, os.path.join(HERE, "backup-db.py"), "--db", args.db],
                       capture_output=True, text=True)
    if r.returncode != 0:
        die("Backup failed, so nothing was changed:\n" + (r.stdout + r.stderr).strip())
    say("  " + r.stdout.strip().splitlines()[0])

    # ---- 3. data checks ---------------------------------------------------------------------------
    step(3, "Data checks (informational)")
    rows = con.execute("SELECT problem, COUNT(*) FROM v_data_checks GROUP BY problem ORDER BY 2 DESC").fetchall()
    con.close()
    if rows:
        for problem, n in rows:
            say(f"  {n:5d}  {problem}")
        say("  (open the v_data_checks view in DB Browser to see which records)")
    else:
        say("  no problems found")

    # ---- 4. build the new data file --------------------------------------------------------------
    step(4, "Building the website data")
    # Compare against the version last SAVED in git (what the website is showing), not just the file on disk:
    # a file written by an earlier run that was never published must still count as a pending change.
    shown = subprocess.run(["git", "show", "HEAD:data/coldex-data.js"], cwd=ROOT, capture_output=True, text=True)
    if shown.returncode == 0:
        old = load_snapshot(text=shown.stdout)
    elif os.path.exists(DATA_FILE):
        old = load_snapshot(DATA_FILE)
    else:
        old = None
    tmp = DATA_FILE + ".new"
    r = subprocess.run([sys.executable, os.path.join(HERE, "export-from-sqlite.py"), "--db", args.db, "--out", tmp],
                       capture_output=True, text=True)
    if r.returncode != 0:
        die("Export failed:\n" + (r.stdout + r.stderr).strip())
    for line in r.stdout.strip().splitlines():
        if line.startswith("warning"):
            say("  " + line)
    new = load_snapshot(tmp)
    say(f"  {len(new['cores'])} cores, {len(new['samples'])} samples, {len(new['subsamples'])} subsamples")

    # ---- 5. what changed -----------------------------------------------------------------------------
    step(5, "What changed compared with the website now")
    if old is None:
        lines, changed = ["  (no previous data file)"], True
    else:
        for table in ("samples", "subsamples"):
            before, after = len(old[table]), len(new[table])
            if before and after < before * 0.95 and not args.force:
                os.remove(tmp)
                die(f"'{table}' would drop from {before} to {after} rows (more than 5%).\n"
                    "That usually means a mistake. Check the database; use --force only if it is intentional.")
        lines, changed = compare(old, new)
    for line in lines:
        say(line)
    if not changed:
        os.remove(tmp)
        say("\nThe website data is already up to date. Nothing to publish.")
        return
    os.replace(tmp, DATA_FILE)
    say(f"\n  wrote {os.path.relpath(DATA_FILE, ROOT)}")

    if args.no_push:
        say("\n--no-push: stopped here. To publish later, run this script again without --no-push.")
        return

    # ---- 6. publish --------------------------------------------------------------------------------------
    step(6, "Publish to GitHub")
    email = git("config", "user.email")
    name = git("config", "user.name")
    remote = git("remote", "get-url", PUBLISH_REMOTE)
    if not email.endswith("@users.noreply.github.com"):
        die(f"The git email for this project is '{email}', not a GitHub no-reply address.\n"
            "Nothing was published. (The data file is updated but not committed.)")
    fetch = subprocess.run(["git", "fetch", "-q", PUBLISH_REMOTE, PUBLISH_BRANCH], cwd=ROOT, capture_output=True, text=True)
    if fetch.returncode != 0:
        die("Couldn't reach GitHub to check the live site:\n" + (fetch.stderr or fetch.stdout).strip() +
            "\nNothing was published. (The data file is updated but not committed.)")
    live_ref = f"{PUBLISH_REMOTE}/{PUBLISH_BRANCH}"
    behind = git("rev-list", "--count", f"HEAD..{live_ref}")
    if behind != "0":
        die(f"The live site has {behind} change(s) this folder doesn't have yet.\n"
            f"Run:  git pull {PUBLISH_REMOTE} {PUBLISH_BRANCH}   (or ask Claude), then run this again.")
    others = [l for l in git("status", "--short").splitlines() if "data/coldex-data.js" not in l]
    if others:
        say("  note: other files have uncommitted changes; they will NOT be included:")
        for l in others[:6]:
            say("    " + l)
    waiting = git("log", "--format=%h %s", f"{live_ref}..HEAD").splitlines()
    if waiting:
        say("  note: these earlier saved changes have not gone live yet and WILL be published too:")
        for l in waiting[:8]:
            say("    " + l)
    say(f"  will commit data/coldex-data.js as: {name} <{email}>")
    say(f"  and publish to the LIVE site: {remote}")
    if not args.yes:
        if not sys.stdin.isatty():
            die("Not running in a terminal, so I can't ask. Use --yes to publish without asking.")
        try:
            answer = input("\nPublish this update to the LIVE site now? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            say("\nNot published. The data file is updated on your computer; run this again to publish.")
            return

    today = datetime.date.today().isoformat()
    git("add", "data/coldex-data.js")
    git("commit", "-m", f"Update data snapshot ({today})\n\n" + "\n".join(l.strip() for l in lines))
    out = subprocess.run(["git", "push", PUBLISH_REMOTE, f"HEAD:{PUBLISH_BRANCH}"], cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        die("The commit was made locally but the push failed:\n" + (out.stderr or out.stdout).strip() +
            f"\nFix the problem, then run: git push {PUBLISH_REMOTE} {PUBLISH_BRANCH}")
    say("\nPublished to the live site. GitHub Pages usually updates within a minute or two "
        "(hard refresh, or use a private window, to see it).")


if __name__ == "__main__":
    main()
