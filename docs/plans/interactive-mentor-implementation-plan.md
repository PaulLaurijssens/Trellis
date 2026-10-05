# Dendrite /teach skill integration — engineering implementation plan

Status: proposed implementation contract incorporating owner feedback; not implemented.
Date: 20 September 2026.
Target: existing VPS deployment and mobile PWA. Implement through the deployed project's repository and release pipeline. The local checkout informed the research; verify its correspondence to the deployed release before coding.

## Mandatory upstream baseline — read before implementation

This project integrates Matt Pocock's **complete `/teach` skill into Dendrite's mentor**. It is not a loosely inspired visual upgrade or a selection of individual teaching techniques. Vendor and adapt the skill as the mentor's versioned teaching workflow, and supply the tools/runtime that allow it to function inside Dendrite.

Required inputs for the engineering team:

- **Skill repository:** https://github.com/mattpocock/skills/tree/main/skills/productivity/teach
- **Core instructions:** https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/SKILL.md
- **Video walkthrough:** https://www.youtube.com/watch?v=s5T5oQJcJ6U
- **Mission format:** https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/MISSION-FORMAT.md
- **Learning-record format:** https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/LEARNING-RECORD-FORMAT.md
- **Resource format:** https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/RESOURCES-FORMAT.md
- **Glossary format:** https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/GLOSSARY-FORMAT.md
- **License:** https://github.com/mattpocock/skills/blob/main/LICENSE

At research time, the latest commit affecting this directory was `321658273cb1d20b76026717d027d505790106d4`. Before implementation, resolve and record the exact upstream commit to vendor and compare it with that reviewed revision. Read all files in the skill directory, including agent metadata. Preserve the upstream files and MIT notice unmodified in a vendor directory; keep Dendrite's adapted version and change log alongside them. Do not automatically pull upstream changes into production.

The repository is the source of the teaching behaviour; the video is the experience reference. Caption access was blocked during research; direct-video AI analysis is saved in `../research/teach-video-analysis.json` and is a paraphrase, not a verified transcript. The team should inspect the video itself when confirming UX details. Do not claim that a stock simulator library ships with the skill: it instructs an agent to author the lessons and reusable assets.

### Definition of integration

The adapted SKILL.md must actually be loaded by the mentor's teaching orchestrator when planning, generating, running and continuing lessons. Its referenced formats must be available to the appropriate agent steps. A documentation link or a few copied prompt bullets do not satisfy this requirement.

The orchestrator must provide the skill with tools to read its scoped teaching workspace, retrieve approved sources, author and inspect HTML/CSS/JS, reuse assets, validate and publish lessons, read learner responses, and propose records/references through Dendrite services. Interactive practice results and conversation must return to that same teaching workflow. The learner should not need to invoke a CLI or manage files.

The initial pilot limits **topic coverage**, not the integration to a few selected features. A hand-authored matrix widget with the old mentor prompt is not the completed skill integration.

### Full skill coverage and agreed adaptations

