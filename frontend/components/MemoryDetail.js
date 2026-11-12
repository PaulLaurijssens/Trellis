"use client";
import LocalizedText from "./LocalizedText";
import { useEffect, useId, useRef, useState } from "react";
import { useT } from "../lib/i18n";
import { openItems, personStatus, provenance } from "../lib/memoryView.mjs";

const INTENTS = ["interested", "queued", "learning"];
const ASSESSMENTS = ["not_yet", "partial", "understood"];
const STATUS_LABEL = { learned: "memory.understood", learning: "memory.learning", queued: "memory.queued", suggested: "memory.interested" };

export function StatusBadge({ concept }) {
  const { t } = useT();
  const status = personStatus(concept);
  return <span className={"badge " + status}>{t(STATUS_LABEL[status])}</span>;
}

// A row of radio buttons that looks like a segmented control. Native radios: arrow keys work.
// The choice shows at once; it falls back to the saved value if saving fails.
function Choice({ label, value, options, disabled, onChange }) {
  const { t } = useT();
  const id = useId();
  const [pending, setPending] = useState(null);
  const queued = useRef(null), running = useRef(false);
  const shown = pending ?? value;
  // Arrow keys change a radio group on every press: save one value at a time, then the latest one.
  const pick = async (option) => {
    setPending(option);
    queued.current = option;
    if (running.current) return;
    running.current = true;
    while (queued.current != null) {
      const next = queued.current;
      queued.current = null;
      await onChange(next);
    }
    running.current = false;
    setPending(null);
  };
  return <div className="memory-choice" role="radiogroup" aria-labelledby={id + "-label"}>
    <span id={id + "-label"} className="memory-choice-label">{label}</span>
    <div className="memory-segments">
      {options.map((option) => <label key={option} className={shown === option ? "on" : ""}>
        <input type="radio" name={id} value={option} checked={shown === option} disabled={disabled} onChange={() => pick(option)} />
        <span>{t("memory." + option)}</span>
      </label>)}
    </div>
  </div>;
}

// A titled block; collapsible in the compact (Learn view) layout. `name` lets focus return to its title.
function Section({ name, title, count, children, collapsible, defaultOpen }) {
  return collapsible
    ? <details className="memory-section" open={defaultOpen}><summary data-focus={name}><h4>{title} · {count}</h4></summary>{children}</details>
    : <section className="memory-section"><h4 tabIndex={-1} data-focus={name}>{title}<span className="memory-count"> · {count}</span></h4>{children}</section>;
}

