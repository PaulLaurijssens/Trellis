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

Tests: `docker compose -f compose.dev.yaml exec backend python -m unittest discover -s tests` runs all
backend tests (no running database needed). `python3 -m unittest discover -s backend/tests -p "test_teach_*.py"`
runs the quick checks without any packages; a `test_teach_*` file that needs the backend packages must
skip itself there (see `test_teach_rescue.py`). GitHub runs both, plus a full `docker compose` start
and a check of the release bundle.
Please add a test with a fix.

Security problems: report them privately, see [SECURITY.md](SECURITY.md).

## Making a release

1. Move the *Unreleased* entries in `CHANGELOG.md` under the new version and date.
2. Optional: test the bundle locally with `scripts/make-bundle.sh --out dist`.
3. Tag and push: `git tag v0.4.0 && git push origin v0.4.0`.

The `release` workflow (`.github/workflows/release.yml`) then builds the images `trellis-api`,
`trellis-frontend` and `trellis-author` for linux/amd64 and linux/arm64, pushes them to
`ghcr.io/paullaurijssens/` with the tags `0.4.0` and `latest`, and makes a GitHub release with
`trellis-bundle.zip`, `setup.sh`, `setup.ps1` and `SHA256SUMS`. A tag with a dash (`v0.4.0-rc.1`) makes a
pre-release and does not move `latest`. You can also start the workflow by hand (*Actions* → *release*
→ *Run workflow*) with a version.

**Once, after the first release:** new GitHub packages are private. Make each of the three packages
public, or the installer and `docker compose pull` fail with "denied": on GitHub, open your profile →
*Packages* → `trellis-api` → *Package settings* → *Change visibility* → *Public*. Do the same for
`trellis-frontend` and `trellis-author`.

Then test the release on a clean machine with the checklist in [docs/TESTING.md](docs/TESTING.md).

Language: user-visible text goes through the dictionaries in `frontend/lib/` and prompts are English
with a "write in {language}" rule. Never hard-code a language check in a component.

## Contributor agreement

By submitting a contribution you agree that it is your own work (or you have the right to submit it),
that it is licensed under the AGPL-3.0 like the rest of the project, and that you grant the project
maintainer a perpetual, worldwide, non-exclusive, royalty-free license to also distribute your
contribution under other license terms. This keeps the option open to offer Trellis under a different
license later (for example a hosted edition) without having to contact every contributor. You keep
the copyright of your work.
