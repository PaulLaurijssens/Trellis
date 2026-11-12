"""Print two MCP access keys for the learner that tests/memory_portability_neo4j.py leaves behind: one with
memory only, one that may also read conversations. For tests/mcp_client_check.py in CI; test databases only.

    TRELLIS_TEST_WIPE=yes python tests/make_mcp_tokens.py
"""
import os

from app import graph, tokens

assert os.getenv("TRELLIS_TEST_WIPE") == "yes", "Test databases only. Set TRELLIS_TEST_WIPE=yes."
pid = graph.run("MATCH (p:Person)-[:UNDERSTANDS]->(:Concept {name:'Attention mechanism'}) RETURN p.id AS id ORDER BY id LIMIT 1")[0]["id"]
print(tokens.create(pid, "ci", ["memory:read"])["token"],
      tokens.create(pid, "ci-conversations", ["memory:read", "conversations:read"])["token"])
