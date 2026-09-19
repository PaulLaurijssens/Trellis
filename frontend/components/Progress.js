"use client";
import { useT } from "../lib/i18n";

// Voortgang = behandelde aspecten tegenover alles wat de mentor tot nu toe
// benoemd heeft (covered + struggles + misconceptions uit UNDERSTANDS).
export function aspects(state) {
  const covered = state?.covered || [];
  const open = [...(state?.struggles || []), ...(state?.misconceptions || [])]
    .filter((x) => !covered.includes(x));
  return { covered, open, total: covered.length + open.length };
}

export default function Progress({ state }) {
  const { t } = useT();
  const { covered, open, total } = aspects(state);
  const C = 2 * Math.PI * 27;
  const frac = total ? covered.length / total : 0;
  return (
    <div className="progress">
      <div className="ring" aria-label={t("progress.of", { done: covered.length, total })}>
        <svg width="64" height="64" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r="27" fill="none" stroke="rgba(130,160,200,0.15)" strokeWidth="4" />
          <circle cx="32" cy="32" r="27" fill="none" stroke="#54A9FF" strokeWidth="4" strokeLinecap="round"
                  strokeDasharray={`${frac * C} ${C}`} transform="rotate(-90 32 32)"
                  style={{ transition: "stroke-dasharray .4s ease" }} />
        </svg>
        <span>{total ? `${covered.length}/${total}` : "–"}</span>
      </div>
      <div className="progress-list">
        {total
          ? <span className="lead">{t("progress.of", { done: covered.length, total })}</span>
          : <span className="lead">{t("progress.none")}</span>}
        {covered.map((c) => <span key={"c" + c} className="done">✓ {c}</span>)}
        {open.map((c) => <span key={"o" + c} className="todo">· {c}</span>)}
        {!total && <span className="todo">{t("progress.noneHint")}</span>}
      </div>
    </div>
  );
}
