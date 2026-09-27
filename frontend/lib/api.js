import { getPerson, handleUnauthorized } from "./session";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// The logged-in person (from the session cookie). Routes keep the person in their path; the API
// refuses any id that is not the session's, so this is a label, not a credential.
const me = () => getPerson() || "-";

async function req(path, opts = {}) {
  let res;
  try {
    res = await fetch(BASE + path, { credentials: "include", ...opts });
  } catch {
    throw new Error("Geen verbinding met de backend. Draait die op " + BASE + "?");
  }
  if (!res.ok) {
    let detail = "Er ging iets mis (HTTP " + res.status + ")";
    try {
      const j = await res.json();
      if (j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {}
    const err = new Error(detail);
    err.status = res.status;
    handleUnauthorized(err);
    throw err;
  }
  return res.json();
}

const json = (body) => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  journey: () => req("/journey/" + me()),
  createGoal: body => req("/journey/" + me() + "/goals", json(body)),
  updateGoal: (id, body) => req("/journey/" + me() + "/goals/" + id, {...json(body), method:"PATCH"}),
  examples: () => req("/journey/" + me() + "/examples"),
  saveExample: (session_id, seq) => req("/journey/" + me() + "/examples", json({session_id,seq})),
  editExample: (id,text) => req("/journey/" + me() + "/examples/"+id, {...json({text}),method:"PATCH"}),
  deleteExample: id => req("/journey/" + me() + "/examples/"+id, {method:"DELETE"}),
  levels: () => req("/levels"),
  graph: () => req("/graph"),
  concept: (name) => req("/concept/" + encodeURIComponent(name)),
  learn: (body) => req("/learn", json(body)),
  markLearned: (name) =>
    req("/concept/" + encodeURIComponent(name) + "/learned", { method: "POST" }),
  chatHistory: (concept) => req("/chat/" + encodeURIComponent(concept)),
  chat: (body) => req("/chat", json(body)),
  newChat: (concept, level) =>
    req("/chat/" + encodeURIComponent(concept) + "/new" + (level ? "?level=" + level : ""), { method: "POST" }),
  endChat: (concept) => req("/chat/" + encodeURIComponent(concept) + "/end", { method: "POST" }),
  acceptSuggestion: (id, action) => req("/suggestions/" + encodeURIComponent(id) + "/accept", json({ action })),
  dismissSuggestion: (id) => req("/suggestions/" + encodeURIComponent(id) + "/dismiss", json({})),
  memory: () => req("/memory/" + me()),
  patchProfile: (body) => req("/memory/" + me() + "/profile", { ...json(body), method: "PATCH" }),
  patchConceptMemory: (name, body) => req("/memory/" + me() + "/concept/" + encodeURIComponent(name), { ...json(body), method: "PATCH" }),
  correctObservation: (name, id, state) => req("/memory/" + me() + "/concept/" + encodeURIComponent(name) + "/observations/" + id, { ...json({ state }), method: "PATCH" }),
  setLearningPosition: (name, body) => req("/memory/" + me() + "/concept/" + encodeURIComponent(name) + "/position", { ...json(body), method: "PATCH" }),
  rebuildMemory: () => req("/memory/rebuild/" + me(), { method: "POST" }),
  backups: () => req("/admin/backups"),
  createBackup: () => req("/admin/backups", { method: "POST" }),
  verifyBackup: (stamp) => req("/admin/backups/" + encodeURIComponent(stamp) + "/verify", { method: "POST" }),

  // Rauwe tekst als body: plakken zonder JSON-escaping.
  analyze: ({ text, title, source_type, url }, jobId) => {
    const q = new URLSearchParams({ title, source_type });
    if (url) q.set("url", url);
    if (jobId) q.set("job_id", jobId);
    return req("/ingest/raw?" + q.toString(), {
      method: "POST",
      headers: { "Content-Type": "text/plain" },
      body: text,
    });
  },
  analyzeYoutube: (url, jobId, language) => req("/ingest/youtube", json({ url, job_id: jobId, ui_language: language, languages: language === "nl" ? ["nl", "en"] : ["en", "nl"] })),
  ingestStatus: (jobId) => req("/ingest/status/" + encodeURIComponent(jobId)),
  ingestTopic: (topic, depth) => req("/ingest/topic", json({ topic, depth })),
  commitCandidates: (body) => req("/candidates/commit", json(body)),
};
