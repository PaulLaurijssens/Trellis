// The mini knowledge tree is derived from /graph: that call already returns every node
// with its status and every relation with its type, so no extra endpoint is needed.
// force-graph replaces link.source/target with node objects; hence idOf().
const idOf = (x) => (x && typeof x === "object" ? x.id : x);

export function buildIndex(graph) {
  const byId = new Map(), byName = new Map();
  for (const n of graph.nodes || []) { byId.set(n.id, n); byName.set(norm(n.name), n); }
  const pre = new Map(), dep = new Map(), rel = new Map(), parts = new Map(), wholes = new Map();
  const push = (m, k, v) => { if (!m.has(k)) m.set(k, []); if (!m.get(k).includes(v)) m.get(k).push(v); };
  for (const l of graph.links || []) {
    const s = idOf(l.source), t = idOf(l.target);
    if (!byId.has(s) || !byId.has(t)) continue;
    if (l.type === "PREREQUISITE_OF") { push(pre, t, s); push(dep, s, t); }
    else if (l.type === "PART_OF") { push(wholes, s, t); push(parts, t, s); }
    else { push(rel, s, t); push(rel, t, s); }
  }
  return { byId, byName, pre, dep, rel, parts, wholes };
}

const norm = (s) => String(s || "").toLowerCase().trim();

export function findNode(index, name) {
  return index.byName.get(norm(name)) || null;
}

const sortNodes = (a, b) => (b.degree || 0) - (a.degree || 0) || a.name.localeCompare(b.name);
const nodesOf = (index, map, id, max = 8) =>
  (map.get(id) || []).map((i) => index.byId.get(i)).filter(Boolean).sort(sortNodes).slice(0, max);

// Subtree around a node: prerequisites (down), what it leads to (up) and loose
// relatives. `depth` = how deep the prerequisites go.
export function subtree(index, node, depth = 1) {
  if (!node) return null;
  const seen = new Set([node.id]);
  const down = (n, d) => {
    if (d === 0) return [];
    return nodesOf(index, index.pre, n.id).filter((c) => !seen.has(c.id)).map((c) => {
      seen.add(c.id);
      return { node: c, kids: down(c, d - 1) };
    });
  };
  const prereqs = down(node, depth);
  const up = (n, d) => {
    if (d === 0) return [];
    return nodesOf(index, index.dep, n.id, 4).filter((c) => !seen.has(c.id)).map((c) => {
      seen.add(c.id);
      return { node: c, parents: up(c, d - 1) };
    });
  };
  const dependents = up(node, depth);
  const related = nodesOf(index, index.rel, node.id).filter((c) => !seen.has(c.id));
  return { node, prereqs, dependents, related, parts: nodesOf(index, index.parts, node.id), wholes: nodesOf(index, index.wholes, node.id) };
}
