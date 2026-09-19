"use client";
import { useT } from "../lib/i18n";

export default function ConversationSuggestions({ suggestions = [], busy, onAction }) {
  const { t } = useT();
  const pending = suggestions.filter((s) => s.state === "pending");
  const saved = suggestions.filter((s) => ["queued", "explored"].includes(s.state));
  const card = (s) => <article className="conversation-suggestion" key={s.id}>
    <div className="suggestion-heading"><span aria-hidden="true">↗</span><strong>{s.name}</strong></div>
    <p>{s.reason}</p>
    <div className="suggestion-actions">
      <button className="btn ghost" disabled={!!busy} onClick={() => onAction(s, "explore")}>{t("suggestions.explore")}</button>
      <button className="textlink" disabled={!!busy} onClick={() => onAction(s, "save")}>{t("suggestions.save")}</button>
      <button className="textlink" disabled={!!busy} onClick={() => onAction(s, "dismiss")}>{t("suggestions.dismiss")}</button>
    </div>
  </article>;
  return <section className="conversation-suggestions" aria-label={t("suggestions.title")}>
    {pending[0] && card(pending[0])}
    {pending.length > 1 && <details className="more-paths"><summary>{t("learn.morePaths", { n: pending.length - 1 })}</summary>{pending.slice(1).map(card)}</details>}
    {saved.length > 0 && <details className="saved-paths"><summary>{t("learn.savedPaths", { n: saved.length })}</summary>{saved.map((s) => <div className="saved-path" key={s.id}><span>{s.name} <small>{t("suggestions." + s.state)}</small></span><button className="textlink" disabled={!!busy} onClick={() => onAction(s, "explore")}>{t("suggestions.revisit")}</button></div>)}</details>}
  </section>;
}
