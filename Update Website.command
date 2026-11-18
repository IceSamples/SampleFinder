#!/bin/zsh
# Double-click this file to update the website from your SQLite database.
# (Make sure you've clicked "Write Changes" in DB Browser first.)
cd "$(dirname "$0")" || exit 1
python3 scripts/update-site.py "$@"
echo
read -k 1 "?Press any key to close this window…"
