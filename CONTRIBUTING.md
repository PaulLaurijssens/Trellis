# Contributing to Trellis

Thank you. Small, focused pull requests are the easiest to review.

## Before you start

- Open an issue first for anything bigger than a bug fix, so we agree on the direction.
- The app must keep working for a single person on a laptop with `docker compose up`. Features that
  need a bigger machine or a cloud account must be optional.
- One memory authority: the Neo4j graph. Markdown, caches and exports are views, never a second truth.
- Nothing the model writes is trusted: lessons run sandboxed, answers are checked server-side,
  proposals from the teaching agent are validated before they touch memory.

## Working on the code

```bash
cp .env.example .env
docker compose -f compose.dev.yaml up -d
cd frontend && npm install && NEXT_PUBLIC_API_URL=/api DEV_API_PROXY=http://localhost:8000 npm run dev
```

Tests: `docker compose -f compose.dev.yaml exec backend python -m unittest discover -s tests` and
`python3 -m unittest discover -s backend/tests -p "test_teach_*.py"`. Please add a test with a fix.

Language: user-visible text goes through the dictionaries in `frontend/lib/` and prompts are English
with a "write in {language}" rule. Never hard-code a language check in a component.

## Contributor agreement

By submitting a contribution you agree that it is your own work (or you have the right to submit it),
that it is licensed under the AGPL-3.0 like the rest of the project, and that you grant the project
maintainer a perpetual, worldwide, non-exclusive, royalty-free license to also distribute your
contribution under other license terms. This keeps the option open to offer Trellis under a different
license later (for example a hosted edition) without having to contact every contributor. You keep
the copyright of your work.
