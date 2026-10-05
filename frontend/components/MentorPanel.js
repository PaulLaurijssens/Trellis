"use client";
import LocalizedText from "./LocalizedText";
import { useEffect, useRef, useState } from "react";
import { GoalCard, HelpfulExamples } from "./LearningDirection";
import LevelPills from "./LevelPills";
import MemoryBlock from "./MemoryBlock";
import MiniTree from "./MiniTree";
import Progress from "./Progress";
import Chat, { render as renderMarkdown } from "./Chat";
import LessonDock from "./LessonDock";
import StudyGuide from "./StudyGuide";
import LessonStage from "./LessonStage";
import { teach as teachApi } from "../lib/teach";
import LearningTrail from "./LearningTrail";
import { fmtTs, momentLink } from "../lib/time";
import { useT } from "../lib/i18n";

const ExpandIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M8.5 1.5 H12.5 V5.5 M12.5 1.5 L8 6 M5.5 12.5 H1.5 V8.5 M1.5 12.5 L6 8" stroke="currentColor" strokeWidth="1.3" fill="none" /></svg>
);
const CollapseIcon = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M5.5 1.5 H1.5 V5.5 M1.5 1.5 L6 6 M8.5 12.5 H12.5 V8.5 M12.5 12.5 L8 8" stroke="currentColor" strokeWidth="1.3" fill="none" /></svg>
);

function Actions({ concept, level, busy, onExplain, onMarkLearned }) {
  const { t } = useT();
  const suggested = concept.status === "suggested" || concept.status === "queued";
  return (
    <>
      <button className={"btn" + (suggested ? "" : " ghost")} disabled={busy.explain || busy.chat || busy.ending || busy.suggestion}
              title={t("panel.explainTitle")}
              onClick={() => onExplain(concept.name, level)}>
        {busy.explain ? <><span className="spinner" /> {t("panel.thinking")}</> : suggested ? <>{t("panel.explain")} <small style={{ opacity: .7 }}>{t("panel.explainLevel", { n: level })}</small></> : t("panel.explain")}
      </button>
      <button className={"btn " + (concept.status === "learned" ? "ok" : "ghost")}
              disabled={busy.mark || concept.status === "learned"}
              onClick={() => onMarkLearned(concept.name)}>
        {concept.status === "learned" ? t("panel.learned") : busy.mark ? "…" : t("panel.markLearned")}
      </button>
      {busy.explain && <span className="hint">{t("panel.thinkingHint")}</span>}
    </>
  );
}

// Tijdcode als "Spring naar 47:12": YouTube linkt naar url + t=<sec>s,
// een andere bron met url naar die url, zonder url alleen als tekst.
function Moment({ url, sec }) {
  const { t } = useT();
  const label = t("panel.jumpTo", { ts: fmtTs(sec) });
  const href = momentLink(url, sec);
  if (!href) return <span className="ts">{fmtTs(sec)}</span>;
  return <a className="ts" href={href} target="_blank" rel="noopener noreferrer" title={label}>{label} ↗</a>;
}

