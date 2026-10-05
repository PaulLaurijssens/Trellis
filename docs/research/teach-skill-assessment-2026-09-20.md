# Dendrite: assessment of Matt Pocock’s teach skill

Date: 20 September 2026. Scope: research and proposed adaptation only; no application or VPS changes.

## Evidence and limits

Read the teach SKILL.md, MISSION-FORMAT.md, LEARNING-RECORD-FORMAT.md,
RESOURCES-FORMAT.md, GLOSSARY-FORMAT.md, directory listing and repository license.
The latest commit touching the skill reported by GitHub was
`321658273cb1d20b76026717d027d505790106d4`. Source URLs:

- https://github.com/mattpocock/skills/tree/main/skills/productivity/teach
- https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/SKILL.md
- https://github.com/mattpocock/skills/blob/main/skills/productivity/teach/LEARNING-RECORD-FORMAT.md
- https://github.com/mattpocock/skills/blob/main/LICENSE
- https://www.youtube.com/watch?v=s5T5oQJcJ6U

YouTube caption retrieval returned RequestBlocked. Google’s direct video analysis
completed with accessible=true. Its raw output and usage are in
`teach-video-analysis.json`. This is an AI-produced paraphrase, not a verified
transcript or independent frame-by-frame inspection. Approximate navigation points:

- 03:40: illustrated cube anatomy/notation lesson and checks.
- 04:24: learning records and a subsequent corner-position lesson.
- 05:24: glossary and condensed solve reference.
- 06:12–08:26: focused corner-cycle recall trainer, guided/blind practice and feedback.

These observations suggest a progression from explanation to targeted practice.
Do not treat incidental model/version claims in the raw analysis as verified facts.
The current repository also specifies reusable shared assets; the video analysis
reports inline styling in demonstrated lessons. The current specification is the
better implementation reference, rather than assuming the demo and main branch match.

Local code inspected: backend/app/chat.py, learn.py, illustrations.py,
personal_context.py, memory_model.py, journey.py, video.py and
frontend/components/TeachingIllustration.js. This is the local checkout, not a
verified audit of the VPS release.

## Recommendation

Adapt the teaching workflow and artifact concept. Preserve Dendrite’s graph,
learning paths, learner identity, memory and sources as the authoritative system.
The main missing layer is a persistent interactive lesson, connected to the mentor
conversation and able to return meaningful practice evidence.

The upstream skill is a teaching protocol for a coding agent with file and browser
tools. It is not a packaged simulator library or an HTML renderer. Copying its
prompt into the existing chat cannot provide those missing capabilities.

## What transfers, and what changes

| Upstream idea | Dendrite adaptation |
|---|---|
| Mission with concrete success criteria | Extend existing goals with desired capability, available time and constraints. Allow casual exploration without a compulsory interview. |
| Short, focused HTML lessons | Saved lessons with one outcome, one useful interactive example, practice and recap; embedded in the mentor experience. |
| Zone of proximal development | Use prerequisites, self-report, demonstrated evidence and current difficulty; ask one diagnostic question when uncertain. No fictional precise readiness score. |
| Knowledge versus skill acquisition | Clear low-friction explanation first; retrieval/prediction/application afterwards, with help and skip options. |
| Learning records | Reuse the evidence ledger. Add exercise-attempt provenance rather than a parallel Markdown memory store. |
| Trusted resources | Reuse Source and Mention records; retrieve additional approved sources when needed. Stored snippets and AI video summaries are not full verified sources. |
| Reusable assets | A shared, versioned component library with Dendrite styling, touch support, accessibility and deterministic calculations. |
| Reference documents | Save compact reusable concept cards, worked examples and a personal glossary, linked back to lessons and sources. |
| One mission per workspace | Multiple learner-owned goals in the same knowledge graph; preserve the current active-goal model. |
| Equal-length quiz answers | Avoid obvious formatting cues, but prioritize clear plausible alternatives over exact character-count constraints. |
| Community recommendations | Optional for real-world practice; do not interrupt normal learning with repeated invitations. |

The repository is MIT licensed. Preserve its copyright and license notice when
incorporating its instruction text or other material. No upstream files were installed.

## Why the current mentor feels limited

The local chat prompt already requests checks, alternate explanations, prerequisite
help and adaptation to the learning profile. The limitation is not simply a missing
teaching instruction. Its response contract is a short Markdown answer plus one
optional diagram. The renderer only accepts flow, comparison, two 2D vectors or
bars. The schema explicitly forbids HTML, SVG, Mermaid and code output. There is no
lesson artifact lifecycle or exercise interaction channel in these inspected paths.
Memory is already relatively strong: conversation evidence is anchored to actual
learner messages, and exposure is separated from self-assessed understanding and
specific demonstrations. Preserve those distinctions.

## Proposed learner experience

A concept opens with a useful next activity: for example, “See how a matrix changes
a shape — about 8 minutes.” Offer a quick explanation as well as a guided lesson.
Continue to allow arbitrary questions and voice input at any point.

