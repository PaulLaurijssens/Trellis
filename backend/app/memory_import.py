"""Import a learning memory file (memory_export / docs/MEMORY-FORMAT.md) into the logged-in learner.

Idempotent: every row is keyed by its id, so importing the same file twice changes nothing. Concepts
are matched by name or alias; what already exists wins, nothing is lowered or overwritten. Layer 1
(conversations, exercise attempts) keeps its ids, sequence numbers and quotes, so `memory.rebuild()`
can verify every piece of evidence afterwards. An id that already belongs to another learner on this
install gets a new id, and every reference to it in the ledgers is rewritten.

`preview()` reads only. `apply()` writes everything in one memory transaction (all or nothing).
"""
import io
import json
import threading
import uuid
import zipfile
import hashlib
from copy import deepcopy
from urllib.parse import urlparse

from . import graph, memory_model
from .memory_export import FORMAT, VERSION

MAX_BYTES = 24 * 1024 * 1024          # nginx accepts 25 MB (deploy/nginx.conf)
MAX_JSON = 32 * 1024 * 1024           # uncompressed memory.json; guards against zip bombs
# Parsed JSON takes far more memory than its text: refuse a file with an absurd number of objects and
# lists before parsing it. A real memory of a few years has tens of thousands.
MAX_STRUCTURES = 1_500_000
LIMITS = {"concepts": 10000, "relations": 50000, "sources": 5000, "conversations": 10000,
          "messages": 150000, "exercises": 50000, "understanding": 10000, "goals": 1000, "examples": 10000}
# Conversations that were not yet processed into memory are processed after the import with the
# install's AI key. Above this number the rest is imported as history only, so one file cannot run up
# the owner's bill.
MAX_PENDING = 50
TEXT = {"name": 200, "definition": 4000, "domain": 200, "alias": 120, "title": 300, "url": 2000}
_busy = threading.Lock()                 # one import at a time: parsing and planning are memory-heavy
RANK = graph.STATUS_RANK


class ImportProblem(ValueError):
    """A file that cannot be imported, with a plain reason for the learner."""


# ---- reading the file -------------------------------------------------------------------------------

def handle(data: bytes, mode: str, pid: str) -> dict:
    """Read, then preview or apply. Runs in a worker thread; a second import waits for none, it is refused."""
    if not _busy.acquire(blocking=False):
        raise ImportProblem("Another import is running. Try again in a minute.")
    try:
        doc = read(data)
        return preview(doc, pid) if mode == "preview" else apply(doc, pid)
    finally:
        _busy.release()


