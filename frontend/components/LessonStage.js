"use client";
// The running lesson: a generated page in a sandboxed frame (opaque origin, no network, no storage).
// The frame stays mounted while the learner talks to the mentor, so an answer never resets the activity.
import { useEffect, useRef, useState } from "react";
import { useT } from "../lib/i18n";
import { attachLesson, teach } from "../lib/teach";
import { momentLink } from "../lib/time";

export default function LessonStage({ lessonId, versionId, minutes, onAsk, onActivity, onReference, onOpenLesson, onClose }) {
  const { t } = useT();
  const frameRef = useRef(null);
  const [version, setVersion] = useState(null);
  const [run, setRun] = useState(null);
  const [status, setStatus] = useState("loading");           // loading | running | completed | stopped | error
  const [synced, setSynced] = useState(true);
  const [online, setOnline] = useState(true);
  const [stopReason, setStopReason] = useState("");
  const handlers = useRef({});
  handlers.current = { onAsk, onActivity, onReference, onOpenLesson };

  useEffect(() => {
    let alive = true;
    setStatus("loading"); setVersion(null); setRun(null);
    Promise.all([teach.version(lessonId, versionId), teach.createRun(versionId, minutes)])
      .then(([v, r]) => { if (alive) { setVersion(v); setRun(r); setStatus("running"); handlers.current.onActivity?.({ run: r, activity_id: r.current_activity, params: (r.state || {})[r.current_activity] || {} }); } })
      .catch(() => alive && setStatus("error"));
    return () => { alive = false; };
  }, [lessonId, versionId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const update = () => setOnline(navigator.onLine !== false);
    update(); window.addEventListener("online", update); window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, []);

  useEffect(() => {
    if (!run || !version || !frameRef.current || status !== "running") return;
    const sources = new Map((version.sources || []).map((s) => [s.id, s]));
    return attachLesson(frameRef.current, teach.artifactUrl(lessonId, versionId), {
      run, manifest: version.manifest, onSync: setSynced,
      onAsk: (ctx) => handlers.current.onAsk?.({ run, ...ctx }),
      onActivity: (ctx) => handlers.current.onActivity?.({ run, ...ctx }),
      // Source navigation is brokered here: the frame cannot open anything itself.
      onOpenSource: ({ source_id, start_sec }) => { const s = sources.get(source_id); const href = s?.url && (momentLink(s.url, start_sec) || s.url); if (href) window.open(href, "_blank", "noopener,noreferrer"); },
      onOpenLink: ({ kind, id }) => (kind === "reference" ? handlers.current.onReference?.(id) : handlers.current.onOpenLesson?.(id)),
      onCompleted: () => setStatus("completed"),
      onHostile: (reason) => { console.warn("Trellis lesson stopped:", reason); setStopReason(reason || ""); setStatus("stopped"); teach.run(run.id).then((r) => teach.checkpoint(run.id, { expected_revision: r.state_revision, status: "needs_attention" })).catch(() => {}); },
    });
  }, [run, version, status === "running"]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div className="teach-stage">
    <div className="teach-stage-bar">
      <b>{version?.manifest?.title || t("teach.title")}</b>
      {(!online || !synced) && <span className="teach-offline" role="status">{online ? t("teach.notSaved") : t("teach.offline")}</span>}
      <button className="textlink" onClick={onClose}>{t("teach.pause")}</button>
    </div>
    {status === "loading" && <p className="teach-hint"><span className="spinner" /> {t("teach.loading")}</p>}
    {status === "error" && <p className="teach-failed" role="alert">{t("teach.loadFailed")}</p>}
    {status === "stopped" && <p className="teach-failed" role="alert">{t("teach.stopped")}{stopReason && <><br /><small>({stopReason})</small></>}</p>}
    {status === "completed" && <div className="teach-ready"><p>{t("teach.completed")}</p><button className="btn primary" onClick={onClose}>{t("teach.backToTopic")}</button></div>}
    {/* sandbox WITHOUT allow-same-origin: opaque origin. No forms, popups, top navigation, downloads or microphone. */}
    {(status === "running" || status === "completed") && <iframe ref={frameRef} className="teach-frame" hidden={status === "completed"} title={version?.manifest?.title || "lesson"}
      sandbox="allow-scripts" referrerPolicy="no-referrer" allow="" />}
  </div>;
}
