# Trellis learning memory: the export format (version 1)

Your learning memory belongs to you. Trellis can write all of it to one file, read that file back
into any Trellis install, and the file is useful without Trellis: Markdown you can read or open as an
Obsidian vault, and JSON that other tools can parse.

- Download it: **My profile → Your data → Download memory**, or `GET /api/memory/{person_id}/export`.
- Bring it in: **My profile → Your data → Import memory** (shows a preview first), or
  `POST /api/memory/{person_id}/import?mode=preview|apply` with the zip or `memory.json` as the body.
- The JSON Schema is [`memory-format.schema.json`](memory-format.schema.json). A test checks a real
  export against it.

## What is in the zip

```
trellis-memory-2026-10-26.zip
  memory.json              everything, complete and importable
  README.md                what is in the file and how to use it
  profile.md               how you learn (layer 3), in plain words
  concepts/<slug>.md       one page per concept: definition, your understanding, evidence quotes,
                           open difficulties, sources, [[wikilinks]] to related concepts
  conversations/<slug>.md  your conversations with the mentor, per concept
```

The Markdown is written in your interface language (English or Dutch). The JSON is the source of
truth; the Markdown is a readable copy of it.

## The three memory layers

| Layer | What it is | In the file |
|---|---|---|
| 1. What happened | Every conversation message and every checked exercise answer. Never rewritten. | `conversations`, `exercises` |
| 2. What you understand, per concept | Evidence (quotes from your messages, checked exercises), difficulties and misconceptions, what you discussed, your own intent and assessment. Every item points back to layer 1. | `understanding` |
| 3. How you learn | What works, what does not, your chosen teaching approaches, your notes. | `profile` |

Next to the layers: the knowledge map (`map`), your learning goals (`goals`), saved helpful examples
(`examples`) and which concepts you asked about (`asked_about`).

## `memory.json`

All strings are UTF-8. Dates are ISO 8601 in UTC.

```jsonc
{
  "format": "trellis-learning-memory",      // always this value
  "version": 1,                             // readers refuse a version above the one they know
  "exported_at": "2026-10-26T14:03:11Z",
  "trellis_version": "0.4.0",
  "person": {"name": "Paul", "ui_language": "en", "level": 3},

  "map": {
    "concepts":  [{"id", "name", "aliases", "definition", "domain", "status", "created_at"}],
    "relations": [{"from", "to", "type", "strength", "reason"}],   // type: PREREQUISITE_OF | PART_OF | RELATED_TO
    "sources":   [{"id", "type", "title", "url", "ingested_at",
                   "mentions": [{"concept", "context", "importance", "start_sec", "quotes": [{"start_sec", "quote"}]}]}]
  },

  "conversations": [{"id", "concept", "level", "started_at", "last_activity", "consolidated", "memory_checkpoint",
                     "messages": [{"seq", "role", "content", "ts", "illustration"}]}],   // role: user | assistant
  "exercises":     [{"id", "run_id", "activity_id", "concepts", "objective_id", "prompt", "response", "response_mode",
                     "outcome", "assessed_by", "assistance_level", "uncertainty", "rationale", "occurred_at"}],

  "understanding": [{"concept", "level", "status", "since", "last_session",
                     "view":   {"summary", "covered", "struggles", "misconceptions", "intent", "self_assessment",
                                "quiz_correct", "quiz_wrong", "manual_fields", "removed",
                                "observations", "evidence", "learning_status"},
                     "ledger": { /* the memory ledger exactly as Trellis stores it */ }}],
  "profile": {"learning_profile": { /* works_well, works_poorly, preferences, teaching_preferences, notes, ... */ },
              "ledger": { /* the profile ledger */ }},

  "goals":       [{"id", "title", "status", "origin", "source_title", "source_id", "steps", "cycle",
                   "created_at", "updated_at", "active"}],
  "examples":    [{"id", "concept", "session_id", "seq", "original", "text", "date", "updated_at", "corrected_at"}],
  "asked_about": [{"concept", "ts"}],
  "counts":      {"concepts", "relations", "sources", "conversations", "messages", "exercises",
                  "understanding", "goals", "examples"}
}
```

Rules a reader can rely on:

- **`view` is for people and other tools, `ledger` is for Trellis.** `view` is the ledger already
  worked out: the current summary, active difficulties, evidence with quotes. Import uses `ledger`.
- **Evidence is traceable.** An evidence item from a conversation has `session_id` and `seq` (the
  message it quotes) and the `quote` itself. An item from an exercise has `origin: "exercise"` and
  points to an attempt in `exercises`. Trellis replays the ledger against the messages on import and
  refuses a file whose quotes do not match.
- **Your status is `view.learning_status`**: `learned` when you said you understand it, otherwise
  `learning`, `queued` or `suggested` from your learning intent. `map.concepts[].status` is the shared
  status on the install you exported from.
- **Concepts are referenced by id inside `map`, by name everywhere else.** Names are unique per install
  (case-insensitive).

## Not in the file

Passwords, the session secret, API keys and AI provider settings, embeddings (they belong to one
embedding model; Trellis makes new ones after an import), generated lessons, study guides, glossary
and reference pages, topic studies, sources that are still being processed, conversation suggestions,
the full text of your sources (titles, links and the quotes linked to concepts are included) and
internal locks and counters.

On an install with several learners, the knowledge map is shared and exported whole (every logged-in
learner already sees it). Conversations, exercises, understanding, profile, goals and examples are
only yours.

## Importing

The import always goes into the logged-in learner. **Preview** reads the file and reports what would
change without writing anything. **Apply** writes everything in one transaction and then replays your
memory from its conversations; if that replay fails, nothing is saved.

Importing is a merge, never a replacement, and importing the same file twice changes nothing.

| What | How it is matched | What happens |
|---|---|---|
| Concepts | name or alias, case-insensitive | Found: that concept is used; its definition is filled only if empty. New: created. The concept's status is never copied from the file's map; it follows your own memory, the same as when you change it in Trellis. |
| Relations | concept pair and type | Added if missing. Unknown types are skipped. |
| Sources | id, then url | Added if missing; links to concepts merged. |
| Conversations | id | New: added. Same conversation with more messages in the file: the later messages are added. Different content for the same message: the version here is kept (with a warning). |
| Exercises | id | New: added. |
| Understanding | concept | New: written as in the file. Existing: the two ledgers are merged (sessions, runs, corrections and earlier observations by id; lists unioned; items you removed stay removed; the newer intent and self-assessment win). Your learning status follows the merged memory. |
| Profile | | Lists unioned, items you removed stay removed; notes from the file only if yours are empty. |
| Goals, examples | id | New: added. An imported goal becomes active only if you have no active goal. |

Ids that belong to another learner on the install get a new id, so two learners can import the same
file without touching each other's memory. Limits: 24 MB upload, 120 MB unpacked, and per-list limits
(for example 20,000 concepts, 300,000 messages).

## Versioning

`version` changes only when a reader would misunderstand the file. Adding a field is not a new
version: readers ignore fields they do not know. A Trellis that reads version N refuses a file with a
higher version and says to update.
