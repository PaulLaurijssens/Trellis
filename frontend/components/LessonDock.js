"use client";
// Entry to interactive lessons for one concept: continue a paused lesson, otherwise set the topic
// goal (2-4 pills, skippable, previewed before it is stored) and ask the teacher for a lesson.
// A failed or unavailable lesson never blocks the page: the normal chat stays right below.
import { useCallback, useEffect, useRef, useState } from "react";
import { useT } from "../lib/i18n";
import { teach } from "../lib/teach";

const INTENTS = ["understand", "apply", "build", "explore"];
const FAMILIARITY = ["new", "basics", "using"];
const APPROACHES = ["concepts", "examples", "hands_on", "mix"];
const MINUTES = [5, 10, 20];
const STAGES = ["queued", "preparing", "generating", "validating"];

function Pills({ label, options, value, onChange, render }) {
  return <fieldset className="teach-pills"><legend>{label}</legend>
    {options.map((o) => <button key={o} type="button" className="teach-pill" aria-pressed={value === o} onClick={() => onChange(value === o ? null : o)}>{render(o)}</button>)}
  </fieldset>;
}

export default function LessonDock({ conceptId, conceptName, group, lang, onOpen, onReference, onExploreTopic }) {
  const { t } = useT();
  const [ctx, setCtx] = useState(null);
  const [mode, setMode] = useState("idle");                 // idle | questions | preview
  const [answers, setAnswers] = useState({});
  const [draft, setDraft] = useState(null);
  const [minutes, setMinutes] = useState(10);
  const [note, setNote] = useState("");
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const alive = useRef(true);

  const load = useCallback(async () => {
    try {
      const c = await teach.context(conceptId, group?.ids || []);
      if (!alive.current) return;
      setCtx(c);
      if (c.defaults?.time_budget_min) setMinutes(c.defaults.time_budget_min);
      if (c.active_job && c.active_job.concept_id === conceptId) setJob((j) => j || c.active_job);
    } catch { if (alive.current) setCtx({ unavailable: true }); }
  }, [conceptId, group]);

  useEffect(() => { alive.current = true; setCtx(null); setMode("idle"); setJob(null); setDraft(null); setError(""); setNote(""); load(); return () => { alive.current = false; }; }, [conceptId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Real stages from the server; no invented percentage.
  useEffect(() => {
    if (!job || ["ready", "failed", "cancelled"].includes(job.stage)) return;
    const timer = setInterval(async () => {
      try { const next = await teach.job(job.id); if (alive.current) { setJob(next); if (next.stage === "ready") load(); } } catch {}
    }, 2500);
    return () => clearInterval(timer);
  }, [job, load]);

  if (!ctx || ctx.unavailable) return null;
  const topic = ctx.topics?.[0] || null;
  const objective = topic?.objective || null;

  const ensureTopic = async () => {
    if (topic) return topic;
    const seed = group ? { title: group.title, concept_ids: group.ids, origin: "curriculum_group", plan_key: group.planKey || null }
                       : { title: conceptName, concept_ids: [conceptId], origin: "learner" };
    return teach.createTopic({ ...seed, language: lang });
  };
  const guard = async (fn) => { setBusy(true); setError(""); try { await fn(); } catch (e) { if (alive.current) setError(e.message || "error"); } finally { if (alive.current) setBusy(false); } };

  const startQuestions = () => { setAnswers({ intent: ctx.defaults?.intent || null, approach: ctx.defaults?.approach || null }); setMode("questions"); };
  const preview = (useDefaults) => guard(async () => {
    const tp = await ensureTopic();
    const a = useDefaults ? { intent: ctx.defaults?.intent || "understand", approach: ctx.defaults?.approach || "mix" } : answers;
    const d = await teach.previewObjective(tp.id, a);
    if (!alive.current) return;
    setAnswers(a); setDraft({ ...d, topic_id: tp.id }); setMode("preview");
  });
  const confirm = () => guard(async () => {
    const { topic_id, drafted_by, ...objectiveBody } = draft;
    await teach.saveObjective(topic_id, { objective: objectiveBody, expected_revision: objective?.revision || 0, answers: { ...answers, time_budget_min: minutes } });
    if (!alive.current) return;
    setMode("idle"); setDraft(null); await load();
  });
  const makeLesson = (withObjective) => guard(async () => {
    const tp = await ensureTopic();
    const created = await teach.createJob({ topic_id: tp.id, concept_id: conceptId, objective_id: withObjective ? objective?.id : null, language: lang,
      time_budget_min: minutes, intent: answers.intent || null, note: note.trim() || null,
      idempotency_key: "job-" + conceptId.slice(0, 8) + "-" + Date.now().toString(36) });
    if (alive.current) setJob(created);
  });
  const open = (lessonId, versionId) => onOpen({ lessonId, versionId, minutes });

  const running = job && STAGES.includes(job.stage);
  return <section className="teach-dock" aria-label={t("teach.title")}>
    <div className="teach-dock-head"><span className="teach-badge">{t("teach.title")}</span>{topic && <span className="teach-topic">{topic.title}</span>}</div>

    {objective && mode === "idle" && <p className="teach-objective"><b>{t("teach.intent." + objective.intent)}</b> · {objective.objective_markdown} <button className="textlink" onClick={startQuestions}>{t("teach.changeGoal")}</button></p>}
    {topic?.proposed && mode === "idle" && <div className="teach-proposal"><p><b>{t("teach.proposal")}</b> {topic.proposed.objective_markdown}</p><p className="teach-hint">{topic.proposed.proposal_reason}</p>
      <div className="teach-actions"><button className="btn" onClick={() => { const p = topic.proposed; setAnswers({ intent: p.intent }); setDraft({ topic_id: topic.id, intent: p.intent, objective_markdown: p.objective_markdown, observable_outcomes: p.observable_outcomes, constraints: p.constraints, out_of_scope: p.out_of_scope, preferred_depth: p.preferred_depth }); setMode("preview"); }}>{t("teach.proposalReview")}</button>
        <button className="textlink" onClick={() => teach.dismissProposal(topic.id).then(load)}>{t("teach.recDismiss")}</button></div></div>}

    {mode === "questions" && <div className="teach-questions">
      <Pills label={t("teach.q.intent")} options={INTENTS} value={answers.intent} onChange={(v) => setAnswers({ ...answers, intent: v })} render={(o) => t("teach.intent." + o)} />
      <Pills label={t("teach.q.familiarity")} options={FAMILIARITY} value={answers.familiarity} onChange={(v) => setAnswers({ ...answers, familiarity: v })} render={(o) => t("teach.familiarity." + o)} />
      <Pills label={t("teach.q.approach")} options={APPROACHES} value={answers.approach} onChange={(v) => setAnswers({ ...answers, approach: v })} render={(o) => t("teach.approach." + o)} />
      <Pills label={t("teach.q.minutes")} options={MINUTES} value={minutes} onChange={(v) => setMinutes(v || 10)} render={(o) => t("teach.minutes", { n: o })} />
      <label className="teach-free"><span>{t("teach.q.free")}</span><textarea rows={2} maxLength={600} value={answers.free_text || ""} onChange={(e) => setAnswers({ ...answers, free_text: e.target.value })} /></label>
      <div className="teach-actions"><button className="btn primary" disabled={busy} onClick={() => preview(false)}>{busy ? <span className="spinner" /> : t("teach.previewGoal")}</button>
        <button className="textlink" disabled={busy} onClick={() => preview(true)}>{t("teach.useDefaults")}</button>
        <button className="textlink" disabled={busy} onClick={() => setMode("idle")}>{t("teach.skip")}</button></div>
    </div>}

    {mode === "preview" && draft && <div className="teach-preview">
      <p className="teach-hint">{t("teach.previewHint")}</p>
      <textarea className="teach-goal" rows={4} maxLength={1200} value={draft.objective_markdown} onChange={(e) => setDraft({ ...draft, objective_markdown: e.target.value })} aria-label={t("teach.goal")} />
      <ul>{draft.observable_outcomes.map((o, i) => <li key={i}>{o}</li>)}</ul>
      <div className="teach-actions"><button className="btn primary" disabled={busy || !draft.objective_markdown.trim()} onClick={confirm}>{t("teach.confirmGoal")}</button>
        <button className="textlink" disabled={busy} onClick={() => setMode("questions")}>{t("teach.back")}</button></div>
    </div>}

    {mode === "idle" && !running && <div className="teach-start">
      {ctx.resume && <button className="btn primary" onClick={() => open(ctx.resume.lesson_id, ctx.resume.version_id)}>{t("teach.continue")}: {ctx.resume.title} →</button>}
      {!objective && <button className={"btn" + (ctx.resume ? "" : " primary")} onClick={startQuestions}>{t("teach.setGoal")}</button>}
      <div className="teach-make">
        <Pills label={t("teach.q.minutes")} options={MINUTES} value={minutes} onChange={(v) => setMinutes(v || 10)} render={(o) => t("teach.minutes", { n: o })} />
        <input className="teach-note" maxLength={400} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("teach.notePlaceholder")} aria-label={t("teach.notePlaceholder")} />
        <button className={"btn" + (objective && !ctx.resume ? " primary" : "")} disabled={busy} onClick={() => makeLesson(!!objective)}>{busy ? <span className="spinner" /> : objective ? t("teach.make") : t("teach.makeWithoutGoal")}</button>
      </div>
    </div>}

    {running && <div className="teach-progress" role="status" aria-live="polite">
      <ol>{STAGES.map((s) => <li key={s} className={s === job.stage ? "now" : STAGES.indexOf(s) < STAGES.indexOf(job.stage) ? "done" : ""}>{t("teach.stage." + s)}</li>)}</ol>
      {job.repairs > 0 && <p className="teach-hint teach-repair">{t("teach.repairing", { n: job.repairs })}</p>}
      <p className="teach-hint">{t("teach.progressHint")}</p>
      <button className="textlink" onClick={() => teach.cancelJob(job.id).then(setJob).catch(() => {})}>{t("teach.cancel")}</button>
    </div>}
    {job?.stage === "ready" && <div className="teach-ready"><p>{job.detail}</p><button className="btn primary" onClick={() => open(job.lesson_id, job.lesson_version_id)}>{t("teach.open")} →</button></div>}
    {job && ["failed", "cancelled"].includes(job.stage) && <p className="teach-failed" role="alert">{t(job.stage === "cancelled" ? "teach.cancelled" : job.error === "not_published" ? "teach.failedTest" : "teach.failed")} <button className="textlink" onClick={() => setJob(null)}>{t("teach.retry")}</button></p>}
    {error && <p className="teach-failed" role="alert">{error}</p>}

    {(ctx.lessons?.length > 0 || ctx.references?.length > 0 || ctx.recommendations?.length > 0) && <details className="teach-more"><summary>{t("teach.more", { lessons: ctx.lessons.length, references: ctx.references.length })}</summary>
      {ctx.lessons.map((l) => <button key={l.lesson_id} className="teach-row" onClick={() => open(l.lesson_id, l.version_id)}><b>{l.title}</b><span>{l.outcome}</span></button>)}
      {ctx.references.map((r) => <button key={r.id} className="teach-row" onClick={() => onReference(r.id)}><b>{t("teach.kind." + r.kind)} · {r.title}</b></button>)}
      {ctx.recommendations.map((r) => <div key={r.id} className="teach-row teach-rec"><b>{t("teach.recommended")}: {r.title}</b><span>{r.reason}</span>
        <span className="teach-actions"><button className="textlink" onClick={() => teach.recommendation(r.id, "accepted").then(() => { onExploreTopic(r.title); load(); })}>{t("teach.recAccept")}</button>
          <button className="textlink" onClick={() => teach.recommendation(r.id, "dismissed").then(load)}>{t("teach.recDismiss")}</button></span></div>)}
    </details>}
  </section>;
}
