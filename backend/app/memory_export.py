"""Export one learner's memory as a portable, readable file (format: docs/MEMORY-FORMAT.md).

A zip with `memory.json` (complete, importable) next to Markdown pages a person or a notes app can
read without Trellis. The knowledge map is shared by everyone on an install and is exported whole;
the three memory layers, goals and examples are only the requester's own. Never exported: passwords,
keys, provider settings, embeddings (model specific), lesson files, pending sources, suggestions.
"""
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone

from . import graph

FORMAT = "trellis-learning-memory"
VERSION = 1


def _loads(raw, default):
    if raw is None or raw == "":
        return default
    if not isinstance(raw, str):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _map(pid):
    concepts = graph.run("""
        MATCH (c:Concept)
        RETURN c.id AS id, c.name AS name, coalesce(c.aliases,[]) AS aliases, coalesce(c.definition,'') AS definition,
               coalesce(c.domain,'') AS domain, coalesce(c.status,'suggested') AS status, c.created_at AS created_at
        ORDER BY toLower(c.name)""")
    relations = graph.run("""
        MATCH (a:Concept)-[r]->(b:Concept) WHERE type(r) IN $types
        RETURN a.id AS from, b.id AS to, type(r) AS type, coalesce(r.strength,1.0) AS strength, r.reason AS reason
        ORDER BY a.id, b.id, type""", types=sorted(graph.VALID_RELS))
    rows = graph.run("""
        MATCH (s:Source)
        WHERE EXISTS { (:Concept)-[:MENTIONED_IN]->(s) } OR EXISTS { (:LearningGoal {person_id:$pid})-[:USES_SOURCE]->(s) }
        OPTIONAL MATCH (c:Concept)-[m:MENTIONED_IN]->(s)
        WITH s, m, c ORDER BY toLower(c.name)
        RETURN s.id AS id, s.type AS type, s.title AS title, s.url AS url, s.ingested_at AS ingested_at,
               [x IN collect({concept:c.name, context:m.context, importance:m.importance, start_sec:m.start_sec,
                              mentions:m.mentions}) WHERE x.concept IS NOT NULL] AS mentions
        ORDER BY toLower(coalesce(s.title,'')), s.id""", pid=pid)
    sources = []
    for row in rows:
        mentions = [{"concept": m["concept"], "context": m.get("context") or "", "importance": m.get("importance"),
                     "start_sec": m.get("start_sec"), "quotes": [q for q in _loads(m.get("mentions"), []) if isinstance(q, dict)]}
                    for m in row["mentions"]]
        sources.append({**{k: row[k] for k in ("id", "type", "title", "url", "ingested_at")}, "mentions": mentions})
    return {"concepts": concepts, "relations": relations, "sources": sources}


def _conversations(pid):
    sessions = graph.run("""
        MATCH (s:ChatSession {person_id:$pid})-[:ABOUT]->(c:Concept)
        RETURN s.id AS id, c.name AS concept, s.level AS level, s.started_at AS started_at, s.last_activity AS last_activity,
               coalesce(s.consolidated,false) AS consolidated, s.memory_checkpoint AS memory_checkpoint
        ORDER BY s.started_at, s.id""", pid=pid)
    for s in sessions:
        s["messages"] = [{"seq": m["seq"], "role": m["role"], "content": m["content"], "ts": m.get("ts"),
                          "illustration": m.get("illustration")} for m in graph.session_messages(s["id"])]
    return sessions


def _exercises(pid, names):
    rows = graph.run("MATCH (a:ExerciseAttempt {person_id:$pid}) RETURN properties(a) AS a ORDER BY a.occurred_at, a.id", pid=pid)
    out = []
    for row in rows:
        a = row["a"]
        out.append({"id": a["id"], "run_id": a.get("run_id"), "activity_id": a.get("activity_id"),
                    "concepts": [names[c] for c in (a.get("concept_ids") or []) if c in names],
                    "objective_id": a.get("objective_id"), "prompt": a.get("prompt_snapshot") or "",
                    "response": _loads(a.get("response_json"), None), "response_mode": a.get("response_mode"),
                    "outcome": a.get("outcome"), "assessed_by": a.get("assessed_by"),
                    "assistance_level": a.get("assistance_level") or "none", "uncertainty": a.get("uncertainty"),
                    "rationale": a.get("rationale") or "", "occurred_at": a.get("occurred_at")})
    return out


