"""Personal access tokens: how another AI (through the MCP server) reads a learner's memory.

The token itself is shown once and never stored: only its SHA-256 hash is kept. A token belongs to one
learner, has scopes, and can be revoked. Tokens are refused on every route except /mcp; the session
cookie, in turn, is refused on /mcp.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from . import graph

PREFIX = "trellis_"
SCOPES = {"memory:read": "Concepts, understanding, profile and learning focus",
          "conversations:read": "The raw conversations with the mentor"}
DEFAULT_SCOPES = ["memory:read"]
MAX_ACTIVE = 20


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _public(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "name", "hint", "scopes", "created_at", "last_used_at", "revoked_at")}


def listing(pid: str) -> list[dict]:
    rows = graph.run("""MATCH (t:AccessToken {person_id:$pid}) WHERE t.revoked_at IS NULL
                        RETURN properties(t) AS t ORDER BY t.created_at DESC""", pid=pid)
    return [_public(r["t"]) for r in rows]


def create(pid: str, name: str, scopes: list[str] | None = None) -> dict:
    name = (name or "").strip()
    if not 1 <= len(name) <= 60:
        raise ValueError("Give the connection a name of 1 to 60 characters.")
    scopes = list(dict.fromkeys(scopes or DEFAULT_SCOPES))
    if not scopes or any(s not in SCOPES for s in scopes):
        raise ValueError("Unknown access scope.")
    if "memory:read" not in scopes:
        scopes.insert(0, "memory:read")
    if len(listing(pid)) >= MAX_ACTIVE:
        raise ValueError(f"You already have {MAX_ACTIVE} connections. Revoke one first.")
    token = PREFIX + secrets.token_urlsafe(32)
    row = {"id": str(uuid.uuid4()), "name": name, "hint": token[:len(PREFIX) + 4] + "…" + token[-4:],
           "scopes": scopes, "created_at": graph._now(), "last_used_at": None, "revoked_at": None}
    graph.run("""MATCH (p:Person {id:$pid})
                 CREATE (p)-[:HAS_TOKEN]->(t:AccessToken {id:$id, person_id:$pid, name:$name, hint:$hint, hash:$hash,
                                                          scopes:$scopes, created_at:$created})""",
              pid=pid, hash=_hash(token), **{k: row[k] for k in ("id", "name", "hint", "scopes")}, created=row["created_at"])
    return {"token": token, "connection": row}


def revoke(pid: str, token_id: str) -> bool:
    rows = graph.run("""MATCH (t:AccessToken {id:$id, person_id:$pid}) WHERE t.revoked_at IS NULL
                        SET t.revoked_at=$now RETURN t.id AS id""", id=token_id, pid=pid, now=graph._now())
    return bool(rows)


def resolve(token: str | None) -> dict | None:
    """The token's owner and scopes, or None. Constant work for unknown tokens (one indexed lookup)."""
    if not token or not token.startswith(PREFIX) or len(token) > 200:
        return None
    rows = graph.run("""MATCH (t:AccessToken {hash:$hash}) WHERE t.revoked_at IS NULL
                        MATCH (p:Person {id:t.person_id})
                        FOREACH (_ IN CASE WHEN t.last_used_at IS NULL OR t.last_used_at < $stale THEN [1] ELSE [] END |
                                 SET t.last_used_at=$now)
                        RETURN t.id AS id, t.person_id AS person_id, t.scopes AS scopes""", hash=_hash(token), now=graph._now(),
                     stale=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat())
    return rows[0] if rows else None
