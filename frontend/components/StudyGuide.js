"use client";
// The Study pane: one complete chapter per concept and depth, written once and stored. This is the
// reading part of the course; the lesson practises it and the mentor answers questions about it.
import { useEffect, useState } from "react";
import { useT } from "../lib/i18n";
import { api } from "../lib/api";
import { render as renderMarkdown } from "./Chat";

export default function StudyGuide({ conceptId, level, onLesson, onAsk }) {
  const { t } = useT();
  const [guide, setGuide] = useState(null);
  const [status, setStatus] = useState("loading");        // loading | writing | ready | error
  const [error, setError] = useState("");

  const write = async (rewrite) => {
    setStatus("writing"); setError("");
    try { setGuide(await api.writeGuide(conceptId, level, rewrite)); setStatus("ready"); }
    catch (e) { setError(e.message || "error"); setStatus("error"); }
  };
  useEffect(() => {
    let alive = true;
    setGuide(null); setStatus("loading"); setError("");
    api.guide(conceptId, level)
      .then((g) => { if (alive) { setGuide(g); setStatus("ready"); } })
      .catch((e) => { if (!alive) return; if (e.status === 404) write(false); else { setError(e.message || "error"); setStatus("error"); } });
    return () => { alive = false; };
  }, [conceptId, level]); // eslint-disable-line react-hooks/exhaustive-deps

  return <section className="study-guide" aria-label={t("study.title")}>
    {status === "loading" && <p className="teach-hint"><span className="spinner" /> {t("study.loading")}</p>}
    {status === "writing" && <div className="study-writing"><span className="spinner" /><div><strong>{t("study.writing")}</strong><p className="teach-hint">{t("study.writingHint")}</p></div></div>}
    {status === "error" && <p className="teach-failed" role="alert">{error} <button className="textlink" onClick={() => write(false)}>{t("teach.retry")}</button></p>}
    {status === "ready" && guide && <>
      <div className="study-body">{renderMarkdown(guide.markdown)}</div>
      {guide.sources?.length > 0 && <p className="teach-hint">{t("panel.sources")}: {guide.sources.map((s) => s.title).join(" · ")}</p>}
      <div className="study-next">
        <button className="btn primary" onClick={onLesson}>{t("study.practice")} →</button>
        <button className="btn ghost" onClick={onAsk}>{t("study.ask")}</button>
        <button className="textlink" onClick={() => write(true)}>{t("study.rewrite")}</button>
      </div>
    </>}
  </section>;
}