VIEW_FIELDS = ("summary", "covered", "struggles", "misconceptions", "intent", "self_assessment",
               "quiz_correct", "quiz_wrong", "manual_fields", "removed")


def memory_import_status(ledger):
    from .memory_import import person_status
    return person_status(ledger)


def _understanding(pid):
    out = []
    for state in graph.all_understands(pid):
        ledger = state.get("memory_v2") or {}
        view = {k: state.get(k) for k in VIEW_FIELDS}
        view["observations"] = [{k: o.get(k) for k in ("id", "kind", "text", "state", "origin", "corrected_by", "date",
                                                        "evidence_ids", "resolution_evidence_ids") if k in o}
                                for o in state.get("observations", [])]
        view["evidence"] = state.get("evidence", [])
        view["learning_status"] = memory_import_status(ledger)
        out.append({"concept": state["concept"], "level": state.get("level"), "status": state.get("status"),
                    "since": state.get("since"), "last_session": state.get("last_session"),
                    "view": view, "ledger": ledger})
    out.sort(key=lambda u: u["concept"].casefold())
    return out


def _profile(pid):
    rows = graph.run("MATCH (p:Person {id:$pid}) RETURN p.profile_memory_v2 AS ledger", pid=pid)
    return {"learning_profile": graph.learning_profile(pid), "ledger": _loads(rows[0]["ledger"] if rows else None, None)}


def _goals(pid):
    rows = graph.run("MATCH (p:Person {id:$pid}) RETURN p.active_goal_id AS active", pid=pid)
    active = rows[0]["active"] if rows else None
    out = []
    for row in graph.run("MATCH (g:LearningGoal {person_id:$pid}) RETURN properties(g) AS g ORDER BY g.created_at, g.id", pid=pid):
        g = row["g"]
        out.append({"id": g["id"], "title": g.get("title"), "status": g.get("status"), "origin": g.get("origin") or "manual",
                    "source_title": g.get("source_title"), "source_id": g.get("source_id"),
                    "steps": _loads(g.get("steps_json"), []), "cycle": bool(g.get("cycle")),
                    "created_at": g.get("created_at"), "updated_at": g.get("updated_at"), "active": g["id"] == active})
    return out


def _examples(pid):
    out = []
    for row in graph.run("MATCH (e:HelpfulExample {person_id:$pid}) RETURN properties(e) AS e ORDER BY e.date, e.id", pid=pid):
        e = row["e"]
        out.append({k: e.get(k) for k in ("id", "concept", "session_id", "seq", "original", "text", "date",
                                          "updated_at", "corrected_at")})
    return out


def _asked(pid):
    return graph.run("""MATCH (:Person {id:$pid})-[a:ASKED_ABOUT]->(c:Concept)
                        RETURN c.name AS concept, a.ts AS ts ORDER BY c.name""", pid=pid)


def build(pid: str) -> dict:
    """The complete memory of one learner as a JSON-ready dict (memory.json)."""
    person = graph.run("MATCH (p:Person {id:$pid}) RETURN p.name AS name, coalesce(p.ui_language,'en') AS ui_language, p.level AS level",
                       pid=pid)
    if not person:
        raise KeyError("Person not found")
    knowledge = _map(pid)
    names = {c["id"]: c["name"] for c in knowledge["concepts"]}
    doc = {"format": FORMAT, "version": VERSION,
           "exported_at": datetime.now(timezone.utc).isoformat(),
           "trellis_version": os.getenv("TRELLIS_VERSION") or "dev",
           "person": person[0], "map": knowledge,
           "conversations": _conversations(pid), "exercises": _exercises(pid, names),
           "understanding": _understanding(pid), "profile": _profile(pid),
           "goals": _goals(pid), "examples": _examples(pid), "asked_about": _asked(pid)}
    doc["counts"] = {"concepts": len(knowledge["concepts"]), "relations": len(knowledge["relations"]),
                     "sources": len(knowledge["sources"]), "conversations": len(doc["conversations"]),
                     "messages": sum(len(s["messages"]) for s in doc["conversations"]),
                     "exercises": len(doc["exercises"]), "understanding": len(doc["understanding"]),
                     "goals": len(doc["goals"]), "examples": len(doc["examples"])}
    return doc


