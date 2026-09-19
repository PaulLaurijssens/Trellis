"use client";

export default function Toasts({ items, onClose, shifted }) {
  if (!items.length) return null;
  return (
    <div className={"toasts" + (shifted ? " shifted" : "")}>
      {items.map((t) => {
        const actions = [...(t.actions || []), ...(t.action ? [t.action] : [])];
        return (
          <div key={t.id} className={"toast " + (t.type || "info")} role={t.type === "error" ? "alert" : "status"}>
            <span className="dot" />
            <span className="txt" title={t.title || undefined}>{t.text}</span>
            {actions.map((a, i) => (
              <button key={i} className="act" onClick={() => { a.onClick(); if (!a.keep) onClose(t.id); }}>{a.label}</button>
            ))}
            <button className="close" aria-label="×" onClick={() => onClose(t.id)}>×</button>
          </div>
        );
      })}
    </div>
  );
}