export function Sources({ mentions, onAsk, busy }) {
  const { t } = useT();
  if (!mentions.length) return <div className="hint">{t("panel.noSources")}</div>;
  return (
    <div className="sources">
      {mentions.map((m, i) => {
        const list = (m.mentions || []).filter((x) => x.quote || x.start_sec != null);
        return (
          <div className="source" key={i}>
            <i />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="source-head">
                <b>{m.url && !list.length ? <a href={m.url} target="_blank" rel="noopener noreferrer">{m.source} ↗</a> : m.source}</b>
                {m.type && <span className="type">{m.type}</span>}
              </div>
              {m.context && <p><LocalizedText>{m.context}</LocalizedText></p>}
              {onAsk && <button className="textlink" disabled={busy} onClick={()=>onAsk(t("journey.sourceQuestion",{name:m.source}))}>{t("journey.askSource")} →</button> }
              {list.length > 0 && (
                <ul className="moments">
                  {list.map((x, j) => (
                    <li key={j}>
                      {x.start_sec != null ? <Moment url={m.url} sec={x.start_sec} /> : (m.url && <a className="ts" href={m.url} target="_blank" rel="noopener noreferrer">{t("panel.source")} ↗</a>)}
                      {x.provenance === "ai_video_analysis" && <span className="hint">{t("video.approximate")}</span>}
                      {x.quote && <span className="q">“{x.quote}”</span>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function MentorPanel({
  concept, chat, graph, levels, level, busy, trail, onReturn, onSuggestion,
  goal, review, examples=[], journeyBusy, onGoalUpdate, onSaveExample, onEditExample, onDeleteExample,
  onLevel, onSend, onNewChat, onEndChat, onRemoveMemory, onObservation, onPosition,
  onExplain, onMarkLearned, onSelect, onClose, nextTopic,
  teachEnabled = false, plan = null, onExploreTopic,
}) {
  const { t, lang } = useT();
  const [contextOpen, setContextOpen] = useState(false);
  // Interactive lessons (feature flag). With teachEnabled=false nothing below renders and the
  // panel is exactly the panel it was.
  const [lesson, setLesson] = useState(null);            // {lessonId, versionId, minutes}
  const [pane, setPane] = useState("lesson");            // phone: one of lesson | mentor at a time
  const [view, setView] = useState("lesson");            // lesson | study: what fills the board
  const [side, setSide] = useState("mentor");            // mentor | context: the panel next to the board
  const [sideWidth, setSideWidth] = useState(() => { try { return Number(localStorage.getItem("trellis.sideWidth")) || 380; } catch { return 380; } });
  const dragSide = (e) => {                               // drag the panel's left edge; the width is a per-browser convenience
    if (e.button !== 0) return;
    e.preventDefault();
    const startX = e.clientX, startW = sideWidth;
    const move = (ev) => setSideWidth(Math.max(300, Math.min(Math.round(window.innerWidth * 0.6), startW + (startX - ev.clientX))));
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); try { localStorage.setItem("trellis.sideWidth", String(sideWidth)); } catch {} };
    window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
  };
  useEffect(() => { try { localStorage.setItem("trellis.sideWidth", String(sideWidth)); } catch {} }, [sideWidth]);
  // Phone: the panel is a sheet over the board. Swipe down on its header (or tap ×) to put it away.
  const touch = useRef(null);
  const sheetTouchStart = (e) => { touch.current = { y: e.touches[0].clientY, x: e.touches[0].clientX }; };
  const sheetTouchEnd = (e) => { const t = touch.current; touch.current = null; if (!t) return; const dy = e.changedTouches[0].clientY - t.y, dx = Math.abs(e.changedTouches[0].clientX - t.x); if (dy > 70 && dx < 60) setContextOpen(false); };
  const [reference, setReference] = useState(null);
  const lessonCtx = useRef(null);                        // {run, activity_id, params}: goes with a question
  useEffect(() => { setLesson(null); setReference(null); setPane("lesson"); setView("lesson"); setSide("mentor"); lessonCtx.current = null; }, [concept?.name]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!concept) return null;
  const conceptId = teachEnabled ? graph?.nodes?.find((n) => n.name === concept.name)?.id : null;
  const planGroup = conceptId && plan?.groups ? plan.groups.find((g) => g.ids.includes(conceptId)) : null;
  const group = planGroup ? { title: planGroup.title, ids: planGroup.ids, planKey: plan.version || null } : null;
  const openReference = (id) => teachApi.reference(id).then(setReference).catch(() => {});
  const openLessonById = (id) => teachApi.context(conceptId, group?.ids).then((c) => { const l = c.lessons.find((x) => x.lesson_id === id); if (l) setLesson({ lessonId: l.lesson_id, versionId: l.version_id }); }).catch(() => {});
  const askFromLesson = (ctx) => { lessonCtx.current = ctx; setPane("mentor"); setSide("mentor"); setContextOpen(true); setTimeout(() => document.querySelector(".lesson-main .chat-input textarea")?.focus(), 50); };
  const send = (m) => onSend(m, lesson && lessonCtx.current ? lessonCtx.current : null);
  const mentions = (concept.mentions || []).filter((m) => m && m.source);
  const firstQuestion = chat?.messages?.find((m) => m.role === "user")?.content;
  const question = firstQuestion && firstQuestion.length <= 140 ? firstQuestion : concept.name;
  const state = chat?.state;
  const recap = (!state?.summary_stale && state?.summary) || (state?.covered?.length ? state.covered.slice(0, 2).join(" · ") : t("learn.freshStart"));
  const introduction = (withDock) => <header className="lesson-heading">
    <LearningTrail trail={trail} onReturn={onReturn} />
    <div className="lesson-eyebrow"><span className={"status-dot " + concept.status} />{concept.name}<label className="depth-select">{t("learn.depth")}<select value={level} disabled={busy.chat || busy.explain} onChange={(e) => onLevel(Number(e.target.value))}>{[1,2,3,4,5].map((n) => <option key={n} value={n}>{t("depth." + n)}</option>)}</select></label></div>
    <h1>{question}</h1>
    <details className="memory-recap"><summary><span><LocalizedText>{recap}</LocalizedText></span><b>{t("learn.viewMemory")}</b></summary><MemoryBlock state={state} onRemove={onRemoveMemory} onObservation={onObservation} onPosition={onPosition} /></details>
    {(!chat?.messages?.length || withDock) && !lesson && <p className="lesson-definition"><LocalizedText>{concept.definition}</LocalizedText></p>}
    {withDock && teachEnabled && conceptId && !lesson && <LessonDock conceptId={conceptId} conceptName={concept.name} group={group} lang={lang}
      onOpen={(l) => { setLesson(l); setPane("lesson"); setView("lesson"); }} onReference={openReference} onExploreTopic={onExploreTopic} />}
  </header>;
  const teaching = teachEnabled && conceptId;
  const showStudy = teaching && view === "study";
  const chatPanel = <Chat concept={concept.name} status={concept.status} chat={chat} busy={!!(busy.chat || busy.explain)} ending={!!busy.ending}
        emptyState={teaching ? <section className="lesson-start lesson-talk"><p>{t("lesson.talkHint")}</p><button className="btn" onClick={() => onExplain(concept.name, level)}>{t("lesson.talk")}</button></section> : undefined}
        draftKey={teachEnabled ? "trellis.draft." + concept.name : null}
        onSend={send} onNew={onNewChat} onEnd={onEndChat} onExplain={() => onExplain(concept.name, level)}
        suggestionBusy={busy.suggestion} onSuggestion={onSuggestion} introduction={teaching ? null : introduction(false)}
        examples={examples} onSaveExample={onSaveExample} exampleBusy={journeyBusy}
        nextTopic={nextTopic} sessionMenu={false} />;
  return <section className={"learn-workspace" + (contextOpen ? " context-open" : "") + (teaching ? " board" : "") + (lesson ? " has-run" : "")} aria-label={t("panel.mentor", { name: concept.name })}>
    <div className="lesson-main">
      <div className="lesson-toolbar"><button className="textlink" onClick={onClose}>← {t("nav.explore")}</button>
        {teaching && <div className="learn-views" role="tablist" aria-label={t("teach.title")}>{["lesson", "study"].map((v) => <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}>{t("teach.tab" + v[0].toUpperCase() + v.slice(1))}</button>)}</div>}
        <button className="textlink" onClick={() => setContextOpen(!contextOpen)} aria-pressed={contextOpen}>{teaching ? t("learn.sidePanel") : t("learn.context")}</button></div>
      {teaching && <div className="board-head">{introduction(view === "lesson" && !lesson)}</div>}
      {lesson && view === "lesson" && <LessonStage lessonId={lesson.lessonId} versionId={lesson.versionId} minutes={lesson.minutes}
        onAsk={askFromLesson} onActivity={(ctx) => { lessonCtx.current = ctx; }} onReference={openReference} onOpenLesson={openLessonById}
        onClose={() => { setLesson(null); lessonCtx.current = null; }} />}
      {reference && <div className="teach-reference" role="dialog" aria-label={reference.title}><div className="teach-stage-bar"><b>{t("teach.kind." + reference.kind)} · {reference.title}</b>
        <button className="textlink" onClick={() => { send(t("teach.askReference", { title: reference.title })); setReference(null); setPane("mentor"); }}>{t("teach.askAbout")}</button>
        <button className="textlink" onClick={() => setReference(null)}>{t("teach.close")}</button></div>
        <div className="teach-reference-body">{renderMarkdown(reference.markdown)}{reference.sources?.length > 0 && <p className="teach-hint">{t("panel.sources")}: {reference.sources.map((s) => s.title).join(" · ")}</p>}</div></div>}
      {showStudy && <div className="study-pane"><StudyGuide conceptId={conceptId} level={level} onLesson={() => setView("lesson")} onAsk={() => { setSide("mentor"); setContextOpen(true); setTimeout(() => document.querySelector(".lesson-side .chat-input textarea")?.focus(), 50); }} /></div>}
      {!teaching && chatPanel}
    </div>
    <aside className={"lesson-context" + (teaching ? " lesson-side" : "")} aria-label={t("learn.context")} style={teaching ? { width: sideWidth } : undefined}>
      {teaching && <div className="side-grip" role="separator" aria-orientation="vertical" aria-label="Resize" onPointerDown={dragSide} />}
      {teaching && <div className="side-switch" role="tablist" onTouchStart={sheetTouchStart} onTouchEnd={sheetTouchEnd}><span className="sheet-grip" aria-hidden="true" /><button role="tab" aria-selected={side === "mentor"} onClick={() => setSide("mentor")}>{t("teach.tabMentor")}</button><button role="tab" aria-selected={side === "context"} onClick={() => setSide("context")}>{t("learn.context")}</button><button className="sheet-close" aria-label={t("common.close")} onClick={() => setContextOpen(false)}>×</button></div>}
      {teaching && side === "mentor" && chatPanel}
      {(!teaching || side === "context") && <div className="side-context">
      {!teaching && <h2>{t("learn.context")}</h2>}
      <MiniTree graph={graph} name={concept.name} status={concept.status} big onSelect={onSelect} busy={busy.chat || busy.explain || busy.ending} onConnections={()=>onSend(t("tree.connectionsPrompt"))} />
      {review && <section className="review-option"><p>{t("journey.reviewHint")}</p><button className="btn" disabled={busy.chat || busy.explain || busy.ending} onClick={()=>onSend(t("journey.reviewRequest"))}>{t("journey.reviewStart")}</button></section>}
      <GoalCard goal={goal} onOpen={onSelect} onUpdate={onGoalUpdate} busy={journeyBusy} />
      <HelpfulExamples examples={examples} onEdit={onEditExample} onDelete={onDeleteExample} busy={journeyBusy} />
      {mentions.length > 0 && <details><summary>{t("panel.sources")} · {mentions.length}</summary><Sources mentions={mentions} onAsk={onSend} busy={busy.chat || busy.explain || busy.ending} /></details>}
      <details><summary>{t("learn.notes")}</summary><MemoryBlock state={state} onRemove={onRemoveMemory} onObservation={onObservation} onPosition={onPosition} /></details>
      <details><summary>{t("learn.conceptDetails")}</summary><p><LocalizedText>{concept.definition}</LocalizedText></p><Actions concept={concept} level={level} busy={busy} onExplain={onExplain} onMarkLearned={onMarkLearned} /></details>
      {trail?.length > 1 && <button className="textlink context-return" onClick={() => onReturn(trail.length - 2)}>← {t("trail.return", { name: trail[trail.length - 2] })}</button>}
      {/* Gespreksopties staan hier en niet meer onder het invoerveld: daar staat nu
          "Volgend onderwerp". Een gesprek afsluiten gebeurt ook vanzelf na 30 minuten stilte. */}
      <details className="context-session"><summary>{t("learn.sessionMenu")}</summary><div className="chat-links">
        <button className="textlink" onClick={onEndChat} disabled={busy.chat || busy.explain || busy.ending || !chat?.messages?.length} title={t("chat.endTitle")}>{busy.ending ? t("chat.ending") : t("chat.end")}</button>
        <button className="textlink" onClick={onNewChat} disabled={busy.chat || busy.explain || busy.ending} title={t("chat.newTitle")}>{t("chat.new")}</button>
      </div></details>
    </div>}
    </aside>
  </section>;
}
