#!/usr/bin/env python3
"""Sandbox helper: try design changes safely, preview them, then publish them.

Run these from the SANDBOX folder (the second copy of the project, on the 'sandbox' branch):

    python3 scripts/sandbox.py preview     # save your changes, send them to the TEST site
    python3 scripts/sandbox.py golive      # publish the sandbox to the LIVE site

Two GitHub sites, two remotes:
    dev   -> IceSamples/SampleFinder-dev   the TEST site (overwritten by every preview; nobody relies on it)
    live  -> IceSamples/SampleFinder       the REAL site

Nothing here touches the live site except 'golive', and that asks first.
"""
import argparse
import datetime
import subprocess
import sys

import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SANDBOX_BRANCH = "sandbox"
LIVE_BRANCH = "main"
TEST_URL = "https://icesamples.github.io/SampleFinder-dev/"
LIVE_URL = "https://icesamples.github.io/SampleFinder/"


def say(msg=""):
    print(msg, flush=True)


def die(msg):
    say(f"\nSTOPPED: {msg}")
    sys.exit(1)


def run(*args, cwd=ROOT):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def git(*args, cwd=ROOT):
    r = run(*args, cwd=cwd)
    if r.returncode != 0:
        die(f"git {' '.join(args)} failed:\n{(r.stderr or r.stdout).strip()}")
    return r.stdout.strip()


def main_folder():
    """Path of the folder where the live branch ('main') is checked out, if there is one."""
    for block in git("worktree", "list", "--porcelain").split("\n\n"):
        if f"branch refs/heads/{LIVE_BRANCH}" in block:
            return block.splitlines()[0].replace("worktree ", "", 1)
    return None


