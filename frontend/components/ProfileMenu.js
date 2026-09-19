"use client";
import { useEffect, useRef, useState } from "react";
import { useT, LANGS } from "../lib/i18n";

// Linksonder: legenda en de avatar met het menu (profiel, rebuild, taal).
export default function ProfileMenu({ onProfile, onRebuild, rebuilding }) {
  const { t, lang, setLang } = useT();
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setConfirm(false); } };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const rebuild = async () => {
    await onRebuild();
    setConfirm(false);
    setOpen(false);
  };

  return (
    <div className="corner">
      <div className="avatar-wrap" ref={ref}>
        <button className={"avatar" + (open ? " on" : "")} onClick={() => { setOpen(!open); setConfirm(false); }}
                aria-label={t("menu.aria")} aria-expanded={open} title="Paul">P</button>
        {open && (
          <div className="menu" role="menu">
            {confirm ? (
              <>
                <div className="confirm">{t("menu.rebuildConfirm")}</div>
                <div className="row">
                  <button className="btn" disabled={rebuilding} onClick={rebuild}>
                    {rebuilding ? <><span className="spinner" /> {t("menu.busy")}</> : t("menu.rebuildYes")}
                  </button>
                  <button className="btn ghost" disabled={rebuilding} onClick={() => setConfirm(false)}>{t("menu.cancel")}</button>
                </div>
              </>
            ) : (
              <>
                <button role="menuitem" onClick={() => { setOpen(false); onProfile(); }}>{t("menu.profile")}</button>
                <button role="menuitem" onClick={() => setConfirm(true)}>{t("menu.rebuild")}</button>
                <div className="menu-lang" role="group" aria-label={t("menu.language")}>
                  <span>{t("menu.language")}</span>
                  <div className="seg sm">
                    {LANGS.map(([code, label]) => (
                      <button key={code} className={code === lang ? "on" : ""} onClick={() => setLang(code)} title={label}>{code.toUpperCase()}</button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>
      <div className="legend" aria-label="Legenda">
        <span title={t("legend.learning")}><i className="learning" />Learning</span>
        <span title={t("legend.queuedTitle")}><i className="queued" />{t("legend.queued")}</span>
        <span title={t("legend.learned")}><i className="learned" />Learned</span>
        <span title={t("legend.suggested")}><i className="suggested" />Suggested</span>
      </div>
    </div>
  );
}
