// Zoeken in de kaart: exacte en gedeeltelijke naam-matches.
export const norm = (s) => String(s || "").toLowerCase().trim().replace(/\s+/g, " ");

export function matchNodes(nodes, query) {
  const q = norm(query);
  if (!q) return { exact: null, partial: [] };
  const exact = nodes.find((n) => norm(n.name) === q) || null;
  const partial = nodes
    .filter((n) => n !== exact && norm(n.name).includes(q))
    .sort((a, b) => (b.degree || 0) - (a.degree || 0))
    .slice(0, 6);
  return { exact, partial };
}
