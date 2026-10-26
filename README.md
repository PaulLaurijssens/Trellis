# Trellis

**Structured learning on the topics you choose, taught by a mentor that learns how you learn.**

Pick your topics and bring your videos, podcasts and papers. Trellis places each one on your personal
knowledge map, turns that map into a learning path, and builds every lesson around you. Lessons are
short and interactive (predict, try, get feedback), and the mentor remembers what you understood and
where you struggled, so a concept comes back for a quick check when it is due.

**Your data and memory are yours.** Everything is stored on your own computer or server, and you use
your own AI key. For each answer, Trellis sends what the mentor needs to the AI provider you choose;
with a local model, nothing leaves your machine. You can download your whole learning memory as one
file, bring it into another Trellis, and let other AI assistants read it through MCP
([Your learning memory](#your-learning-memory-take-it-anywhere)).

> Status: **alpha**, a personal project made public. It works for its author every day; expect rough
> edges. Issues and pull requests are welcome. License: AGPL-3.0 (free to use, self-host and change;
> if you offer it as a service, you must share your changes).

**Try it** (about 15 minutes). You need Docker Desktop and a key from one AI provider. The installer
checks your computer, downloads Trellis and starts it.

Windows (PowerShell):

```powershell
irm https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.ps1 | iex
```

Mac or Linux (Terminal):

```bash
curl -fsSL https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.sh | bash
```

Then open <http://localhost:8080> and follow the three setup steps. The steps below explain each part.

<!-- Screenshots go here: docs/img/roadmap.png, docs/img/lesson.png, docs/img/phone.png -->

---

## Setting it up (15 minutes, no programming needed)

You need a computer that stays on while you use Trellis: your own laptop is fine to start. If you
get stuck, see *Troubleshooting* below, or paste this README into an AI assistant (ChatGPT, Claude,
Gemini) together with the exact error text, and ask it to walk you through.

### 1. Install Docker Desktop

Docker runs the five parts of Trellis in isolated boxes, so you install nothing else.

- Download it from <https://www.docker.com/products/docker-desktop/> (Mac, Windows or Linux).
- Install and start it. Wait until the whale icon in your menu bar or tray stops animating.
- Windows: Docker Desktop will ask to enable WSL 2. Say yes and reboot if asked.

Trellis needs about 4 GB of RAM while running and 3 GB of disk. In Docker Desktop → Settings →
Resources, give Docker at least 6 GB of memory.

Docker Desktop is free for personal use, education, open-source projects and small businesses
(fewer than 250 employees and less than $10 million in annual revenue). Larger companies need a paid
Docker subscription to use it for work. On Linux, the free Docker Engine is enough:
<https://docs.docker.com/engine/install/>.

### 2. Run the installer

Windows: open **PowerShell** (Start menu, type "PowerShell") and run:

```powershell
irm https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.ps1 | iex
```

Mac or Linux: open **Terminal** and run:

```bash
curl -fsSL https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.sh | bash
```

The installer asks before it changes anything. It checks Docker, memory, disk space and the port,
puts Trellis in a `Trellis` folder in your home folder, makes the database password for you, downloads
the ready-made images and starts Trellis. The first start takes a few minutes. Later starts take
seconds. When it is done, it shows the address: **<http://localhost:8080>**.

**Stuck on a step?** The installer stops with what went wrong, what to try, and a ready prompt to paste into
ChatGPT, Claude or Copilot. Prefer an AI assistant to guide you from the start? See
[Install with an AI assistant](docs/INSTALL-WITH-AI.md).

You can run the installer again at any time. It checks everything again, repairs known problems and
starts Trellis. Your data stays.

**Prefer to read a script before you run it?** Download the installer and the checksum file from the
[latest release](https://github.com/PaulLaurijssens/Trellis/releases/latest), check the file, read it,
then run it:

```bash
curl -fsSLO https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.sh
curl -fsSLO https://github.com/PaulLaurijssens/Trellis/releases/latest/download/SHA256SUMS
grep ' setup.sh$' SHA256SUMS | sha256sum -c   # Mac: grep ' setup.sh$' SHA256SUMS | shasum -a 256 -c
less setup.sh
bash setup.sh
```

```powershell
Invoke-WebRequest https://github.com/PaulLaurijssens/Trellis/releases/latest/download/setup.ps1 -OutFile setup.ps1
Invoke-WebRequest https://github.com/PaulLaurijssens/Trellis/releases/latest/download/SHA256SUMS -OutFile SHA256SUMS
(Get-FileHash setup.ps1 -Algorithm SHA256).Hash   # compare with the setup.ps1 line in SHA256SUMS
notepad setup.ps1
powershell -ExecutionPolicy Bypass -File setup.ps1
```

No installer? See *Manual install* below: it does the same in four commands.

### 3. Finish the setup in the browser

The first visit shows a three-step setup screen:

1. **Your name.** Trellis is in English; you can add your own language (see
   [Add your language](#add-your-language)).
2. **Your AI model.** Trellis talks to a model provider with **your own key**, and you pay that
   provider directly; Trellis itself costs nothing. Pick one:

   | Provider | Where to get a key | Notes |
   |---|---|---|
   | Google Gemini (recommended) | <https://aistudio.google.com/apikey> → *Create API key* | Also does voice input and video analysis. |
   | OpenAI | <https://platform.openai.com/api-keys> | Add a payment method first. |
   | Anthropic Claude | <https://console.anthropic.com/settings/keys> | Needs a second provider for embeddings; the screen asks. |
   | Mistral | <https://console.mistral.ai/api-keys> | |
   | Ollama (local, free) | <https://ollama.com/download>, then `ollama pull qwen3:32b nomic-embed-text` | Needs a strong GPU. Lessons may fail. |
   | Other | Any provider that LiteLLM supports: Azure OpenAI, Microsoft Foundry, OpenRouter and more | Recipes in [docs/PROVIDERS.md](docs/PROVIDERS.md). |

   Before you continue, Trellis tests your key and the three models with a very small request. When
   something is wrong (a wrong key, a model your plan does not include, no credit), the screen says
   what to fix. A key from Azure or Microsoft Foundry is not an OpenAI key: use **Other**. The owner
   can change the provider and key later in *My profile → Settings → AI provider*. The embedding size
   cannot change later; [docs/PROVIDERS.md](docs/PROVIDERS.md) explains why.

   The key is stored only inside your own Trellis database, and used only to call that provider.
   **Costs:** a conversation turn costs a few cents; an interactive lesson about $0.40–$0.80
   (150k–300k tokens). Every lesson job records its token use.
3. **Your password.** Trellis is a private notebook; this password is its only door.

Done. Add your first source with the **Add +** button.

### Manual install (without the installer)

The installer does nothing you cannot do yourself. You need Docker Desktop (step 1) and a terminal.

1. **Get the files.** Either download
   [trellis-bundle.zip](https://github.com/PaulLaurijssens/Trellis/releases/latest/download/trellis-bundle.zip)
   and unzip it (it holds a `trellis` folder), or get the source code:

   ```bash
   git clone https://github.com/PaulLaurijssens/Trellis.git
   ```

   No git? Download the ZIP from the green **Code** button on GitHub and unzip it. Then go into the
   folder: `cd trellis` (bundle) or `cd Trellis` (source).

2. **Set one password for the database.** Copy the example settings file:

   ```bash
   cp .env.example .env          # Windows PowerShell: copy .env.example .env
   ```

   Open `.env` in any text editor and replace `change-me` after `NEO4J_PASSWORD=` with a long random
   string (letters and digits, 20+ characters). You will never have to type it; it protects the
   database inside Docker. Everything else in the file can stay as it is.

3. **Start Trellis.**

   ```bash
   docker compose up -d --wait
   ```

   This downloads the ready-made images and returns when Trellis answers: a few minutes the first
   time, seconds after that. In a source folder, Docker builds an image itself when there is no
   ready-made image for that version; `docker compose up -d --build --wait` always builds from the
   source (10 to 15 minutes).

4. Open **<http://localhost:8080>** and finish the setup in the browser (step 3 above).

`TRELLIS_PORT=8090` in `.env` uses another port when 8080 is taken. `TRELLIS_VERSION=0.4.0` in `.env`
runs that version instead of the newest one.

### What you can add

| Add + tab | What goes in | Notes |
|---|---|---|
| Topic | A term you want to understand | Trellis writes a short source about it with your model. |
| YouTube | A video link | Captions are fetched; without captions, Gemini watches the video. |
| File | A PDF, an audio file or a text file | PDF up to 30 MB. Audio (mp3, m4a, wav, ogg) up to 25 MB is transcribed by your model provider: a few cents for an hour. |
| Link | A web article, a PDF link, or a podcast feed (RSS) | A feed lists its episodes; pick one and it is downloaded and transcribed. Some sites block automatic reading (paywalls, bot checks, pages built with JavaScript). Then the Link tab asks you to paste the article text right there, and keeps the link as the source. |
| Transcript, Paper/text | Pasted text | Time codes like `4:45` or `[00:12]` are kept, so the mentor can point to the moment. |

Everything goes through the same review step: you tick the concepts you want before anything
enters your map.

### Your learning space

**The roadmap.** The *Learning path* view draws your whole map as a roadmap: shared foundations on
the left, specialist topics on the right, and a green line for your route. **Start learning** turns
that route into a course with ordered steps; the roadmap then shows your progress per branch.

**A topic page** has three parts:

- **Lesson**: the lessons of this topic as blocks (done, in progress, new). **Make me a lesson**
  builds a new interactive lesson for the time you have (5, 10 or 20 minutes). It takes a few minutes.
- **Study**: a written study guide at the depth you choose, from *First steps* to *Advanced*, built
  from your own sources.
- **Mentor**: a side panel next to the lesson. Ask anything; the mentor knows your study guide and
  the lesson in front of you. *In context* shows where the concept sits in your map, your course,
  and the sources that mention it. On a phone, the panel is a sheet you swipe away.

**Due today** in the sidebar lists concepts that are ready for a short check: a streak of good
answers lengthens the gap (1, 3, 7, 14, 30 days), a miss shortens it. It is an invitation, not
homework.

### How lessons are checked

Every lesson is tested in a hidden browser before you see it: it must be safe (no internet, no
forbidden code), start within 10 seconds, run without errors, be complete, and be readable. Phone
layout problems block a lesson only when you ask for it on a phone; a lesson made on a computer gets
a "may not work well on a phone" note instead.

A lesson that still fails is never thrown away. Trellis first checks it once more without the AI,
which costs nothing. If it still fails, you see what failed, in plain words, and choose:

- **Fix these**: the AI continues from that lesson and fixes only those problems, for fewer tokens
  than a new lesson.
- **Open it anyway**: free. Only for quality problems (hard-to-read text, an error in one part), never
  for safety ones.

### Everyday commands

Run these in the Trellis folder (the installer puts it in your home folder: `~/Trellis`).

```bash
docker compose up -d --wait # start (after a reboot, Trellis starts again by itself once Docker runs)
docker compose down         # stop (your data stays)
docker compose ps           # what runs, and whether it is healthy
docker compose logs -f api  # watch the server log when something looks wrong
```

### Troubleshooting

**Make a report.** The installer can collect what a helper needs (versions, memory, disk, container
status, the last log lines) with passwords and keys hidden. Attach it to a
[bug report](https://github.com/PaulLaurijssens/Trellis/issues/new/choose) or paste it in an AI chat.

```bash
bash ~/Trellis/setup.sh --report                                              # Mac, Linux
powershell -ExecutionPolicy Bypass -File $HOME\Trellis\setup.ps1 -Report      # Windows
```

**See the logs.** In the Trellis folder, `docker compose ps` shows each part and whether it is
healthy. `docker compose logs --tail 100 api` shows the last lines of one part (also `frontend`,
`web`, `neo4j`, `author`). In Docker Desktop: *Containers* → *trellis* → click a container → *Logs*.

**The page does not load after the computer was asleep.** Docker Desktop sometimes loses the port
after sleep: Trellis runs, but <http://localhost:8080> does not answer. Run
`docker compose up -d --force-recreate web` in the Trellis folder, or run the installer again.

**Port 8080 is already in use.** Put `TRELLIS_PORT=8090` (or another free port) in `.env` and run
`docker compose up -d --wait`. Then open <http://localhost:8090>.

**Downloading the images fails** (`TLS handshake timeout`, `x509: certificate signed by unknown
authority`, `connection reset`, `i/o timeout`). Your network blocks or inspects the connection to
`ghcr.io`. Check:

- Can you open <https://ghcr.io> in your browser? If not, the network blocks it. Try another network
  (a phone hotspot is fine for the download) or ask your IT department to allow `ghcr.io` and
  `pkg-containers.githubusercontent.com`.
- A company proxy: set it in Docker Desktop → Settings → Resources → Proxies.
- A network that inspects encrypted traffic (some company, school and antivirus products do) needs
  its root certificate in your system's certificate store. Docker Desktop on Mac and Windows uses that
  store; restart Docker Desktop after you add it.
- `manifest unknown` or `not found`: the version in `TRELLIS_VERSION` in `.env` does not exist. Remove
  the line to get the newest version.

**Building from source fails.** You only build when you ask for it (`--build`) or when there is no
ready-made image. `npm error Exit handler never called`, `ECONNRESET`, `SELF_SIGNED_CERT_IN_CHAIN` or
pip's `CERTIFICATE_VERIFY_FAILED` mean the network failed, not Trellis. First try the ready-made images:
`docker compose up -d --wait` without `--build`. If you must build on a filtered network, point the
build at a package mirror that your network allows:

```bash
docker compose build --build-arg PIP_INDEX_URL=https://mirror.example.com/pypi/simple \
                     --build-arg NPM_CONFIG_REGISTRY=https://mirror.example.com/npm/
docker compose up -d --wait
```

**A part stays "unhealthy" or keeps restarting.** Usually too little memory: give Docker at least
6 GB (Docker Desktop → Settings → Resources). Then look at the logs of that part (see above).

**The setup screen says the key or the model is wrong.** It names the problem: a wrong key, a model
your plan does not include, no credit, or a wrong endpoint. [docs/PROVIDERS.md](docs/PROVIDERS.md)
has what each provider needs, and recipes for Azure OpenAI, Microsoft Foundry and OpenRouter.

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

## Your learning memory: take it anywhere

Trellis remembers your learning in three layers: what happened (every conversation and checked
exercise), what you understand per concept (with quotes from your own messages as evidence), and how
you learn. You can see and correct all of it in *My profile → Memory*, and it is yours to take along:

- **Download it.** *My profile → Your data → Download memory* gives one zip file: JSON that other
  tools can read, and Markdown pages that open as an Obsidian vault. The format is open and
  documented in [docs/MEMORY-FORMAT.md](docs/MEMORY-FORMAT.md).
- **Bring it into another Trellis.** *Import memory* shows what will change and merges it with what
  is there. Nothing is overwritten, and importing twice changes nothing.
- **Let another AI read it.** Create an access key under *Connect an AI*, and Claude Code, Claude
  Desktop, Cursor, VS Code or your own agent can read your learning memory through MCP (read only;
  revoke the key any time). Setup in [docs/MCP.md](docs/MCP.md).

The export is a personal copy, not a backup of the whole install: for that, see *Backups* below.

## Backups

Trellis makes a backup every night at 03:10 UTC and keeps the last 14 in the `backups/` folder next
to the code. A backup is two files with one timestamp: your whole graph (`trellis-<stamp>.jsonl.gz`)
and your lesson files (`artifacts-<stamp>.tar.gz`). You can also press **Make a backup now** in
*My profile → Settings*, and **Verify** checks that a backup is readable and complete.

Copy the `backups/` folder to another place now and then (a cloud drive is fine: the files hold your
notes and your model key is **not** in them).

**Restore** replaces everything with one backup, on the machine that runs Trellis:

```bash
./scripts/restore.sh 20260927T031000Z      # the timestamp of the files in backups/
```

It stops the app, loads the graph and the lesson files, and starts the app again (a few seconds for
hundreds of concepts, a minute or two for tens of thousands). Log in with the password you had at
the time of the backup. Moving to a new computer: install Trellis there, copy the two files into its
`backups/` folder, run the same command.

## Updating

Press **Make a backup now** in *My profile → Settings* first; the nightly backup can be a day old.
Then, in the Trellis folder:

- **Installed with the installer or the bundle:** if `.env` has a `TRELLIS_VERSION=` line, change it
  to the new version (see [Releases](https://github.com/PaulLaurijssens/Trellis/releases)). Then run
  `docker compose pull && docker compose up -d --wait`. When the release notes say that
  `compose.yaml` changed, download the new `trellis-bundle.zip` and copy its `compose.yaml` over the
  old one. Keep your `.env` and `backups/`.
- **Source checkout:** `git pull && docker compose up -d --build --wait`.

Your memory stays: the graph and the lesson files live in Docker volumes. When an update changes the
shape of the data, it ships a migration in `db/migrations/`; the API applies pending migrations at
start and remembers the version in the database.
`docker compose exec api python -m app.migrate --dry-run` shows what an update would apply.

## Lesson costs

An interactive lesson is the most expensive thing Trellis does. **My profile → Settings → Lesson
costs** shows the lessons and tokens of the last 30 days with a rough estimate in dollars. To keep the
bill down, Trellis inlines the small workspace files (one read instead of seven), lets the cheap
model plan the lesson before the strong model writes it, keeps only the newest screenshots in the
model's context, and uses prompt caching where the provider supports it. There is no cost limit by
default. The owner can set one per lesson in the same card ($0.50, $1 or $2): near the limit the
author stops adding new parts and publishes what passed its checks. `.env.example` lists the other knobs.

## Reset a password

On the machine that runs Trellis:

```bash
docker compose exec api python -m app.reset_password
```

It asks for the new password and prints which account it changed.

## Add your language

Trellis comes in English. The mentor already answers in the language you write in, whatever it is.
To get the screens, lessons, study guides and memory in your own language as well, let an AI coding
agent (Claude Code, Cursor, Codex, ...) add it. It takes a few minutes and some tokens.

You need a source checkout, because the ready-made images contain English only:

```bash
# Get the source and open it in your coding agent
git clone https://github.com/PaulLaurijssens/Trellis.git
cd Trellis
```

Give the agent this prompt, with your language filled in:

```text
Add <LANGUAGE> to Trellis as a user interface and content language, with code <CODE> (ISO 639-1, for example de, fr, pt-BR).

1. backend/app/languages.py: add "<CODE>": {"name": "<English name>", "native": "<name in the language itself>"} to LANGUAGES. Optionally add a STOPWORDS set of about 40 short, unmistakable function words for this language that are not English words.
2. frontend/lib/<CODE>.js: copy frontend/lib/en.js and translate every value into <LANGUAGE>. Keep every key and every {placeholder} exactly as they are. Keep product and model names (Trellis, Neo4j, OpenAI, Gemini, Claude, Ollama) untranslated. Use the informal, friendly tone of the English text.
3. frontend/lib/languages.js: import the new dictionary and add { code: "<CODE>", native: "<name in the language itself>", dict: <variable> } to LANGUAGES.
4. Run: cd frontend && node --test tests/*.test.mjs. The languages test must pass (no unknown keys, same placeholders as English). Fix any failure.
5. Do not change anything else.
```

Then rebuild and start Trellis, and pick the language in *My profile → Settings*:

```bash
# Build from your changed source and start
docker compose up -d --build --wait
```

After an update (`git pull`), new English texts show in English until you ask the agent again to
*"translate the keys that are in frontend/lib/en.js but missing in frontend/lib/<CODE>.js"*.
Made a good one? A pull request is welcome.

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
cp .env.example .env                               # set NEO4J_PASSWORD and one model key
docker compose -f compose.dev.yaml up -d           # hot reload: app on :3000, API on :8000, Neo4j browser on :7474
```

Tests:

```bash
docker compose -f compose.dev.yaml exec backend python -m unittest discover -s tests   # all backend tests
cd backend && pip install -r requirements.lock.txt && python -m unittest discover -s tests   # the same, without Docker
python3 -m unittest discover -s backend/tests -p "test_teach_*.py"                        # quick checks, no packages needed
docker compose -f compose.dev.yaml exec backend python tests/e2e_kept_lesson.py           # see the "kept lesson" screen, no AI tokens
cd frontend && node --test tests/*.test.mjs                                               # frontend unit tests
cd frontend && node tests/run-browser.mjs        # browser flows (Playwright) against the dev app on :3000, API mocked
```

The `test_*.py` unit tests need no database. The `*_neo4j.py` scripts do, and wipe it: run them only
against a test database with `TRELLIS_TEST_WIPE=yes`. The end-to-end lesson test (real Chromium,
phone size) and the layout-regression test live in `author/tests/`. GitHub runs the quick checks,
all backend tests, the database scripts against a fresh Neo4j, the official MCP client against the
MCP server, the frontend unit tests, the production build, every browser flow, a full
`docker compose` start that waits for every health check, and a check of the release bundle on every
push. Testing a release by hand: [docs/TESTING.md](docs/TESTING.md). See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Trellis has one password and no HTTPS of its own, so it listens only on your own computer by
default; use Tailscale or a server with Caddy to reach it from elsewhere ([docs/VPS.md](docs/VPS.md)).
Lessons run in a locked frame with no network and no storage, and your AI key never reaches the
browser. Found a security problem? Please report it privately, as described in
[SECURITY.md](SECURITY.md), not in a public issue.

## License

AGPL-3.0, see [LICENSE](LICENSE). Third-party work and its licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
