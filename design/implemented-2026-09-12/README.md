# Learn / Explore redesign — 12 September 2026

**Later correction:** the boxed graph and halo-only motion below have been
superseded by the [restored living graph](../graph-restored-2026-09-12/README.md)
after hands-on user feedback.

Status: implemented locally. Production build, 22 isolated backend tests, nine
frontend tests, and the browser fixture flow pass. Live Neo4j persistence and
real model answers still need a practical check. No database reset was performed.

## Implemented

- Separate Explore and Learn modes using the existing Next.js/FastAPI/Neo4j app,
  shared selection and existing conversation trail. Switching modes preserves
  the map viewport. Selecting a map node opens a concise preview first.
- Focused Learn workspace: current question, named depth selector, collapsed
  memory, one conversation scroll area, fixed composer, and optional context
  rail. Sources, notes and concept actions are secondary disclosures. One pending
  suggestion appears first; additional suggestions and accepted paths are collapsed.
- Teaching illustrations in explanations and chat: flow relationships,
  comparisons, illustrative 2D vectors and bar charts. The model chooses when a
  supported visual helps; the learner can explicitly request one. Validated
  declarative data is rendered by React/SVG and stored as JSON on ChatMessage.
  Follow-up prompts and memory consolidation retain the visual context. Existing
  messages remain compatible; they do not gain illustrations retroactively.
- Stable topic regions using existing domain metadata. Unclassified concepts use
  adjacent domains or connected neighborhoods named after an actual hub. The
  layout creates no new semantic categories or graph relationships.
- Zoom detail with short explanations: topic overview, named concepts, then
  relationship labels and inspectable reasons. Search, topic selection, browse,
  Fit, zoom buttons, wheel zoom and keyboard panning remain available.
- Highlighted learning order follows all recorded PREREQUISITE_OF dependencies.
  Independent branches are identified as such in the explanatory text. Cycles
  show a warning instead of a fabricated order. PART_OF and RELATED_TO have
  distinct treatment and never count as prerequisites, including in the mini-tree.
- Optional ambient halo animation, saved through the profile as
  Person.ambient_motion, with local fallback and operating-system reduced-motion
  support. Node positions remain still. Animation stops while Learn hides the map.
- Existing brand palette and fonts preserved. Responsive layout and NL/EN labels.
  Status text says “Marked understood” to distinguish self-assessment from proof.

## Validation

The browser check intercepts all backend requests; it does not use Neo4j or an
LLM. It covers rendering illustrations, progressive suggestions, failed save and
retry, proposal acceptance, detours, reload/return, map viewport preservation,
prerequisite routing, all zoom levels, motion preference updates, reduced motion,
Dutch controls, mobile context toggling, horizontal overflow and empty maps.
No browser runtime errors occurred. Screenshots were visually inspected.

- [Learn screenshot](redesign-learn.png)
- [Explore screenshot](redesign-explore.png)
- [Mobile screenshot](redesign-mobile.png)

These are screenshots of the implemented app using explicitly simulated content.
They are not a record of the learner's data. The approved earlier mockups remain
in [the design review](../ux-review-2026-09-11/README.md).

## Next practical check, before phase 2

1. Restart the local app with the updated frontend and backend. Existing data is
   compatible; no schema migration or destructive reset is needed for this UI.
2. Use one real source and follow a prerequisite detour back to the original
   question. Check grouping and relationship reasons against the source.
3. Ask for a visual, ask a follow-up about it, and reload. Check that the image
   content and saved motion preference survive a backend restart.
4. Review actual graph density and route quality before a large content import.

A topological ordering is only as pedagogically sound as the stored prerequisite
links. It is not a newly validated curriculum. Group correction controls,
advanced clustering, large-graph performance validation, generated raster images,
free-form scientific diagrams and cross-session question/goal tracking are not
part of this increment. The four teaching visual types cover supported cases;
unsupported visuals should be explained in prose. Phase 2's evidence-based
understanding and memory lifecycle are still pending.
