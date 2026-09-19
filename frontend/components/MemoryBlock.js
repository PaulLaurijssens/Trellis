"use client";
import LocalizedText from "./LocalizedText";
import { useState } from "react";
import { useT } from "../lib/i18n";

export default function MemoryBlock({ state, onRemove, onObservation, onPosition }) {
  const {t}=useT();
  const [saving,setSaving]=useState(false);
  if(!state)return null;
  const evidence=state.evidence||[],observations=(state.observations||[]).filter(o=>o.kind!=="covered");
  const active=observations.filter(o=>o.state==="active"),history=observations.filter(o=>o.state!=="active");
  const date=value=>value?new Date(value).toLocaleDateString():t("memory.unknownDate");
  const change=async action=>{setSaving(true);try{await action();}finally{setSaving(false);}};
  const proof=e=><div className="memory-proof" key={e.id}><strong>{t("memory."+e.kind)} · {t("memory."+e.outcome)}</strong><p><LocalizedText>{e.assessment}</LocalizedText></p><blockquote>{e.quote}</blockquote><small>{date(e.date)} · {t("memory.message",{n:e.seq+1})}</small></div>;
  const observation=o=><article className="memory-observation" key={o.id}>
    <p><LocalizedText>{o.text}</LocalizedText></p><small>{t("memory."+o.state)} · {o.corrected_by==="learner"?t("memory.learnerCorrection"):o.origin==="legacy"?t("memory.legacy"):t("memory.conversation")}</small>
    {(o.evidence_ids?.length>0||o.resolution_evidence_ids?.length>0)&&<details><summary>{t("memory.sources")}</summary>{[...new Set([...(o.evidence_ids||[]),...(o.resolution_evidence_ids||[])])].map(id=>evidence.find(e=>e.id===id)).filter(Boolean).map(proof)}</details>}
    {onObservation&&<div className="memory-actions">{o.state==="active"?<><button disabled={saving} onClick={()=>change(()=>onObservation(o.id,"resolved"))}>{t("memory.resolve")}</button><button disabled={saving} onClick={()=>change(()=>onObservation(o.id,"superseded"))}>{t("memory.dismiss")}</button></>:<button disabled={saving} onClick={()=>change(()=>onObservation(o.id,"active"))}>{t("memory.reactivate")}</button>}</div>}
  </article>;
  return <div className="memo memory-evolution">
    <div className="memory-position">
      <label>{t("memory.intent")}{onPosition?<select aria-label={t("memory.intent")} disabled={saving} value={state.intent||"learning"} onChange={e=>change(()=>onPosition({intent:e.target.value}))}>{["interested","queued","learning"].map(v=><option key={v} value={v}>{t("memory."+v)}</option>)}</select>:<span>{t("memory."+(state.intent||"learning"))}</span>}</label>
      <label>{t("memory.selfAssessment")}{onPosition?<select aria-label={t("memory.selfAssessment")} disabled={saving} value={state.self_assessment?.value||""} onChange={e=>change(()=>onPosition({assessment:e.target.value}))}><option value="" disabled>{t("memory.unrated")}</option>{["not_yet","partial","understood"].map(v=><option key={v} value={v}>{t("memory."+v)}</option>)}</select>:<span>{t("memory."+(state.self_assessment?.value||"unrated"))}</span>}</label>
      {state.self_assessment&&<small>{date(state.self_assessment.date)} · {t("memory.selfNotEvidence")}</small>}
    </div>
    {state.summary&&(state.summary_stale?<details><summary>{t("memory.previousSummary")}</summary><p><LocalizedText>{state.summary}</LocalizedText></p></details>:<p className="sum"><LocalizedText>{state.summary}</LocalizedText></p>)}
    <details open><summary>{t("memory.discussed")} · {(state.covered||[]).length}</summary><div className="memory-covered">{(state.covered||[]).map(item=><span key={item}><LocalizedText>{item}</LocalizedText>{onRemove&&<button aria-label={t("memo.remove",{item})} onClick={()=>onRemove("covered",state.covered.filter(x=>x!==item))}>×</button>}</span>)}</div></details>
    <details><summary>{t("memory.evidence")} · {evidence.filter(e=>e.outcome==="demonstrated").length}</summary><p className="hint">{t("memory.evidenceHint")}</p>{evidence.length?evidence.map(proof):<p>{t("memory.noEvidence")}</p>}</details>
    <details open={active.length>0}><summary>{t("memory.openQuestions")} · {active.length}</summary>{active.map(observation)}{!state.observations&&["struggles","misconceptions"].flatMap(field=>(state[field]||[]).map(item=><p key={field+item}>{item}</p>))}</details>
    {history.length>0&&<details><summary>{t("memory.history")} · {history.length}</summary>{history.map(observation)}</details>}
  </div>;
}
