const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req(path, opts = {}) {
  let res;
  try {
    res = await fetch(BASE + path, opts);
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
  journey: () => req("/journey/paul"),
  createGoal: body => req("/journey/paul/goals", json(body)),
  updateGoal: (id, body) => req("/journey/paul/goals/" + id, {...json(body), method:"PATCH"}),
  examples: () => req("/journey/paul/examples"),
  saveExample: (session_id, seq) => req("/journey/paul/examples", json({session_id,seq})),
  editExample: (id,text) => req("/journey/paul/examples/"+id, {...json({text}),method:"PATCH"}),
  deleteExample: id => req("/journey/paul/examples/"+id, {method:"DELETE"}),
  levels: () => req("/levels"),
  graph: () => req("/graph"),
  concept: (name) => req("/concept/" + encodeURIComponent(name)),
  learn: (body) => req("/learn", json(body)),
  markLearned: (name) =>
    req("/concept/" + encodeURIComponent(name) + "/learned?person_id=paul", { method: "POST" }),
  chatHistory: (concept, person = "paul") =>
    req("/chat/" + encodeURIComponent(concept) + "?person_id=" + person),
  chat: (body) => req("/chat", json(body)),
  newChat: (concept, level, person = "paul") =>
    req("/chat/" + encodeURIComponent(concept) + "/new?person_id=" + person +
        (level ? "&level=" + level : ""), { method: "POST" }),
  endChat: (concept, person = "paul") =>
    req("/chat/" + encodeURIComponent(concept) + "/end?person_id=" + person, { method: "POST" }),
  acceptSuggestion: (id, action, person = "paul") =>
    req("/suggestions/" + encodeURIComponent(id) + "/accept", json({ person_id: person, action })),
  dismissSuggestion: (id, person = "paul") =>
    req("/suggestions/" + encodeURIComponent(id) + "/dismiss", json({ person_id: person })),
  memory: (person = "paul") => req("/memory/" + person),
  patchProfile: (person, body) =>
    req("/memory/" + person + "/profile", { ...json(body), method: "PATCH" }),
  patchConceptMemory: (person, name, body) =>
    req("/memory/" + person + "/concept/" + encodeURIComponent(name),
        { ...json(body), method: "PATCH" }),
  correctObservation: (person, name, id, state) => req("/memory/"+person+"/concept/"+encodeURIComponent(name)+"/observations/"+id,{...json({state}),method:"PATCH"}),
  setLearningPosition: (person, name, body) => req("/memory/"+person+"/concept/"+encodeURIComponent(name)+"/position",{...json(body),method:"PATCH"}),
  rebuildMemory: (person = "paul") => req("/memory/rebuild/" + person, { method: "POST" }),

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
