"""Neo4j toegang. Alle Cypher op één plek."""
import json, os, uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from neo4j import GraphDatabase

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "changeme123")),
    notifications_min_severity="OFF",     # schema hints ("index already exists" etc.) flooded the API log
)

VALID_RELS = {"PREREQUISITE_OF", "PART_OF", "RELATED_TO"}
# Leerstatus van een concept. Loopt maar één kant op: een concept dat je al
# leert wordt niet weer een suggestie.
VALID_STATUS = ("suggested", "queued", "learning", "learned")
# queued = uit een analyse opgenomen maar nog niet geleerd; zit onder learning.
STATUS_RANK = {"suggested": 0, "queued": 1, "learning": 2, "learned": 3}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_transaction = ContextVar("memory_transaction", default=None)

def memory_transaction(person_id, callback):
    if _transaction.get() is not None:
        return callback()
    def execute(tx):
        token = _transaction.set(tx)
        try:
            # All memory commits/corrections use this same per-person write lock.
            tx.run("MERGE (p:Person {id:$pid}) SET p.memory_revision=coalesce(p.memory_revision,0)+1",pid=person_id).consume()
            return callback()
        finally:
            _transaction.reset(token)
    with driver.session() as session:
        return session.execute_write(execute)

def run(query: str, **params):
    tx=_transaction.get()
    if tx is not None:
        return [r.data() for r in tx.run(query, **params)]
    with driver.session() as s:
        return [r.data() for r in s.run(query, **params)]