| Upstream section | Required Dendrite behaviour | Adaptation, not omission |
|---|---|---|
| Teaching workspace | Inspect mission, resources, records, notes, lessons, references and assets across sessions | Scoped Markdown/files backed by the existing memory and artifact services |
| Philosophy: knowledge, skills, wisdom | Ground explanations in trusted material and teach through practice and feedback | Community recommendations excluded by owner request; retain appropriate real-world application |
| Fluency versus storage strength | Retrieval, spacing and relevant interleaving; distinguish immediate success from retention | Feed Dendrite's evidence/review system, not a second score |
| Lessons | Generate short, attractive, focused HTML lessons, source links and follow-up invitations | Serve authenticated saved artifacts in the PWA; no local browser-opening command |
| Assets | Inspect and reuse shared styles, widgets, diagrams and simulators; author reusable additions | Versioned approved asset library with isolated generation and validation |
| Mission | Every guided lesson follows a concrete objective and appropriate constraints | Objective per main topic; optional initial pills; allow existing quick-question mode |
| Zone of proximal development | Use prior understanding and current difficulty to select and adapt the next lesson | Existing evidence and prerequisites; no invented numerical readiness certainty |
| Knowledge | Find/use high-trust resources and identify missing support | Existing source store plus controlled retrieval; preserve excerpt/provenance boundaries |
| Skills | Interactive tasks with tight feedback loops and meaningful practice | Validated activity events and assessments; relax exact equal-length answer rule |
| Reference documents | Produce linked reusable summaries, procedures, examples and glossaries | Store with topics/concepts and saved lessons |
| NOTES.md | Persist relevant teaching preferences and observations | Existing learner profile/memory, with provenance and correction support |
| Learning-record format | Record demonstrated understanding, prior-knowledge claims, corrections and objective shifts; preserve supersession | Existing evidence ledger with exercise provenance; no fabricated conversation quotes |
| Mission format | Why, observable outcomes, constraints and scope | Structured topic objective plus Markdown representation |
| Resources format | Annotated trusted sources, gaps and revision | Existing source records; omit community section for this release |
| Glossary format | Consistent terminology, concise definitions, revision as understanding develops | Personal learning glossary alongside, not replacing, the complete concept graph |

Only the listed owner-approved adaptations are intended. Any further behavioural omission must be documented for review rather than silently dropping a skill section.

## 1. Outcome and scope

Turn the mentor into an adaptive teacher that creates short, visually rich, interactive lessons, observes learner responses and uses the existing memory system to decide what to teach next.

Preserve the knowledge graph, graph/path navigation, learner identity, conversation history, understanding distinctions, source provenance and existing memory authority. Do not migrate to a second file-based memory database. Do not reset existing knowledge or learning progress.

Integrate the full adapted Matt Pocock /teach workflow defined above, including Markdown teaching context, objective-driven instruction, generated HTML, reusable assets, learning records and references. Custom HTML generation is a first-class capability, not restricted to a future phase after a large template library. Use reusable components and code generation together.

Out of scope for this release: community recommendations; replacing graph/path navigation; multi-learner tenancy redesign; arbitrary external scripts in lessons; automatic deployment by the teaching agent; full offline AI tutoring; automatic marking of broad mastery from lesson completion.

## 2. Settled product decisions

1. One memory authority: the existing Dendrite memory service/store.
2. Markdown is welcome as stored content and as a generated working representation of that memory. No independent Markdown store with separate truth or uncontrolled bidirectional synchronization.
3. Each main topic can have a learner-specific objective, including theoretical, practical or mixed learning intent. Objectives belong to the learner and stable topic identity, not a mutable display title or transient visual cluster.
4. A first visit may show 2–4 concise pill-based questions; use known answers as defaults, allow skipping and do not repeat the interview each lesson.
5. Save lessons as versioned HTML assets on the VPS, together with their dependencies and run state. “Local HTML” means server-local storage served through authenticated Dendrite routes, not a browser-accessible file path.
6. The lesson-authoring agent may inspect an explicitly prepared workspace and generate HTML/CSS/JavaScript. Expose this behind the application lesson-generation service and its validation/publishing boundary.
7. Reference material is a new explicit feature associated with topics and concepts.
8. One activity at a time on mobile; keep text and voice questions available.
9. Match Dendrite typography, colours, spacing and interaction patterns across generated lessons. No per-lesson redesign of the surrounding application.
10. Keep the VPS's private access, restricted egress, secrets handling and immutable deployment approach.

## 3. Objectives and initial questions

### Data semantics

Add TopicObjective keyed by person_id and topic_id, with objective_id, revision, status, intent (understand/apply/build/explore), objective_markdown, observable_outcomes[], preferred_depth, constraints, created_at and updated_at. A concept may have more than one topic association; store the selected objective on the lesson/run so the context is unambiguous. Allow explicit concept-level refinements without overwriting the broader objective.

Do not assume every topic needs a practical project. Examples:

