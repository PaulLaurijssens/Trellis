# Clear learning entry points — 12 September 2026

Selecting a cluster now shows a Start learning card with the starting topic and
its reason. It follows recorded prerequisites toward the named cluster topic,
skipping concepts marked understood. If that path is already understood, it
chooses another unmarked topic in the cluster and follows its prerequisites.
If everything is marked understood, the action offers a review. Cycles are
flagged rather than presented as a valid learning sequence. This uses graph
relationships, not the visual layout's distance tiers.

The cluster CTA requests an explanation and opens Learn once it is ready.
Individual nodes open Learn directly, restoring any conversation. An empty
conversation now has a large introduction card and Start lesson button; learners
can also type a question. The start button uses the selected depth. Loading,
errors and retry continue through the existing explanation flow.

Validation: 12 frontend tests and production build passed. The browser check
uses the real graph snapshot with intercepted model/API responses and verifies
that the recommended topic is actually started, outside-node navigation opens
Learn directly, and Start lesson displays the returned explanation. Existing
deselection, motion, keyboard and mobile checks also pass. No live model calls
or database writes were made by these checks.

- [Cluster start card](cluster-start.png)
- [Lesson start card](lesson-start.png)
