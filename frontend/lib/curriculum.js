"use client";
// Het leerpad-plan, gedeeld door het Leerpad en de knop "Volgend onderwerp".
// Stale-while-revalidate: het laatst bekende plan staat meteen op het scherm (uit geheugen
// of localStorage), en wordt op de achtergrond bijgewerkt als de graaf veranderd is. De
// backend bewaart het plan en deelt alleen nieuwe concepten opnieuw in, dus dat bijwerken
// is meestal een fractie van een seconde in plaats van de 30+ s van een volledig plan.
import { useEffect, useMemo, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STORE = "trellis.curriculum.v1";
const idOf = (x) => (typeof x === "object" ? x.id : x);

const memory = {};        // lang -> { snapshot, plan }
const inflight = {};      // snapshot -> Promise
const listeners = new Set();

function read(lang) {
  if (memory[lang]) return memory[lang];
  try {
    const saved = JSON.parse(localStorage.getItem(STORE + "." + lang) || "null");
    if (saved?.plan?.groups) memory[lang] = saved;
  } catch {}
  return memory[lang] || null;
}

function write(lang, entry) {
  memory[lang] = entry;
  try { localStorage.setItem(STORE + "." + lang, JSON.stringify(entry)); } catch {}
  listeners.forEach((fn) => fn());
}

export function snapshotOf(graph, lang) {
  return JSON.stringify({
    nodes: graph.nodes.map(({ id, name, definition, domain }) => ({ id, name, definition, domain })),
    links: graph.links.map((e) => ({ source: idOf(e.source), target: idOf(e.target), type: e.type })),
    language: lang,
  });
}

function fetchPlan(snapshot, lang) {
  if (!inflight[snapshot]) {
    inflight[snapshot] = fetch(BASE + "/curriculum", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: snapshot })
      .then((r) => { if (!r.ok) throw Error(); return r.json(); })
      .then((plan) => { write(lang, { snapshot, plan }); return plan; })
      .finally(() => { delete inflight[snapshot]; });
  }
  return inflight[snapshot];
}

// enabled=false: niets ophalen, alleen een eventueel al bekend plan teruggeven.
export function usePlan(graph, lang, enabled = true) {
  const snapshot = useMemo(() => snapshotOf(graph, lang), [graph, lang]);
  const [, rerender] = useState(0);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const fn = () => rerender((n) => n + 1);
    listeners.add(fn);
    return () => listeners.delete(fn);
  }, []);
  const known = typeof window === "undefined" ? null : read(lang);
  const fresh = known?.snapshot === snapshot;
  useEffect(() => {
    if (!enabled || !graph.nodes.length || fresh) return;
    let alive = true;
    setError(false);
    fetchPlan(snapshot, lang).catch(() => { if (alive) setError(true); });
    return () => { alive = false; };
  }, [enabled, snapshot, lang, fresh, retry, graph.nodes.length]);
  return { plan: known?.plan || null, updating: enabled && !fresh && !error, error, retry: () => setRetry((n) => n + 1) };
}

// Plan-volgorde: fase oplopend, binnen een fase de volgorde van de groepen.
function order(plan) {
  return plan.groups
    .map((g, i) => ({ g, i }))
    .sort((a, b) => a.g.stage - b.g.stage || a.i - b.i)
    .flatMap(({ g }) => g.ids);
}

// Het eerstvolgende niet-begrepen onderwerp NA het huidige in het leerpad; staat het huidige
// er niet in, dan het eerste niet-begrepen onderwerp van het hele pad.
export function nextInPlan(plan, graph, currentName) {
  if (!plan?.groups?.length) return null;
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const ids = order(plan);
  const current = graph.nodes.find((n) => n.name === currentName);
  const from = current ? ids.indexOf(current.id) + 1 : 0;
  const pick = (start) => ids.slice(start).map((cid) => nodes.get(cid))
    .find((n) => n && n.name !== currentName && n.status !== "learned");
  return pick(from) || pick(0) || null;
}
