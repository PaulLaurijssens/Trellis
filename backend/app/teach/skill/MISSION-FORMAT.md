<!-- Trellis adaptation of mattpocock/skills teach @ 3216582 (MIT). Changes: see CHANGELOG.md -->
# MISSION.md Format

`MISSION.md` is at the workspace root. Trellis exports it from the learner's confirmed topic objective; you read it and propose revisions with `propose_objective_revision`. It captures the _reason_ the user is learning this topic. Every teaching decision (what to teach next, which resources to surface, which exercises to design) should trace back to this document.

## Template

```md
# Mission: {Topic}

Intent: {understand | apply | build | explore}

## Why
{1-3 sentences. The concrete goal the learner is chasing. What changes for them when they have this? A theoretical mission is valid: then say what the learner wants to be able to explain, judge or recognise.}

## Success looks like
- {A specific, observable thing the user will be able to do}
- {Another specific thing}
- {…}

## Constraints
- {Time, budget, prior commitments, learning preferences, anything that bounds the approach}

## Out of scope
- {Adjacent topics the user explicitly does not want to chase right now, protecting the zone of proximal development}
```

## Rules

- **One selected objective per lesson.** A topic can have more than one objective; the task names the one this lesson serves.
- **Concrete over abstract.** "Run a half marathon by October" beats "get fitter." "Ship a Rust CLI to my team" beats "learn Rust."
- **Push back on vagueness.** Trellis interviews the learner with a few short questions before the first lesson. If the mission is still vague, propose a sharper revision; do not silently sharpen it yourself.
- **Revise when reality shifts.** Missions change. When the user's goal moves, propose a revision: don't leave a stale mission steering future sessions.
- **Keep it short.** If `MISSION.md` runs past a screen, it has stopped being a compass and started being a plan.
