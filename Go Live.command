#!/bin/zsh
# Double-click to publish the sandbox to the LIVE site. It asks before changing anything.
# Run this from the SANDBOX folder.
cd "$(dirname "$0")" || exit 1
python3 scripts/sandbox.py golive "$@"
echo
read -k 1 "?Press any key to close this window…"
