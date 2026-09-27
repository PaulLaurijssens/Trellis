"""Backups from inside the app: no cron on the host, no Docker socket, no downtime.

A backup is two files with one timestamp in BACKUP_DIR:
  trellis-<stamp>.jsonl.gz    the whole graph as JSON lines (APOC streaming export: one line per node
                              or relationship, embeddings included), made while the app runs;
  artifacts-<stamp>.tar.gz    the lesson files and shared components (content-addressed, so a graph
                              that references a lesson always finds it in the archive of the same stamp).
Why JSON and not Cypher: a Cypher dump puts every embedding (3072 numbers) as a literal in its own
statement, and the database caches each distinct statement; loading a few hundred of those exhausted
a 1 GB heap. restore.py loads the JSON with parameters instead: one cached statement, small batches.
Restore = `scripts/restore.sh <stamp>` (README). The nightly run happens in the API process
(main.startup); the owner can also press the button in Settings."""
import asyncio
import gzip
import io
import json
import logging
import os
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

from . import graph

log = logging.getLogger("uvicorn.error")
BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "/backups"))
ARTIFACT_DIR = Path(os.getenv("TEACH_ARTIFACT_DIR", "/artifacts"))
KEEP = int(os.getenv("BACKUP_KEEP", "14"))
NIGHTLY_HOUR_UTC = int(os.getenv("BACKUP_HOUR_UTC", "3"))
_lock = asyncio.Lock()


def available() -> bool:
    return BACKUP_DIR.is_dir() and os.access(BACKUP_DIR, os.W_OK)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def export_graph() -> tuple[str, dict]:
    rows = graph.run('''CALL apoc.export.json.all(null, {stream:true, batchSize:500})
        YIELD nodes, relationships, properties, data RETURN nodes, relationships, properties, data''')
    if not rows:
        raise RuntimeError("APOC export returned nothing")
    text = "".join(r["data"] for r in rows if r["data"])      # streamed in batches; counts are running totals
    return text, {k: max(int(r[k] or 0) for r in rows) for k in ("nodes", "relationships", "properties")}


def create() -> dict:
    """Synchronous; call through run_in_thread from async code."""
    if not available():
        raise RuntimeError("Backup folder is not writable")
    stamp = _stamp()
    started = time.monotonic()
    cypher, counts = export_graph()
    graph_path = BACKUP_DIR / f"trellis-{stamp}.jsonl.gz"
    tmp = graph_path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        f.write(cypher)
    tmp.rename(graph_path)
    result = {"stamp": stamp, "graph_bytes": graph_path.stat().st_size, **counts, "artifacts_bytes": 0}
    (BACKUP_DIR / f"trellis-{stamp}.json").write_text(json.dumps({"stamp": stamp, "format": "apoc-json-lines-1", **counts}))
    if ARTIFACT_DIR.is_dir():
        art_path = BACKUP_DIR / f"artifacts-{stamp}.tar.gz"
        tmp = art_path.with_suffix(".tmp")
        with tarfile.open(tmp, "w:gz") as tar:
            tar.add(ARTIFACT_DIR, arcname=".")
        tmp.rename(art_path)
        result["artifacts_bytes"] = art_path.stat().st_size
    result["seconds"] = round(time.monotonic() - started, 1)
    rotate()
    log.info("backup %s: %s nodes, %s rels, %.1f MB graph, %.1f MB artifacts, %ss", stamp, counts["nodes"], counts["relationships"],
             result["graph_bytes"] / 1e6, result["artifacts_bytes"] / 1e6, result["seconds"])
    return result


def rotate():
    for pattern in ("trellis-*.jsonl.gz", "trellis-*.json", "artifacts-*.tar.gz"):
        files = sorted(BACKUP_DIR.glob(pattern), key=lambda p: p.name, reverse=True)
        for old in files[KEEP:]:
            old.unlink(missing_ok=True)


def listing() -> list[dict]:
    out = {}
    if not BACKUP_DIR.is_dir():
        return []
    for path in BACKUP_DIR.iterdir():
        name = path.name
        if name.startswith("trellis-") and name.endswith(".jsonl.gz"):
            out.setdefault(name[8:-9], {})["graph_bytes"] = path.stat().st_size
        elif name.startswith("artifacts-") and name.endswith(".tar.gz"):
            out.setdefault(name[10:-7], {})["artifacts_bytes"] = path.stat().st_size
    return [{"stamp": stamp, **info} for stamp, info in sorted(out.items(), reverse=True)]


def read_lines(stamp: str):
    """Yields the parsed JSON lines of a backup."""
    with gzip.open(BACKUP_DIR / f"trellis-{stamp}.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def verify(stamp: str) -> dict:
    """Reads the archive back: the graph file parses, and every published lesson version in it exists in
    the artifact archive of the same stamp with the right hash."""
    import hashlib
    graph_path = BACKUP_DIR / f"trellis-{stamp}.jsonl.gz"
    art_path = BACKUP_DIR / f"artifacts-{stamp}.tar.gz"
    if not graph_path.is_file():
        raise FileNotFoundError(stamp)
    nodes = rels = 0; hashes = set()
    for item in read_lines(stamp):
        if item.get("type") == "node":
            nodes += 1
            if "LessonVersion" in item.get("labels", []) and item["properties"].get("status") == "published":
                hashes.add(item["properties"].get("content_hash"))
        elif item.get("type") == "relationship":
            rels += 1
    missing, bad = [], []
    if hashes:
        if not art_path.is_file():
            raise FileNotFoundError(f"artifacts-{stamp}.tar.gz")
        with tarfile.open(art_path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.isfile() and m.name.endswith("/index.html")]
            for h in hashes:
                found = next((m for m in members if f"/{h}/index.html" in m.name), None)
                if not found:
                    missing.append(h); continue
                if hashlib.sha256(tar.extractfile(found).read()).hexdigest() != h:
                    bad.append(h)
    return {"stamp": stamp, "nodes": nodes, "relationships": rels, "lesson_versions": len(hashes), "missing": missing,
            "hash_mismatch": bad, "ok": nodes > 0 and not missing and not bad}


async def nightly_loop():
    """Runs once a day at NIGHTLY_HOUR_UTC. Errors are logged, never fatal."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=NIGHTLY_HOUR_UTC, minute=10, second=0, microsecond=0)
        if target <= now:
            target = target.replace(day=now.day) + __import__("datetime").timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        if available() and os.getenv("BACKUP_NIGHTLY", "true").lower() != "false":
            try:
                async with _lock:
                    await asyncio.to_thread(create)
            except Exception as exc:
                log.warning("nightly backup failed: %s", exc)