def read(data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise ImportProblem("The file is larger than 24 MB.")
    raw = data
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                info = z.getinfo("memory.json")
                if info.file_size > MAX_JSON:
                    raise ImportProblem("memory.json in the zip is too large.")
                raw = z.read(info)
        except KeyError:
            raise ImportProblem("This zip has no memory.json. Choose a file exported by Trellis.")
        except zipfile.BadZipFile:
            raise ImportProblem("This zip file is damaged.")
    if len(raw) > MAX_JSON or raw.count(b"{") + raw.count(b"[") > MAX_STRUCTURES:
        raise ImportProblem("This memory file is too large to import.")
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise ImportProblem("This is not a Trellis memory file (no readable JSON).")
    return validate(doc)


def _list(doc, *path):
    value = doc
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    if value is None:
        return []
    if not isinstance(value, list):
        raise ImportProblem(f"'{'.'.join(path)}' must be a list.")
    return value


def validate(doc) -> dict:
    if not isinstance(doc, dict) or doc.get("format") != FORMAT:
        raise ImportProblem("This is not a Trellis memory file.")
    version = doc.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ImportProblem("The file has no valid version.")
    if version > VERSION:
        raise ImportProblem(f"This file uses format version {version}; this Trellis reads up to {VERSION}. Update Trellis first.")
    checks = {"concepts": _list(doc, "map", "concepts"), "relations": _list(doc, "map", "relations"),
              "sources": _list(doc, "map", "sources"), "conversations": _list(doc, "conversations"),
              "exercises": _list(doc, "exercises"), "understanding": _list(doc, "understanding"),
              "goals": _list(doc, "goals"), "examples": _list(doc, "examples")}
    for key, rows in checks.items():
        if len(rows) > LIMITS[key]:
            raise ImportProblem(f"Too many {key} ({len(rows)}); the limit is {LIMITS[key]}.")
        if any(not isinstance(r, dict) for r in rows):
            raise ImportProblem(f"Every item in {key} must be an object.")
    names = set()
    for c in checks["concepts"]:
        if not isinstance(c.get("id"), str) or not isinstance(c.get("name"), str) or not c["name"].strip():
            raise ImportProblem("Every concept needs an id and a name.")
        if len(c["name"].strip()) > TEXT["name"]:
            raise ImportProblem(f"A concept name is longer than {TEXT['name']} characters.")
        key = c["name"].strip().casefold()
        if key in names:
            raise ImportProblem(f"The concept '{c['name']}' appears twice.")
        names.add(key)
    messages = 0
    for s in checks["conversations"]:
        if not isinstance(s.get("id"), str) or not isinstance(s.get("concept"), str):
            raise ImportProblem("Every conversation needs an id and a concept.")
        rows = s.get("messages") or []
        if not isinstance(rows, list) or any(not isinstance(m, dict) or not isinstance(m.get("seq"), int)
                                             or m.get("role") not in ("user", "assistant") or not isinstance(m.get("content"), str)
                                             for m in rows):
            raise ImportProblem("A conversation has a message without seq, role or content.")
        messages += len(rows)
    if messages > LIMITS["messages"]:
        raise ImportProblem(f"Too many messages ({messages}).")
    for u in checks["understanding"]:
        if not isinstance(u.get("concept"), str) or not isinstance(u.get("ledger"), dict):
            raise ImportProblem("Every understanding entry needs a concept and a ledger.")
        ledger = u["ledger"]
        if not all(isinstance(ledger.get(k, {} if k in ("sessions", "runs", "corrections") else []), dict if k in ("sessions", "runs", "corrections") else list)
                   for k in ("sessions", "runs", "corrections", "legacy")):
            raise ImportProblem(f"The memory ledger for '{u['concept']}' is damaged.")
    for e in checks["exercises"]:
        if not isinstance(e.get("id"), str) or not isinstance(e.get("run_id"), str):
            raise ImportProblem("Every exercise needs an id and a run id.")
    for key in ("goals", "examples"):
        if any(not isinstance(r.get("id"), str) for r in checks[key]):
            raise ImportProblem(f"Every item in {key} needs an id.")
    return doc


# ---- planning (reads only) --------------------------------------------------------------------------

def person_status(ledger) -> str:
    """The learner's own status for a concept, the same rule as memory.set_learning_position."""
    if ((ledger or {}).get("self_assessment") or {}).get("value") == "understood":
        return "learned"
    return {"interested": "suggested", "queued": "queued", "learning": "learning"}.get((ledger or {}).get("intent"), "learning")


def _existing_concepts():
    rows = graph.run("MATCH (c:Concept) RETURN c.id AS id, c.name AS name, coalesce(c.aliases,[]) AS aliases, coalesce(c.status,'suggested') AS status")
    by_key, ids = {}, {r["id"] for r in rows}
    for r in rows:
        by_key.setdefault(r["name"].casefold(), r)
    for r in rows:
        for alias in r["aliases"]:
            by_key.setdefault(str(alias).casefold(), r)
    return by_key, ids


def _owners(label, ids):
    if not ids:
        return {}
    rows = graph.run(f"MATCH (n:{label}) WHERE n.id IN $ids RETURN n.id AS id, n.person_id AS person", ids=list(ids))
    return {r["id"]: r["person"] for r in rows}


def _visible(ledger) -> str:
    """What the learner sees of a ledger (the projection), for telling whether a merge changes anything."""
    view = memory_model.project(deepcopy(ledger))
    keep = ("summary", "covered", "intent", "self_assessment", "quiz_correct", "quiz_wrong", "manual_fields")
    return json.dumps({**{k: view.get(k) for k in keep},
                       "observations": sorted((o["id"], o["state"]) for o in view["observations"]),
                       "evidence": sorted(e["id"] for e in view["evidence"])}, sort_keys=True, default=str)


def plan(doc: dict, pid: str) -> dict:
    by_key, taken = _existing_concepts()
    concept_ids, concept_names, new_concepts, matched = {}, {}, [], []
    for c in _list(doc, "map", "concepts"):
        hit = by_key.get(c["name"].strip().casefold())
        if hit:
            concept_ids[c["id"]] = hit["id"]; concept_names[c["name"]] = hit["name"]; matched.append(c["name"])
        else:
            cid = c["id"] if c["id"] not in taken else str(uuid.uuid4())
            taken.add(cid)
            concept_ids[c["id"]] = cid; concept_names[c["name"]] = c["name"]; new_concepts.append({**c, "id": cid})
    name_to_id = {name: concept_ids[c["id"]] for c in _list(doc, "map", "concepts") for name in [c["name"]]}

    def remap(label, rows, key="id"):
        owners = _owners(label, {r[key] for r in rows})
        mapping, new, skipped = {}, [], 0
        for r in rows:
            owner = owners.get(r[key])
            if owner is None:
                mapping[r[key]] = r[key]; new.append(r)
            elif owner == pid:
                mapping[r[key]] = r[key]; skipped += 1
            else:
                mapping[r[key]] = str(uuid.uuid4()); new.append(r)
        return mapping, new, skipped

    warnings = []
    conversations = [s for s in _list(doc, "conversations") if s["concept"] in name_to_id]
    if len(conversations) < len(_list(doc, "conversations")):
        warnings.append("Some conversations refer to a concept that is not in the file; they were left out.")
    session_ids, new_sessions, skipped_sessions = remap("ChatSession", conversations)
    # A newer export of a conversation this learner already has here: add the messages that came later.
    new_keys = {id(s) for s in new_sessions}
    mine = [s for s in conversations if id(s) not in new_keys]
    grown = {}
    if mine:
        rows = graph.run("""MATCH (s:ChatSession {person_id:$pid}) WHERE s.id IN $ids
                            OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:ChatMessage)
                            RETURN s.id AS id, collect([m.seq, m.content]) AS messages""", pid=pid, ids=[s["id"] for s in mine])
        local = {r["id"]: {seq: content for seq, content in r["messages"] if seq is not None} for r in rows}
        for s in mine:
            have = local.get(s["id"], {})
            incoming = {m["seq"]: m for m in s.get("messages") or []}
            if any(seq in incoming and incoming[seq]["content"] != content for seq, content in have.items()):
                warnings.append("A conversation differs between this Trellis and the file; the version here was kept.")
                continue
            extra = [incoming[q] for q in sorted(incoming) if q not in have]
            if extra and max(incoming) > max(have, default=-1) and set(have) <= set(incoming):
                grown[s["id"]] = {**s, "messages": extra}
    pending = [s for s in new_sessions if not s.get("consolidated")]
    if len(pending) > MAX_PENDING:
        # The most recent ones are processed; older ones are kept as history only.
        pending.sort(key=lambda s: str(s.get("last_activity") or s.get("started_at") or ""), reverse=True)
        history = {id(s) for s in pending[MAX_PENDING:]}
        new_sessions = [{**s, "consolidated": True} if id(s) in history else s for s in new_sessions]
        warnings.append(f"{len(pending) - MAX_PENDING} older conversation(s) were never processed into memory; they are imported as history only.")
        pending = pending[:MAX_PENDING]
    if pending:
        warnings.append(f"{len(pending)} conversation(s) were not yet processed into memory. Trellis will process them with your AI provider after the import.")
    attempts = list(_list(doc, "exercises"))
    attempt_ids, new_attempts, skipped_attempts = remap("ExerciseAttempt", attempts)
    goal_ids, new_goals, skipped_goals = remap("LearningGoal", list(_list(doc, "goals")))
    understanding = [u for u in _list(doc, "understanding") if u["concept"] in name_to_id]
    # Existing understanding counts as merged only when the merge changes what the learner sees, so a
    # file imported twice previews as "nothing new".
    merged = fresh = 0
    for u in understanding:
        current = graph.understands_state(pid, name_to_id[u["concept"]])
        fresh += not current
        if current:
            incoming = _complete(remap_ledger(u["ledger"], session_ids, attempt_ids))
            merged += _visible(merge_ledgers(current["memory_v2"], incoming, set(grown))) != _visible(current["memory_v2"])
    # The map is shared by every learner on this install: a file may connect its own new concepts, but
    # never rewire concepts that are already here.
    created = {c["id"] for c in new_concepts}
    usable = [r for r in _list(doc, "map", "relations")
              if r.get("type") in graph.VALID_RELS and r.get("from") in concept_ids and r.get("to") in concept_ids
              and concept_ids[r["from"]] != concept_ids[r["to"]]]
    relations = [r for r in usable if concept_ids[r["from"]] in created or concept_ids[r["to"]] in created]
    kept = {id(r) for r in relations}
    dropped = len(_list(doc, "map", "relations")) - len(usable)
    if dropped:
        warnings.append(f"{dropped} relation(s) of an unknown type or to a missing concept were left out.")
    between = [{"a": concept_ids[r["from"]], "b": concept_ids[r["to"]], "type": r["type"]} for r in usable if id(r) not in kept]
    if between:
        missing = graph.run("""UNWIND $rows AS row MATCH (a:Concept {id:row.a}), (b:Concept {id:row.b})
            WHERE NOT EXISTS { MATCH (a)-[r]->(b) WHERE type(r) = row.type } RETURN count(*) AS n""", rows=between)[0]["n"]
        if missing:
            warnings.append(f"{missing} link(s) between concepts that are already on this map were left out: the map is shared, "
                            "so a file never changes how existing concepts connect.")
    return {"doc": doc, "pid": pid, "concept_ids": concept_ids, "concept_names": concept_names, "name_to_id": name_to_id,
            "new_concepts": new_concepts, "matched_concepts": matched, "relations": relations,
            "session_ids": session_ids, "new_sessions": new_sessions, "attempt_ids": attempt_ids, "new_attempts": new_attempts,
            "goal_ids": goal_ids, "new_goals": new_goals, "understanding": understanding, "warnings": warnings,
            "grown_sessions": grown, "created": created,
            "counts": {"concepts_new": len(new_concepts), "concepts_matched": len(matched), "relations": len(relations),
                       "sources": len(_list(doc, "map", "sources")),
                       "conversations_new": len(new_sessions), "conversations_skipped": skipped_sessions - len(grown),
                       "conversations_updated": len(grown),
                       "messages_new": sum(len(s.get("messages") or []) for s in new_sessions),
                       "exercises_new": len(new_attempts), "exercises_skipped": skipped_attempts,
                       "understanding_new": fresh, "understanding_merged": merged,
                       "goals_new": len(new_goals), "goals_skipped": skipped_goals,
                       "examples": len(_list(doc, "examples"))}}


def summary(p: dict) -> dict:
    doc = p["doc"]
    return {"person": (doc.get("person") or {}).get("name"), "exported_at": doc.get("exported_at"),
            "counts": p["counts"], "warnings": p["warnings"]}


def preview(doc: dict, pid: str) -> dict:
    return summary(plan(doc, pid))


# ---- ledger merging (pure) -----------------------------------------------------------------------------

def remap_ledger(ledger: dict, session_ids: dict, attempt_ids: dict) -> dict:
    """Rewrite session and attempt ids inside a memory_v2 ledger (only those that changed)."""
    out = deepcopy(ledger)
    changed = {k: v for k, v in session_ids.items() if k != v}
    if changed and isinstance(out.get("sessions"), dict):
        out["sessions"] = {changed.get(sid, sid): entry for sid, entry in out["sessions"].items()}
        for entry in out["sessions"].values():
            for e in entry.get("evidence", []):
                if e.get("session_id") in changed:
                    e["session_id"] = changed[e["session_id"]]
    moved = {k: v for k, v in attempt_ids.items() if k != v}
    if moved and isinstance(out.get("runs"), dict):
        for entry in out["runs"].values():
            for e in entry.get("evidence", []):
                if e.get("attempt_id") in moved:
                    e["attempt_id"] = moved[e["attempt_id"]]
                    if e.get("assessment_id"):
                        e["assessment_id"] = e["attempt_id"]
    return out


def _union(first, second, blocked=()):
    out, seen = [], {memory_model.norm(b) for b in blocked}
    for item in list(first or []) + list(second or []):
        key = memory_model.norm(item)
        if str(item).strip() and key not in seen:
            seen.add(key); out.append(item)
    return out


def _complete(ledger):
    """A ledger from a file may lack optional keys; fill them so project() can read it."""
    doc = deepcopy(ledger)
    doc.setdefault("version", 2); doc.setdefault("baseline", {}); doc.setdefault("legacy", [])
    doc.setdefault("sessions", {}); doc.setdefault("runs", {}); doc.setdefault("corrections", {})
    doc.setdefault("intent", "learning"); doc.setdefault("self_assessment", None)
    for entry in doc["sessions"].values():
        for key in ("evidence", "observations", "changes"):
            entry.setdefault(key, [])
        entry.setdefault("date", None)
    return doc


def _tombstones(current_removed, incoming_removed, present):
    """The file's removals count too, except for items the learner has here now (re-added, or never removed here)."""
    here = {memory_model.norm(x) for x in present}
    return _union(current_removed, [x for x in incoming_removed or [] if memory_model.norm(x) not in here])


def merge_ledgers(current: dict, incoming: dict, prefer_incoming=()) -> dict:
    """Union of two memory_v2 ledgers of the same learner and concept. The current one wins on any
    conflict (intent, summary, corrections), except for conversation entries in `prefer_incoming`:
    those conversations grew in the file, so the file's entry matches the messages now stored."""
    out = deepcopy(current)
    incoming = deepcopy(incoming)
    # Legacy and manual observation ids contain the concept id, which can differ between installs.
    # The same observation (kind + wording) keeps the id it has here; the file's corrections follow it.
    here = {(o["kind"], memory_model.norm(o["text"])): o["id"] for o in out.get("legacy", [])}
    renamed = {}
    for o in incoming.get("legacy", []):
        same = here.get((o["kind"], memory_model.norm(o["text"])))
        if same and same != o["id"]:
            renamed[o["id"]] = same
    if renamed:
        incoming["legacy"] = [o for o in incoming["legacy"] if o["id"] not in renamed]
        incoming["corrections"] = {renamed.get(k, k): v for k, v in incoming.get("corrections", {}).items()}
        for entry in incoming.get("sessions", {}).values():
            for change in entry.get("changes", []):
                change["observation_id"] = renamed.get(change.get("observation_id"), change.get("observation_id"))
            if entry.get("summary_inactive_ids"):
                entry["summary_inactive_ids"] = [renamed.get(i, i) for i in entry["summary_inactive_ids"]]
    base, other = out.setdefault("baseline", {}), incoming.get("baseline", {})
    present = [*base.get("covered", []), *base.get("struggles", []), *base.get("misconceptions", [])]
    base["removed"] = _tombstones(base.get("removed", []), other.get("removed", []), present)
    for field in ("covered", "struggles", "misconceptions"):
        base[field] = _union(base.get(field, []), other.get(field, []), base["removed"])
    base["manual_fields"] = sorted(set(base.get("manual_fields") or []) | set(other.get("manual_fields") or []))
    if not base.get("summary") and other.get("summary"):
        base["summary"] = other["summary"]
    for field in ("quiz_correct", "quiz_wrong"):
        base[field] = max(int(base.get(field, 0) or 0), int(other.get(field, 0) or 0))
    legacy = {o["id"]: o for o in incoming.get("legacy", [])}
    legacy.update({o["id"]: o for o in out.get("legacy", [])})
    out["legacy"] = list(legacy.values())
    sessions = dict(incoming.get("sessions", {}))
    sessions.update({k: v for k, v in out.get("sessions", {}).items() if k not in prefer_incoming or k not in sessions})
    out["sessions"] = sessions
    runs = deepcopy(incoming.get("runs", {}))
    for rid, entry in out.get("runs", {}).items():
        if rid in runs:
            known = {e["id"]: e for e in runs[rid].get("evidence", [])}
            known.update({e["id"]: e for e in entry.get("evidence", [])})
            runs[rid] = {**runs[rid], **entry, "evidence": list(known.values()),
                         "date": max(runs[rid].get("date") or "", entry.get("date") or "") or None}
        else:
            runs[rid] = entry
    out["runs"] = runs
    corrections = dict(incoming.get("corrections", {})); corrections.update(out.get("corrections", {}))
    out["corrections"] = corrections
    claims = {c["id"]: c for c in incoming.get("claims", []) if isinstance(c, dict) and c.get("id")}
    claims.update({c["id"]: c for c in out.get("claims", []) if isinstance(c, dict) and c.get("id")})
    if claims:
        out["claims"] = sorted(claims.values(), key=lambda c: c.get("date") or "")[-40:]
    mine, theirs = out.get("self_assessment"), incoming.get("self_assessment")
    if theirs and (not mine or str(theirs.get("date") or "") > str(mine.get("date") or "")):
        out["self_assessment"] = theirs
    return out


def _merge_profile_lists(current: dict, incoming: dict) -> dict:
    out = dict(current)
    present = [x for f in graph.PROFILE_LISTS for x in current.get(f, []) or []]
    out["removed"] = _tombstones(current.get("removed", []), incoming.get("removed", []), present)
    for field in graph.PROFILE_LISTS:
        out[field] = _union(current.get(field, []), incoming.get(field, []), out["removed"])
    out["manual_fields"] = sorted(set(current.get("manual_fields") or []) | set(incoming.get("manual_fields") or []))
    return out


def merge_profile(current: dict, incoming: dict) -> dict:
    out = _merge_profile_lists(current, incoming)
    out["teaching_preferences"] = list(dict.fromkeys([*(current.get("teaching_preferences") or []),
                                                      *(incoming.get("teaching_preferences") or [])]))[:40]
    if not (current.get("notes") or "").strip():
        out["notes"] = incoming.get("notes") or ""
    return out


# ---- applying --------------------------------------------------------------------------------------------

def _write_concepts(p):
    # A concept's shared status is never taken from the file: on every start, graph.migrate_memory links
    # every learner to every 'learned' concept. New concepts start as 'queued' at most; the importer's own
    # understanding raises them below (_raise_status), exactly as their own clicks would.
    for c in p["new_concepts"]:
        aliases = list({a.strip().casefold(): a.strip() for a in (c.get("aliases") or []) if isinstance(a, str) and a.strip()
                        and len(a.strip()) <= TEXT["alias"]}.values())[:10]
        status = "queued" if c.get("status") in ("queued", "learning", "learned") else "suggested"
        graph.run("""
            CREATE (c:Concept {id:$id, name:$name, definition:$definition, domain:$domain, status:$status,
                               created_at:coalesce($created, $now), aliases:[]})
            WITH c
            UNWIND (CASE WHEN size($aliases)=0 THEN [null] ELSE $aliases END) AS alias
            WITH c, alias WHERE alias IS NOT NULL AND toLower(alias) <> toLower(c.name)
              AND NOT EXISTS { MATCH (o:Concept) WHERE o <> c AND (toLower(o.name)=toLower(alias)
                               OR any(a IN coalesce(o.aliases,[]) WHERE toLower(a)=toLower(alias))) }
            SET c.aliases = c.aliases + alias""",
                  id=c["id"], name=c["name"].strip(), definition=_text(c.get("definition"), "definition"), domain=_text(c.get("domain"), "domain"),
                  status=status, created=c.get("created_at"), now=graph._now(), aliases=aliases)
    for c in _list(p["doc"], "map", "concepts"):
        if c["name"] in p["matched_concepts"] and (c.get("definition") or "").strip():
            graph.run("MATCH (c:Concept {id:$id}) WHERE trim(coalesce(c.definition,''))='' SET c.definition=$definition",
                      id=p["concept_ids"][c["id"]], definition=_text(c["definition"], "definition"))


def _text(value, kind):
    return value.strip()[:TEXT[kind]] if isinstance(value, str) else ""


def _url(value):
    """Only web links: a javascript: or data: link in a file must never become a clickable source."""
    if not isinstance(value, str) or len(value) > TEXT["url"]:
        return None
    return value if urlparse(value.strip()).scheme in ("http", "https") else None


def _raise_status(cid, status):
    graph.run("""MATCH (c:Concept {id:$id})
        SET c.status = CASE WHEN $rank > $ranks[coalesce(c.status,'suggested')] THEN $status ELSE coalesce(c.status,'suggested') END""",
              id=cid, rank=RANK[status], ranks=RANK, status=status)


def _write_map(p):
    for r in p["relations"]:
        graph.run(f"""MATCH (a:Concept {{id:$a}}), (b:Concept {{id:$b}})
            MERGE (a)-[r:{r['type']}]->(b) ON CREATE SET r.strength=$s, r.reason=$reason""",
                  a=p["concept_ids"][r["from"]], b=p["concept_ids"][r["to"]],
                  s=float(r.get("strength") if isinstance(r.get("strength"), (int, float)) else 1.0), reason=r.get("reason"))
    source_ids = {}
    for s in _list(p["doc"], "map", "sources"):
        if not isinstance(s.get("id"), str):
            continue
        url = _url(s.get("url"))
        found = graph.run("""OPTIONAL MATCH (a:Source {id:$id}) OPTIONAL MATCH (b:Source) WHERE $url IS NOT NULL AND b.url = $url
                             RETURN coalesce(a.id, b.id) AS id LIMIT 1""", id=s["id"], url=url)
        sid = found[0]["id"] if found and found[0]["id"] else None
        new_source = not sid
        if new_source:
            sid = s["id"]
            graph.run("CREATE (:Source {id:$id, type:$type, title:$title, url:$url, ingested_at:coalesce($at,$now)})",
                      id=sid, type=_text(s.get("type"), "domain") or "text", title=_text(s.get("title"), "title"), url=url,
                      at=s.get("ingested_at"), now=graph._now())
        source_ids[s["id"]] = sid
        for m in s.get("mentions") or []:
            cid = p["name_to_id"].get(m.get("concept")) if isinstance(m, dict) else None
            # Mentions only for what this file brought: never new quotes on a shared source and concept.
            if not cid or not (new_source or cid in p["created"]):
                continue
            graph.run("""MATCH (c:Concept {id:$cid}), (s:Source {id:$sid}) MERGE (c)-[m:MENTIONED_IN]->(s)
                ON CREATE SET m.context=$context, m.importance=$importance, m.mentions=$mentions, m.start_sec=$start""",
                      cid=cid, sid=sid, context=m.get("context") or "", importance=m.get("importance"),
                      mentions=json.dumps(m.get("quotes") or [], ensure_ascii=False), start=m.get("start_sec"))
    p["source_ids"] = source_ids


def _messages(rows):
    return [{"seq": m["seq"], "role": m["role"], "content": m["content"], "ts": m.get("ts"),
             "illustration": json.dumps(m["illustration"], ensure_ascii=False) if m.get("illustration") else None}
            for m in sorted(rows, key=lambda m: m["seq"])]


def _write_layer1(p):
    pid = p["pid"]
    for s in p["new_sessions"]:
        sid = p["session_ids"][s["id"]]
        messages = _messages(s.get("messages") or [])
        graph.run("""MATCH (p:Person {id:$pid}), (c:Concept {id:$cid})
            CREATE (s:ChatSession {id:$sid, person_id:$pid, concept_id:$cid, level:$level, started_at:$started,
                                   last_activity:$last, consolidated:$consolidated, memory_checkpoint:$checkpoint,
                                   message_revision:size($messages), imported_at:$now})
            CREATE (p)-[:HAD_SESSION]->(s) CREATE (s)-[:ABOUT]->(c)
            WITH s UNWIND $messages AS m
            CREATE (s)-[:HAS_MESSAGE]->(:ChatMessage {seq:m.seq, role:m.role, content:m.content, ts:m.ts, illustration:m.illustration})""",
                  pid=pid, cid=p["name_to_id"][s["concept"]], sid=sid, level=s.get("level") or 3,
                  started=s.get("started_at") or graph._now(), last=s.get("last_activity") or s.get("started_at") or graph._now(),
                  consolidated=bool(s.get("consolidated")), checkpoint=s.get("memory_checkpoint"), now=graph._now(),
                  messages=messages)
    for sid, s in p["grown_sessions"].items():
        graph.run("""MATCH (s:ChatSession {id:$sid, person_id:$pid})
            SET s.last_activity=$last, s.consolidated=$consolidated, s.memory_checkpoint=$checkpoint,
                s.message_revision=coalesce(s.message_revision,0)+size($messages), s.memory_error=null
            WITH s UNWIND $messages AS m
            CREATE (s)-[:HAS_MESSAGE]->(:ChatMessage {seq:m.seq, role:m.role, content:m.content, ts:m.ts, illustration:m.illustration})""",
                  sid=sid, pid=pid, last=s.get("last_activity"), consolidated=bool(s.get("consolidated")),
                  checkpoint=s.get("memory_checkpoint"), messages=_messages(s["messages"]))
    for a in p["new_attempts"]:
        graph.run("""CREATE (:ExerciseAttempt {id:$id, run_id:$run, person_id:$pid, activity_id:$activity, concept_ids:$cids,
                     objective_id:$objective, prompt_snapshot:$prompt, response_json:$response, response_mode:$mode,
                     assistance_level:$level, outcome:$outcome, assessed_by:$by, uncertainty:$uncertainty, rationale:$rationale,
                     occurred_at:$at, received_at:$at, imported_at:$now})""",
                  id=p["attempt_ids"][a["id"]], run=a["run_id"], pid=pid, activity=a.get("activity_id"),
                  cids=[p["name_to_id"][n] for n in (a.get("concepts") or []) if n in p["name_to_id"]],
                  objective=a.get("objective_id"), prompt=str(a.get("prompt") or "")[:1200],
                  response=json.dumps(a.get("response"), ensure_ascii=False), mode=a.get("response_mode"),
                  level=a.get("assistance_level") or "none", outcome=a.get("outcome"), by=a.get("assessed_by"),
                  uncertainty=a.get("uncertainty"), rationale=a.get("rationale") or "", at=a.get("occurred_at"), now=graph._now())


def _write_layer2(p):
    pid = p["pid"]
    for u in p["understanding"]:
        cid = p["name_to_id"][u["concept"]]
        incoming = _complete(remap_ledger(u["ledger"], p["session_ids"], p["attempt_ids"]))
        current = graph.understands_state(pid, cid)
        doc = merge_ledgers(current["memory_v2"], incoming, set(p["grown_sessions"])) if current else incoming
        projected = memory_model.project(doc)
        last = max(str((current or {}).get("last_session") or ""), str(u.get("last_session") or "")) or None
        projected.update(level=(current or {}).get("level") or u.get("level"), last_session=last,
                         status=(current or {}).get("status") or u.get("status"))
        graph.write_understands(pid, cid, projected)
        if not current and u.get("since"):
            graph.run("MATCH (:Person {id:$pid})-[x:UNDERSTANDS]->(:Concept {id:$cid}) SET x.since=$since", pid=pid, cid=cid, since=u["since"])
        _raise_status(cid, person_status(doc))


def _write_layer3(p):
    pid, prof = p["pid"], p["doc"].get("profile") or {}
    incoming = prof.get("learning_profile") if isinstance(prof.get("learning_profile"), dict) else {}
    current = graph.learning_profile(pid)
    graph.save_learning_profile(pid, merge_profile(current, incoming))
    ledger = prof.get("ledger") if isinstance(prof.get("ledger"), dict) else None
    if ledger:
        changed = {k: v for k, v in p["session_ids"].items() if k != v}
        sessions = {changed.get(k, k): v for k, v in (ledger.get("sessions") or {}).items()}
        rows = graph.run("MATCH (p:Person {id:$pid}) RETURN p.profile_memory_v2 AS doc", pid=pid)
        mine = json.loads(rows[0]["doc"]) if rows and rows[0]["doc"] else None
        theirs = ledger.get("baseline") if isinstance(ledger.get("baseline"), dict) else {}
        if mine:
            # memory._profile_commit rebuilds the lists from baseline + sessions, so both must be merged.
            mine["baseline"] = _merge_profile_lists(mine.get("baseline") or {}, theirs)
            mine["sessions"] = {**sessions, **{k: v for k, v in mine.get("sessions", {}).items()
                                               if k not in p["grown_sessions"] or k not in sessions}}
        else:
            mine = {"baseline": theirs or deepcopy(graph.EMPTY_PROFILE), "sessions": sessions}
        graph.run("MATCH (p:Person {id:$pid}) SET p.profile_memory_v2=$doc", pid=pid, doc=json.dumps(mine, ensure_ascii=False))


def _write_journey(p):
    pid = p["pid"]
    active = graph.run("MATCH (p:Person {id:$pid}) OPTIONAL MATCH (g:LearningGoal {id:p.active_goal_id, person_id:$pid, status:'active'}) RETURN g.id AS id",
                       pid=pid)
    has_active = bool(active and active[0]["id"])
    for g in p["new_goals"]:
        steps = []
        for step in g.get("steps") or []:
            name = step.get("name") if isinstance(step, dict) else None
            if name in p["name_to_id"]:
                steps.append({**step, "concept_id": p["name_to_id"][name], "name": p["concept_names"].get(name, name)})
        if not steps:
            p["warnings"].append(f"The goal '{g.get('title')}' had no known steps and was left out.")
            continue
        make_active = bool(g.get("active")) and not has_active
        status = "active" if make_active else ("paused" if g.get("status") == "active" else g.get("status") or "paused")
        gid = p["goal_ids"][g["id"]]
        graph.run("""MATCH (p:Person {id:$pid})
            CREATE (g:LearningGoal {id:$gid, person_id:$pid, title:$title, status:$status, origin:$origin, source_id:$source_id,
                                    source_title:$source_title, steps_json:$steps, cycle:$cycle, created_at:$created, updated_at:$updated})
            CREATE (p)-[:HAS_GOAL]->(g)
            FOREACH (_ IN CASE WHEN $active THEN [1] ELSE [] END | SET p.active_goal_id=$gid)
            WITH g UNWIND $cids AS cid MATCH (c:Concept {id:cid}) MERGE (g)-[:INCLUDES]->(c)""",
                  pid=pid, gid=gid, title=str(g.get("title") or "Goal")[:400], status=status,
                  origin=g.get("origin") if g.get("origin") in ("manual", "roadmap") else "manual",
                  source_id=p["source_ids"].get(g.get("source_id")), source_title=g.get("source_title"),
                  steps=json.dumps(steps, ensure_ascii=False), cycle=bool(g.get("cycle")),
                  created=g.get("created_at") or graph._now(), updated=g.get("updated_at") or graph._now(),
                  active=make_active, cids=[s["concept_id"] for s in steps])
        if p["source_ids"].get(g.get("source_id")):
            graph.run("MATCH (g:LearningGoal {id:$gid}), (s:Source {id:$sid}) MERGE (g)-[:USES_SOURCE]->(s)",
                      gid=gid, sid=p["source_ids"][g["source_id"]])
        has_active = has_active or make_active
    examples = 0
    session_concepts = {s["id"]: s["concept"] for s in _list(p["doc"], "conversations")}
    for e in _list(p["doc"], "examples"):
        sid = p["session_ids"].get(e.get("session_id"))
        seq = e.get("seq")
        if not sid or not isinstance(seq, int):
            continue
        eid = hashlib.sha256(f"{pid}:{sid}:{seq}".encode()).hexdigest()[:32]     # same id as journey.save_example
        concept = session_concepts.get(e.get("session_id"), e.get("concept"))
        cid = p["name_to_id"].get(concept)
        if not cid:
            continue
        if graph.run("MATCH (e:HelpfulExample {id:$eid}) RETURN e.id AS id", eid=eid):
            continue
        rows = graph.run("""CREATE (e:HelpfulExample {id:$eid, person_id:$pid, concept_id:$cid, concept:$concept, session_id:$sid,
                seq:$seq, original:$original, text:$text, date:$date, updated_at:coalesce($updated,$now), corrected_at:$corrected,
                confirmed_by:'learner'})
            WITH e OPTIONAL MATCH (:ChatSession {id:$sid})-[:HAS_MESSAGE]->(m:ChatMessage {seq:$seq})
            FOREACH (_ IN CASE WHEN m IS NULL THEN [] ELSE [1] END | MERGE (e)-[:FROM_MESSAGE]->(m))
            RETURN e.id AS id""",
                         eid=eid, pid=pid, cid=cid, concept=p["concept_names"].get(concept, concept), sid=sid, seq=seq,
                         original=e.get("original") or e.get("text") or "", text=e.get("text") or e.get("original") or "",
                         date=e.get("date"), updated=e.get("updated_at"), corrected=e.get("corrected_at"), now=graph._now())
        examples += len(rows)
    for a in _list(p["doc"], "asked_about"):
        cid = p["name_to_id"].get(a.get("concept")) if isinstance(a, dict) else None
        if cid:
            graph.run("""MATCH (p:Person {id:$pid}), (c:Concept {id:$cid}) MERGE (p)-[x:ASKED_ABOUT]->(c) ON CREATE SET x.ts=$ts""",
                      pid=pid, cid=cid, ts=a.get("ts") or graph._now())
    p["counts"]["examples_new"] = examples


def apply(doc: dict, pid: str) -> dict:
    from . import memory

    def commit():
        p = plan(doc, pid)
        _write_concepts(p)
        _write_map(p)
        _write_layer1(p)
        _write_layer2(p)
        _write_layer3(p)
        _write_journey(p)
        # Prove the result before it is saved: replaying the ledgers checks every quote against its
        # message and every exercise against its attempt. A failure rolls the whole import back.
        try:
            memory.rebuild(pid)
        except memory.ConsolidationError as exc:
            raise ImportProblem("The memory in this file does not match its conversations, so nothing was imported. " + str(exc))
        return {**summary(p), "new_concept_ids": [c["id"] for c in p["new_concepts"]]}
    return graph.memory_transaction(pid, commit)


def embed_missing(limit: int = 2000) -> int:
    """Imported concepts have no embedding (embeddings are model specific). Give them one with this
    install's model, so similar-concept matching works for them too. Best effort: a concept without
    an embedding still works everywhere else (name, alias and fulltext search)."""
    from . import llm
    rows = graph.run("MATCH (c:Concept) WHERE c.embedding IS NULL RETURN c.id AS id, c.name AS name, coalesce(c.definition,'') AS definition LIMIT $n",
                     n=limit)
    done = 0
    for start in range(0, len(rows), 50):
        batch = rows[start:start + 50]
        vectors = llm.embed([f"{r['name']}: {r['definition']}".strip(": ") for r in batch])
        for r, v in zip(batch, vectors):
            graph.run("MATCH (c:Concept {id:$id}) WHERE c.embedding IS NULL SET c.embedding=$v", id=r["id"], v=v)
            done += 1
    return done