// Shared by the Memory tab (full) and the Learn view (compact). Everything the learner can correct
// about one concept: where they stand, the summary, open difficulties, evidence and what was discussed.
export default function MemoryDetail({ name, state, compact = false, onPatch, onObservation, onPosition, onOpen }) {
  const { t, lang } = useT();
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [undo, setUndo] = useState(null);           // {item}: the Discussed item just removed
  const [said, setSaid] = useState("");             // polite announcement after a save
  const undoTimer = useRef(null);
  const root = useRef(null);
  useEffect(() => () => clearTimeout(undoTimer.current), []);
  if (!state) return null;
  // The control that was used often disappears (an item moves list, an edit closes): keep focus nearby.
  const focus = (selector) => setTimeout(() => root.current?.querySelector(selector)?.focus(), 0);
  // The same message twice in a row would not be announced again; a trailing space makes it new.
  const announce = (message) => setSaid((prev) => prev === message ? message + "\u00a0" : message);

  const evidence = state.evidence || [];
  const shown = evidence.filter((e) => e.outcome === "demonstrated").length;
  const observations = (state.observations || []).filter((o) => o.kind !== "covered");
  const open = openItems(state);
  const earlier = observations.filter((o) => o.state !== "active");
  const covered = state.covered || [];
  const manualSummary = (state.manual_fields || []).includes("summary");
  const source = provenance(state);
  const date = (value) => value ? new Date(value).toLocaleDateString(lang) : t("memory.unknownDate");

  const change = async (action, message) => {
    setSaving(true);
    try { await action(); if (message) announce(message); return true; }
    catch { return false; }       // the caller shows the error; the control keeps its old value
    finally { setSaving(false); }
  };
  const removeCovered = async (item) => {
    if (await change(() => onPatch("covered", covered.filter((x) => x !== item)))) {
      setUndo({ item });
      clearTimeout(undoTimer.current);
      undoTimer.current = setTimeout(() => setUndo(null), 10000);
      focus(".memory-undo button");
    }
  };
  const restoreCovered = async () => {
    const item = undo.item;
    setUndo(null);
    await change(() => onPatch("covered", [...covered, item]), t("memory.restored", { item }));
    focus('[data-focus="discussed"]');
  };
  const closeEdit = () => { setEditing(false); focus(".memory-summary .textlink"); };
  const saveSummary = async () => {
    if (await change(() => onPatch("summary", draft.trim()), t("memory.summarySaved"))) closeEdit();
  };
  const correct = async (id, next, message) => {
    await change(() => onObservation(id, next), message);
    focus('[data-focus="attention"]');
  };

  const proof = (e) => <li className={"memory-proof " + e.outcome} key={e.id}>
    <span className="memory-proof-mark" aria-hidden="true">{e.outcome === "demonstrated" ? "✓" : "↻"}</span>
    <div>
      <strong>{t("memory." + e.outcome)}</strong> <span className="memory-kind">{t("memory." + e.kind)}</span>
      {e.assessment && <p><LocalizedText>{e.assessment}</LocalizedText></p>}
      {e.origin === "exercise" ? <p className="memory-exercise">{e.prompt}</p> : e.quote && <blockquote>{e.quote}</blockquote>}
      <small>{date(e.date)} · {e.origin === "exercise" ? t("memory.exercise") : t("memory.message", { n: (e.seq ?? 0) + 1 })}</small>
    </div>
  </li>;

  const observation = (o) => {
    const ids = [...new Set([...(o.evidence_ids || []), ...(o.resolution_evidence_ids || [])])];
    const sources = ids.map((id) => evidence.find((e) => e.id === id)).filter(Boolean);
    return <li className={"memory-observation " + o.state} key={o.id}>
      <span className={"memory-tag " + o.kind}>{t(o.kind === "misconceptions" ? "memory.misconception" : "memory.difficulty")}</span>
      <p><LocalizedText>{o.text}</LocalizedText></p>
      <small>{o.state !== "active" && <>{t("memory." + o.state)} · </>}{o.corrected_by === "learner" ? t("memory.learnerCorrection") : o.origin === "legacy" ? t("memory.legacy") : t("memory.conversation")}</small>
      {sources.length > 0 && <details className="memory-sources"><summary>{t("memory.sources")} · {sources.length}</summary><ul className="memory-proofs">{sources.map(proof)}</ul></details>}
      {onObservation && !o.fallback && <div className="memory-actions">
        {o.state === "active"
          ? <><button disabled={saving} onClick={() => correct(o.id, "resolved", t("memory.markedResolved"))}>{t("memory.resolve")}</button>
              <button disabled={saving} onClick={() => correct(o.id, "superseded", t("memory.markedWrong"))}>{t("memory.dismiss")}</button></>
          : <button disabled={saving} onClick={() => correct(o.id, "active", t("memory.markedActive"))}>{t("memory.reactivate")}</button>}
      </div>}
    </li>;
  };

  return <div ref={root} className={"memory-evolution memory-detail" + (compact ? " compact" : "")}>
    {!compact && <header className="memory-detail-head">
      <div><h3>{name}</h3><StatusBadge concept={state} /></div>
      {onOpen && <button className="btn" onClick={onOpen}>{t("memory.studyThis")}</button>}
    </header>}

    <section className="memory-section memory-stand" aria-label={t("memory.whereIStand")}>
      {!compact && <h4>{t("memory.whereIStand")}</h4>}
      {onPosition ? <>
        <Choice label={t("memory.intent")} value={state.intent || "learning"} options={INTENTS}
                onChange={(intent) => change(() => onPosition({ intent }), t("memory.saved"))} />
        <Choice label={t("memory.selfAssessment")} value={state.self_assessment?.value || ""} options={ASSESSMENTS}
                onChange={(assessment) => change(() => onPosition({ assessment }), t("memory.saved"))} />
      </> : <p>{t("memory.intent")}: {t("memory." + (state.intent || "learning"))} · {t("memory.selfAssessment")}: {t("memory." + (state.self_assessment?.value || "unrated"))}</p>}
      <small>{state.self_assessment ? date(state.self_assessment.date) + " · " : ""}{t("memory.selfNotEvidence")}</small>
    </section>

    <section className="memory-section memory-summary">
      <div className="memory-section-head">
        <h4>{t("memory.summary")}</h4>
        {onPatch && !editing && <button className="textlink" disabled={saving} onClick={() => { setDraft(state.summary || ""); setEditing(true); }}>{state.summary ? t("memory.edit") : t("memory.write")}</button>}
      </div>
      {editing ? <form onSubmit={(e) => { e.preventDefault(); saveSummary(); }}>
        <textarea aria-label={t("memory.summary")} rows={compact ? 3 : 4} maxLength={2000} value={draft} autoFocus
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); closeEdit(); } }} />
        <div className="memory-row">
          <button className="btn" disabled={saving || draft.trim() === (state.summary || "").trim()}>{t("profile.save")}</button>
          <button type="button" className="btn ghost" onClick={closeEdit}>{t("menu.cancel")}</button>
        </div>
      </form> : state.summary ? <>
        <p className={"sum" + (state.summary_stale ? " stale" : "")}><LocalizedText>{state.summary}</LocalizedText></p>
        {manualSummary ? <small>{t("memory.editedByYou")}</small> : state.summary_stale && <small>{t("memory.staleSummary")}</small>}
      </> : <p className="memory-empty">{t("profile.noSummary")}</p>}
    </section>

    <Section name="attention" title={t("memory.openQuestions")} count={open.length}>
      {open.length ? <ul className="memory-list">{open.map(observation)}</ul> : <p className="memory-empty">{t("memory.nothingOpen")}</p>}
    </Section>

    <Section title={t("memory.evidence")} count={shown} collapsible={compact} defaultOpen={!compact}>
      <p className="memory-hint">{t("memory.evidenceHint")}</p>
      {evidence.length ? <ul className="memory-proofs">{evidence.map(proof)}</ul> : <p className="memory-empty">{t("memory.noEvidence")}</p>}
    </Section>

    <Section name="discussed" title={t("memory.discussed")} count={covered.length} collapsible={compact} defaultOpen>
      {covered.length ? <ul className="memory-covered">{covered.map((item) => <li key={item}>
        <LocalizedText>{item}</LocalizedText>
        {onPatch && <button disabled={saving} aria-label={t("memo.remove", { item })} title={t("memo.removeTitle")} onClick={() => removeCovered(item)}>×</button>}
      </li>)}</ul> : <p className="memory-empty">{t("memory.nothingDiscussed")}</p>}
      <div role="status">{undo && <div className="memory-undo"><span>{t("memory.removed", { item: undo.item })}</span><button className="textlink" disabled={saving} onClick={restoreCovered}>{t("memory.undo")}</button></div>}</div>
    </Section>

    {earlier.length > 0 && <details className="memory-section memory-earlier"><summary><h4>{t("memory.history")} · {earlier.length}</h4></summary>
      <ul className="memory-list">{earlier.map(observation)}</ul>
    </details>}

    <p className="memory-provenance">{t("memory.provenance", { conversations: source.conversations, exercises: source.exercises })}</p>
    <p className="sr-only" aria-live="polite">{said}</p>
  </div>;
}
