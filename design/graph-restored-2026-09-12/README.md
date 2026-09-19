# Graph correction after hands-on feedback — 12 September 2026

The earlier boxed atlas is replaced by a force-directed knowledge graph. Actual
connections determine the layout and cluster outlines. Domain strings no longer
split related concepts into separate boxes. Standalone concepts remain nodes.
Cluster names come from an existing highly connected concept; the grouping is a
visual neighborhood, not a new taxonomy or learning order.

Nodes drift gently and move slightly toward a nearby cursor, with bounded motion
that preserves the shape of the network. The profile toggle freezes positions;
reduced-motion settings, a hidden Learn view, and background tabs stop animation.

The whole network remains visible at overview. Main topic names are shown first;
zoom progressively reveals names at the next graph-distance tier while smaller
nodes remain unlabelled. Ancestor labels remain available, with collision handling
to avoid text piles. Hover, keyboard focus and search reveal individual names.
The visual tiers do not change the prerequisite-only learning route.

Validation uses a read-only snapshot of the actual 93-node, 68-edge graph as well
as the existing learning-flow fixtures. No database mutation or model request is
made by these browser tests. Motion, frozen positions, reduced motion, zoom,
next-tier dots without next-tier names, keyboard cluster focus and responsive
layout are checked. Eleven frontend tests and the production build pass.

- `frontend/tests/graph-review.mjs`: optionally set `MENTOR_GRAPH_FIXTURE` to a
  saved `/graph` response; otherwise uses synthetic data. All API calls intercepted.
- `frontend/tests/mentor-flow.mjs`: existing end-to-end learning-flow fixture.

This correction supersedes the stable boxed layout and halo-only motion described
in the earlier implementation report. Learn and teaching illustrations are retained.

Testing URL: http://localhost:3000

## Screenshots with the real graph snapshot

- [Overview](living-graph-overview.png)
- [Zoomed neighborhood](living-graph-zoom.png)
- [Mobile](living-graph-mobile.png)
