#!/usr/bin/env bash
# Restore a Trellis backup into an EMPTY database.   ./scripts/restore.sh 20260927T031000Z
# Stops the app, wipes the graph, loads backups/trellis-<stamp>.cypher.gz, restores the lesson files,
# starts the app. Your current data is replaced: make a fresh backup first (Settings -> Backups).
set -euo pipefail
STAMP="${1:?usage: scripts/restore.sh <stamp>   (see: ls backups)}"
cd "$(dirname "$0")/.."
GRAPH="backups/trellis-$STAMP.cypher.gz"; ART="backups/artifacts-$STAMP.tar.gz"
[ -f "$GRAPH" ] || { echo "no such backup: $GRAPH"; exit 1; }
source .env
echo "1/4 stopping the app (the database keeps running)"
docker compose stop api frontend author web >/dev/null
echo "2/4 wiping the graph"
CS() { docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain "$@"; }
# All constraints and indexes in one call (APOC), then the nodes in batches: works for big graphs too.
CS "CALL apoc.schema.assert({}, {}, true) YIELD label RETURN count(*)" >/dev/null
CS "MATCH (n) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 1000 ROWS" >/dev/null
[ "$(CS 'MATCH (n) RETURN count(n)' | tail -1)" = "0" ] || { echo "the graph is not empty after the wipe; stopping"; exit 1; }
echo "3/4 loading $GRAPH"
gunzip -c "$GRAPH" | docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain --fail-fast >/dev/null
if [ -f "$ART" ]; then
  echo "    restoring lesson files"
  # As the app's own user: the folder belongs to it, so no chown (the API has no such capability).
  docker compose run --rm --no-deps -T --entrypoint sh -v "$PWD/$ART:/restore.tar.gz:ro" api -c \
    'rm -rf /artifacts/* /artifacts/.[!.]* 2>/dev/null; tar -C /artifacts -xzf /restore.tar.gz --no-same-owner' >/dev/null
fi
echo "4/4 starting the app"
docker compose up -d >/dev/null
COUNT=$(docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain "MATCH (n) RETURN count(n)" | tail -1)
echo "done: $COUNT nodes. Open http://localhost:8080 and log in with the password from before the backup."
