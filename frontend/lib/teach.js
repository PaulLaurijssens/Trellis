// Interactive lessons (/teach integration): API client + the HOST side of the lesson event bridge.
//
// The lesson runs in <iframe sandbox="allow-scripts"> with an opaque origin. Everything it sends is
// untrusted: this file checks the sender, the schema, the size, the rate, the run and the activity
// before anything reaches the server, and the server checks again. The frame can ask; it cannot write.
import { getPerson, handleUnauthorized } from "./session";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const me = () => getPerson() || "-";

async function req(path, opts = {}) {
  const res = await fetch(BASE + "/teach/" + me() + path, { credentials: "include", ...opts });
  if (!res.ok) {
    let detail = "HTTP " + res.status;
    try { const j = await res.json(); if (j.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch {}
    const err = new Error(detail); err.status = res.status; handleUnauthorized(err); throw err;
  }
  return res.json();
}
const body = (data, method = "POST") => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });

export const teach = {
  flags: () => fetch(BASE + "/teach/flags/" + me(), { credentials: "include" }).then((r) => (r.ok ? r.json() : { enabled: false })).catch(() => ({ enabled: false })),
  context: (conceptId, groupIds) => req("/concepts/" + conceptId + "/context", body({ group_ids: groupIds || [] })),
  createTopic: (data) => req("/topics", body(data)),
  objective: (topicId) => req("/topics/" + topicId + "/objective"),
  previewObjective: (topicId, answers) => req("/topics/" + topicId + "/objective/preview", body(answers)),
  saveObjective: (topicId, data) => req("/topics/" + topicId + "/objective", body(data, "PUT")),
  dismissProposal: (topicId) => req("/topics/" + topicId + "/objective/proposal", { method: "DELETE" }),
  createJob: (data) => req("/lesson-jobs", body(data)),
  usageSummary: (days = 30) => req("/lesson-jobs/summary?days=" + days),
  job: (id) => req("/lesson-jobs/" + id),
  cancelJob: (id) => req("/lesson-jobs/" + id + "/cancel", { method: "POST" }),
  version: (lessonId, versionId) => req("/lessons/" + lessonId + "/versions/" + versionId),
  artifactUrl: (lessonId, versionId) => BASE + "/teach/" + me() + "/lessons/" + lessonId + "/versions/" + versionId + "/artifact",
  createRun: (versionId, minutes) => req("/runs", body({ lesson_version_id: versionId, time_budget_min: minutes || null })),
  run: (id) => req("/runs/" + id),
  checkpoint: (id, data) => req("/runs/" + id, body(data, "PATCH")),
  attempt: (id, data) => req("/runs/" + id + "/attempts", body(data)),
  ask: (id, data) => req("/runs/" + id + "/questions", body(data)),
  reference: (id) => req("/references/" + id),
  recommendation: (id, state) => req("/recommendations/" + id, body({ state })),
};

const FRAME_TYPES = ["activity.state_changed", "activity.answer_submitted", "activity.hint_requested",
  "mentor.question_requested", "source.open_requested", "link.open_requested", "lesson.resize"];
const MAX_BYTES = 16 * 1024;

function wellFormed(msg, activityIds) {
  if (!msg || typeof msg !== "object" || msg.v !== 1 || !FRAME_TYPES.includes(msg.type)) return false;
  if (typeof msg.seq !== "number" || (msg.activity_id !== null && !activityIds.includes(msg.activity_id))) return false;
  if (msg.payload === null || typeof msg.payload !== "object" || Array.isArray(msg.payload)) return false;
  try { return JSON.stringify(msg).length <= MAX_BYTES; } catch { return false; }
}

