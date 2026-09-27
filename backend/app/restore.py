"""Restore a backup into THIS database, replacing everything.
    docker compose run --rm --no-deps api python -m app.restore <stamp>      (scripts/restore.sh does this)
Loads the JSON lines with parameters in small batches, so embeddings never become statement literals."""
import sys
import tarfile
import time
from collections import defaultdict
from pathlib import Path

from . import backup, graph


def wipe():
    graph.run("CALL apoc.schema.assert({}, {}, true) YIELD label RETURN count(*)")
    graph.run("MATCH (n) CALL { WITH n DETACH DELETE n } IN TRANSACTIONS OF 1000 ROWS")
    left = graph.run("MATCH (n) RETURN count(n) AS n")[0]["n"]
    if left:
        raise RuntimeError(f"{left} nodes left after the wipe")


def load(stamp: str) -> dict:
    nodes_by_labels, rels_by_type, dims = defaultdict(list), defaultdict(list), set()
    for item in backup.read_lines(stamp):
        if item.get("type") == "node":
            props = item.get("properties") or {}
            if isinstance(props.get("embedding"), list):
                dims.add(len(props["embedding"]))
            nodes_by_labels[tuple(sorted(item.get("labels") or ["Unlabelled"]))].append({"iid": str(item["id"]), "props": props})
        elif item.get("type") == "relationship":
            rels_by_type[item["label"]].append({"start": str(item["start"]["id"]), "end": str(item["end"]["id"]), "props": item.get("properties") or {}})
    graph.run("CREATE INDEX trellis_restore_iid IF NOT EXISTS FOR (n:_Restore) ON (n._iid)")
    n = 0
    for labels, rows in nodes_by_labels.items():
        label_str = "".join(f"`{l}`:" for l in labels).rstrip(":")
        for i in range(0, len(rows), 200):
            graph.run(f"UNWIND $rows AS r CREATE (x:{label_str}:_Restore) SET x = r.props, x._iid = r.iid", rows=rows[i:i + 200])
            n += len(rows[i:i + 200])
    r = 0
    for rel_type, rows in rels_by_type.items():
        for i in range(0, len(rows), 500):
            graph.run(f"UNWIND $rows AS r MATCH (a:_Restore {{_iid:r.start}}), (b:_Restore {{_iid:r.end}}) "
                      f"CREATE (a)-[x:`{rel_type}`]->(b) SET x = r.props", rows=rows[i:i + 500])
            r += len(rows[i:i + 500])
    graph.run("MATCH (n:_Restore) CALL { WITH n REMOVE n:_Restore, n._iid } IN TRANSACTIONS OF 1000 ROWS")
    graph.run("DROP INDEX trellis_restore_iid IF EXISTS")
    return {"nodes": n, "relationships": r, "embedding_dims": sorted(dims)}


def main(stamp: str) -> int:
    started = time.monotonic()
    graph_path = backup.BACKUP_DIR / f"trellis-{stamp}.jsonl.gz"
    art_path = backup.BACKUP_DIR / f"artifacts-{stamp}.tar.gz"
    if not graph_path.is_file():
        print(f"no such backup: {graph_path}"); return 1
    print("1/4 wiping the graph"); wipe()
    print("2/4 schema"); graph.init_schema()
    print(f"3/4 loading {graph_path.name}"); counts = load(stamp)
    if len(counts["embedding_dims"]) == 1:
        graph.ensure_vector_index(counts["embedding_dims"][0])
    elif counts["embedding_dims"]:
        print("   WARNING: embeddings of different sizes in the backup; no vector index created")
    if art_path.is_file():
        root = backup.ARTIFACT_DIR
        for child in root.iterdir():
            if child.is_dir():
                import shutil; shutil.rmtree(child)
            else:
                child.unlink()
        with tarfile.open(art_path, "r:gz") as tar:
            tar.extractall(root, filter="data")
        print(f"    lesson files restored from {art_path.name}")
    have = graph.run("MATCH (n) RETURN count(n) AS n")[0]["n"]
    print(f"4/4 done in {time.monotonic() - started:.0f}s: {have} nodes, {counts['relationships']} relationships, "
          f"vector size {counts['embedding_dims'] or 'none'}")
    if have != counts["nodes"]:
        print(f"   WARNING: loaded {counts['nodes']} but the graph has {have}")
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__); sys.exit(2)
    sys.exit(main(sys.argv[1]))
