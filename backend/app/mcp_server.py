"""Read access to the learning memory for other AIs: a small MCP server (docs/MCP.md).

Streamable HTTP, stateless, JSON responses only (no event stream), tools only. Every request needs a
personal access token (tokens.py) as `Authorization: Bearer ...`; the session cookie is not accepted
here, and a browser page from another site is refused by its Origin header. All tools read only, and
every answer is scoped to the token's own learner.
"""
import json
import os
import re
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Response

from . import graph, journey, personal_context, tokens

router = APIRouter()
VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
RATE = 120                      # calls per token per minute
_calls: dict[str, deque] = defaultdict(deque)
MAX_TEXT = 24000

INSTRUCTIONS = ("Trellis holds this learner's own learning memory: the concepts they study, what they have shown "
                "they understand (with quotes as evidence), open difficulties and misconceptions, and how they like "
                "to learn. Use it to adapt explanations. A self-assessment or a discussed topic is not proof of "
                "mastery; only 'demonstrated' evidence is. The learner owns this memory and decides what enters it.")


def _tool(name, title, description, properties=None, required=None, scope="memory:read"):
    return {"name": name, "title": title, "description": description, "scope": scope,
            "inputSchema": {"type": "object", "properties": properties or {}, "required": required or [],
                            "additionalProperties": False},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}}


