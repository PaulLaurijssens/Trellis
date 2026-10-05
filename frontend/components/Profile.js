"use client";
import LocalizedText from "./LocalizedText";
import { useEffect, useState } from "react";
import { useT, LANGS } from "../lib/i18n";
import Backups from "./Backups";
import LessonCosts from "./LessonCosts";

const CHOICES = ["Step-by-step explanations", "Concrete examples", "Code examples", "Visual diagrams", "Analogies", "Short explanations", "Technical depth", "Optional practice questions"];

const LISTS = [
  { key: "works_well", label: "profile.worksWell", hint: "profile.worksWellHint" },
  { key: "works_poorly", label: "profile.worksPoorly", hint: "profile.worksPoorlyHint" },
  { key: "preferences", label: "profile.preferences", hint: "profile.preferencesHint" },
];

export default function Profile({ person, onClose, onRebuilt, ambientMotion, onAmbientMotion, reducedMotion, motionSaving, account, onLogout }) {
  const { t, lang, setLang } = useT();
  const [tab,setTab] = useState("settings");
  const [custom,setCustom] = useState("");
  const [data, setData] = useState(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmRebuild, setConfirmRebuild] = useState(false);
  const [msg, setMsg] = useState(null);   // {text, err}

  const load = async () => {
    const m = await person.load();
    setData(m);
    setNotes(m.learning_profile?.notes || "");
  };
  useEffect(() => { load().catch((e) => setMsg({ text: e.message, err: true })); }, []);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const p = data?.learning_profile || {};

  const patch = async (body) => {
    setBusy(true);
    setMsg(null);
    try { await person.patch(body); await load(); return true; }
    catch (e) { setMsg({ text: e.message, err: true }); return false; }
    finally { setBusy(false); }
  };

  const rebuild = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await person.rebuild();
      await load();
      setMsg({ text: t("profile.rebuilt", { sessions: r.sessions, done: r.verwerkt }) });
      onRebuilt?.();
    } catch (e) { setMsg({ text: e.message, err: true }); }
    finally { setBusy(false); setConfirmRebuild(false); }
  };

  return (
    <div className="profile profile-organized" role="dialog" aria-label={t("profile.title")}>
      <div className="profile-head">
        <div>
          <h2>{t("profile.title")}</h2>
          <p>{t("profile.simpleIntro")}</p>
        </div>
        <button className="icon-btn x" onClick={onClose} aria-label={t("common.close")}>×</button>
      </div>

      {msg && (
        <div role={msg.err ? "alert" : "status"} className={"notice" + (msg.err ? " err" : "")}>
          <span>{msg.text}</span>
          <button className="icon-btn x" onClick={() => setMsg(null)} aria-label={t("common.close")}>×</button>
        </div>
      )}

      {!data ? <p className="hint">{t("profile.loading")}</p> : (
        <>
          <div className="profile-tabs" role="tablist" aria-label={t("profile.title")}>
            {["settings","teaching","memory"].map((key,i)=><button key={key} id={"profile-tab-"+key} role="tab" aria-selected={tab===key} aria-controls="profile-content" tabIndex={tab===key?0:-1} onClick={()=>setTab(key)} onKeyDown={e=>{if(["ArrowLeft","ArrowRight","Home","End"].includes(e.key)){e.preventDefault();const keys=["settings","teaching","memory"],next=e.key==="Home"?0:e.key==="End"?2:(i+(e.key==="ArrowRight"?1:2))%3;setTab(keys[next]);document.getElementById("profile-tab-"+keys[next])?.focus();}}}>{t("profile.tab."+key)}</button>)}
          </div>
          <div id="profile-content" role="tabpanel" aria-labelledby={"profile-tab-"+tab}>
          {tab === "settings" && <div className="profile-settings">
            <div className="card"><h4>{t("profile.language")}</h4><p className="hint">{t("profile.languageSafe")}</p><div className="seg">{LANGS.map(([code,label])=><button key={code} aria-pressed={code===lang} className={code===lang?"on":""} disabled={busy} onClick={async()=>{setBusy(true);try{await setLang(code);}catch(e){setMsg({text:e.message,err:true});}finally{setBusy(false);}}}>{label}</button>)}</div></div>
            {account && <div className="card account-card"><h4>{t("profile.account")}</h4><p className="hint">{t("profile.accountHint", { name: account.name })}</p><button className="btn ghost" onClick={onLogout}>{t("menu.logout")}</button></div>}
            {account?.is_admin && <Backups />}
            <LessonCosts canEdit={!!account?.is_admin} />
            <div className="card motion-setting"><h4>{t("profile.motion")}</h4><label><input type="checkbox" checked={ambientMotion} disabled={motionSaving} onChange={(e) => onAmbientMotion(e.target.checked)} />{t("profile.motionLabel")}</label><p className="hint">{reducedMotion ? t("profile.motionReduced") : t("profile.motionHint")}</p></div>
          </div>}
          {tab === "teaching" && <div className="profile-teaching">
            <section className="card"><h4>{t("profile.yourChoices")}</h4><p className="hint">{t("profile.choicesHint")}</p><div className="preference-pills">
              {[...CHOICES,...(p.teaching_preferences||[]).filter(x=>!CHOICES.includes(x))].map(item=><button key={item} className={"preference-pill chosen"+((p.teaching_preferences||[]).includes(item)?" selected":"")} aria-pressed={(p.teaching_preferences||[]).includes(item)} disabled={busy} onClick={()=>patch({teaching_preferences:(p.teaching_preferences||[]).includes(item)?p.teaching_preferences.filter(x=>x!==item):[...(p.teaching_preferences||[]),item]})}>{CHOICES.includes(item)?t("profile.choice."+CHOICES.indexOf(item)):item}</button>)}
            </div><form className="custom-preference" onSubmit={async e=>{e.preventDefault();if(custom.trim()){if(await patch({teaching_preferences:[...new Set([...(p.teaching_preferences||[]),custom.trim()])]}))setCustom("");}}}><input aria-label={t("profile.custom")} placeholder={t("profile.custom")} maxLength={240} value={custom} onChange={e=>setCustom(e.target.value)}/><button className="btn" disabled={busy||!custom.trim()}>{t("profile.addPreference")}</button></form></section>
            <section className="mentor-preferences"><h3>{t("profile.mentorNotes")}</h3><p className="hint">{t("profile.mentorNotesHint")}</p>
            {LISTS.map(({ key, label, hint }) => (
              <div className="card" key={key}>
                <h4>{t(label)} <small>· {t(hint)}</small></h4>
                {(p[key] || []).length === 0 && <p className="hint">{t("profile.nothing")}</p>}
                {(p[key] || []).map((item) => (
                  <span key={item} className="preference-pill observed">
                    <LocalizedText>{item}</LocalizedText>
                    <button className="x" disabled={busy} title={t("memo.removeTitle")}
                            aria-label={t("memo.remove", { item })}
                            onClick={() => patch({ [key]: p[key].filter((x) => x !== item) })}>×</button>
                  </span>
                ))}
              </div>
            ))}
            </section>
            <div className="card">
              <h4>{t("profile.notes")}</h4>
              <textarea aria-label={t("profile.notes")} rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} />
              <div className="row">
                <button className="btn" disabled={busy || notes === (p.notes || "")} onClick={() => patch({ notes })}>{t("profile.save")}</button>
              </div>
            </div>
          </div>}

          {tab === "memory" && <>
          <div className="sub">
            <h3>{t("profile.states")} <small>{t("profile.concepts", { n: data.concepts.length })}</small></h3>
            {confirmRebuild ? (
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span className="hint" style={{ fontSize: 16 }}>{t("menu.rebuildConfirm")}</span>
                <button className="btn" disabled={busy} onClick={rebuild}>
                  {busy ? <><span className="spinner" /> {t("menu.busy")}</> : t("menu.rebuildYes")}
                </button>
                <button className="btn ghost" onClick={() => setConfirmRebuild(false)}>{t("menu.cancel")}</button>
              </div>
            ) : (
              <button className="btn ghost" onClick={() => setConfirmRebuild(true)}>{t("menu.rebuild")}</button>
            )}
          </div>

          <div className="profile-grid">
            {data.concepts.length === 0 && <p className="hint">{t("profile.noSessions")}</p>}
            {data.concepts.map((c) => (
              <div className="card" key={c.concept}>
                <div className="top">
                  <h4>{c.concept}</h4>
                  <span className={"badge " + c.concept_status}>{c.concept_status}</span>
                </div>
                {c.summary ? <p><LocalizedText>{c.summary}</LocalizedText></p> : <p className="hint">{t("profile.noSummary")}</p>}
                <p className="hint" style={{ marginTop: 8 }}>
                  {t("profile.stats", { covered: (c.covered || []).length, struggles: (c.struggles || []).length,
                                        mis: (c.misconceptions || []).length, ok: c.quiz_correct, total: c.quiz_correct + c.quiz_wrong })}
                  {(c.manual_fields || []).length > 0 && t("profile.manual")}
                  {" · "}{t("memory.evidence")}: {(c.evidence||[]).filter(e=>e.outcome==="demonstrated").length}
                </p>
              </div>
            ))}
          </div>
          </>}
          </div>
        </>
      )}
    </div>
  );
}
