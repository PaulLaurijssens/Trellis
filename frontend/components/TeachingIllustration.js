"use client";
import { useId } from "react";
import { useT } from "../lib/i18n";

export default function TeachingIllustration({ illustration: d }) {
  const { t } = useT();
  const id = useId().replace(/:/g, "");
  if (!d || !["flow", "comparison", "vectors", "bars"].includes(d.type)) return null;
  let content;
  if (d.type === "comparison") {
    content = <div className="teaching-comparison">{d.columns.map((c, i) => <section key={i}><h4>{c.label}</h4><ul>{c.items.map((item, j) => <li key={j}>{item}</li>)}</ul></section>)}</div>;
  } else if (d.type === "bars") {
    const max = Math.max(...d.items.map((i) => i.value), 1e-10);
    content = <div className="teaching-bars">{d.items.map((item, i) => <div key={i}><span>{item.label}</span><div className="bar-track"><i style={{ width: `${100 * item.value / max}%` }} /></div><span>{item.value} {d.unit}</span></div>)}</div>;
  } else if (d.type === "vectors") {
    const max = Math.max(1, ...d.vectors.flatMap((v) => [Math.abs(v.x), Math.abs(v.y)]));
    const scale = 105 / max, origin = 150;
    content = <div className="teaching-vectors"><svg viewBox="0 0 300 300" role="img" aria-label={d.vectors.map((v) => `${v.label}: (${v.x}, ${v.y})`).join("; ")}>
      <defs>{["#54A9FF", "#E5A64A"].map((c, i) => <marker key={i} id={`${id}-${i}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10 Z" fill={c} /></marker>)}</defs>
      <path d="M20 150H280M150 20V280" stroke="#607287" fill="none" />
      <text x="280" y="170" fill="#A9B8CC">x</text><text x="160" y="22" fill="#A9B8CC">y</text>
      {d.vectors.map((v, i) => <line key={i} x1={origin} y1={origin} x2={origin + v.x * scale} y2={origin - v.y * scale} stroke={i ? "#E5A64A" : "#54A9FF"} strokeWidth="3" markerEnd={`url(#${id}-${i})`} />)}
    </svg><div>{d.vectors.map((v, i) => <p key={i} className={i ? "amber" : "blue"}>{v.label} = ({v.x}, {v.y})</p>)}<p>{t("visual.dot")}: <strong>{Number((d.vectors[0].x * d.vectors[1].x + d.vectors[0].y * d.vectors[1].y).toFixed(4))}</strong></p></div></div>;
  } else {
    const names = new Map(d.nodes.map((n) => [n.id, n.label]));
    content = <div className="teaching-flow"><div className="flow-nodes">{d.nodes.map((n) => <div key={n.id}>{n.label}</div>)}</div><ul className="flow-relations">{d.edges.map((e, i) => <li key={i}><span>{names.get(e.from)}</span><span className="flow-arrow">{e.label && <small>{e.label}</small>} → </span><span>{names.get(e.to)}</span></li>)}</ul></div>;
  }
  return <figure className="teaching-figure"><h3>{d.title}</h3>{content}{d.caption && <figcaption>{d.caption}</figcaption>}</figure>;
}
