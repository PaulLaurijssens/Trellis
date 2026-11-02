"use client";

// The descriptions from mentor.LEVELS are long sentences; they are the pill's tooltip,
// and the short part before the colon is its aria-label.
export function shortLabel(n, text) {
  return n + " · " + String(text || "").split(":")[0];
}

export default function LevelPills({ levels, value, onChange, disabled, small, label = "Niveau" }) {
  return (
    <div className={"levels" + (small ? " sm" : "")} role="radiogroup" aria-label="Niveau">
      {label && <span className="lbl">{label}</span>}
      {Object.entries(levels).map(([n, text]) => (
        <button
          key={n}
          type="button"
          role="radio"
          aria-checked={Number(n) === Number(value)}
          aria-label={shortLabel(n, text)}
          title={text}
          className={Number(n) === Number(value) ? "on" : ""}
          disabled={disabled}
          onClick={() => onChange(Number(n))}
        >{n}</button>
      ))}
    </div>
  );
}