def ask(question, yes):
    if yes:
        return True
    if not sys.stdin.isatty():
        die("Not running in a terminal, so I can't ask. Use --yes to go ahead without asking.")
    try:
        return input(f"\n{question} [y/N] ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def preflight():
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != SANDBOX_BRANCH:
        mf = main_folder()
        die(f"This folder is on the '{branch}' branch. Sandbox tools only run in the SANDBOX folder "
            f"(branch '{SANDBOX_BRANCH}').\n"
            "Nothing was changed." + (f"\n(The live project folder is: {mf})" if mf else ""))
    email = git("config", "user.email")
    if not email.endswith("@users.noreply.github.com"):
        die(f"The git email here is '{email}', not a GitHub no-reply address. Nothing was changed.")
    for remote in ("dev", "live"):
        if run("remote", "get-url", remote).returncode != 0:
            die(f"No git remote named '{remote}' is set up in this folder.")


def fetch(remote):
    r = run("fetch", "-q", remote)
    if r.returncode != 0:
        die(f"Couldn't reach GitHub ({remote}):\n{(r.stderr or r.stdout).strip()}")


def bring_in_live_changes():
    """Merge anything new on the live site (e.g. data updates) into the sandbox, so they stay in step."""
    behind = git("rev-list", "--count", f"HEAD..live/{LIVE_BRANCH}")
    if behind == "0":
        return
    say(f"  The live site has {behind} newer change(s) (such as data updates); bringing them into the sandbox…")
    r = run("merge", "--no-edit", f"live/{LIVE_BRANCH}")
    if r.returncode != 0:
        run("merge", "--abort")
        die("Those live changes overlap with changes you made in the sandbox, so they can't be combined "
            "automatically.\nNothing was sent anywhere and the live site is untouched; your own changes are "
            "still saved in the sandbox. Ask Claude to help combine them.")


def preview(args):
    preflight()
    say("Preview on the TEST site")
    say("=" * 60)

    changes = [l for l in git("status", "--short").splitlines()]
    if changes:
        say("\nUnsaved changes in the sandbox folder:")
        for l in changes[:15]:
            say("  " + l)
        if len(changes) > 15:
            say(f"  … and {len(changes) - 15} more")
        if not ask("Save these as a snapshot so they can be previewed?", args.yes):
            die("Not saved, so nothing was sent. (Your files are untouched.)")
        git("add", "-A")
        git("commit", "-q", "-m", f"Sandbox snapshot ({datetime.date.today().isoformat()})")
        say("  saved.")

    fetch("live")
    fetch("dev")
    bring_in_live_changes()

    head = git("rev-parse", "HEAD")
    dev_head = run("rev-parse", f"dev/{LIVE_BRANCH}").stdout.strip()
    if head == dev_head:
        say("\nThe test site already shows exactly this. Nothing to send.")
        say(f"  {TEST_URL}")
        return
    remote_url = git("remote", "get-url", "dev")
    say(f"\nThis replaces whatever is on the TEST site ({remote_url}). The live site is not touched.")
    if not ask("Send the sandbox to the test site?", args.yes):
        say("\nNot sent. Your changes are saved in the sandbox.")
        return
    r = run("push", "--force-with-lease", "dev", f"HEAD:{LIVE_BRANCH}")
    if r.returncode != 0:
        die("The push to the test site failed:\n" + (r.stderr or r.stdout).strip())
    say(f"\nSent. The test site usually updates within a minute or two (hard refresh to see it):\n  {TEST_URL}")


def golive(args):
    preflight()
    say("Go LIVE")
    say("=" * 60)

    changes = git("status", "--short").splitlines()
    if changes:
        say("\nThe sandbox has unsaved changes:")
        for l in changes[:15]:
            say("  " + l)
        die("Run 'Preview on Dev Site' first. It saves these changes, and lets you look at them on the "
            "test site before they go live.")

    fetch("live")
    fetch("dev")
    bring_in_live_changes()

    ahead = git("log", "--format=%h %s", f"live/{LIVE_BRANCH}..HEAD").splitlines()
    if not ahead:
        say("\nThe live site already has everything in the sandbox. Nothing to publish.")
        return
    say(f"\nThese saved changes are not on the live site yet ({len(ahead)}):")
    for l in ahead[:12]:
        say("  " + l)
    if len(ahead) > 12:
        say(f"  … and {len(ahead) - 12} more")
    say("\nFiles that would change on the live site:")
    for l in git("diff", "--stat", f"live/{LIVE_BRANCH}", "HEAD").splitlines()[-12:]:
        say("  " + l)
    if git("rev-parse", "HEAD") != run("rev-parse", f"dev/{LIVE_BRANCH}").stdout.strip():
        say("\n  note: the test site is not showing exactly this version yet (run 'Preview on Dev Site' to look first).")

    remote_url = git("remote", "get-url", "live")
    say(f"\nThis changes the LIVE site that everyone sees: {remote_url}")
    if not ask("Publish to the LIVE site now?", args.yes):
        say("\nNot published. Nothing changed on the live site.")
        return
    r = run("push", "live", f"HEAD:{LIVE_BRANCH}")
    if r.returncode != 0:
        die("The push to the live site failed (nothing was changed there):\n" + (r.stderr or r.stdout).strip())

    # keep the main project folder in step with what is now live
    mf = main_folder()
    if mf:
        run("fetch", "-q", "live", cwd=mf)
        m = run("merge", "--ff-only", f"live/{LIVE_BRANCH}", cwd=mf)
        if m.returncode != 0:
            say(f"\n  note: couldn't update the main project folder automatically ({mf}).\n"
                f"  Run there:  git pull live {LIVE_BRANCH}")
    say(f"\nPublished to the live site. GitHub Pages usually updates within a minute or two "
        f"(hard refresh, or a private window, to see it):\n  {LIVE_URL}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["preview", "golive"])
    ap.add_argument("--yes", action="store_true", help="don't ask before acting")
    args = ap.parse_args()
    {"preview": preview, "golive": golive}[args.command](args)


if __name__ == "__main__":
    main()