# ---- Markdown: the same memory, readable without Trellis (opens as an Obsidian vault) --------------

WORDS = {
    "en": {"definition": "Definition", "prerequisites": "Needs first", "leads_to": "Leads to", "related": "Related",
           "part_of": "Part of", "mine": "My understanding", "stand": "Where I stand", "intent": "Learning intent",
           "self": "My own assessment (not evidence)", "summary": "Summary", "attention": "Needs attention",
           "shown": "What I have shown", "discussed": "Discussed", "earlier": "Earlier observations",
           "sources": "Sources", "struggles": "Difficulty", "misconceptions": "Misconception",
           "demonstrated": "shown", "needs_practice": "needs practice", "assisted": "with help",
           "conversation": "conversation", "exercise": "exercise", "none": "Nothing yet.",
           "profile": "How I learn", "works_well": "Works well", "works_poorly": "Does not work well",
           "preferences": "Preferences", "chosen": "Teaching approaches I chose", "notes": "Notes",
           "conversations": "Conversations", "learner": "Me", "mentor": "Mentor", "edited": "edited by me",
           "resolved": "solved", "superseded": "dismissed", "active": "open"},
}


def slug(name: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", str(name), flags=re.UNICODE).strip().replace(" ", "-").lower()
    return re.sub(r"-{2,}", "-", s)[:80] or "concept"


def _slugs(concepts):
    taken, out = set(), {}
    for c in concepts:
        base = slug(c["name"]); s = base; n = 2
        while s in taken:
            s = f"{base}-{n}"; n += 1
        taken.add(s); out[c["id"]] = s
    return out


def _yaml(value):
    return json.dumps(value, ensure_ascii=False)


def _link(slugs, cid, names):
    return f"[[{slugs[cid]}|{names[cid]}]]" if cid in slugs else ""


def concept_markdown(concept, doc, slugs, w):
    names = {c["id"]: c["name"] for c in doc["map"]["concepts"]}
    cid = concept["id"]
    mine = next((u for u in doc["understanding"] if u["concept"] == concept["name"]), None)
    lines = ["---", f"name: {_yaml(concept['name'])}", f"aliases: {_yaml(concept['aliases'])}",
             f"status: {(mine or {}).get('view', {}).get('learning_status') or concept['status']}", f"domain: {_yaml(concept['domain'])}", f"trellis_id: {cid}", "---", "",
             f"# {concept['name']}", ""]
    lines += [concept["definition"] or w["none"], ""]
    rels = doc["map"]["relations"]
    groups = (("prerequisites", [r["from"] for r in rels if r["to"] == cid and r["type"] == "PREREQUISITE_OF"]),
              ("leads_to", [r["to"] for r in rels if r["from"] == cid and r["type"] == "PREREQUISITE_OF"]),
              ("part_of", [r["to"] for r in rels if r["from"] == cid and r["type"] == "PART_OF"]),
              ("related", [r["to"] if r["from"] == cid else r["from"] for r in rels
                           if r["type"] == "RELATED_TO" and cid in (r["from"], r["to"])]))
    for key, ids in groups:
        if ids:
            lines += [f"**{w[key]}:** " + ", ".join(_link(slugs, i, names) for i in dict.fromkeys(ids)), ""]
    if mine:
        v = mine["view"]
        lines += [f"## {w['mine']}", ""]
        sa = (v.get("self_assessment") or {}).get("value")
        lines += [f"- {w['intent']}: {v.get('intent') or 'learning'}"] + ([f"- {w['self']}: {sa}"] if sa else []) + [""]
        if v.get("summary"):
            edited = f" ({w['edited']})" if "summary" in (v.get("manual_fields") or []) else ""
            lines += [f"**{w['summary']}{edited}:** {v['summary']}", ""]
        evidence = {e["id"]: e for e in v.get("evidence", [])}
        active = [o for o in v.get("observations", []) if o.get("state") == "active"]
        lines += [f"### {w['attention']}", ""] + ([f"- {w.get(o['kind'], o['kind'])}: {o['text']}" for o in active] or [w["none"]]) + [""]
        lines += [f"### {w['shown']}", ""]
        shown = sorted(evidence.values(), key=lambda e: e.get("date") or "")
        for e in shown:
            what = e.get("quote") or e.get("prompt") or ""
            origin = w["exercise"] if e.get("origin") == "exercise" else w["conversation"]
            lines.append(f"- {str(e.get('date') or '')[:10]} · {w.get(e.get('outcome'), e.get('outcome'))} · {origin}: {what}")
        lines += ([] if shown else [w["none"]]) + [""]
        if v.get("covered"):
            lines += [f"### {w['discussed']}", ""] + [f"- {x}" for x in v["covered"]] + [""]
        earlier = [o for o in v.get("observations", []) if o.get("state") != "active"]
        if earlier:
            lines += [f"### {w['earlier']}", ""] + [f"- {o['text']} ({w.get(o['state'], o['state'])})" for o in earlier] + [""]
    sources = [(s, m) for s in doc["map"]["sources"] for m in s["mentions"] if m["concept"] == concept["name"]]
    if sources:
        lines += [f"## {w['sources']}", ""]
        for s, m in sources:
            title = s.get("title") or s.get("url") or s["id"]
            head = f"[{title}]({s['url']})" if s.get("url") else title
            lines.append(f"- {head}" + (f": {m['context']}" if m.get("context") else ""))
        lines.append("")
    return "\n".join(lines)


def profile_markdown(doc, w):
    p = doc["profile"]["learning_profile"] or {}
    lines = [f"# {w['profile']}", ""]
    for key in ("chosen", "works_well", "works_poorly", "preferences"):
        items = p.get("teaching_preferences" if key == "chosen" else key) or []
        lines += [f"## {w[key]}", ""] + ([f"- {x}" for x in items] or [w["none"]]) + [""]
    lines += [f"## {w['notes']}", "", p.get("notes") or w["none"], ""]
    return "\n".join(lines)


def conversations_markdown(concept_name, sessions, w):
    lines = [f"# {w['conversations']}: {concept_name}", ""]
    for s in sessions:
        lines += [f"## {str(s.get('started_at') or '')[:16].replace('T', ' ')}", ""]
        for m in s["messages"]:
            who = w["learner"] if m["role"] == "user" else w["mentor"]
            lines += [f"**{who}:** {m['content']}", ""]
    return "\n".join(lines)


README = """# Trellis learning memory

Exported {date} from Trellis ({version}) for {name}.

- `memory.json`: everything, in the open format described at
  https://github.com/PaulLaurijssens/Trellis/blob/main/docs/MEMORY-FORMAT.md . Import it into any
  Trellis (My profile > Your data > Import), or read it with any tool that reads JSON.
- `concepts/`: one page per concept with what you understood, the evidence and the sources. The folder
  opens as an Obsidian vault; links between concepts work.
- `conversations/`: your conversations with the mentor, per concept.
- `profile.md`: how you learn.

Not included: your password, API keys and AI provider settings, embeddings (rebuilt on import),
generated lessons, study guides, glossary and reference pages, topic studies, and the full text of
your sources (their titles, links and the quotes linked to concepts are included).

This file holds your conversations and what you understand. Keep it somewhere private.

Counts: {counts}
"""


def zip_bytes(doc: dict) -> bytes:
    lang = doc["person"].get("ui_language") if doc["person"].get("ui_language") in WORDS else "en"
    w = WORDS.get(lang, WORDS["en"])
    concepts = doc["map"]["concepts"]
    slugs = _slugs(concepts)
    by_concept = {}
    for s in doc["conversations"]:
        by_concept.setdefault(s["concept"], []).append(s)
    ids = {c["name"]: c["id"] for c in concepts}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("memory.json", json.dumps(doc, ensure_ascii=False, indent=1))
        z.writestr("README.md", README.format(date=doc["exported_at"][:10], version=doc["trellis_version"],
                                              name=doc["person"].get("name") or "", counts=json.dumps(doc["counts"])))
        z.writestr("profile.md", profile_markdown(doc, w))
        for c in concepts:
            z.writestr(f"concepts/{slugs[c['id']]}.md", concept_markdown(c, doc, slugs, w))
        for name, sessions in by_concept.items():
            z.writestr(f"conversations/{slugs.get(ids.get(name), slug(name))}.md", conversations_markdown(name, sessions, w))
    return buf.getvalue()


def filename() -> str:
    return f"trellis-memory-{datetime.now(timezone.utc).date().isoformat()}.zip"
