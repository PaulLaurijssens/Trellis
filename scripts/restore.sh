#!/usr/bin/env bash
# Restore a Trellis backup, replacing EVERYTHING in this install.   ./scripts/restore.sh 20260927T031000Z
# The files come from backups/ (trellis-<stamp>.jsonl.gz + artifacts-<stamp>.tar.gz). Make a fresh
# backup first if the current data matters (My profile -> Settings -> Make a backup now).
set -euo pipefail
STAMP="${1:?usage: scripts/restore.sh <stamp>   (see: ls backups)}"
cd "$(dirname "$0")/.."
[ -f "backups/trellis-$STAMP.jsonl.gz" ] || { echo "no such backup: backups/trellis-$STAMP.jsonl.gz"; exit 1; }
echo "stopping the app (the database keeps running)"
docker compose stop api frontend author web >/dev/null
docker compose run --rm --no-deps -T api python -m app.restore "$STAMP"
echo "starting the app"
docker compose up -d >/dev/null
echo "Open http://localhost:8080 and log in with the password from the time of the backup."
