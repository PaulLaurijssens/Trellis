# Changelog

All notable changes to Trellis. Dates are UTC. Versions follow the git tags.

## [Unreleased]

### Added
- **Your learning memory, portable.** *My profile → Your data* downloads your whole learning memory
  as one zip (JSON plus Markdown that opens in Obsidian) and imports such a file into any Trellis,
  with a preview first. Importing merges, keeps your corrections, refuses a file whose evidence does
  not match its conversations, and changes nothing the second time. Format:
  [docs/MEMORY-FORMAT.md](docs/MEMORY-FORMAT.md) with a JSON Schema.
- **Connect an AI (MCP).** A read-only MCP server at `/api/mcp` lets Claude Code, Claude Desktop,
  Cursor, VS Code or your own agent read your concepts, understanding, evidence, learning profile
  and focus. Access keys are per assistant, shown once, revocable, and conversations are shared only
  when you allow it. [docs/MCP.md](docs/MCP.md).
- A new **Memory** tab: every concept with search, filters (learning now, understood, needs
  attention, planned) and sorting, and one place to correct a concept's memory: where you stand,
  the summary (now editable), open difficulties, evidence, what was discussed (with Undo).
  It works on a phone (list, then detail) and with the keyboard.
- **How I learn** replaces *Teaching preferences*: your choices, what Trellis noticed (removable with
  Undo) and your notes, without a colour legend to decode.
- A guided installer for Windows (`setup.ps1`) and Mac and Linux (`setup.sh`), with a one-line
  command in the README. It checks Docker, memory, disk and the port, makes the database password,
  downloads Trellis and starts it. Safe to run again; `--report` makes a diagnostic report with
  secrets hidden.
- Ready-made images on ghcr.io (`trellis-api`, `trellis-frontend`, `trellis-author`) for Intel/AMD and
  ARM computers. `docker compose up` downloads them, so a first install no longer builds anything.
- A release bundle (`trellis-bundle.zip` with `SHA256SUMS`) with only the files needed to run
  Trellis, made by `scripts/make-bundle.sh` and the new release workflow.
- The setup screen tests the key and all three models before you continue, and says what is wrong:
  a wrong key, a key that looks like another provider's (for example an Azure key under OpenAI), a
  model your plan does not include, no credit, a wrong endpoint or a wrong embedding size.
- An **AI provider** card in *My profile → Settings*: the owner can change the provider, the models
  and the key after setup, with the same test.
- **Other** takes an endpoint and an API version, so Azure OpenAI and Microsoft Foundry work.
  [docs/PROVIDERS.md](docs/PROVIDERS.md) has the recipes.
- When the Gemini Pro model has no free quota, setup offers the Flash model as the mentor model.
- `/health` shows the version and the commit.
- Health checks for every part of Trellis. `docker compose up -d --wait` returns when the app works.
- README: *Troubleshooting* (a page that does not load after sleep, filtered networks, build errors,
  logs) and a note about Docker Desktop licensing. [docs/TESTING.md](docs/TESTING.md) is a checklist
  for testers, with a bug report form on GitHub.
- Optional build arguments `PIP_INDEX_URL` and `NPM_CONFIG_REGISTRY` to build from source through a
  package mirror.
- When a site will not hand over an article (paywall, bot check, a page built with JavaScript), the
  Link tab says why and asks you to paste the text right there. The link stays the source, with the
  page title filled in when the site gave one.

### Changed
- A failed model call shows a clear message in the language of the interface (key rejected, quota
  used up, model busy, model not found, no connection, timeout) instead of "HTTP 500".
- A busy or rate-limited provider is tried again a few times, with growing waits, before Trellis
  gives up. A rejected key is never retried.
- The README install section starts with the installer; the old steps are now *Manual install*.
- The web server starts only when the API and the app are healthy.
- *Rebuild memory* moved to *My profile → Your data*, with an explanation of what it does.
- The Learn view shows the same memory panel as the Memory tab, with radio buttons instead of drop-down
  menus for your intent and assessment.

### Fixed
- Putting back an item you removed from your memory (a discussed topic, a profile observation) now
  works; before, a removed item stayed blocked for good.

## [0.3.0] - 2026-10-06

### Added
- A lesson that fails its checks is kept instead of thrown away. Trellis checks it once more without
  the AI (free); if it still fails, you see what failed in plain words and choose **Fix these** (the AI
  continues from that lesson and fixes only those problems) or **Open it anyway** (quality problems
  only, never safety ones).
- An optional cost limit per lesson in *My profile → Settings → Lesson costs*. Off by default.
- A health check before a lesson job starts: a lesson checker that cannot see the lesson components
  stops the job before any tokens are spent.
- A GitHub job that runs all backend tests with the packages installed.
- `SECURITY.md` and this changelog.

### Changed
- A lesson made on a computer no longer fails on phone layout problems; it shows a "may not work well
  on a phone" note. A lesson asked for on a phone must still work on a phone.
- Lessons may be up to 10 MB (was 3 MB) and get 10 seconds to start (was 5).
- The login screen tells "the server did not answer" apart from "wrong password".
- Neo4j notifications no longer flood the API log.
- README: a clearer introduction, the topic page and the lesson checks explained, and an accurate
  statement about what is sent to your AI provider.

### Fixed
- Fresh installs from `compose.yaml` could not make lessons: the lesson checker looked in the wrong
  folder for the lesson components.
- A default token cap of 220k stopped lesson jobs on a fresh install. It is removed.
- The lesson screen did not receive the phone note and the "opened anyway" note.
- `test_curriculum` overwrote the stored roadmap layout when run against a dev database.

## [0.2.0] - 2026-10-05

### Added
- Roadmap redesign: compact topic nodes, stages, a green line for your route, zoom and legend.
- **Start learning** turns the roadmap route into a course, with progress per branch.
- Topic page with **Lesson**, **Study** and **Mentor**: a study guide per depth, the lesson list as
  blocks (done, in progress, new), and a mentor side panel (draggable; a bottom sheet on phones).
- Exercise evidence from lessons enters the learning memory.
- **Due today**: spaced checks after 1, 3, 7, 14 and 30 days.
- Adding PDFs, audio files, text files, article links and podcast feeds.
- Database migrations in `db/migrations/`, applied at start.
- Lesson cost pass (prompt caching, workspace digest, fewer screenshots in context, a planning step on
  the cheap model) and a lesson cost card in Settings.

### Changed
- One close-button style everywhere, sized for touch.

## [0.1.0] - 2026-09-27

First public version: a knowledge graph from YouTube videos, pasted text and topics, with review
before anything enters the map; a mentor with a replayable learning memory; interactive lessons that
run in a sandbox after a test on a phone-sized screen; a setup screen for your own model key; nightly
backups and restore; installable as an app on a phone.

[0.3.0]: https://github.com/PaulLaurijssens/Trellis/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/PaulLaurijssens/Trellis/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/PaulLaurijssens/Trellis/releases/tag/v0.1.0