NAME = {"type": "string", "description": "Concept name or alias, as on the learner's map", "minLength": 1, "maxLength": 200}
TOOLS = [
    _tool("search_memory", "Search my learning memory",
          "Find concepts on the learner's knowledge map by name, alias or definition. Returns each match with its "
          "learning status and a one-line view of the learner's understanding.",
          {"query": {"type": "string", "minLength": 1, "maxLength": 200},
           "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10}}, ["query"]),
    _tool("get_concept", "What I know about a concept",
          "Definition, place on the map (needs first, leads to, related), sources, and the learner's understanding: "
          "summary, open difficulties and misconceptions, demonstrated evidence, own assessment and intent.",
          {"name": NAME}, ["name"]),
    _tool("list_concepts", "List my concepts",
          "The concepts the learner studies or plans to study, with status and indicators. Filter by status, or "
          "only those that need attention (open difficulties or misconceptions).",
          {"status": {"type": "string", "enum": ["learning", "learned", "queued", "suggested"]},
           "needs_attention": {"type": "boolean"},
           "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 50},
           "offset": {"type": "integer", "minimum": 0, "default": 0}}),
    _tool("get_learner_profile", "How I learn",
          "What works for this learner, what does not, their preferences and the teaching approaches they chose. "
          "Applies to all topics."),
    _tool("get_learning_focus", "What I am working on",
          "The active learning goal and its next steps, concepts due for a short review, open difficulties across "
          "concepts, and recently studied concepts."),
    _tool("get_teaching_brief", "How to teach me this",
          "The same personal context Trellis gives its own mentor before explaining this concept: what the learner "
          "already discussed, struggled with, demonstrated, and how they like to learn.",
          {"name": NAME}, ["name"]),
    _tool("get_conversations", "My conversations about a concept",
          "The most recent conversations between the learner and the Trellis mentor about one concept (raw text). "
          "Needs a connection that allows conversations.",
          {"name": NAME, "limit": {"type": "integer", "minimum": 1, "maximum": 5, "default": 2}}, ["name"],
          scope="conversations:read"),
]


class ToolProblem(Exception):
    """Shown to the calling AI as a tool error (isError), not as a protocol error."""


# ---- the tools -------------------------------------------------------------------------------------

def _concept(name):
    c = graph.find_concept(name)
    if not c:
        raise ToolProblem(f"No concept named '{name}' on this learner's map. Use search_memory to find the right name.")
    return c


def _one_line(state):
    if not state:
        return "not studied yet"
    shown = sum(e.get("outcome") == "demonstrated" for e in state.get("evidence", []))
    open_ = len(state.get("struggles", [])) + len(state.get("misconceptions", []))
    own = (state.get("self_assessment") or {}).get("value")
    bits = [f"{shown} demonstrated", f"{open_} open difficult{'y' if open_ == 1 else 'ies'}"]
    if own:
        bits.append(f"own assessment: {own}")
    return ", ".join(bits)


def _mine(pid):
    return {s["concept_id"]: s for s in graph.all_understands(pid)}


def _lucene(text):
    return re.sub(r'([+\-!(){}\[\]^"~*?:\\/]|&&|\|\|)', r"\\\1", text.strip())


def search_memory(pid, query, limit=10):
    limit = max(1, min(int(limit or 10), 20))
    try:
        rows = graph.run("""CALL db.index.fulltext.queryNodes('concept_text', $q) YIELD node, score
                            RETURN node.id AS id, node.name AS name, coalesce(node.status,'suggested') AS status,
                                   coalesce(node.definition,'') AS definition LIMIT $n""",
                         q=_lucene(query) + "~", n=limit)
    except Exception:
        rows = []
    if not rows:
        rows = graph.run("""MATCH (c:Concept) WHERE toLower(c.name) CONTAINS toLower($q) OR toLower(coalesce(c.definition,'')) CONTAINS toLower($q)
                               OR any(a IN coalesce(c.aliases,[]) WHERE toLower(a) CONTAINS toLower($q))
                            RETURN c.id AS id, c.name AS name, coalesce(c.status,'suggested') AS status,
                                   coalesce(c.definition,'') AS definition ORDER BY size(c.name) LIMIT $n""", q=query, n=limit)
    mine = _mine(pid)
    results = [{"name": r["name"], "status": r["status"], "definition": r["definition"][:300],
                "understanding": _one_line(mine.get(r["id"]))} for r in rows]
    text = "\n".join(f"- {r['name']} ({r['status']}; {r['understanding']}): {r['definition'][:160]}" for r in results)
    return text or f"Nothing matches '{query}'.", {"results": results}


def get_concept(pid, name):
    c = _concept(name)
    ctx = graph.concept_context(c["name"]) or {}
    leads = [r["name"] for r in graph.run("MATCH (:Concept {id:$id})-[:PREREQUISITE_OF]->(n:Concept) RETURN n.name AS name ORDER BY name", id=c["id"])]
    state = graph.understands_state(pid, c["id"])
    sources = [{"title": m.get("source"), "url": m.get("url"), "context": m.get("context")} for m in ctx.get("mentions", [])]
    data = {"name": c["name"], "status": c["status"], "definition": c.get("definition") or "",
            "needs_first": ctx.get("prerequisites", []), "leads_to": leads, "related": ctx.get("related", []),
            "sources": sources, "understanding": None}
    lines = [f"# {c['name']} ({c['status']})", c.get("definition") or "(no definition)"]
    if data["needs_first"]:
        lines.append("Needs first: " + ", ".join(data["needs_first"]))
    if leads:
        lines.append("Leads to: " + ", ".join(leads))
    if data["related"]:
        lines.append("Related: " + ", ".join(data["related"]))
    if state:
        evidence = sorted(state.get("evidence", []), key=lambda e: e.get("date") or "", reverse=True)
        u = {"summary": state.get("summary") if not state.get("summary_stale") else None,
             "intent": state.get("intent"), "own_assessment": (state.get("self_assessment") or {}).get("value"),
             "open_difficulties": state.get("struggles", []), "misconceptions": state.get("misconceptions", []),
             "discussed": state.get("covered", []), "last_studied": state.get("last_session"),
             "evidence": [{"outcome": e.get("outcome"), "kind": e.get("kind"), "origin": e.get("origin"),
                           "what": e.get("quote") or e.get("prompt"), "assessment": e.get("assessment") or "",
                           "date": e.get("date")} for e in evidence[:5]],
             "demonstrated_total": sum(e.get("outcome") == "demonstrated" for e in evidence)}
        data["understanding"] = u
        lines.append("\n## The learner's understanding")
        if u["summary"]:
            lines.append("Summary: " + u["summary"])
        lines.append(f"Intent: {u['intent']}; own assessment (not evidence): {u['own_assessment'] or 'none'}; "
                     f"demonstrated: {u['demonstrated_total']}")
        if u["open_difficulties"]:
            lines.append("Open difficulties: " + "; ".join(u["open_difficulties"]))
        if u["misconceptions"]:
            lines.append("Misconceptions: " + "; ".join(u["misconceptions"]))
        for e in u["evidence"]:
            lines.append(f"- {str(e['date'] or '')[:10]} {e['outcome']} ({e['kind']}, {e['origin']}): {e['what']}")
    else:
        lines.append("\nThe learner has not studied this concept yet.")
    if sources:
        lines.append("\nSources: " + "; ".join(f"{s['title']} {s['url'] or ''}".strip() for s in sources))
    return "\n".join(lines), data


def list_concepts(pid, status=None, needs_attention=None, limit=50, offset=0):
    limit, offset = max(1, min(int(limit or 50), 100)), max(0, int(offset or 0))
    states = graph.all_understands(pid)
    rows = []
    for s in states:
        if status and s.get("concept_status") != status:
            continue
        open_ = len(s.get("struggles", [])) + len(s.get("misconceptions", []))
        if needs_attention and not open_:
            continue
        rows.append({"name": s["concept"], "status": s.get("concept_status"), "open_difficulties": open_,
                     "demonstrated": sum(e.get("outcome") == "demonstrated" for e in s.get("evidence", [])),
                     "last_studied": s.get("last_session")})
    page = rows[offset:offset + limit]
    text = "\n".join(f"- {r['name']} ({r['status']}): {r['demonstrated']} demonstrated, {r['open_difficulties']} open"
                     for r in page) or "No concepts match."
    return text, {"total": len(rows), "offset": offset, "concepts": page}


def get_learner_profile(pid):
    p = graph.learning_profile(pid)
    lang = graph.ui_language(pid)
    data = {"language": lang, "chosen_teaching_approaches": p.get("teaching_preferences") or [],
            "works_well": p.get("works_well") or [], "works_poorly": p.get("works_poorly") or [],
            "preferences": p.get("preferences") or [], "notes": p.get("notes") or ""}
    parts = [f"Preferred language: {graph.LANGUAGE_NAMES_EN.get(lang, lang)}"]
    for key, label in (("chosen_teaching_approaches", "Chose"), ("works_well", "Works well"),
                       ("works_poorly", "Does not work"), ("preferences", "Preferences")):
        if data[key]:
            parts.append(f"{label}: " + "; ".join(data[key]))
    if data["notes"]:
        parts.append("Notes: " + data["notes"])
    return "\n".join(parts), data


def get_learning_focus(pid):
    overview = journey.overview(pid)
    goal = overview.get("active_goal")
    states = graph.all_understands(pid)
    open_ = [{"concept": s["concept"], "kind": o["kind"], "text": o["text"]}
             for s in states for o in s.get("observations", []) if o.get("state") == "active"][:15]
    recent = [{"concept": s["concept"], "last_studied": s.get("last_session")} for s in states if s.get("last_session")][:5]
    data = {"goal": None, "due_for_review": [{"concept": r["concept"], "kind": r["kind"], "days_since": r["days"]}
                                             for r in overview.get("review", [])],
            "open_difficulties": open_, "recently_studied": recent}
    lines = []
    if goal:
        steps = goal.get("steps", [])
        nxt = [s["name"] for s in steps if not s.get("done")][:5]
        data["goal"] = {"title": goal["title"], "steps_done": sum(bool(s.get("done")) for s in steps),
                        "steps_total": len(steps), "next_steps": nxt}
        lines.append(f"Goal: {goal['title']} ({data['goal']['steps_done']}/{len(steps)} steps). Next: {', '.join(nxt) or 'none'}")
    else:
        lines.append("No active learning goal.")
    if data["due_for_review"]:
        lines.append("Due for a short review: " + ", ".join(f"{r['concept']} ({r['kind']})" for r in data["due_for_review"]))
    if open_:
        lines.append("Open difficulties: " + "; ".join(f"{o['concept']}: {o['text']}" for o in open_))
    if recent:
        lines.append("Recently studied: " + ", ".join(r["concept"] for r in recent))
    return "\n".join(lines), data


def get_teaching_brief(pid, name):
    c = _concept(name)
    brief = personal_context.personal_context(pid, c["id"]).strip()
    text = f"# How to teach this learner '{c['name']}'\n{c.get('definition') or ''}\n{brief or 'No personal memory for this concept yet.'}"
    return text[:MAX_TEXT], {"concept": c["name"], "brief": brief[:MAX_TEXT]}


def get_conversations(pid, name, limit=2):
    c = _concept(name)
    limit = max(1, min(int(limit or 2), 5))
    sessions = graph.run("""MATCH (s:ChatSession {person_id:$pid, concept_id:$cid})
                            RETURN s.id AS id, s.started_at AS started_at ORDER BY s.last_activity DESC LIMIT $n""",
                         pid=pid, cid=c["id"], n=limit)
    out, budget = [], MAX_TEXT
    for s in sessions:
        messages = []
        for m in graph.session_messages(s["id"]):
            content = m["content"][:max(0, budget)]
            budget -= len(content)
            messages.append({"role": "learner" if m["role"] == "user" else "mentor", "text": content, "ts": m.get("ts")})
            if budget <= 0:
                break
        out.append({"started_at": s["started_at"], "messages": messages})
        if budget <= 0:
            break
    text = "\n\n".join(f"## {str(s['started_at'])[:16]}\n" + "\n".join(f"{m['role']}: {m['text']}" for m in s["messages"]) for s in out)
    return text or f"No conversations about '{c['name']}' yet.", {"concept": c["name"], "conversations": out}


HANDLERS = {"search_memory": search_memory, "get_concept": get_concept, "list_concepts": list_concepts,
            "get_learner_profile": get_learner_profile, "get_learning_focus": get_learning_focus,
            "get_teaching_brief": get_teaching_brief, "get_conversations": get_conversations}


# ---- the protocol --------------------------------------------------------------------------------------

def _visible(scopes):
    return [{k: v for k, v in t.items() if k != "scope"} for t in TOOLS if t["scope"] in scopes]


def _check_args(tool, args):
    schema = tool["inputSchema"]
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    unknown = set(args) - set(schema["properties"])
    if unknown:
        raise ValueError("unknown argument(s): " + ", ".join(sorted(unknown)))
    for key in schema["required"]:
        if key not in args:
            raise ValueError(f"missing argument: {key}")
    for key, value in args.items():
        spec = schema["properties"][key]
        kind = spec["type"]
        ok = (isinstance(value, str) if kind == "string" else isinstance(value, bool) if kind == "boolean"
              else isinstance(value, int) and not isinstance(value, bool))
        if not ok:
            raise ValueError(f"{key} must be a {kind}")
        if kind == "string" and not (spec.get("minLength", 0) <= len(value.strip() if spec.get("minLength") else value) and len(value) <= spec.get("maxLength", 10000)):
            raise ValueError(f"{key} has the wrong length")
        if "enum" in spec and value not in spec["enum"]:
            raise ValueError(f"{key} must be one of: " + ", ".join(spec["enum"]))
        if kind == "integer" and not (spec.get("minimum", value) <= value <= spec.get("maximum", value)):
            raise ValueError(f"{key} is out of range")


def handle(message, access):
    """One JSON-RPC message -> its response dict, or None for a notification or a response."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid Request")
    method, mid = message.get("method"), message.get("id")
    if method is None:                        # a response from the client: nothing to answer
        return None
    is_notification = "id" not in message
    params = message.get("params") or {}
    if is_notification:
        return None
    if not isinstance(params, dict):
        return _error(mid, -32602, "params must be an object")
    if method == "initialize":
        asked = params.get("protocolVersion")
        version = asked if asked in VERSIONS else VERSIONS[1]
        return _result(mid, {"protocolVersion": version,
                             "capabilities": {"tools": {"listChanged": False}},
                             "serverInfo": {"name": "trellis", "title": "Trellis learning memory",
                                            "version": os.getenv("TRELLIS_VERSION") or "dev"},
                             "instructions": INSTRUCTIONS})
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": _visible(access["scopes"])})
    if method == "tools/call":
        name, args = params.get("name"), params.get("arguments") or {}
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if tool is None:
            return _error(mid, -32602, f"Unknown tool: {name}")
        if tool["scope"] not in access["scopes"]:
            return _result(mid, _content(f"This connection may not use {name}. In Trellis, create a connection that allows "
                                         "conversations (My profile > Your data > Connect an AI).", None, error=True))
        try:
            _check_args(tool, args)
        except ValueError as exc:
            return _error(mid, -32602, f"Invalid arguments for {name}: {exc}")
        try:
            text, data = HANDLERS[name](access["person_id"], **args)
        except ToolProblem as exc:
            return _result(mid, _content(str(exc), None, error=True))
        return _result(mid, _content(text, data))
    return _error(mid, -32601, f"Method not found: {method}")


def _content(text, data, error=False):
    out = {"content": [{"type": "text", "text": text[:MAX_TEXT]}], "isError": error}
    if data is not None:
        out["structuredContent"] = data
    return out


def _result(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _json(body, status=200):
    return Response(json.dumps(body, ensure_ascii=False), status_code=status, media_type="application/json")


def _origin_allowed(request: Request) -> bool:
    """Spec: refuse a browser page from another site (DNS rebinding). Clients outside a browser send no
    Origin. nginx passes Host without its port, so host names are compared, not host:port."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    allowed = {o.strip().rstrip("/") for o in os.getenv("MCP_ALLOWED_ORIGINS", "").split(",") if o.strip()}
    if origin.rstrip("/") in allowed:
        return True
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    return bool(host) and urlparse(origin).hostname == urlparse("//" + host).hostname


def _limited(token_id) -> bool:
    now, calls = time.monotonic(), _calls[token_id]
    while calls and now - calls[0] > 60:
        calls.popleft()
    if len(calls) >= RATE:
        return True
    calls.append(now)
    return False


@router.post("/mcp")
async def mcp(request: Request):
    if not _origin_allowed(request):
        return _json({"error": "Origin not allowed"}, 403)
    auth = request.headers.get("authorization") or ""
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    access = tokens.resolve(token)
    if not access:
        return Response(json.dumps({"error": "A Trellis access token is required (Authorization: Bearer ...)."}),
                        status_code=401, media_type="application/json",
                        headers={"WWW-Authenticate": 'Bearer realm="trellis", error="invalid_token"'})
    version = request.headers.get("mcp-protocol-version")
    if version and version not in VERSIONS:
        return _json(_error(None, -32600, f"Unsupported MCP-Protocol-Version {version}"), 400)
    if _limited(access["id"]):
        return Response(json.dumps(_error(None, -32000, "Too many requests; wait a minute.")), status_code=429,
                        media_type="application/json", headers={"Retry-After": "60"})
    try:
        body = json.loads(await request.body())
    except ValueError:
        return _json(_error(None, -32700, "Parse error"), 400)
    if isinstance(body, list):
        if not body:
            return _json(_error(None, -32600, "Empty batch"), 400)
        answers = [a for a in (handle(m, access) for m in body[:50]) if a is not None]
        return _json(answers) if answers else Response(status_code=202)
    answer = handle(body, access)
    return _json(answer) if answer is not None else Response(status_code=202)


@router.get("/mcp")
@router.delete("/mcp")
def no_stream():
    """No server-initiated stream and no sessions in this stateless server."""
    return Response(status_code=405, headers={"Allow": "POST"})