- Theoretical: explain how attention combines information and recognise its limitations.
- Hands-on: implement and inspect a small attention calculation.
- Exploratory: compare possible applications and decide what to investigate further.

Topic objectives may link to an existing LearningGoal. Do not replace or silently update that goal. Support multiple topic objectives with one explicitly selected for a lesson. Where a concept lacks a stable main-topic owner, offer objective selection or a temporary lesson intent; do not silently persist a generated cluster ID as durable identity.

### First-visit flow

Show at most four questions in one compact sequence:

1. What do you want from this topic? Understand / Apply / Build / Explore.
2. How familiar is it? New to me / Know the basics / Already using it.
3. How should we approach it? Concepts / Examples / Hands-on / A mix.
4. How much time today? 5 / 10 / 20 minutes.

Include optional free text and “Use my defaults / Skip”. Familiarity is self-report, not evidence of mastery. Session time belongs to the run, not a permanent topic constraint. Reuse existing preferences; do not ask what is already known unless the user wants to change it. Preview the objective for confirmation before storing it. Changes to the objective are versioned; the mentor proposes substantive revisions and the learner accepts them.

## 4. Markdown within existing memory

Support MemoryDocument through the existing memory service, not a new memory backend:

- document_id, person_id, topic_id/concept_ids, kind, markdown, revision;
- kind: objective, teaching_notes, learning_record or reference;
- origin, supporting_evidence_ids, source_refs, created_at, updated_at;
- status and supersedes links when relevant.

Reuse equivalent existing entities rather than duplicating them. For example, objective_markdown belongs to TopicObjective, and a learning-record narrative may be a view over an evidence record. The engineering design must explicitly name the authoritative entity for each field.

