"use client";
import LocalizedText from "./LocalizedText";
import { useState } from "react";
import { useT } from "../lib/i18n";

export function GoalCard({ goal, onOpen, onUpdate, busy }) {
  const { t } = useT();
  if (!goal) return null;
  const next = goal.steps.find(s => !s.done);
  return <section className="goal-card">
    <small>{t("journey.goal")}</small><h3>{goal.title}</h3>
    {goal.source_title && <p className="hint">{t("panel.source")}: {goal.source_title}</p>}
    {goal.cycle && <p className="hint">{t("journey.cycle")}</p>}
    {next && <><p>{t("journey.next")}: <b>{next.name}</b></p><p className="hint">{next.reason || (next.for_concept ? t("journey.prerequisite", { name: next.for_concept }) : t("journey.chosen"))}</p><button className="btn" onClick={() => onOpen(next.name)}>{t("journey.continue")} →</button></>}
    <details><summary>{t("journey.route")} · {goal.steps.length}</summary><p className="hint">{t("journey.doneHint")}</p><ol className="goal-steps">{goal.steps.map(s => <li key={s.concept_id}><label><input type="checkbox" checked={s.done} disabled={busy} onChange={e => onUpdate(goal.id, { concept_id: s.concept_id, done: e.target.checked })} /><span>{t("journey.stepDone")}</span></label><button className="textlink" onClick={() => onOpen(s.name)}>{s.name}</button>{(s.reason || s.for_concept) && <small>{s.reason || t("journey.prerequisite", { name: s.for_concept })}</small>}</li>)}</ol></details>
    <div className="goal-actions"><button className="textlink" disabled={busy} onClick={() => onUpdate(goal.id, { status: "paused" })}>{t("journey.pause")}</button><button className="textlink" disabled={busy} onClick={() => onUpdate(goal.id, { status: "completed" })}>{t("journey.finish")}</button></div>
  </section>;
}

export function LearningHome({ data, error, nodes, onRetry, onOpen, onCreate, onUpdate, busy, children, selectedName, onSearch }) {
  const { t } = useT();
  const [title, setTitle] = useState(""), [source, setSource] = useState(""), [targets, setTargets] = useState([]), [formOpen,setFormOpen]=useState(false);
  const active = data?.active_goal;
  const recent = data?.recent;
  const next = active?.steps?.find(s => !s.done);
  return <aside className="learning-sidebar" aria-label={t("home.yourLearning")}>
    <header className="learning-sidebar-head"><h2>{t("home.yourLearning")}</h2></header>
    {children}
    <div className="learning-sidebar-content">
      {error ? <div role="alert"><p>{t("journey.loadError")}</p><button className="btn" onClick={onRetry}>{t("journey.retry")}</button></div> : !data ? <p>{t("journey.loading")}</p> : <>
        <GoalCard goal={active} onOpen={onOpen} onUpdate={onUpdate} busy={busy} />
        {recent && recent.concept !== selectedName && <section className="last-conversation"><small>{t("journey.recent")}</small><h3>{recent.concept}</h3><p className="hint">{t(recent.consolidated ? "journey.fromMemory" : "journey.fromConversation")}</p><button className="btn primary" onClick={() => onOpen(recent.concept)}>{t("journey.resume")} →</button></section>}
        {!recent && !selectedName && !active && <section className="learning-welcome"><h3>{t("home.start")}</h3><p>{t("home.startHint")}</p><button className="btn primary" onClick={onSearch}>{t("home.chooseTopic")}</button></section>}
        {!!data.review?.length && <details><summary>{t("journey.review")}</summary><p className="hint">{t("journey.reviewHint")}</p>{data.review.map(r => <div className="review-option" key={r.concept}><button className="textlink" onClick={() => onOpen(r.concept, true)}>{r.concept} →</button><small>{r.date.slice(0,10)}</small><blockquote>{r.quote}</blockquote></div>)}</details>}
        {!!data.goals?.filter(g => g.status !== "active").length && <details><summary>{t("journey.saved")}</summary>{data.goals.filter(g => g.status !== "active").map(g => <div className="saved-goal" key={g.id}><span>{g.title} <small>· {t("journey." + g.status)}</small></span><button disabled={busy} className="textlink" onClick={() => onUpdate(g.id, { status: "active" })}>{t("journey.resume")}</button></div>)}</details>}
        <section className="learning-next-actions"><h3>{t("home.nextAction")}</h3><button className="btn ghost" onClick={onSearch}>{t("home.otherTopic")} ↗</button><button className="btn ghost" onClick={()=>setFormOpen(!formOpen)} aria-expanded={formOpen}>{t("journey.newGoal")} +</button></section>
        {formOpen && <form className="goal-form" onSubmit={async e => {e.preventDefault(); if(await onCreate({title,source_id:source || null,concept_ids:targets})){setTitle("");setTargets([]);setSource("");setFormOpen(false);}}}>
          <label>{t("journey.goalQuestion")}<textarea aria-label={t("journey.goalQuestion")} required maxLength={400} value={title} onChange={e=>setTitle(e.target.value)} placeholder={t("journey.goalPlaceholder")} /></label>
          <label>{t("journey.source")}<select aria-label={t("journey.source")} value={source} onChange={e=>setSource(e.target.value)}><option value="">{t("journey.noSource")}</option>{data.sources?.map(s=><option key={s.id} value={s.id}>{s.title}</option>)}</select></label>
          <label>{t("journey.topics")}<select aria-label={t("journey.topics")} multiple size={5} value={targets} onChange={e=>setTargets([...e.target.selectedOptions].map(o=>o.value))}>{[...nodes].sort((a,b)=>a.name.localeCompare(b.name)).map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
          <p className="hint">{t("journey.planHint")}</p><button className="btn" disabled={busy || !title.trim() || (!source && !targets.length)}>{busy?t("panel.thinking"):t("journey.save")}</button>
        </form>}
      </>}
    </div>
  </aside>;
}

function HelpfulExample({ example, onEdit, onDelete, busy }) {
  const {t}=useT();
  const [editing,setEditing]=useState(false),[text,setText]=useState(example.text);
  return <article className="helpful-example"><p><LocalizedText>{example.text}</LocalizedText></p><small>{example.date?.slice(0,10)} · {t("journey.message",{n:example.seq+1})}{example.corrected_at ? " · "+t("journey.corrected") : ""}</small>
    <details><summary>{t("journey.original")}</summary><blockquote>{example.original}</blockquote></details>
    {editing && <form onSubmit={async e=>{e.preventDefault();if(await onEdit(example.id,text))setEditing(false);}}><textarea aria-label={t("journey.editExample")} value={text} onChange={e=>setText(e.target.value)} required maxLength={12000}/><button className="btn" disabled={busy}>{t("journey.save")}</button><button type="button" className="textlink" onClick={()=>{setText(example.text);setEditing(false);}}>{t("journey.cancel")}</button></form>}
    <div className="goal-actions"><button className="textlink" disabled={busy} onClick={()=>setEditing(!editing)}>{t("journey.edit")}</button><button className="textlink" disabled={busy} onClick={()=>onDelete(example.id)}>{t("journey.remove")}</button></div>
  </article>;
}
export function HelpfulExamples({ examples, onEdit, onDelete, busy }) {
  const {t}=useT();
  return <details className="helpful-examples"><summary>{t("journey.examples")} · {examples.length}</summary><p className="hint">{t("journey.examplesHint")}</p>{examples.map(e=><HelpfulExample key={e.id} example={e} onEdit={onEdit} onDelete={onDelete} busy={busy}/>)}</details>;
}
