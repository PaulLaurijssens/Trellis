# /teach skill conformance matrix (plan §14)

Skill: upstream `3216582`, adaptation revision = `skill.adaptation_revision()` (recorded on every
`LessonVersion` and in every job trace). Status as of M1 (2026-09-20). "Trace" = the job trace from
`GET /teach/{pid}/lesson-jobs/{id}?trace=true`; "e2e" = `author/tests/e2e_host.py` (real Chromium, phone).

| Upstream section | Implementation | Test / scenario | Result (M1) |
|---|---|---|---|
| Teaching workspace | `teach/workspace.py` (read-only export, revision-stamped, in memory per job); tools `workspace_list/read` | Trace of jobs `0cc6b3ac`, `e2a0a96d`: reads MISSION, NOTES, CONCEPTS, RESOURCES, lessons/INDEX, reference/INDEX, assets/README | PASS |
| Philosophy: knowledge, skills, wisdom | `skill/SKILL.md` (communities removed, CHANGELOG #4); `sources_search`, `report_resource_gap`, `recommend_topic` | Trace `e2a0a96d`: `sources_search` ×2, `report_resource_gap` | PASS |
| Fluency vs storage strength | SKILL.md text + separate records: `ExerciseAttempt.assistance_level`, `outcome`, `assessed_by`; `model.assistance_level` | `test_teach_model`: assisted ≠ unassisted; forged score → `needs_practice` | PASS (projection into memory + spaced retrieval: M2/M4) |
| Lessons | `teach/orchestrator.py` (`lesson_write_file/validate/publish`), `teach/artifacts.py`, `author/` workbench, PWA `LessonStage.js` | e2e 18/18 on the agent-authored pilot "Matrices as Transformations" | PASS |
| Assets | `teach/assets/trellis-lesson/1.0.0` (stylesheet, fonts, SDK, README), `assets/` in the workspace, bundling at publish | `author/tests/run_fixture.py`; validator rejects unknown assets and writes to `assets/` | PASS (`asset_propose`: linted, versioned, immutable; first agent-made component expected in M3) |
| Mission | `teach/objectives.py` (`Topic`, `TopicObjective` revisions), `LessonDock.js` pills + preview + confirm | curl scenario: create topic → preview → save rev 1 → stale save refused (400) | PASS |
| Zone of proximal development | Workspace: `learning-records/`, `lessons/ATTEMPTS.md`, `CONCEPTS.md` prerequisites; TASK step 1 | Trace: read before authoring; second lesson did not repeat the first | PASS (evidence-based adaptation grows with M2) |
| Knowledge | `RESOURCES.md` export from `:Source` + `MENTIONED_IN`; manifest sources must be in the workspace; citations through `data-dl-source` | Validator: cited source must be in the manifest; host opens sources, the frame cannot | PASS |
| Skills | SDK `predict/quiz/activity/slider/plane`; server-side checkers `model.check_answer`; rubric assessment with uncertainty | e2e: prediction → server feedback; unit tests of all checkers | PASS |
| Reference documents | `lessons.save_reference` (revisions, no twins), `propose_reference`, reference viewer in `MentorPanel.js` | Trace: `propose_reference` OK in both jobs; listed in the dock | PASS (reference cards polish: M2) |
| NOTES.md | `propose_note` → `memory._profile_commit` (same replayable ledger as chat consolidation) | Code path shared with existing `test_memory_model`/profile tests | PASS (not yet exercised by an agent run) |
| Learning-record format | Workspace view over `memory_v2` (evidence, corrected misconceptions, claims, self-assessment); `propose_learning_record` stores claims only | `learning_records()` view; claims never enter projection (`memory_model.project` ignores them) | PARTIAL: exercise evidence → `memory_v2.runs` is M2 |
| Mission format | `skill/MISSION-FORMAT.md` + `workspace.mission()` | Trace: MISSION.md read first | PASS |
| Resources format | `skill/RESOURCES-FORMAT.md` + `workspace.resources()` incl. `## Gaps` | Gap reported in job `e2a0a96d` appears under Gaps on the next export | PASS |
| Glossary format | `propose_glossary_term` (needs an unassisted demonstrated attempt), `GLOSSARY.md` export; concept definitions untouched | Tool refuses without evidence | PASS (first real term needs M2 evidence) |

Running lessons also load the skill: `teach/lesson_chat.py` appends verbatim SKILL.md sections to the
mentor prompt for questions asked inside a lesson (e2e: "contextual question answered through the lesson route").
