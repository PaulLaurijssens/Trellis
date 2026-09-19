// Boomstructuur van kandidaten uit een analyse, op basis van candidate_relations.
// Hoofdtopics: kandidaten die doel zijn van PART_OF/PREREQUISITE_OF en zelf geen
// ouder hebben (of: ouderloos maar wel in een relatie). Subtopics hangen via
// PART_OF/PREREQUISITE_OF (ouder) of RELATED_TO (verwant) aan een hoofdtopic.
// Kandidaten zonder enige relatie vormen de groep "Losse onderwerpen".
const norm = (s) => String(s || "").toLowerCase().trim();
export const score = (c) => (c.importance || 0) * 10 + (c.chunk_count || 0) + (c.llm_importance || 0) / 10;

export function buildReviewTree(candidates, relations) {
  const byKey = new Map();
  for (const c of candidates) {
    byKey.set(norm(c.name), c);
    for (const a of c.aliases || []) if (!byKey.has(norm(a))) byKey.set(norm(a), c);
  }
  const parentsOf = new Map();      // name -> Set(parent names)   (PART_OF / PREREQUISITE_OF)
  const childrenOf = new Map();
  const related = new Map();        // name -> Set(names)
  const add = (m, k, v) => { if (!m.has(k)) m.set(k, new Set()); m.get(k).add(v); };
  for (const r of relations || []) {
    const a = byKey.get(norm(r.from)), b = byKey.get(norm(r.to));
    if (!a || !b || a === b) continue;
    if (r.type === "RELATED_TO") { add(related, a.name, b.name); add(related, b.name, a.name); }
    else { add(parentsOf, a.name, b.name); add(childrenOf, b.name, a.name); }
  }
  const byName = new Map(candidates.map((c) => [c.name, c]));
  const sorted = (names) => [...names].map((n) => byName.get(n)).filter(Boolean).sort((x, y) => score(y) - score(x));

  // Ouder = de hoogst scorende van de structurele ouders; cycli breken we
  // door een ouder die lager scoort dan het kind zelf te negeren.
  const parent = new Map();
  for (const c of candidates) {
    const ps = sorted(parentsOf.get(c.name) || []).filter((p) => score(p) >= score(c) || !(parentsOf.get(p.name) || new Set()).has(c.name));
    if (ps.length) parent.set(c.name, ps[0].name);
  }
  // Ketens naar de wortel volgen (met cyclusbeveiliging).
  const rootOf = (name) => {
    const seen = new Set();
    let cur = name;
    while (parent.has(cur) && !seen.has(cur)) { seen.add(cur); cur = parent.get(cur); }
    return cur;
  };

  const placed = new Set();
  const mains = candidates
    .filter((c) => !parent.has(c.name) && (childrenOf.has(c.name) || (related.has(c.name) && !parent.has(c.name))))
    .sort((x, y) => score(y) - score(x));

  const buildNode = (c, depth) => {
    placed.add(c.name);
    const kids = sorted(childrenOf.get(c.name) || [])
      .filter((k) => parent.get(k.name) === c.name && !placed.has(k.name))
      .map((k) => buildNode(k, depth + 1));
    return { cand: c, kind: "child", children: kids };
  };
  const roots = mains.map((m) => ({ ...buildNode(m, 0), kind: "main" }));

  // Losse RELATED_TO-verwanten onder het hoofdtopic van hun beste buur.
  for (const c of candidates) {
    if (placed.has(c.name) || !related.has(c.name)) continue;
    const buddies = sorted(related.get(c.name)).filter((b) => placed.has(b.name));
    if (!buddies.length) continue;
    const root = roots.find((r) => r.cand.name === rootOf(buddies[0].name));
    if (!root) continue;
    root.children.push({ cand: c, kind: "related", children: [] });
    placed.add(c.name);
  }
  // Hoofdtopics die alleen verwanten hebben maar zelf niet 'main' werden: al
  // afgehandeld; wat overblijft zonder relaties is los.
  const loose = candidates.filter((c) => !placed.has(c.name)).sort((x, y) => score(y) - score(x));
  for (const r of roots) r.children.sort((x, y) => score(y.cand) - score(x.cand));
  return { roots, loose };
}

export function descendants(node) {
  const out = [];
  const walk = (n) => { for (const k of n.children) { out.push(k.cand.name); walk(k); } };
  walk(node);
  return out;
}
