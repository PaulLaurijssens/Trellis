# Changelog

All notable changes to Trellis. Dates are UTC. Versions follow the git tags.

## [Unreleased]

### Added
- When a site will not hand over an article (paywall, bot check, a page built with JavaScript), the
  Link tab says why and asks you to paste the text right there. The link stays the source, with the
  page title filled in when the site gave one.

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
