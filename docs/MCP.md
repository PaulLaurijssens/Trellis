# Connect another AI to your learning memory (MCP)

Trellis runs an [MCP](https://modelcontextprotocol.io) server, so an AI assistant you already use
(Claude Code, Claude Desktop, Cursor, VS Code, or your own agent) can read what Trellis knows about
your learning: which concepts you study, what you have shown you understand, where you get stuck and
how you like to learn. The assistant can then explain things at your level without you repeating it.

The memory stays in your Trellis. The assistant gets read access through a key that you create, can
see and revoke. It can never change your memory.

## 1. Create an access key

**My profile → Your data → Connect an AI**. Give the key a name (the assistant it is for), and tick
**Also share full conversations** only if that assistant should read your raw conversations with the
mentor. Copy the key: Trellis stores only a fingerprint of it and cannot show it again.

What a key shares:

| Access | Tools | What the assistant can read |
|---|---|---|
| Memory (always) | `search_memory`, `get_concept`, `list_concepts`, `get_learner_profile`, `get_learning_focus`, `get_teaching_brief` | Concepts and how they connect, your summaries, difficulties and misconceptions, evidence (short quotes from your messages and checked exercises), your own assessment and intent, your learning profile, goals and saved examples. |
| Conversations (optional) | `get_conversations` | The full text of your recent conversations about one concept. |

Whatever the assistant reads goes to the company that runs that assistant's model, under that
company's terms. Share the conversations scope only with assistants you trust with them.

## 2. Add Trellis to your assistant

The server address is your Trellis address plus `/api/mcp`:

- Trellis on your own computer: `http://localhost:8080/api/mcp`
- Trellis on a server: `https://your-trellis-domain/api/mcp`

Replace `trellis_…` below with your key.

**Claude Code**

```bash
# Adds Trellis for your user; use --scope project to share it with a repository instead
claude mcp add --transport http trellis http://localhost:8080/api/mcp --header "Authorization: Bearer trellis_…"
```

**Cursor** (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "trellis": {
      "url": "http://localhost:8080/api/mcp",
      "headers": { "Authorization": "Bearer trellis_…" }
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`; VS Code asks for the key once and stores it securely)

```json
{
  "inputs": [{ "type": "promptString", "id": "trellis-key", "description": "Trellis access key", "password": true }],
  "servers": {
    "trellis": {
      "type": "http",
      "url": "http://localhost:8080/api/mcp",
      "headers": { "Authorization": "Bearer ${input:trellis-key}" }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`, through the `mcp-remote` bridge; needs Node.js)

```json
{
  "mcpServers": {
    "trellis": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8080/api/mcp", "--header", "Authorization:${TRELLIS_AUTH}"],
      "env": { "TRELLIS_AUTH": "Bearer trellis_…" }
    }
  }
}
```

**claude.ai and ChatGPT connectors** need a public HTTPS address and an OAuth sign-in. Trellis uses
access keys instead, so these are not supported yet.

Client configuration formats change; if one of these does not work, check your assistant's MCP
documentation for "HTTP server with a header".

## 3. Try it

Ask your assistant something like: *"Use Trellis: what do I already understand about attention, and
what should I review?"* or *"Explain residual connections the way my Trellis profile says I learn
best."*

## Reaching Trellis from elsewhere

Trellis listens on your own computer only (`127.0.0.1:8080`) unless you changed `TRELLIS_BIND`. To
use it from a laptop or phone elsewhere, put both devices on a private network such as
[Tailscale](https://tailscale.com) and use the Tailscale address, or run Trellis on a server with
HTTPS ([VPS.md](VPS.md)). Do not expose plain HTTP to the internet: the key travels in a header.

## The tools

All tools are read-only (`readOnlyHint`) and return both text and structured JSON.

| Tool | Input | Returns |
|---|---|---|
| `search_memory` | `query`, `limit` | Concepts matching a name, alias or definition, with your status and a one-line view of your understanding. |
| `get_concept` | `name` | Definition, prerequisites, what it leads to, related concepts, sources, and your understanding: summary, open difficulties, demonstrated evidence, own assessment and intent. |
| `list_concepts` | `status`, `needs_attention`, `limit`, `offset` | The concepts you study or plan to study, filterable. |
| `get_learner_profile` | none | What works for you, what does not, your preferences and chosen teaching approaches. |
| `get_learning_focus` | none | Your active goal and next steps, concepts due for review, open difficulties, recently studied concepts. |
| `get_teaching_brief` | `name` | The same personal context Trellis gives its own mentor before explaining that concept. |
| `get_conversations` | `name`, `limit` | Recent conversations about one concept (needs the conversations scope). |

The server also sends instructions telling the assistant that only *demonstrated* evidence counts as
proof of understanding; a self-assessment or a discussed topic does not.

## Protocol details

- Transport: Streamable HTTP, `POST /mcp` (behind nginx: `/api/mcp`), JSON responses, stateless.
  `GET` is not supported (no server-initiated stream). Batches are accepted.
- Protocol versions: 2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05.
- Authentication: `Authorization: Bearer <key>`. A missing or revoked key gets 401 with
  `WWW-Authenticate: Bearer`. The browser session cookie is never accepted on `/mcp`, and access keys
  are refused everywhere else.
- Browser pages from another site are refused (Origin check). Allow extra origins with
  `MCP_ALLOWED_ORIGINS=https://a.example,https://b.example`.
- Rate limit: 120 calls per minute per key.
- Tested with the official MCP Python SDK: `backend/tests/mcp_client_check.py`.