The lesson has a simple flow:

1. A concrete outcome and connection to the learner’s goal.
2. A concise explanation beside a relevant visual.
3. A prediction before revealing the result.
4. A small manipulation or application task with immediate feedback.
5. A recap, saved reference and an optional later retrieval check.

Example: a matrix lesson draws a square on a coordinate plane. Change scaling,
rotation or shear and observe the transformation. Predict which control changes
area; test it; then explain why. The mentor can discuss the current parameters and
the learner’s actual prediction. Dragging sliders alone is not understanding.

Example: an attention lesson lets the learner choose a query token, compare example
scores and adjust temperature. Label simplified calculations as illustrative, not
observations from a real language model. The learner predicts which token receives
more weight before changing the controls.

On desktop the visual occupies the main lesson surface, with conversation available
alongside or below. Keep the graph context collapsible. On mobile show one activity
at a time with a reachable “Ask mentor” action, touch controls, and exact resume.
Keep familiar Dendrite styling; avoid adding another dense dashboard.

## HTML approach

Use two rendering paths:

A. Trusted components first. The model supplies a validated lesson specification:
objective, explanation blocks, source references, interaction type and parameters,
practice prompt, and assessment rubric. The application renders interactive HTML
through vetted React/SVG/canvas components. Start with matrix transformations,
vector similarity, step-by-step processes and prediction/reveal exercises. This
expands the present declarative system while making it genuinely interactive.

B. Custom HTML/JS for lessons that need something new. Run those artifacts in a
separately isolated, restricted lesson frame, not injected into the application DOM.
Use a sandbox, restrictive CSP, no ambient credentials or arbitrary network calls,
and a small validated message bridge. Do not grant same-origin access together
with scripts for content sharing the app origin. External citations should be
handled by the parent application. Browser-test artifacts before publishing; allow
fallback to a standard visual when generation fails. Sandboxing alone does not
prevent excessive computation or make the educational content correct.

Reference: https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe

Custom widgets must not be able to mark concepts mastered or mutate graph records.
Treat their events as untrusted input. Use server-side scoring for deterministic
exercises; use explicit rubrics and source grounding for open responses, preserving
uncertainty. A generated widget’s success message is not independent evidence.

## Persistence and integration

Add Lesson, LessonVersion, LessonRun and ExerciseAttempt records associated with
existing person, concept, goal, source and chat-session identities. Keep large
artifact files in controlled storage; retain references and relationships in Neo4j.
A saved version should include its content hash, component versions, model/prompt
version, sources and validation status. Resume the same version rather than silently
regenerating a different lesson.

Track phase, current step, widget parameters, predictions, answers, hints, attempts
and last checkpoint. Send the mentor compact current-state context instead of the
entire HTML document on every turn. Keep voice/text questions part of the same run.
Record evidence such as “correctly predicted area change without hints” with the
actual task and response. Preserve self-report, exposure, assisted performance and
unassisted evidence separately. Later retrieval is separate evidence of retention.

Avoid duplicate facts: the lesson system should feed the existing memory ledger and
learning-path recommendations, not create a competing mastery model. Extend memory
validation for exercise provenance; do not fabricate chat quotes to satisfy its
current conversation-only validation.

## Suggested delivery sequence

1. Pilot one matrix-transformation lesson end to end: start, manipulate, predict,
   ask a question, receive feedback, save and resume on the PWA. Keep the current
   mentor as fallback. Use the current VPS repository/release process.
2. Add the lesson planner and reusable interactive templates. Test a second,
   different concept such as attention/vector similarity to avoid overfitting.
3. Integrate exercise evidence, reference cards and spaced review with the existing
   memory system. Let observed difficulty change the next lesson.
4. Add sandboxed custom HTML generation for gaps the templates cannot cover, with
   artifact validation, repair limits, caching and generation budgets.

Generate substantial artifacts once and reuse them. A slider movement should not
trigger an LLM request. Separate lesson-generation latency from normal conversation,
show preparation progress, and retain a useful explanation if generation fails.
Offline downloaded lessons are possible, but app-shell PWA caching alone does not
make lessons, scoring or mentor replies available offline. Queue supported attempts
with stable IDs and sync idempotently; explain which feedback needs connectivity.

## Pilot acceptance checks

- Correct, source-supported calculations; changing inputs updates the diagram.
- No horizontal overflow on a phone; touch and keyboard operation; readable labels.
- Ask a question about the exact current state and receive a relevant answer.
- Closing and reopening resumes the same lesson, step and parameters.
- A hint-assisted answer is not recorded as unassisted mastery.
- Existing graph paths and memories remain intact; no duplicate memory authority.
- Generated content cannot access authentication, arbitrary network or graph writes.
- Compare against the current mentor using a novel application task and a later
  retrieval check, not merely clicks, time spent or how attractive the lesson looks.

The expected benefit is better teaching interaction, not simply more elaborate
illustrations. The proposed pilot should validate that benefit before broad rollout.
