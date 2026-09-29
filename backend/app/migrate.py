"""Versioned data migrations: db/migrations/NNN_<slug>.cypher, applied once, in order, at API start.

A (:Schema {id:"trellis", version}) node remembers the last applied number. Files with a higher
number run in order; each file's statements run first, then the version is written. If a file
fails halfway, the version stays at the previous number and the next start retries that file, so
every migration must be safe to run twice (MERGE, SET, IF NOT EXISTS).

    python -m app.migrate --dry-run     # list pending files, change nothing
    python -m app.migrate               # apply pending files
"""
import logging
import os
import re
import sys
from . import graph

DIR = os.getenv("MIGRATIONS_DIR", "/import/migrations")
NAME = re.compile(r"^(\d{3})_[a-z0-9_-]+\.cypher$")
log = logging.getLogger("uvicorn.error")


def current() -> int:
    rows = graph.run("MATCH (s:Schema {id:'trellis'}) RETURN s.version AS v")
    return int(rows[0]["v"] or 0) if rows else 0


def files(directory: str = DIR) -> list[tuple[int, str]]:
    """All migration files as (number, path), sorted. Two files with one number is an error."""
    found = []
    if not os.path.isdir(directory):
        return found
    for name in sorted(os.listdir(directory)):
        m = NAME.match(name)
        if m:
            found.append((int(m.group(1)), os.path.join(directory, name)))
    numbers = [n for n, _ in found]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Two migration files share a number: " + ", ".join(p for _, p in found))
    return found


def pending(directory: str = DIR) -> list[tuple[int, str]]:
    version = current()
    return [(n, p) for n, p in files(directory) if n > version]


def apply(directory: str = DIR) -> list[str]:
    """Apply every pending file. Returns the names applied."""
    applied = []
    for number, path in pending(directory):
        with open(path) as f:
            statements = graph._split_cypher(f.read())
        for stmt in statements:
            graph.run(stmt)
        graph.run("MERGE (s:Schema {id:'trellis'}) SET s.version=$v, s.updated_at=$now", v=number, now=graph._now())
        applied.append(os.path.basename(path))
        log.info("migration applied: %s", os.path.basename(path))
    return applied


if __name__ == "__main__":
    todo = pending()
    if "--dry-run" in sys.argv:
        print(f"schema version {current()}; pending: " + (", ".join(os.path.basename(p) for _, p in todo) or "none"))
    else:
        done = apply()
        print("applied: " + (", ".join(done) or "nothing") + f"; schema version now {current()}")
