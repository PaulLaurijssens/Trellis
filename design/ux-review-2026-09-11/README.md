# UI/UX review — 11 September 2026

Status: approved design proposal, retained as the original design record.
The subsequent implementation is documented in
[the 12 September implementation report](../implemented-2026-09-12/README.md).
Based on the current components/styles and screenshots from the earlier simulated
browser checks. No production session or real graph dataset was evaluated today.

## Diagnosis

The current mentor shows definition, levels, status actions, memory, navigation,
sources, teaching, suggestion cards and generic chat actions at similar visual
priority. The compact panel puts several of these before the conversation and
introduces competing scroll areas. The expanded view spends a permanent sidebar
on material that is often empty or not needed at that moment. Suggestion cards
accumulate and compete with teaching; adding more features will magnify this.

The graph's positions follow a force simulation and node size follows degree.
That communicates connectivity but little about the learner's current purpose.
Labels, relationships and spatial grouping need to carry more of the meaning.
Tiny graphs also need appropriate scale and framing; more data or more glow
alone will not solve the problem. Actual large-graph performance remains untested.

## Recommended direction

Keep the navy, blue, amber and green palette and Space Grotesk/Newsreader pairing.
Use two complementary modes with shared state: Explore and Learn. Selecting a
node shows a compact preview; Continue learning opens the focused conversation.
Returning restores the map viewport and selection. An optional split view can
remain, but should not be the primary full learning experience.

### Learn

- Make the current question and conversation primary. One scroll area plus a
  stable composer. Preserve reading position when suggestions arrive.
- Collapse memory to a one-line recap and View memory. Keep every observation
  inspectable and editable through a drawer, rather than removing the feature.
- Replace five persistent level buttons with one named depth selector.
- Show one relevant suggestion inline; tuck alternatives behind More paths.
  Accepted suggestions become compact history entries, not permanent action cards.
- Reveal Sources and Learning notes on demand. Hide empty sections.
- Keep a small optional neighborhood diagram; collapse the rail at narrow widths.
- Use two contextual prompts rather than five generic chips plus multiple footer
  actions. Put New conversation and session management in a clear menu.
- Preserve the learner's question when taking a detour, including a visible return
  action. A durable question/goal spanning sessions is a later data-model feature.
- Make optional teaching visuals possible later. The vector drawing in the mockup
  illustrates that opportunity; it is not implemented by the current text renderer.

### Explore

- Group connected topics into readable regions with stable positions. Start from
  existing domain metadata and relationships; let the learner inspect/correct
  groupings. Do not generate claims or links merely to make the map attractive.
- Use zoom-dependent detail: topic regions at overview, named concepts closer in,
  edge types and explanations on selection. Keep the active route's labels visible.
- Highlight a relevant path and distinguish prerequisite, part-of and related
  edges with consistent direction and line treatment. A proposed learning route
  should be labelled as a proposal, not an objective curriculum.
- Use restrained size differences and glow. Default to a settled, stable map;
  make ambient motion optional and respect reduced-motion preferences.
- Fit small graphs comfortably in the available canvas; never enlarge a few nodes
  to fill the screen. Offer Fit and neighborhood focus controls.
- Give selection a concise preview with one main action, Continue learning.
- Keep status colors, but add text/shape indicators and distinguish a user's
  self-assessment from evidence of understanding.
- A compact Resume strip is useful; avoid turning the map into a dashboard.

## Proposed sequence before phase 2

1. Simplify Learn hierarchy and collapse secondary information using existing data.
2. Improve graph framing, label visibility, stable layout and selection preview.
3. Prototype grouping and highlighted paths with a real source; review before
   investing in advanced clustering or adding learning-goal infrastructure.

Evaluate by asking the learner to resume a question, understand why two concepts
connect, explore a prerequisite and return, find a citation and correct memory.
Also check keyboard access, text contrast, long conversations and small viewports.

## Mockups

- [Learn concept](learn-concept.png)
- [Explore concept](explore-concept.png)
- [Generation prompts and method](prompts.md)

These images illustrate hierarchy and composition. Their example graph is not an
export from Neo4j, and the diagrams/labels should not be treated as authoritative
technical or pedagogical content. No application code or database was changed.
