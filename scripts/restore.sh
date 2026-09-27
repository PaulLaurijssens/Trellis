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
docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "MATCH (n) DETACH DELETE n" >/dev/null
docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain "SHOW CONSTRAINTS YIELD name RETURN name" | tail -n +2 | while read -r c; do
  [ -n "$c" ] && docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "DROP CONSTRAINT \`${c//\"/}\` IF EXISTS" >/dev/null; done
docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain "SHOW INDEXES YIELD name, type WHERE type <> 'LOOKUP' RETURN name" | tail -n +2 | while read -r i; do
  [ -n "$i" ] && docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "DROP INDEX \`${i//\"/}\` IF EXISTS" >/dev/null; done
echo "3/4 loading $GRAPH"
gunzip -c "$GRAPH" | docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain >/dev/null
if [ -f "$ART" ]; then
  echo "    restoring lesson files"
  docker compose run --rm --no-deps -T --user root --entrypoint sh -v "$PWD/$ART:/restore.tar.gz:ro" api -c \
    'rm -rf /artifacts/* && tar -C /artifacts -xzf /restore.tar.gz && chown -R 10002:10002 /artifacts' >/dev/null
fi
echo "4/4 starting the app"
docker compose up -d >/dev/null
COUNT=$(docker compose exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain "MATCH (n) RETURN count(n)" | tail -1)
echo "done: $COUNT nodes. Open http://localhost:8080 and log in with the password from before the backup."
