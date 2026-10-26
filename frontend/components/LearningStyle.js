"use client";
import LocalizedText from "./LocalizedText";
import { useEffect, useRef, useState } from "react";
import { useT } from "../lib/i18n";

const CHOICES = ["Step-by-step explanations", "Concrete examples", "Code examples", "Visual diagrams", "Analogies", "Short explanations", "Technical depth", "Optional practice questions"];

const NOTICED = [
  { key: "works_well", label: "profile.worksWell", hint: "profile.worksWellHint" },
  { key: "works_poorly", label: "profile.worksPoorly", hint: "profile.worksPoorlyHint" },
  { key: "preferences", label: "profile.preferences", hint: "profile.preferencesHint" },
];

// "How I learn": what the learner chose, what Trellis noticed (removable, with Undo), and free notes.
export default function LearningStyle({ profile, busy, patch }) {
  const { t } = useT();
  const p = profile || {};
  const chosen = p.teaching_preferences || [];
  const [custom, setCustom] = useState("");
  const [notes, setNotes] = useState(p.notes || "");
  const [undo, setUndo] = useState(null);            // {key, item}
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => { setNotes(p.notes || ""); }, [p.notes]);

  const toggle = (item) => patch({ teaching_preferences: chosen.includes(item) ? chosen.filter((x) => x !== item) : [...chosen, item] });
  const remove = async (key, item) => {
    if (await patch({ [key]: (p[key] || []).filter((x) => x !== item) })) {
      setUndo({ key, item });
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setUndo(null), 10000);
      setTimeout(() => document.querySelector(".mentor-preferences .memory-undo button")?.focus(), 0);
    }
  };
  const restore = async () => {
    const { key, item } = undo;
    setUndo(null);
    await patch({ [key]: [...(p[key] || []), item] });
  };

  return <div className="profile-teaching">
    <section className="card">
      <h4>{t("profile.yourChoices")}</h4>
      <p className="hint">{t("profile.choicesHint")}</p>
      <div className="preference-pills">
        {[...CHOICES, ...chosen.filter((x) => !CHOICES.includes(x))].map((item) => <button key={item}
            className={"preference-pill chosen" + (chosen.includes(item) ? " selected" : "")} aria-pressed={chosen.includes(item)}
            disabled={busy} onClick={() => toggle(item)}>
          {CHOICES.includes(item) ? t("profile.choice." + CHOICES.indexOf(item)) : item}
        </button>)}
      </div>
      <form className="custom-preference" onSubmit={async (e) => {
        e.preventDefault();
        if (custom.trim() && await patch({ teaching_preferences: [...new Set([...chosen, custom.trim()])] })) setCustom("");
      }}>
        <input aria-label={t("profile.custom")} placeholder={t("profile.custom")} maxLength={240} value={custom} onChange={(e) => setCustom(e.target.value)} />
        <button className="btn" disabled={busy || !custom.trim()}>{t("profile.addPreference")}</button>
      </form>
    </section>

    <section className="card mentor-preferences">
      <h4>{t("profile.mentorNotes")}</h4>
      <p className="hint">{t("profile.mentorNotesHint")}</p>
      {NOTICED.map(({ key, label, hint }) => <div className="noticed-group" key={key}>
        <h5>{t(label)} <small>{t(hint)}</small></h5>
        {(p[key] || []).length === 0 ? <p className="hint">{t("profile.nothing")}</p> : <ul className="noticed-list">
          {(p[key] || []).map((item) => <li key={item} className="preference-pill observed">
            <LocalizedText>{item}</LocalizedText>
            <button className="x" disabled={busy} title={t("memo.removeTitle")} aria-label={t("memo.remove", { item })} onClick={() => remove(key, item)}>×</button>
          </li>)}
        </ul>}
      </div>)}
      <div role="status">{undo && <div className="memory-undo"><span>{t("memory.removed", { item: undo.item })}</span><button className="textlink" disabled={busy} onClick={restore}>{t("memory.undo")}</button></div>}</div>
    </section>

    <section className="card">
      <h4>{t("profile.notes")}</h4>
      <p className="hint">{t("profile.notesHint")}</p>
      <textarea aria-label={t("profile.notes")} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
      <div className="row">
        <button className="btn" disabled={busy || notes === (p.notes || "")} onClick={() => patch({ notes })}>{t("profile.save")}</button>
      </div>
    </section>
  </div>;
}
