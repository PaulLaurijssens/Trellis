# Trellis

**A personal knowledge graph with an AI mentor that teaches you from your own sources.**

You feed Trellis the things you learn from: YouTube videos, articles, papers, your own notes. It turns
them into a map of concepts and how they depend on each other. A mentor explains any concept at the
depth you choose, remembers what you understood and where you struggled, and builds short interactive
lessons for you: predict, try, get feedback. Everything runs on your own machine or server, with your
own model key. Your data never leaves it.

> Status: **alpha**, a personal project made public. It works for its author every day; expect rough
> edges. Issues and pull requests are welcome. License: AGPL-3.0 (free to use, self-host and change;
> if you offer it as a service, you must share your changes).

---

## Setting it up (15 minutes, no programming needed)

You need a computer that stays on while you use Trellis: your own laptop is fine to start. If you
get stuck, paste this README into an AI assistant (ChatGPT, Claude, Gemini) together with the exact
error text, and ask it to walk you through. That is how this guide is meant to be used.

### 1. Install Docker Desktop

Docker runs the five parts of Trellis in isolated boxes, so you install nothing else.

- Download it from <https://www.docker.com/products/docker-desktop/> (Mac, Windows or Linux).
- Install and start it. Wait until the whale icon in your menu bar or tray stops animating.
- Windows: Docker Desktop will ask to enable WSL 2. Say yes and reboot if asked.

Trellis needs about 4 GB of RAM while running and 3 GB of disk. In Docker Desktop → Settings →
Resources, give Docker at least 6 GB of memory.

### 2. Get the code

Open a terminal (Mac: Terminal app; Windows: PowerShell) and run:

```bash
git clone https://github.com/plaurijssens/trellis.git
cd trellis
```

No git? Download the ZIP from the green **Code** button on GitHub, unzip it, and `cd` into the folder.

### 3. Set one password for the database

Copy the example settings file and put a long random string in it:

```bash
cp .env.example .env
```

Open `.env` in any text editor and replace `change-me` after `NEO4J_PASSWORD=` with a long random
string (letters and digits, 20+ characters). You will never have to type it; it protects the database
inside Docker. Everything else in the file can stay as it is.

### 4. Start Trellis

```bash
docker compose up -d
```

The first start downloads and builds everything: 5–10 minutes depending on your connection. Later
starts take seconds. When the command returns, open **<http://localhost:8080>** in your browser.

### 5. Finish the setup in the browser

The first visit shows a three-step setup screen:

1. **Your name and language.** English and Dutch today; more can be added (see *Languages*).
2. **Your AI model.** Trellis talks to a model provider with **your own key**, and you pay that
   provider directly; Trellis itself costs nothing. Pick one:

   | Provider | Where to get a key | Notes |
   |---|---|---|
   | Google Gemini (recommended) | <https://aistudio.google.com/apikey> → *Create API key* | Also does voice input and video analysis. |
   | OpenAI | <https://platform.openai.com/api-keys> | Add a payment method first. |
   | Anthropic Claude | <https://console.anthropic.com/settings/keys> | Needs a second provider for embeddings; the screen asks. |
   | Mistral | <https://console.mistral.ai/api-keys> | |
   | Ollama (local, free) | <https://ollama.com/download>, then `ollama pull qwen3:32b nomic-embed-text` | Needs a strong GPU. Lessons may fail. |

   The key is stored only inside your own Trellis database, and used only to call that provider.
   **Costs:** a conversation turn costs a few cents; an interactive lesson about $0.40–$0.80
   (150k–300k tokens). Every lesson job records its token use.
3. **Your password.** Trellis is a private notebook; this password is its only door.

Done. Add your first source with the **Add +** button: a YouTube link, or pasted text.

### Everyday commands

```bash
docker compose up -d        # start (also after a reboot)
docker compose down         # stop (your data stays)
git pull && docker compose up -d --build     # update to a newer version
docker compose logs -f api  # watch the server log when something looks wrong
```

---

## Using Trellis from your phone, or from anywhere

By default Trellis listens only on the computer it runs on (`127.0.0.1:8080`). That is deliberate:
there is a password, but no HTTPS. To use it from your phone or another computer you need HTTPS in
front of it. Two good ways, both described in [docs/VPS.md](docs/VPS.md):

- **Tailscale** (easiest, private): install Tailscale on the computer and your phone, run
  `tailscale serve --bg 8080`, open the `https://…ts.net` address it prints. Nothing is exposed to
  the internet.
- **A rented server + Caddy** (a domain name, reachable from anywhere).

Once you open Trellis over HTTPS on a phone, use "Add to Home Screen": it installs as an app.

## Backups

Trellis makes a backup every night at 03:10 UTC and keeps the last 14 in the `backups/` folder next
to the code. A backup is two files with one timestamp: your whole graph (`trellis-<stamp>.cypher.gz`)
and your lesson files (`artifacts-<stamp>.tar.gz`). You can also press **Make a backup now** in
*My profile → Settings*, and **Verify** checks that a backup is readable and complete.

Copy the `backups/` folder to another place now and then (a cloud drive is fine: the files hold your
notes and your model key is **not** in them).

**Restore** replaces everything with one backup, on the machine that runs Trellis:

```bash
./scripts/restore.sh 20260927T031000Z      # the timestamp of the files in backups/
```

## Reset a password

On the machine that runs Trellis:

```bash
docker compose exec api python -m app.reset_password
```

It asks for the new password and prints which account it changed.

## Languages

The interface and the mentor speak English and Dutch. The mentor answers in the language you write
in. Adding a language is two files: an entry in `backend/app/languages.py` and a dictionary
`frontend/lib/<code>.js` (copy `en.js` and translate the values). Pull requests welcome.

## How it works, in one paragraph

Sources go through an extraction pipeline that proposes concepts and their relations; you review
and accept them into a Neo4j graph. The mentor (any LiteLLM-supported model) answers with the
concept's context, your stored source excerpts and your memory: what you covered, what you
demonstrated, where you struggled. Memory is a replayable ledger, never a score. Interactive lessons
follow Matt Pocock's [/teach skill](https://github.com/mattpocock/skills/tree/main/skills/productivity/teach):
an agent reads a read-only export of your memory, writes a small HTML lesson from shared components,
and a sandboxed browser tests it on a phone-sized screen before you ever see it. Lessons run in a
locked frame with no network and no storage; answers are checked on the server. Design notes are in
[docs/](docs/).

## For developers

```bash
cp .env.example .env                                    # set NEO4J_PASSWORD and one model key
docker compose -f compose.dev.yaml up -d                # hot reload: API on :8000, Neo4j browser on :7474
cd frontend && npm install && NEXT_PUBLIC_API_URL=/api DEV_API_PROXY=http://localhost:8000 npm run dev
docker compose -f compose.dev.yaml exec backend python -m unittest discover -s tests   # backend tests
python3 -m unittest discover -s backend/tests -p "test_teach_*.py"                     # pure tests, no database
```

The end-to-end lesson test (real Chromium, phone size) and the layout-regression test live in
`author/tests/`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

AGPL-3.0, see [LICENSE](LICENSE). Third-party work and its licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
