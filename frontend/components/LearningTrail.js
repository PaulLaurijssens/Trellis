"use client";
import { useT } from "../lib/i18n";

export default function LearningTrail({ trail, onReturn }) {
  const { t } = useT();
  if (!trail || trail.length < 2) return null;
  return (
    <nav className="learning-trail" aria-label={t("trail.label")}>
      <span className="hint">{t("trail.label")}</span>
      <ol>
        {trail.map((name, i) => (
          <li key={name}>
            {i > 0 && <span aria-hidden="true">›</span>}
            {i === trail.length - 1
              ? <span aria-current="page">{name}</span>
              : <button className="textlink" onClick={() => onReturn(i)}
                        title={t("trail.return", { name })}>{name}</button>}
          </li>
        ))}
      </ol>
      <button className="textlink trail-back" onClick={() => onReturn(trail.length - 2)}>
        ← {t("trail.return", { name: trail[trail.length - 2] })}
      </button>
    </nav>
  );
}