// attachLesson(iframe, url, {run, manifest, ...callbacks}) -> detach(). The listeners are registered
// BEFORE the frame gets its src, so the lesson's single "lesson.ready" can never be missed.
// callbacks: onAsk({activity_id, params}), onOpenSource({source_id,start_sec}), onOpenLink({kind,id}),
//            onActivity({activity_id, params, step}), onCompleted(), onHostile(reason), onSync(ok)
export function attachLesson(iframe, url, { run, manifest, onAsk, onOpenSource, onOpenLink, onActivity, onCompleted, onHostile, onSync }) {
  const activityIds = manifest.activities.map((a) => a.id);
  const sourceIds = (manifest.sources || []).map((s) => s.source_id);
  let port = null, ready = false, lastSeq = 0, dropped = 0, alive = true;
  let revision = run.state_revision, saving = false, queued = null, windowStart = 0, inWindow = 0;
  // The newest state the lesson reported, so a re-handshake after a reload resumes exactly there.
  const latest = { state: { ...(run.state || {}) }, step: run.step || 0, current_activity: run.current_activity || null };
  let reannounce = null;              // after a late or repeated load: accept one new handshake for a while

  const drop = () => { dropped += 1; if (dropped > 50) hostile("too many malformed messages"); };
  const hostile = (reason) => { if (!alive) return; detach(); onHostile && onHostile(reason); };

  // One checkpoint at a time; the newest state wins. A 409 means another tab saved first: take its
  // revision and try again, so "close and reopen" always finds the last thing the learner did.
  let inflight = Promise.resolve();
  async function push(force) {
    while (queued && (alive || force)) {
      const next = queued; queued = null;
      try {
        const saved = await teach.checkpoint(run.id, { ...next, expected_revision: revision });
        revision = saved.state_revision; onSync && onSync(true);
      } catch (e) {
        queued = { ...next, ...(queued || {}) };
        if (e.status !== 409) { onSync && onSync(false); return; }
        try { revision = (await teach.run(run.id)).state_revision; } catch { onSync && onSync(false); return; }
      }
    }
  }
  function flush(force) {
    if (saving) return inflight;
    saving = true;
    inflight = push(force).finally(() => { saving = false; if (queued && alive) setTimeout(flush, navigator.onLine === false ? 5000 : 1500); });
    return inflight;
  }
  const save = (data) => { queued = { ...(queued || {}), ...data }; flush(); };
  const online = () => flush();
  const hidden = () => { if (document.visibilityState === "hidden") flush(); };

  async function onPortMessage(event) {
    const msg = event.data, now = Date.now();
    if (now - windowStart > 1000) { windowStart = now; inWindow = 0; }
    if (++inWindow > 10) return drop();                                   // rate limit: 10 messages / second
    if (!wellFormed(msg, activityIds) || msg.seq <= lastSeq) return drop();
    lastSeq = msg.seq;
    const p = msg.payload;
    if (msg.type === "activity.state_changed") {
      const step = Number.isInteger(p.step) && p.step >= 0 && p.step < 64 ? p.step : undefined;
      if (msg.activity_id) { latest.state[msg.activity_id] = p.params || {}; latest.current_activity = msg.activity_id; if (step !== undefined) latest.step = step; save({ activity_id: msg.activity_id, params: p.params || {}, step }); onActivity && onActivity({ activity_id: msg.activity_id, params: p.params || {}, step }); }
      else if (step !== undefined) { latest.step = step; save({ step }); onActivity && onActivity({ activity_id: null, params: {}, step }); }
      if (p.completed === true) { save({ status: "completed" }); onCompleted && onCompleted(); }
    } else if (msg.type === "activity.answer_submitted" && msg.activity_id && typeof p.client_op_id === "string") {
      let feedback;
      try { feedback = await teach.attempt(run.id, { activity_id: msg.activity_id, response: p.response ?? null, params: p.params || {}, hint_usage: p.hint_usage || {}, client_op_id: p.client_op_id.slice(0, 80) }); onSync && onSync(true); }
      catch { feedback = { outcome: "offline", message: "" }; onSync && onSync(false); }
      if (port) port.postMessage({ v: 1, type: "host.feedback", activity_id: msg.activity_id, client_op_id: p.client_op_id, payload: { outcome: feedback.outcome, message: feedback.message || "", assessed_by: feedback.assessed_by || null, uncertainty: feedback.uncertainty || null } });
    } else if (msg.type === "mentor.question_requested") {
      onAsk && onAsk({ activity_id: msg.activity_id, params: p.params || {} });
    } else if (msg.type === "source.open_requested") {
      if (sourceIds.includes(p.source_id)) onOpenSource && onOpenSource({ source_id: p.source_id, start_sec: typeof p.start_sec === "number" ? p.start_sec : null }); else drop();
    } else if (msg.type === "link.open_requested") {
      if ((p.kind === "lesson" || p.kind === "reference") && typeof p.id === "string" && /^[0-9a-f-]{36}$/.test(p.id)) onOpenLink && onOpenLink({ kind: p.kind, id: p.id }); else drop();
    }
  }

  function onWindowMessage(event) {
    if (event.source !== iframe.contentWindow || (ready && !reannounce)) return;   // origin is "null" for a sandboxed frame: never trust it alone
    const msg = event.data;
    if (!msg || msg.v !== 1 || msg.type !== "lesson.ready" || !Array.isArray(msg.activities)) return drop();
    if ([...msg.activities].sort().join("|") !== [...activityIds].sort().join("|")) return hostile("the lesson announced other activities than its manifest");
    if (port) { port.onmessage = null; port.close(); }                   // a re-handshake replaces the old channel
    if (reannounce) { clearTimeout(reannounce); reannounce = null; }
    ready = true; lastSeq = 0;
    const channel = new MessageChannel();
    port = channel.port1; port.onmessage = onPortMessage;
    iframe.contentWindow.postMessage({ v: 1, type: "host.init", payload: { run_id: run.id, channel: run.channel, locale: manifest.language,
      reduced_motion: window.matchMedia("(prefers-reduced-motion: reduce)").matches, state: latest.state, step: latest.step, current_activity: latest.current_activity } }, "*", [channel.port2]);
  }
  // The frame's `load` event is NOT proof of navigation: the lesson announces itself as soon as its
  // script runs, and Chrome fires `load` only after every embedded font and image is in, so with a
  // slow machine or many extensions the load arrives AFTER the handshake for the very same document.
  // So a load after the handshake never stops the lesson. It only opens a window in which a fresh
  // lesson.ready (a real reload) is accepted and replaces the channel; a document that navigated
  // elsewhere has no port and cannot reach anything, which is the sandbox doing its job.
  const onLoad = () => {
    if (!ready) return;
    if (reannounce) clearTimeout(reannounce);
    reannounce = setTimeout(() => { reannounce = null; }, 5000);
  };

  function detach() {
    if (!alive) return;
    alive = false;
    inflight.then(() => flush(true));                // pausing: the last change still reaches the server
    window.removeEventListener("message", onWindowMessage); window.removeEventListener("online", online);
    document.removeEventListener("visibilitychange", hidden);
    iframe.removeEventListener("load", onLoad);
    if (reannounce) { clearTimeout(reannounce); reannounce = null; }
    if (port) { port.onmessage = null; port.close(); port = null; }
  }
  window.addEventListener("message", onWindowMessage); window.addEventListener("online", online);
  document.addEventListener("visibilitychange", hidden);
  iframe.addEventListener("load", onLoad);
  iframe.src = url;
  return detach;
}
