#!/bin/zsh
# Double-click to send your SANDBOX changes to the TEST site (the live site is not touched).
# Run this from the SANDBOX folder.
cd "$(dirname "$0")" || exit 1
python3 scripts/sandbox.py preview "$@"
echo
read -k 1 "?Press any key to close this window…"
