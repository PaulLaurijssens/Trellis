// Pure helpers for the Memory tab: per-learner status, filters, sort and the one-line row summary.

// Concept.status is shared by everyone on the install; this learner's own status follows their
// learning intent and self-assessment (the same rule the API uses when they change it).
export function personStatus(c) {
  if (c?.self_assessment?.value === "understood") return "learned";
  return { interested: "suggested", queued: "queued", learning: "learning" }[c?.intent] || c?.concept_status || "suggested";
}

export const demonstrated = (c) => (c?.evidence || []).filter((e) => e.outcome === "demonstrated").length;

// Active difficulties and misconceptions. Older states without observations fall back to the lists.
export function openItems(c) {
  if (Array.isArray(c?.observations)) return c.observations.filter((o) => o.kind !== "covered" && o.state === "active");
  return ["struggles", "misconceptions"].flatMap((kind) => (c?.[kind] || []).map((text) => ({ id: kind + ":" + text, kind, text, state: "active", fallback: true })));
}

export const lastActivity = (c) => c?.last_session || c?.since || null;

export const FILTERS = {
  all: () => true,
  learning: (c) => personStatus(c) === "learning",
  learned: (c) => personStatus(c) === "learned",
  attention: (c) => openItems(c).length > 0,
  planned: (c) => ["queued", "suggested"].includes(personStatus(c)),
};

export const SORTS = {
  recent: (a, b) => String(lastActivity(b) || "").localeCompare(String(lastActivity(a) || "")) || a.concept.localeCompare(b.concept),
  name: (a, b) => a.concept.localeCompare(b.concept, undefined, { sensitivity: "base" }),
  evidence: (a, b) => demonstrated(b) - demonstrated(a) || SORTS.recent(a, b),
};

export const fold = (s) => String(s || "").normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

function matches(c, query) {
  const q = fold(query).trim();
  if (!q) return true;
  return [c.concept, c.summary, ...(c.covered || [])].some((text) => fold(text).includes(q));
}

export function visible(concepts, { query = "", filter = "all", sort = "recent" } = {}) {
  return (concepts || []).filter((c) => (FILTERS[filter] || FILTERS.all)(c) && matches(c, query)).sort(SORTS[sort] || SORTS.recent);
}

export function counts(concepts) {
  return Object.fromEntries(Object.entries(FILTERS).map(([key, test]) => [key, (concepts || []).filter(test).length]));
}

// Conversations and exercises the memory of one concept was built from.
export function provenance(c) {
  const doc = c?.memory_v2;
  if (doc && typeof doc === "object") return { conversations: Object.keys(doc.sessions || {}).length, exercises: Object.keys(doc.runs || {}).length };
  const evidence = c?.evidence || [];
  return { conversations: new Set(evidence.filter((e) => e.origin !== "exercise").map((e) => e.session_id)).size,
           exercises: evidence.filter((e) => e.origin === "exercise").length };
}

// "2 days ago", in the interface language. Null for a missing or unreadable date.
export function relativeDate(value, lang = "en", now = Date.now()) {
  const time = value ? new Date(value).getTime() : NaN;
  if (!Number.isFinite(time)) return null;
  const days = Math.round((time - now) / 86400000);
  const format = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  if (Math.abs(days) < 7) return format.format(days, "day");
  if (Math.abs(days) < 60) return format.format(Math.round(days / 7), "week");
  if (Math.abs(days) < 730) return format.format(Math.round(days / 30), "month");
  return format.format(Math.round(days / 365), "year");
}
