<!-- Dendrite adaptation of mattpocock/skills teach @ 3216582 (MIT). Changes: see CHANGELOG.md -->
# RESOURCES.md Format

`RESOURCES.md` is the set of trusted sources the learner has stored for this topic, exported from Dendrite's source store with the stored summary and excerpts of each. Knowledge for lessons should be drawn from here, not from parametric guesses. Dendrite omits the Wisdom (Communities) group in this release, by the owner's decision; the structure below shows it only because it is upstream's format.

## Structure

```md
# {Topic} Resources

## Knowledge

- [Book: _The Science and Practice of Strength Training_ by Zatsiorsky & Kraemer](https://example.com)
  Foundational text on programming and adaptation. Use for: anything to do with periodisation, recovery, intensity zones.
- [Article: "How Much Should I Train?" by Greg Nuckols (Stronger By Science)](https://example.com)
  Evidence-based review of volume landmarks. Use for: weekly set targets per muscle group.

## Wisdom (Communities)

- [r/weightroom](https://reddit.com/r/weightroom)
  High-signal subreddit, moderated against bro-science. Use for: programme critique, plateau troubleshooting.
- Local: Tuesday strength class at {gym name}
  Use for: real-time coaching feedback on lifts.
```

## Rules

- **High-trust only.** Prefer primary sources, recognised experts, peer-reviewed work, and communities with strong moderation. If a resource is marketing dressed as education, leave it out.
- **Annotate every entry.** A bare link is useless in three months. Add one line: what it covers and when to reach for it.
- **Group by Knowledge / Wisdom.** Mirrors the philosophy in [SKILL.md](./SKILL.md). It is fine for a resource to appear in only one group.
- **Surface gaps explicitly.** If no stored resource supports an area the mission needs, call `report_resource_gap`; it appears under `## Gaps`. When a whole topic is missing, call `recommend_topic`: the learner decides whether to add it.
- **Prune ruthlessly.** You cannot remove a stored source. Do not cite a resource that turned out to be wrong, shallow, or off-mission, and say so in a note. Better five sharp sources than thirty mediocre ones.
- **Record community preferences.** If the user has opted out of joining communities, note it here so future sessions don't keep proposing them.
