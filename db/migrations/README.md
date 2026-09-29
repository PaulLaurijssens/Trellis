# Migrations

One file per change of the data shape: `NNN_short_name.cypher`, numbers in order, never reused.
The API applies pending files at start (`app/migrate.py`) and records the number on the
`:Schema {id:"trellis"}` node. Write every file so it can run twice without harm (`MERGE`,
`SET`, `IF NOT EXISTS`). Make a backup before you update: *My profile → Settings → Make a backup now*.

Check by hand: `docker compose exec api python -m app.migrate --dry-run`.
