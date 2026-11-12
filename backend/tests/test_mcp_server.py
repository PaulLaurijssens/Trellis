import unittest
from types import SimpleNamespace
from unittest.mock import patch

try:
    from app import mcp_server
except ImportError:                      # the "pure" CI job has no packages; the backend job runs this
    mcp_server = None

READ = {"id": "t1", "person_id": "paul", "scopes": ["memory:read"]}
ALL = {**READ, "scopes": ["memory:read", "conversations:read"]}


def call(message, access=READ):
    return mcp_server.handle({"jsonrpc": "2.0", **message}, access)


@unittest.skipIf(mcp_server is None, "needs the backend packages")
class McpProtocolTests(unittest.TestCase):
    def test_initialize_echoes_a_supported_version_and_falls_back_otherwise(self):
        ok = call({"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}})
        self.assertEqual(ok["result"]["protocolVersion"], "2025-03-26")
        self.assertEqual(ok["result"]["capabilities"], {"tools": {"listChanged": False}})
        other = call({"id": 2, "method": "initialize", "params": {"protocolVersion": "1999-01-01"}})
        self.assertIn(other["result"]["protocolVersion"], mcp_server.VERSIONS)

    def test_notifications_and_responses_get_no_answer(self):
        self.assertIsNone(call({"method": "notifications/initialized"}))
        self.assertIsNone(call({"id": 5, "result": {}}))

    def test_tools_are_listed_by_scope_and_all_read_only(self):
        names = [t["name"] for t in call({"id": 1, "method": "tools/list"})["result"]["tools"]]
        self.assertNotIn("get_conversations", names)
        self.assertIn("get_conversations", [t["name"] for t in call({"id": 1, "method": "tools/list"}, ALL)["result"]["tools"]])
        for tool in call({"id": 1, "method": "tools/list"}, ALL)["result"]["tools"]:
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertNotIn("scope", tool)

    def test_errors_follow_the_spec(self):
        self.assertEqual(call({"id": 1, "method": "nope"})["error"]["code"], -32601)
        self.assertEqual(call({"id": 1, "method": "tools/call", "params": {"name": "nope"}})["error"]["code"], -32602)
        bad = call({"id": 1, "method": "tools/call", "params": {"name": "search_memory", "arguments": {"limit": 3}}})
        self.assertEqual(bad["error"]["code"], -32602)
        extra = call({"id": 1, "method": "tools/call", "params": {"name": "get_learner_profile", "arguments": {"x": 1}}})
        self.assertEqual(extra["error"]["code"], -32602)
        scope = call({"id": 1, "method": "tools/call", "params": {"name": "get_conversations", "arguments": {"name": "x"}}})
        self.assertTrue(scope["result"]["isError"])
        self.assertEqual(mcp_server.handle({"id": 1}, READ)["error"]["code"], -32600)

    def test_tool_result_has_text_and_structured_content_and_the_person_of_the_token(self):
        seen = {}
        def fake(pid, query, limit=10):
            seen["pid"] = pid
            return "- Softmax", {"results": [{"name": "Softmax"}]}
        with patch.dict(mcp_server.HANDLERS, {"search_memory": fake}):
            out = call({"id": 7, "method": "tools/call", "params": {"name": "search_memory", "arguments": {"query": "soft"}}})
        self.assertEqual(seen["pid"], "paul")
        self.assertFalse(out["result"]["isError"])
        self.assertEqual(out["result"]["content"][0], {"type": "text", "text": "- Softmax"})
        self.assertEqual(out["result"]["structuredContent"]["results"][0]["name"], "Softmax")

    def test_a_missing_concept_is_a_tool_error_not_a_protocol_error(self):
        def missing(pid, name):
            raise mcp_server.ToolProblem("No concept named 'x'")
        with patch.dict(mcp_server.HANDLERS, {"get_concept": missing}):
            out = call({"id": 1, "method": "tools/call", "params": {"name": "get_concept", "arguments": {"name": "x"}}})
        self.assertTrue(out["result"]["isError"])

    def test_lucene_special_characters_are_escaped(self):
        self.assertEqual(mcp_server._lucene('C++ (intro): "x"'), 'C\\+\\+ \\(intro\\)\\: \\"x\\"')

    def test_origin_check(self):
        req = lambda origin, host: SimpleNamespace(headers={k: v for k, v in {"origin": origin, "host": host}.items() if v})
        self.assertTrue(mcp_server._origin_allowed(req(None, "localhost")))
        self.assertTrue(mcp_server._origin_allowed(req("http://localhost:8080", "localhost")))      # nginx drops the port
        self.assertFalse(mcp_server._origin_allowed(req("https://evil.example", "localhost")))
        self.assertFalse(mcp_server._origin_allowed(req("http://evil.example", "evil.example")))   # DNS rebinding
        with patch.dict("os.environ", {"MCP_ALLOWED_ORIGINS": "https://evil.example"}):
            self.assertTrue(mcp_server._origin_allowed(req("https://evil.example", "localhost")))


if __name__ == "__main__":
    unittest.main()