def _split_cypher(script: str) -> list[str]:
    """Splits een Cypher-script in statements. Strips //-commentaar vóór het
    splitsen op ';', en negeert beide binnen quotes/backticks."""
    stmts, buf, quote = [], [], None
    i, n = 0, len(script)
    while i < n:
        ch = script[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
        elif ch in ("'", '"', "`"):
            quote = ch
            buf.append(ch)
            i += 1
        elif ch == "/" and script[i + 1 : i + 2] == "/":
            while i < n and script[i] != "\n":
                i += 1
        elif ch == ";":
            stmts.append("".join(buf).strip())
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    stmts.append("".join(buf).strip())
    return [s for s in stmts if s]


def init_schema(path: str = "/import/schema.cypher"):
    with open(path) as f:
        for stmt in _split_cypher(f.read()):
            run(stmt)


def vector_index_dim() -> int | None:
    rows = run("SHOW INDEXES YIELD name, type, options WHERE name = 'concept_embedding' RETURN options")
    if not rows:
        return None
    try:
        return int(rows[0]["options"]["indexConfig"]["vector.dimensions"])
    except (KeyError, TypeError, ValueError):
        return None


def ensure_vector_index(dim: int):
    """The embedding size is fixed at setup. A different size later would silently break similarity
    search, so it is refused unless the graph holds no embeddings yet (then the index is rebuilt)."""
    current = vector_index_dim()
    if current == dim:
        return
    if current is not None:
        embedded = run("MATCH (c:Concept) WHERE c.embedding IS NOT NULL RETURN count(c) AS n")[0]["n"]
        if embedded:
            raise ValueError(f"This database already holds {embedded} concepts embedded with size {current}. "
                             f"Keep an embedding provider with size {current}, or start with an empty database.")
        run("DROP INDEX concept_embedding IF EXISTS")
    run(f"""CREATE VECTOR INDEX concept_embedding IF NOT EXISTS FOR (c:Concept) ON (c.embedding)
            OPTIONS {{ indexConfig: {{ `vector.dimensions`: {int(dim)}, `vector.similarity_function`: 'cosine' }} }}""")


def create_pending_source(type_: str, title: str, url: str | None = None) -> str:
    """Een suggestieronde parkeert zijn bron als :PendingSource. Pas als er
    echt van geleerd wordt promoveert die naar een volwaardige :Source."""
    sid = str(uuid.uuid4())
    run("""CREATE (p:PendingSource {id:$id, type:$type, title:$title, url:$url, created_at:$ts})""",
        id=sid, type=type_, title=title, url=url, ts=_now())
    return sid


def source_exists(source_id: str) -> bool:
    """Vooraf te controleren, zodat een verlopen bron geen half-geschreven
    concept achterlaat en geen LLM-call verspilt."""
    rows = run("""
        OPTIONAL MATCH (p:PendingSource {id:$id})
        OPTIONAL MATCH (s:Source {id:$id})
        RETURN coalesce(p, s) IS NOT NULL AS found
    """, id=source_id)
    return bool(rows and rows[0]["found"])


def promote_source(source_id: str) -> dict | None:
    """Maakt van een PendingSource een Source. Idempotent: een tweede /learn
    op dezelfde bron vindt hem gewoon terug."""
    rows = run("""
        OPTIONAL MATCH (p:PendingSource {id:$id})
        OPTIONAL MATCH (s:Source {id:$id})
        WITH coalesce(p, s) AS n
        WHERE n IS NOT NULL
        REMOVE n:PendingSource
        SET n:Source, n.ingested_at = coalesce(n.ingested_at, $ts)
        RETURN n.id AS id, n.title AS title, n.type AS type
    """, id=source_id, ts=_now())
    return rows[0] if rows else None


def purge_pending_sources(days: int = 7) -> int:
    """Suggestierondes waar nooit van geleerd is, verlopen. De timestamps zijn
    ISO-8601 in UTC en dus lexicografisch vergelijkbaar."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = run("""
        MATCH (p:PendingSource) WHERE p.created_at < $cutoff
        DETACH DELETE p
        RETURN count(p) AS purged
    """, cutoff=cutoff)
    return rows[0]["purged"] if rows else 0


def find_similar(embedding: list[float], k: int = 3) -> list[dict]:
    return run("""
        CALL db.index.vector.queryNodes('concept_embedding', $k, $emb)
        YIELD node, score
        RETURN node.id AS id, node.name AS name, node.definition AS definition, score
    """, k=k, emb=embedding)


def upsert_concept(name: str, definition: str, aliases: list[str], domain: str,
                   embedding: list[float], status: str = "suggested") -> str:
    cid = str(uuid.uuid4())
    # Een alias wordt alleen toegevoegd als geen ander Concept die term al claimt
    # als naam of alias (case-insensitive). Anders zou bijv. "forward pass" zowel
    # een eigen node zijn als alias van backpropagation, en wordt lookup ambigu.
    rows = run("""
        MERGE (c:Concept {name:$name})
        ON CREATE SET c.id=$id, c.definition=$definition, c.domain=$domain,
                      c.embedding=$emb, c.created_at=$ts
        WITH c
        CALL {
            WITH c
            UNWIND $aliases AS alias
            WITH c, alias
            WHERE trim(alias) <> ''
              AND toLower(alias) <> toLower(c.name)
              AND NOT EXISTS {
                  MATCH (other:Concept)
                  WHERE other <> c
                    AND (toLower(other.name) = toLower(alias)
                         OR any(a IN coalesce(other.aliases,[]) WHERE toLower(a) = toLower(alias)))
              }
            RETURN collect(alias) AS free
        }
        WITH c, free,
             CASE coalesce(c.status,'suggested') WHEN 'learned' THEN 3 WHEN 'learning' THEN 2
                  WHEN 'queued' THEN 1 ELSE 0 END AS have
        SET c.aliases = apoc.coll.toSet(coalesce(c.aliases,[]) + free),
            // Status nooit verlagen: suggested < queued < learning < learned.
            c.status = CASE WHEN have >= $rank THEN coalesce(c.status,'suggested') ELSE $status END,
            // Alleen /learn levert een gezaghebbende definitie; suggesties niet.
            c.definition = CASE
                WHEN $status = 'learning' AND trim($definition) <> '' THEN $definition
                WHEN $status = 'queued' AND trim($definition) <> '' AND trim(coalesce(c.definition,'')) = '' THEN $definition
                ELSE c.definition END
        RETURN c.id AS id
    """, name=name, id=cid, definition=definition, aliases=aliases, domain=domain,
        emb=embedding, status=status, rank=STATUS_RANK.get(status, 0), ts=_now())
    return rows[0]["id"]


def link_mention(concept_id: str, source_id: str, context: str, importance: int,
                 mentions: list[dict] | None = None):
    """Context (samenvattende zin) plus de mentions-lijst [{start_sec, quote}]
    als JSON, en de eerste tijdcode apart voor eenvoudige queries."""
    mentions = [m for m in (mentions or []) if m.get("quote") or m.get("start_sec") is not None]
    first = next((m["start_sec"] for m in mentions if m.get("start_sec") is not None), None)
    run("""
        MATCH (c:Concept {id:$cid}), (s:Source {id:$sid})
        MERGE (c)-[m:MENTIONED_IN]->(s)
        SET m.context=$ctx, m.importance=$imp,
            m.mentions = CASE WHEN $mentions <> '[]' THEN $mentions ELSE m.mentions END,
            m.start_sec = coalesce($first, m.start_sec)
    """, cid=concept_id, sid=source_id, ctx=context, imp=importance,
        mentions=json.dumps(mentions, ensure_ascii=False), first=first)


def source_concepts(source_id: str) -> list[dict]:
    """Concepten die daadwerkelijk uit deze bron geleerd zijn (met hun aliassen),
    om relaties uit de analyse alleen tussen geleerde kandidaten te leggen."""
    return run("""
        MATCH (c:Concept)-[:MENTIONED_IN]->(s:Source {id:$sid})
        RETURN c.id AS id, c.name AS name, coalesce(c.aliases,[]) AS aliases
    """, sid=source_id)


def link_concepts(from_id: str, to_id: str, rel: str, strength: float = 1.0,
                  reason: str | None = None):
    if rel not in VALID_RELS:
        return
    run(f"""
        MATCH (a:Concept {{id:$a}}), (b:Concept {{id:$b}})
        MERGE (a)-[r:{rel}]->(b)
        SET r.strength=$s, r.reason=coalesce($reason, r.reason)
    """, a=from_id, b=to_id, s=strength, reason=reason)


def link_asked_about(person_id: str, concept_id: str):
    run("""
        MERGE (p:Person {id:$pid})
        WITH p
        MATCH (c:Concept {id:$cid})
        MERGE (p)-[a:ASKED_ABOUT]->(c)
        SET a.ts=$ts
    """, pid=person_id, cid=concept_id, ts=_now())


def _mark_learned(name: str, person_id: str) -> dict | None:
    """Zet status op 'learned' en legt vast dat de persoon het begrijpt."""
    rows = run("""
        MATCH (c:Concept)
        WHERE toLower(c.name) = toLower($name)
           OR any(a IN coalesce(c.aliases,[]) WHERE toLower(a) = toLower($name))
        WITH c LIMIT 1
        SET c.status = 'learned'
        MERGE (p:Person {id:$pid})
        MERGE (p)-[u:UNDERSTANDS]->(c)
        SET u.since = coalesce(u.since, $ts), u.level = coalesce(p.level, 3)
        RETURN c.name AS name, c.status AS status, p.id AS person
    """, name=name, pid=person_id, ts=_now())
    return rows[0] if rows else None


def mark_learned(name, person_id):
    def commit():
        result=_mark_learned(name,person_id)
        if result:
            concept=find_concept(name)
            state=understands_state(person_id,concept["id"])
            doc=state["memory_v2"]
            doc["self_assessment"]={"value":"understood","date":_now(),"origin":"learner"}
            write_understands(person_id,concept["id"],state)
        return result
    return memory_transaction(person_id,commit)


def get_graph(limit: int = 500) -> dict:
    nodes = run("""
        MATCH (c:Concept)
        OPTIONAL MATCH (c)-[m:MENTIONED_IN]->()
        WITH c, count(m) AS mentions
        OPTIONAL MATCH (c)-[r]-(:Concept)
        RETURN c.id AS id, c.name AS name, c.domain AS domain,
               coalesce(c.status,'suggested') AS status, mentions, count(r) AS degree
        ORDER BY mentions DESC LIMIT $limit
    """, limit=limit)
    edges = run("""
        MATCH (a:Concept)-[r]->(b:Concept)
        RETURN a.id AS source, b.id AS target, type(r) AS type,
               coalesce(r.strength,1.0) AS strength, r.reason AS reason
    """)
    return {"nodes": nodes, "edges": edges}


def concept_context(name: str) -> dict | None:
    rows = run("""
        MATCH (c:Concept) WHERE toLower(c.name) = toLower($name) OR $name IN coalesce(c.aliases,[])
        OPTIONAL MATCH (c)-[m:MENTIONED_IN]->(s:Source)
        OPTIONAL MATCH (p:Concept)-[:PREREQUISITE_OF]->(c)
        OPTIONAL MATCH (c)-[:RELATED_TO]-(rel:Concept)
        RETURN c.name AS name, c.definition AS definition,
               coalesce(c.status,'suggested') AS status,
               collect(DISTINCT {source:s.title, context:m.context, url:s.url, type:s.type,
                                 start_sec:m.start_sec, mentions:m.mentions}) AS mentions,
               collect(DISTINCT p.name) AS prerequisites,
               collect(DISTINCT rel.name) AS related
    """, name=name)
    if not rows:
        return None
    row = rows[0]
    out = []
    for m in row["mentions"]:
        if not m.get("source"):
            continue
        try:
            lst = json.loads(m.get("mentions") or "[]")
        except (TypeError, ValueError):
            lst = []
        out.append({**m, "mentions": [x for x in lst if isinstance(x, dict)]})
    row["mentions"] = out
    return row


# ============================================================
# Laag 1: ruwe gesprekslog. Bron van waarheid, deterministisch.
# ============================================================

def match_names(names: list[str]) -> dict[str, dict]:
    """Lichte match van kandidaatnamen op bestaande concepten (naam of alias,
    case-insensitive). Geen embeddings: dat doet de echte resolutie bij commit."""
    wanted = {str(n).lower().strip() for n in names if str(n).strip()}
    if not wanted:
        return {}
    rows = run("""
        MATCH (c:Concept)
        RETURN c.name AS name, coalesce(c.aliases,[]) AS aliases, coalesce(c.status,'suggested') AS status
    """)
    out = {}
    for r in rows:
        for key in [r["name"], *r["aliases"]]:
            k = str(key).lower().strip()
            if k in wanted:
                out[k] = {"name": r["name"], "status": r["status"]}
    return out


def find_concept(name: str) -> dict | None:
    rows = run("""
        MATCH (c:Concept)
        WHERE toLower(c.name) = toLower($name)
           OR any(a IN coalesce(c.aliases,[]) WHERE toLower(a) = toLower($name))
        RETURN c.id AS id, c.name AS name, c.definition AS definition,
               coalesce(c.status,'suggested') AS status
        LIMIT 1
    """, name=name)
    return rows[0] if rows else None


def create_session(person_id: str, concept_id: str, level: int) -> str:
    sid = str(uuid.uuid4())
    run("""
        MERGE (p:Person {id:$pid})
        WITH p
        MATCH (c:Concept {id:$cid})
        CREATE (s:ChatSession {id:$sid, person_id:$pid, concept_id:$cid, level:$level,
                               started_at:$ts, last_activity:$ts, consolidated:false})
        CREATE (p)-[:HAD_SESSION]->(s)
        CREATE (s)-[:ABOUT]->(c)
    """, pid=person_id, cid=concept_id, sid=sid, level=level, ts=_now())
    from . import journey
    journey.attach_session(person_id, sid)
    return sid


def active_session(person_id: str, concept_id: str) -> dict | None:
    """De laatste nog niet geconsolideerde sessie voor dit concept."""
    rows = run("""
        MATCH (s:ChatSession {person_id:$pid, concept_id:$cid})
        WHERE s.consolidated = false
        RETURN s.id AS id, s.level AS level, s.started_at AS started_at
        ORDER BY s.started_at DESC LIMIT 1
    """, pid=person_id, cid=concept_id)
    return rows[0] if rows else None


def add_message(session_id: str, role: str, content: str, illustration=None) -> int:
    rows = run("""
        MATCH (s:ChatSession {id:$sid})
        SET s.message_revision=coalesce(s.message_revision,0)+1, s.consolidated=false
        WITH s
        OPTIONAL MATCH (s)-[:HAS_MESSAGE]->(m:ChatMessage)
        WITH s, coalesce(max(m.seq), -1) + 1 AS seq
        CREATE (s)-[:HAS_MESSAGE]->(:ChatMessage {seq:seq, role:$role, content:$content, ts:$ts, illustration:$illustration})
        SET s.last_activity = $ts
        RETURN seq
    """, sid=session_id, role=role, content=content, ts=_now(),
        illustration=json.dumps(illustration, ensure_ascii=False) if illustration else None)
    return rows[0]["seq"] if rows else 0


def session_messages(session_id: str) -> list[dict]:
    rows = run("""
        MATCH (:ChatSession {id:$sid})-[:HAS_MESSAGE]->(m:ChatMessage)
        RETURN m.seq AS seq, m.role AS role, m.content AS content, m.ts AS ts, m.illustration AS illustration
        ORDER BY m.seq
    """, sid=session_id)
    from .illustrations import validate
    for row in rows:
        try:
            row["illustration"] = validate(json.loads(row.get("illustration") or "null"))
        except (ValueError, TypeError):
            row["illustration"] = None
    return rows


def session_info(session_id: str) -> dict | None:
    rows = run("""
        MATCH (s:ChatSession {id:$sid})-[:ABOUT]->(c:Concept)
        RETURN s.id AS id, s.person_id AS person_id, s.level AS level,
               c.id AS concept_id, c.name AS concept, s.consolidated AS consolidated,
               s.started_at AS started_at, s.last_activity AS last_activity,
               coalesce(s.message_revision,0) AS message_revision, s.memory_checkpoint AS memory_checkpoint,
               s.memory_error AS memory_error
    """, sid=session_id)
    return rows[0] if rows else None


def stale_sessions(minutes: int) -> list[str]:
    """Sessies die lang genoeg stil liggen om te consolideren."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    rows = run("""
        MATCH (s:ChatSession) WHERE s.consolidated = false AND s.last_activity < $cutoff
        RETURN s.id AS id ORDER BY s.last_activity
    """, cutoff=cutoff)
    return [r["id"] for r in rows]


def person_sessions(person_id: str) -> list[str]:
    """Alle sessies chronologisch: de invoer voor een rebuild."""
    rows = run("""
        MATCH (s:ChatSession {person_id:$pid})
        RETURN s.id AS id ORDER BY s.started_at
    """, pid=person_id)
    return [r["id"] for r in rows]


def mark_consolidated(session_id: str):
    run("MATCH (s:ChatSession {id:$sid}) SET s.consolidated = true, s.memory_error=null", sid=session_id)


# ============================================================
# Laag 2: begripstoestand per concept (UNDERSTANDS-relatie).
# Afgeleid uit laag 1, dus volledig herbouwbaar.
# ============================================================

STATE_LISTS = ("covered", "struggles", "misconceptions")
STATE_SCALARS = ("summary", "quiz_correct", "quiz_wrong")


def _ensure_understands(person_id: str, concept_id: str, level: int):
    run("""
        MERGE (p:Person {id:$pid})
        WITH p
        MATCH (c:Concept {id:$cid})
        MERGE (p)-[u:UNDERSTANDS]->(c)
        ON CREATE SET u.since = $ts, u.level = $level, u.status = 'in_progress'
    """, pid=person_id, cid=concept_id, level=level, ts=_now())


def ensure_understands(person_id, concept_id, level):
    def commit():
        _ensure_understands(person_id,concept_id,level)
        state=understands_state(person_id,concept_id)
        if state:
            state["memory_v2"]["intent"]="learning"
            status="learned" if (state["memory_v2"].get("self_assessment") or {}).get("value")=="understood" else "learning"
            run("MATCH (c:Concept {id:$cid}) SET c.status=$status",cid=concept_id,status=status)
            write_understands(person_id,concept_id,state)
    return memory_transaction(person_id,commit)


def set_level(person_id: str, concept_id: str, session_id: str | None, level: int):
    """Gekozen niveau vastleggen op de sessie (standaard voor de rest van het
    gesprek) en op UNDERSTANDS (zodat een volgend gesprek erop opent)."""
    run("""
        MATCH (p:Person {id:$pid})-[u:UNDERSTANDS]->(c:Concept {id:$cid})
        SET u.level = $level
    """, pid=person_id, cid=concept_id, level=level)
    if session_id:
        run("MATCH (s:ChatSession {id:$sid}) SET s.level = $level", sid=session_id, level=level)


def understands_state(person_id: str, concept_id: str) -> dict | None:
    rows = run("""
        MATCH (p:Person {id:$pid})-[u:UNDERSTANDS]->(c:Concept {id:$cid})
        RETURN c.id AS concept_id, c.status AS concept_status, u.memory_v2 AS memory_v2, u.level AS level, u.status AS status, u.summary AS summary,
               coalesce(u.covered,[]) AS covered,
               coalesce(u.struggles,[]) AS struggles,
               coalesce(u.misconceptions,[]) AS misconceptions,
               coalesce(u.quiz_correct,0) AS quiz_correct,
               coalesce(u.quiz_wrong,0) AS quiz_wrong,
               coalesce(u.removed,[]) AS removed,
               coalesce(u.manual_fields,[]) AS manual_fields,
               u.last_session AS last_session, u.since AS since
    """, pid=person_id, cid=concept_id)
    return _memory_state(rows[0]) if rows else None


def write_understands(person_id: str, concept_id: str, state: dict):
    run("""
        MERGE (p:Person {id:$pid})
        WITH p
        MATCH (c:Concept {id:$cid})
        MERGE (p)-[u:UNDERSTANDS]->(c)
        SET u.since = coalesce(u.since, $ts),
            u.covered = $covered, u.struggles = $struggles,
            u.misconceptions = $misconceptions, u.summary = $summary,
            u.quiz_correct = $quiz_correct, u.quiz_wrong = $quiz_wrong,
            u.removed = $removed, u.manual_fields = $manual_fields,
            u.last_session = coalesce($last_session, u.last_session),
            u.status = coalesce($status, u.status, 'in_progress'),
            u.level = coalesce($level, u.level),
            u.memory_v2 = coalesce($memory_v2, u.memory_v2)
    """, pid=person_id, cid=concept_id, ts=_now(),
        memory_v2=json.dumps(state["memory_v2"],ensure_ascii=False) if state.get("memory_v2") else None,
        covered=state.get("covered", []), struggles=state.get("struggles", []),
        misconceptions=state.get("misconceptions", []), summary=state.get("summary"),
        quiz_correct=int(state.get("quiz_correct", 0)), quiz_wrong=int(state.get("quiz_wrong", 0)),
        removed=state.get("removed", []), manual_fields=state.get("manual_fields", []),
        last_session=state.get("last_session"), status=state.get("status"),
        level=state.get("level"))


def all_understands(person_id: str) -> list[dict]:
    rows = run("""
        MATCH (p:Person {id:$pid})-[u:UNDERSTANDS]->(c:Concept)
        RETURN c.name AS concept, c.id AS concept_id, coalesce(c.status,'suggested') AS concept_status,
               u.memory_v2 AS memory_v2, u.level AS level, u.status AS status, u.summary AS summary,
               coalesce(u.covered,[]) AS covered,
               coalesce(u.struggles,[]) AS struggles,
               coalesce(u.misconceptions,[]) AS misconceptions,
               coalesce(u.quiz_correct,0) AS quiz_correct,
               coalesce(u.quiz_wrong,0) AS quiz_wrong,
               coalesce(u.removed,[]) AS removed,
               coalesce(u.manual_fields,[]) AS manual_fields,
               u.last_session AS last_session, u.since AS since
        ORDER BY coalesce(u.last_session, u.since) DESC
    """, pid=person_id)

    return [_memory_state(row) for row in rows]


# ============================================================
# Laag 3: leerprofiel per persoon. JSON-string op de Person-node.
# ============================================================

from . import languages as _languages
LANGUAGES = {code: entry["native"] for code, entry in _languages.LANGUAGES.items()}     # code -> native name (UI)
LANGUAGE_NAMES_EN = {code: entry["name"] for code, entry in _languages.LANGUAGES.items()}   # code -> English name (prompts)


def ui_language(person_id: str) -> str:
    """Voorkeurstaal van de persoon (UI en geheugen). Standaard Nederlands."""
    rows = run("MERGE (p:Person {id:$pid}) RETURN p.ui_language AS lang", pid=person_id)
    lang = (rows[0]["lang"] if rows else None) or "en"
    return lang if lang in LANGUAGES else "en"


def set_ui_language(person_id: str, lang: str) -> str:
    if lang not in LANGUAGES:
        raise ValueError("unknown language")
    run("MERGE (p:Person {id:$pid}) SET p.ui_language = $lang", pid=person_id, lang=lang)
    return lang


PROFILE_LISTS = ("works_well", "works_poorly", "preferences")


def display_preferences(person_id):
    rows = run("MERGE (p:Person {id:$pid}) RETURN coalesce(p.ambient_motion, true) AS ambient_motion", pid=person_id)
    return rows[0] if rows else {"ambient_motion": True}


def set_ambient_motion(person_id, enabled):
    run("MERGE (p:Person {id:$pid}) SET p.ambient_motion=$enabled", pid=person_id, enabled=enabled)

EMPTY_PROFILE = {"works_well": [], "works_poorly": [], "preferences": [],
                 "notes": "", "removed": [], "manual_fields": [], "updated_at": None}


def learning_profile(person_id: str) -> dict:
    rows = run("""
        MERGE (p:Person {id:$pid})
        RETURN p.learning_profile AS profile, p.name AS name, p.level AS level
    """, pid=person_id)
    raw = rows[0]["profile"] if rows else None
    profile = dict(EMPTY_PROFILE)
    if raw:
        try:
            profile.update(json.loads(raw))
        except (ValueError, TypeError):
            pass          # kapotte JSON blokkeert de chat niet
    return profile


def save_learning_profile(person_id: str, profile: dict):
    profile = {**profile, "updated_at": _now()}
    run("MERGE (p:Person {id:$pid}) SET p.learning_profile = $json",
        pid=person_id, json=json.dumps(profile, ensure_ascii=False))
    return profile


# ---- Context voor de systeemprompt ----

def concept_prompt_context(concept_id: str) -> dict:
    rows = run("""
        MATCH (c:Concept {id:$cid})
        OPTIONAL MATCH (pre:Concept)-[r:PREREQUISITE_OF]->(c)
        WITH c, collect(DISTINCT {name: pre.name, status: coalesce(pre.status,'suggested'),
                                  reason: r.reason}) AS prereqs
        OPTIONAL MATCH (c)-[m:MENTIONED_IN]->(s:Source)
        WITH c, prereqs, collect(DISTINCT {source: s.title, context: m.context, quotes: m.mentions, url: s.url}) AS mentions
        OPTIONAL MATCH (c)-[:RELATED_TO]-(rel:Concept)
        RETURN c.name AS name, c.definition AS definition,
               coalesce(c.status,'suggested') AS status,
               [x IN prereqs WHERE x.name IS NOT NULL] AS prerequisites,
               [x IN mentions WHERE x.source IS NOT NULL] AS mentions,
               collect(DISTINCT rel.name) AS related
    """, cid=concept_id)
    return rows[0] if rows else {}


# Conversation suggestions stay separate from Concept nodes until accepted.
def create_session_suggestions(session_id, person_id, message_seq, items):
    proposals = [{**item, "id": str(uuid.uuid4())} for item in items]
    rows = run("""
        MATCH (s:ChatSession {id:$sid, person_id:$pid})-[:ABOUT]->(c:Concept)
        UNWIND $items AS item
        CREATE (s)-[:HAS_SUGGESTION]->(p:ConceptSuggestion)
        SET p = item, p.state = 'pending', p.message_seq = $seq,
            p.created_at = $ts, p.current_concept = c.name, p.session_id = s.id
        RETURN properties(p) AS suggestion
    """, sid=session_id, pid=person_id, seq=message_seq, ts=_now(), items=proposals)
    return [r["suggestion"] for r in rows]


def session_suggestions(session_id, person_id, message_seq=None):
    rows = run("""
        MATCH (:ChatSession {id:$sid, person_id:$pid})-[:HAS_SUGGESTION]->(p:ConceptSuggestion)
        WHERE $seq IS NULL OR p.message_seq = $seq
        RETURN properties(p) AS suggestion ORDER BY p.message_seq, p.created_at, p.id
    """, sid=session_id, pid=person_id, seq=message_seq)
    return [r["suggestion"] for r in rows]


def act_on_suggestion(suggestion_id, person_id, action):
    """Atomic and retry-safe. Person lock serializes acceptance/canonical lookup."""
    if action not in {"save", "explore", "dismiss"}:
        raise ValueError("Invalid action")

    def write(tx):
        row = tx.run("""
            MATCH (owner:Person {id:$pid})-[:HAD_SESSION]->(s:ChatSession {person_id:$pid})
                  -[:HAS_SUGGESTION]->(p:ConceptSuggestion {id:$id})
            SET owner.suggestion_lock = coalesce(owner.suggestion_lock, 0) + 1
            WITH s, p MATCH (s)-[:ABOUT]->(current:Concept)
            RETURN properties(p) AS proposal, current.id AS current_id
        """, pid=person_id, id=suggestion_id).single()
        if row is None:
            raise KeyError("Suggestion not found")
        p, current_id = row["proposal"], row["current_id"]
        state = p["state"]
        if action == "dismiss":
            if state not in {"pending", "dismissed"}:
                raise ValueError("Accepted suggestions cannot be dismissed")
            tx.run("MATCH (p:ConceptSuggestion {id:$id}) SET p.state='dismissed'", id=suggestion_id).consume()
            return {"id": suggestion_id, "concept": None, "state": "dismissed"}
        if state == "dismissed":
            raise ValueError("Suggestion was dismissed")
        from .suggestions import validate
        if not validate({"suggestions": [p]}, ""):
            raise ValueError("Invalid stored suggestion")
        # Reuse accepted identity even if its name/aliases changed since acceptance.
        if state in {"queued", "explored"}:
            c = tx.run("""
                MATCH (:ConceptSuggestion {id:$id})-[:ACCEPTED_AS]->(c:Concept)
                RETURN c.id AS id, c.name AS name
            """, id=suggestion_id).single()
            if c is None:
                raise ValueError("Previously accepted concept is no longer available")
        else:
            # Existing names/aliases are authoritative; new names use a stable spelling.
            c = tx.run("""
                MATCH (c:Concept) WHERE toLower(c.name)=toLower($name)
                  OR any(a IN coalesce(c.aliases,[]) WHERE toLower(a)=toLower($name))
                RETURN c.id AS id, c.name AS name ORDER BY c.name LIMIT 1
            """, name=p["name"]).single()
        target_state = "learning" if action == "explore" or state == "explored" else "queued"
        if c is None:
            c = tx.run("""
                MERGE (c:Concept {name:$name})
                ON CREATE SET c.id=$cid, c.definition=$definition, c.aliases=[],
                    c.domain='', c.created_at=$ts, c.status=$status
                RETURN c.id AS id, c.name AS name
            """, name=p["name"].lower(), cid=str(uuid.uuid4()), definition=p["definition"], ts=_now(), status=target_state).single()
        if c["id"] == current_id:
            raise ValueError("Suggestion resolves to the current concept")
        tx.run("""
            MATCH (c:Concept {id:$cid})
            SET c.status = CASE WHEN c.status='learned' THEN 'learned'
                 WHEN c.status='learning' OR $status='learning' THEN 'learning' ELSE 'queued' END
        """, cid=c["id"], status=target_state).consume()
        a, b = (c["id"], current_id) if p["direction"] == "suggested_to_current" else (current_id, c["id"])
        tx.run(f"""
            MATCH (a:Concept {{id:$a}}), (b:Concept {{id:$b}})
            MERGE (a)-[r:{p['relation']}]->(b)
            ON CREATE SET r.strength=1.0, r.reason=$reason
        """, a=a, b=b, reason=p["reason"]).consume()
        final_state = "explored" if target_state == "learning" else "queued"
        tx.run("""
            MATCH (p:ConceptSuggestion {id:$id}), (c:Concept {id:$cid})
            SET p.state=$state, p.accepted_concept=c.name
            MERGE (p)-[:ACCEPTED_AS]->(c)
        """, id=suggestion_id, cid=c["id"], state=final_state).consume()
        return {"id": suggestion_id, "concept": c["name"], "state": final_state}

    with driver.session() as session:
        return session.execute_write(write)


def concept_suggestions(concept_id, person_id):
    rows = run("""
        MATCH (s:ChatSession {person_id:$pid})-[:ABOUT]->(:Concept {id:$cid})
        MATCH (s)-[:HAS_SUGGESTION]->(p:ConceptSuggestion)
        RETURN properties(p) AS suggestion ORDER BY p.created_at DESC LIMIT 100
    """, cid=concept_id, pid=person_id)
    return [r["suggestion"] for r in rows]


def _memory_state(row):
    from . import memory_model
    doc=row.get("memory_v2")
    if isinstance(doc,str):row["memory_v2"]=json.loads(doc)
    doc=memory_model.initialize(row,row.get("concept_id"),row.get("concept_status"))
    # Scalar session/depth metadata lives outside the derived ledger.
    return {**row,**memory_model.project(doc),"level":row.get("level"),"last_session":row.get("last_session")}


def migrate_memory(person_id=None):
    """Startup migration for every person (older single-user installs kept 'learned' on the concept)."""
    people = [person_id] if person_id else [r["id"] for r in run("MATCH (p:Person) RETURN p.id AS id")]
    total = 0
    for pid in people:
        def commit(pid=pid):
            run("""MATCH (c:Concept {status:'learned'}) MATCH (p:Person {id:$pid})
                MERGE (p)-[:UNDERSTANDS]->(c)""", pid=pid)
            states = all_understands(pid)
            for state in states: write_understands(pid, state["concept_id"], state)
            return len(states)
        total += memory_transaction(pid, commit)
    return total
