import { getPerson, handleUnauthorized } from "./session";
import { httpError, networkError } from "./errors";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// The logged-in person (from the session cookie). Routes keep the person in their path; the API
// refuses any id that is not the session's, so this is a label, not a credential.
const me = () => getPerson() || "-";

async function req(path, opts = {}) {
  let res;
  try {
    res = await fetch(BASE + path, { credentials: "include", ...opts });
  } catch {
    throw networkError(BASE);
  }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch {}
    const err = httpError(res.status, data);
    handleUnauthorized(err);
    throw err;
  }
  return res.json();
}

// A file download (the memory export): same error handling as req, but the body is a Blob.
async function download(path) {
  let res;
  try {
    res = await fetch(BASE + path, { credentials: "include" });
  } catch {
    throw networkError(BASE);
  }
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch {}
    const err = httpError(res.status, data);
    handleUnauthorized(err);
    throw err;
  }
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "")?.[1] || "trellis-memory.zip";
  return { blob: await res.blob(), name };
}

// The address another AI connects to: the API base plus /mcp, made absolute for the browser's host.
export function mcpUrl() {
  const base = /^https?:/.test(BASE) ? BASE : (typeof window === "undefined" ? "" : window.location.origin) + BASE;
  return base.replace(/\/$/, "") + "/mcp";
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
  exportMemory: () => download("/memory/" + me() + "/export"),
  // Raw file as the body (zip or JSON); preview changes nothing, apply merges.
  importMemory: (file, mode) => req("/memory/" + me() + "/import?mode=" + mode, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: file }),
  connections: () => req("/memory/" + me() + "/connections"),
  createConnection: (name, scopes) => req("/memory/" + me() + "/connections", json({ name, scopes })),
  revokeConnection: (id) => req("/memory/" + me() + "/connections/" + encodeURIComponent(id), { method: "DELETE" }),
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
  guide: (conceptId, level) => req("/concepts/" + conceptId + "/guide?level=" + level),
  writeGuide: (conceptId, level, rewrite) => req("/concepts/" + conceptId + "/guide", json({ level, rewrite: !!rewrite })),
  analyzeFile: (file, title, jobId) => { const fd = new FormData(); fd.append("file", file); fd.append("title", title || ""); if (jobId) fd.append("job_id", jobId); return req("/ingest/file", { method: "POST", body: fd }); },
  analyzeUrl: (url, jobId) => req("/ingest/url", json({ url, job_id: jobId })),
  podcastEpisodes: (feed_url) => req("/ingest/podcast/episodes", json({ feed_url })),
  analyzePodcast: (episode, jobId) => req("/ingest/podcast", json({ ...episode, job_id: jobId })),
  analyzeYoutube: (url, jobId, language) => req("/ingest/youtube", json({ url, job_id: jobId, ui_language: language, languages: language === "en" ? ["en"] : [language, "en"] })),
  ingestStatus: (jobId) => req("/ingest/status/" + encodeURIComponent(jobId)),
  ingestTopic: (topic, depth) => req("/ingest/topic", json({ topic, depth })),
  commitCandidates: (body) => req("/candidates/commit", json(body)),
};
