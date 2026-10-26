"use client";
import { useEffect, useRef, useState } from "react";
import { useT, LANGS } from "../lib/i18n";
import Backups from "./Backups";
import LessonCosts from "./LessonCosts";
import AIProvider from "./AIProvider";
import About from "./About";
import LearningStyle from "./LearningStyle";
import MemoryView from "./MemoryView";
import YourData from "./YourData";

const TABS = ["settings", "teaching", "memory", "data"];

export default function Profile({ person, onClose, onChanged, onOpenConcept, ambientMotion, onAmbientMotion, reducedMotion, motionSaving, account, onLogout }) {
  const { t, lang, setLang } = useT();
  const [tab,setTab] = useState("settings");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);   // {text, err}
  const notice = useRef(null);
  useEffect(() => { if (msg?.err) notice.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [msg]);

  const load = async () => setData(await person.load());
  useEffect(() => { load().catch((e) => setMsg({ text: e.message, err: true })); }, []);

  useEffect(() => {
    // A control that handles Escape itself (an open edit, the phone detail) calls preventDefault.
    const onKey = (e) => { if (e.key === "Escape" && !e.defaultPrevented) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const patch = async (body) => {
    setBusy(true);
    setMsg(null);
    try { await person.patch(body); await load(); return true; }
    catch (e) { setMsg({ text: e.message, err: true }); return false; }
    finally { setBusy(false); }
  };

  // One concept's memory changed in the Memory tab: keep the list in step and tell the page (the map
  // colours and an open Learn view follow the learner's status).
  const concept = async (name, action) => {
    setMsg(null);
    try {
      const state = await action();
      setData((d) => ({ ...d, concepts: d.concepts.map((c) => c.concept === name ? { ...c, ...state, concept: name } : c) }));
      onChanged?.(name);
    } catch (e) { setMsg({ text: e.message, err: true }); throw e; }
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
        <div ref={notice} role={msg.err ? "alert" : "status"} className={"notice" + (msg.err ? " err" : "")}>
          <span>{msg.text}</span>
          <button className="icon-btn x" onClick={() => setMsg(null)} aria-label={t("common.close")}>×</button>
        </div>
      )}

      {!data ? <p className="hint">{t("profile.loading")}</p> : (
        <>
          <div className="profile-tabs" role="tablist" aria-label={t("profile.title")}>
            {TABS.map((key,i)=><button key={key} id={"profile-tab-"+key} role="tab" aria-selected={tab===key} aria-controls="profile-content" tabIndex={tab===key?0:-1} onClick={()=>setTab(key)} onKeyDown={e=>{if(["ArrowLeft","ArrowRight","Home","End"].includes(e.key)){e.preventDefault();const n=TABS.length,next=e.key==="Home"?0:e.key==="End"?n-1:(i+(e.key==="ArrowRight"?1:n-1))%n;setTab(TABS[next]);document.getElementById("profile-tab-"+TABS[next])?.focus();}}}>{t("profile.tab."+key)}</button>)}
          </div>
          <div id="profile-content" role="tabpanel" aria-labelledby={"profile-tab-"+tab}>
          {tab === "settings" && <div className="profile-settings">
            <div className="card"><h4>{t("profile.language")}</h4>{LANGS.length < 2 ? <p className="hint">{t("profile.languageAdd")} <a href="https://github.com/PaulLaurijssens/Trellis#add-your-language" target="_blank" rel="noreferrer">{t("profile.languageHow")}</a></p> : <><p className="hint">{t("profile.languageSafe")}</p><div className="seg">{LANGS.map(([code,label])=><button key={code} aria-pressed={code===lang} className={code===lang?"on":""} disabled={busy} onClick={async()=>{setBusy(true);try{await setLang(code);}catch(e){setMsg({text:e.message,err:true});}finally{setBusy(false);}}}>{label}</button>)}</div></>}</div>
            {account && <div className="card account-card"><h4>{t("profile.account")}</h4><p className="hint">{t("profile.accountHint", { name: account.name })}</p><button className="btn ghost" onClick={onLogout}>{t("menu.logout")}</button></div>}
            {account?.is_admin && <AIProvider />}
            {account?.is_admin && <Backups />}
            <LessonCosts canEdit={!!account?.is_admin} />
            <div className="card motion-setting"><h4>{t("profile.motion")}</h4><label><input type="checkbox" checked={ambientMotion} disabled={motionSaving} onChange={(e) => onAmbientMotion(e.target.checked)} />{t("profile.motionLabel")}</label><p className="hint">{reducedMotion ? t("profile.motionReduced") : t("profile.motionHint")}</p></div>
            <About />
          </div>}
          {tab === "teaching" && <LearningStyle profile={data.learning_profile} busy={busy} patch={patch} />}
          {tab === "memory" && <MemoryView concepts={data.concepts}
            onPosition={(name, body) => concept(name, () => person.position(name, body))}
            onObservation={(name, id, state) => concept(name, () => person.observation(name, id, state))}
            onPatch={(name, body) => concept(name, () => person.patchConcept(name, body))}
            onOpen={onOpenConcept ? (name) => { onClose(); onOpenConcept(name); } : null} />}
          {tab === "data" && <YourData rebuild={person.rebuild} onChanged={async () => { await load().catch(() => {}); onChanged?.(); }} />}
          </div>
        </>
      )}
    </div>
  );
}
