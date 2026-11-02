"""Check the Trellis MCP server with the official MCP Python client (not a runtime dependency).

    pip install mcp                       # in a separate virtualenv
    python tests/mcp_client_check.py http://localhost:8080/api/mcp <token> [<token with conversations>]

Uses a learner with at least the concept "Attention mechanism" (tests/memory_portability_neo4j.py seeds one).
"""
import asyncio
import json
import sys

try:
    import httpx
except ImportError:            # mcp 2.x ships its own fork
    import httpx2 as httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

CONCEPT = "Attention mechanism"


def field(obj, name):
    """mcp 1.x uses camelCase attributes, 2.x snake_case."""
    snake = "".join("_" + c.lower() if c.isupper() else c for c in name)
    return getattr(obj, snake) if hasattr(obj, snake) else getattr(obj, name)


async def session(url, token, run):
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=30) as http:
        async with streamable_http_client(url, http_client=http) as (read, write, *_):
            async with ClientSession(read, write) as s:
                init = await s.initialize()
                return await run(s, init)


async def read_only(s, init):
    assert field(init, "serverInfo").name == "trellis", init
    tools = {t.name for t in (await s.list_tools()).tools}
    assert tools == {"search_memory", "get_concept", "list_concepts", "get_learner_profile", "get_learning_focus",
                     "get_teaching_brief"}, tools
    out = {}
    for name, args in (("search_memory", {"query": "attention"}), ("get_concept", {"name": CONCEPT}),
                       ("list_concepts", {}), ("get_learner_profile", {}), ("get_learning_focus", {}),
                       ("get_teaching_brief", {"name": CONCEPT})):
        result = await s.call_tool(name, args)
        assert not field(result, "isError"), (name, result)
        assert result.content[0].text.strip(), name
        out[name] = field(result, "structuredContent")
    assert out["search_memory"]["results"][0]["name"] == CONCEPT
    assert out["get_concept"]["understanding"]["demonstrated_total"] >= 1
    missing = await s.call_tool("get_concept", {"name": "No such concept"})
    assert field(missing, "isError")
    return field(init, "protocolVersion")


async def with_conversations(s, init):
    tools = {t.name for t in (await s.list_tools()).tools}
    assert "get_conversations" in tools
    result = await s.call_tool("get_conversations", {"name": CONCEPT, "limit": 1})
    assert not field(result, "isError") and field(result, "structuredContent")["conversations"][0]["messages"], result
    return True


async def refused(url):
    async with httpx.AsyncClient(timeout=10) as http:
        body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        assert (await http.post(url, json=body)).status_code == 401
        assert (await http.post(url, json=body, headers={"Authorization": "Bearer trellis_wrong"})).status_code == 401
        assert (await http.get(url)).status_code in (401, 405)


async def main(url, token, full=None):
    version = await session(url, token, read_only)
    if full:
        await session(url, full, with_conversations)
    await refused(url)
    print(f"PASS: official MCP client, protocol {version}: tools listed by scope, every tool answers, bad tokens refused.")


if __name__ == "__main__":
    asyncio.run(main(*sys.argv[1:]))