Expose a prepared authoring workspace containing familiar representations such as MISSION.md, NOTES.md, RESOURCES.md and learning-records/*.md. These are revision-stamped snapshots exported from Dendrite. The authoring agent can inspect them and propose changes. All accepted changes pass through typed application APIs with ownership checks, expected revision and provenance validation. File edits do not directly mutate memory. Discard temporary snapshots after the job according to retention policy.

Do not put credentials or unrelated personal history in this workspace. Do not turn source text, Markdown notes or video excerpts into executable instructions.

### Evidence contract

Extend the current conversation-evidence model to support exercise evidence without manufacturing chat quotes:

ExerciseAttempt: attempt_id, run_id, lesson_version_id, activity_id, person_id, concept_ids, objective_id, prompt_snapshot, response, response_mode, hint_usage, assistance_level, parameters_snapshot, occurred_at, received_at, idempotency_key.

Assessment: assessment_id, attempt_id, outcome, rubric_version, assessed_by (deterministic/mentor/learner_self_report), rationale, uncertainty, supporting_source_refs.

Keep exposure, practice, assisted success, demonstrated application, self-assessment and later retention distinct. Opening a lesson, elapsed time, slider activity or a client-reported success flag cannot independently establish understanding. Deterministic exercises are checked on the server where feasible; open responses use explicit rubrics with uncertainty. Memory updates remain amendable and replayable through current correction semantics.

## 5. Lesson and artifact model

Add or map equivalent entities:

- Lesson: stable identity, person/topic/concept/objective associations and title.
- LessonVersion: immutable specification, objective_revision, source snapshot references, artifact manifest, content hash, component versions, generator/prompt version, validation report and publication status.
- LessonRun: selected version, person_id, conversation/session association, current activity, state revision, widget state, started_at, updated_at and status.
- ExerciseAttempt and Assessment: evidence as above.
- ReferenceMaterial: markdown and/or HTML artifact, topic/concept links, sources, language, revision and origin lesson.

Store relationships/metadata through current persistence patterns, normally Neo4j. Store HTML/CSS/JS/media under a dedicated VPS artifact volume with stable IDs and content hashes. Never store generated lessons inside immutable application images or depend on a developer's laptop. Include artifacts in backup and restore together with their database references.

Artifacts can be one standalone HTML file or a small package with pinned shared assets. A manifest declares the entrypoint, exact dependency versions/hashes, language, activity IDs and available interaction events. Browser URLs are authenticated application routes, not arbitrary filesystem paths. Prevent path traversal and cross-learner access even in the current single-user deployment.

A run stays on its original lesson version. Regeneration creates another version; do not change the content underneath a paused learner. Subsequent lessons may use new objectives or components without rewriting prior evidence.

## 6. Authoring pipeline: agent plus controlled service

Application orchestration and code-capable authoring are complementary.

Pipeline:

1. Select objective, relevant concept neighbourhood, source excerpts, learner memory and available session time.
2. Produce a bounded lesson specification: one outcome, activities, explanation, visual mechanism, practice rubric, source links and desired interaction types.
3. Prepare a scoped workspace with Markdown context and read-only shared assets.
4. Author HTML/CSS/JS using the shared design system and interaction SDK. Allow custom visuals/simulations when useful. Do not force all subjects into a handful of diagrams.
5. Validate structure, dependencies, educational invariants, mobile layout, interaction events and isolation.
6. Repair within a bounded retry budget. If still invalid, retain the normal explanation or a simpler validated visual and offer retry.
7. Publish an immutable artifact version and open a run.
8. Persist questions, attempts and checkpoints; update existing memory through validated evidence services.

Job lifecycle: queued → preparing → generating → validating → ready, with failed/cancelled terminal states. Show real stage progress, not invented percentages. Support cancellation, deduplicate repeat submissions, and enforce time/token/concurrency limits. Suggested initial policy: one active authoring job per learner and at most one automated repair attempt; make limits configurable.

No model request per slider movement. Run deterministic interactions in the browser. Send compact state summaries only when asking the mentor or submitting an activity. Cache reusable lesson artifacts by relevant specification/version inputs; never return another learner's personalised artifact through a shared cache.

## 7. Shared design and interaction toolkit

First release must include:

- Versioned Dendrite stylesheet and design tokens: readable type, dark palette, touch targets, spacing, reduced-motion support, focus states and responsive sizing.
- Lesson shell: objective, activity navigation, source references, hint, feedback, reset, recap and ask-mentor hooks.
- Reusable helpers for diagrams, numerical inputs/sliders, prediction/reveal and simple quizzes.
- A matrix transformation activity as the pilot; a second unrelated interaction to prove generalisation.
- A supported way to author custom SVG/canvas/HTML interactions using the same shell and event contract.

Consistency comes from shared assets, an authoring specification and browser validation, not a requirement to generate an entirely new style on each request. Do not fetch scripts or fonts from arbitrary CDNs at runtime. Prefer bundled assets and deterministic calculations. Label illustrative values and simplified models; never portray them as measured data.

## 8. Isolation and VPS constraints

Separate two trust boundaries:

### Authoring execution

Run generated code, browser previews and any validation commands in a non-privileged isolated worker/container. No Docker socket, host filesystem, deployment permissions, production database credentials or unrestricted shell on the VPS. Mount only job-local writable storage and approved read-only assets. Apply CPU/memory/process/time/storage limits and cleanup. Generation/research services use the existing egress policy; do not loosen the VPS-wide allowlist for generated lessons.

### Learner-side execution

Render custom artifacts in a restricted lesson frame on a separate origin where practical, or an opaque-origin sandbox with a reviewed CSP. Permit only required script execution; do not combine same-origin privileges with scripts for content sharing the application origin. Block arbitrary network, top navigation, popups, forms and credential access. Broker source navigation through the parent application. Keep voice recording in Dendrite's trusted UI.

Use a small versioned event bridge. Validate message source against the active frame, payload schema/size, run binding, activity IDs and a per-run channel token. Opaque-origin messages may have origin "null"; never trust that value alone. For example:

- lesson.ready
- activity.state_changed (debounced checkpoints)
- activity.answer_submitted
- activity.hint_requested
- mentor.question_requested

Treat all frame events as untrusted, including scores. The parent/server controls persistence and assessment. The frame cannot directly change memory, objectives or graph edges. Test credential access, network attempts, navigation, forged events and excessive execution. A sandbox does not establish content correctness or eliminate resource-exhaustion risk.

## 9. Learner UX

Graph and learning paths remain the main navigation. On entering a topic:

- Continue a paused lesson when available.
- Otherwise offer a concise recommended lesson outcome and duration.
- Retain quick explanation, arbitrary questions and voice input.
- Offer optional initial pills if the topic objective is missing.

During a lesson, show one primary activity and a persistent Ask mentor control. Questions include activity ID, current visual parameters and relevant recent attempts so “why did that move?” has context. Answering a question must not reset the activity. Allow simpler explanation, another example, skip and return to the path.

Desktop can show the activity alongside conversation; keep graph context collapsible. Mobile uses one activity at a time, with conversation in a reachable sheet or alternate view; returning restores exact activity state. Preserve scroll/focus appropriately and provide alternatives to drag-only inputs.

Do not make lessons mandatory for every question. A short factual question can remain a short answer.

## 10. Reference materials

Add a References area to topic/concept context, collapsed when not needed. Support compact concept summaries, worked examples, formulas, step-by-step procedures and glossaries. References can be authored during a lesson or saved explicitly by the learner; make saved state clear and avoid one duplicate reference per conversation turn.

Link references to their source material and producing lesson/version. Keep canonical concept definitions separate from the learner's own explanation. A personal glossary may record what the learner can express; it must not replace the broader knowledge base containing unlearned concepts. Maintain revision history for corrections and supersession. Allow opening a reference while asking the mentor about it.

## 11. Suggested service interfaces

Names below are proposed contracts; align them with existing API conventions:

- GET/PUT /topics/{topic_id}/objective — authenticated learner, revision-checked update.
- POST /lesson-jobs — concept/topic/objective, language, time budget, optional intent; idempotency key.
- GET /lesson-jobs/{id}; POST /lesson-jobs/{id}/cancel.
- GET /lessons/{id}/versions/{version}; authenticated artifact manifest/content routes.
- POST /lesson-runs; GET/PATCH /lesson-runs/{id} — version-pinned run and revision-checked checkpoints.
- POST /lesson-runs/{id}/attempts — validated, idempotent exercise submission.
- POST /lesson-runs/{id}/questions — existing mentor pipeline plus bounded activity context.
- GET /topics/{id}/references and /concepts/{id}/references.
- Revision-checked reference create/update and existing memory correction endpoints.

Derive person identity from existing authentication; do not trust client-supplied person_id as authorisation. Whitelist persisted widget-state fields with size limits rather than saving arbitrary DOM/JS state. Use stable operation IDs for reconnects and retries.

## 12. PWA, interruption and offline behaviour

Required for initial rollout: reliable save/resume, interrupted request recovery, visible connectivity state and persistence of an unsent question draft where consistent with existing privacy rules. Verify on the deployed iPhone/Android browser targets and available Tailscale/private-access setup.

Optional follow-on: explicitly downloaded lesson bundles and references. Cache exact versioned assets; queue supported attempts with unique IDs and sync once. Store offline data per user, clear appropriately on logout and define retention. Offline deterministic feedback must be labelled separately from pending server assessment. New mentor responses, lesson generation and source retrieval need connectivity. Do not claim offline capability merely because the PWA is installable.

## 13. Delivery milestones and acceptance gates

### M0 — deployed baseline and integration design

Verify deployed commit, authentication, PWA caching, model access, memory schema, backups, egress and release process. Map proposed records to existing entities and document authoritative ownership. Deliver agreed API/event schemas, artifact storage/isolation design, and a feature-flagged migration/rollback plan. Do not start a parallel local fork unaware of VPS changes.

### M1 — integrated skill, objectives, runtime and one interactive pilot

Vendor the complete upstream skill and supporting formats, produce the adapted SKILL.md and change log, wire it into the teaching orchestrator and verify its tool access. Implement topic objectives and optional onboarding pills; versioned artifact storage; shared design shell; isolated runtime; one matrix lesson; mentor questions with visual context; exact resume. Include a scoped code-authoring path producing the pilot HTML using shared assets, not only hand-authored production content.

Gate: integration traces identify the skill revision and show the adapted skill driving lesson creation and continuation, including resource use, a saved HTML lesson, reference material and memory proposals. The learner starts on phone, makes a prediction, manipulates the example, asks a contextual question, closes/reopens and resumes unchanged. Existing chat remains available if artifact generation fails.

### M2 — evidence and reference integration

Implement attempts, assessment, memory projection and reference cards. Extend current memory validation for exercise provenance. Add a second concept/activity, e.g. attention-weight exploration, to test adaptation across topics.

Gate: assisted and unassisted answers remain distinguishable; a slider interaction or forged score never marks mastery; repeated requests do not duplicate evidence; reference links and sources remain valid.

### M3 — broaden the integrated skill across topics

Expand and harden the skill-driven authoring already present in M1: choose standard helpers or custom HTML, use learner memory to adapt tasks, and reuse assets across more topics. Add generation budgets, bounded repairs, validation reports and activity-specific feedback. Persist supported Markdown proposals through existing services.

Gate: multiple topics retain consistent styling, readable mobile layout and accurate calculations; unsupported simulations fall back gracefully; current activity is recoverable after errors.

### M4 — retention and mobile polish

Connect later retrieval checks to existing review logic; improve reference reuse; optionally add explicit offline downloads after the online workflow is reliable. Evaluate learning outcomes before extending the activity catalogue broadly.

## 14. Test and release checklist

- **Skill conformance:** every row in the full-skill coverage table has an implementation location, integration test/scenario and result. Store this matrix with the adapted skill.
- **End-to-end teaching scenario:** start a topic objective, retrieve grounded resources, generate a styled interactive HTML lesson, observe a learner difficulty, adapt the activity, persist evidence and a reference, then resume in another session using that memory. Verify the same workflow on mobile.
- **Instruction provenance:** lesson versions record upstream skill revision and Dendrite adaptation revision; changing either is an explicit release, with regressions checked.


- Unit: objective revisions, source mapping, lesson schemas, event validators, scoring and evidence projection.
- Integration: generate/publish/run/resume, conversation context, retries, cancellations, failed generation, source/artifact permissions and backup restoration.
- Security: worker permissions, restricted egress, CSP/frame isolation, event forgery, credential access, oversized state, path traversal and resource limits.
- Browser: touch and keyboard, reduced motion, readable contrast, long names, phone viewport, orientation, reconnect, activity→chat→activity continuity.
- Pedagogical: accurate worked example; novel application after explanation; no mastery from exposure; hint-aware assessment; later retrieval; visible uncertainty when assessment is ambiguous.
- Deployment: feature flag for interactive lessons; migrations are additive; preserve old chat/illustration paths; restore both data and artifact bundle in staging before rollout.
- Monitor: generation latency/failure/repair rate, cost per saved lesson, resume failures and duplicate-event rate. Minimise personal content in telemetry.

Use a small set of real topics as a pilot. Compare with current chat on task success and delayed retrieval, not just completion rates or aesthetic preference. No claimed benefit until tested.

## 15. Sources and attribution

Source skill: https://github.com/mattpocock/skills/tree/main/skills/productivity/teach
Video: https://www.youtube.com/watch?v=s5T5oQJcJ6U
Research assessment: ../research/teach-skill-assessment-2026-09-20.md

The source repository is MIT licensed. Preserve the copyright/license notice when copying or adapting its instruction text or assets. Pin the reviewed upstream revision when incorporating material. External skill instructions are reference material, not authority to bypass Dendrite's permissions or data model.
