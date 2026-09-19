"use client";
import LocalizedText from "./LocalizedText";
import { useMemo } from "react";
import { learningRoute } from "../lib/atlas.mjs";
import { Sources } from "./MentorPanel";
import { useT } from "../lib/i18n";

export default function ConceptPreview({ concept, graph, onLearn, onSelect, onClose, recent }) {
  const { t } = useT();
  const node = graph.nodes.find((n) => n.name === concept.name);
  const route = useMemo(() => learningRoute(graph, node?.id), [graph, node?.id]);
  const mentions = concept.mentions?.filter((m) => m.source) || [];
  return <section className="concept-preview embedded-preview" aria-label={t("explore.preview")}>
    <button className="icon-btn preview-close" onClick={onClose} aria-label={t("common.close")}>×</button>
    <span className="eyebrow">{t(recent ? "home.currentRecent" : "explore.selected")}</span><h1>{concept.name}</h1>
    <span className="preview-status"><i className={"status-dot " + concept.status} />{t("status." + concept.status)}</span>
    <p className="preview-definition"><LocalizedText>{concept.definition}</LocalizedText></p>
    <button className="btn primary" onClick={onLearn}>{t("explore.continue")} →</button>
    <details className="learning-route"><summary>{t("explore.route")}</summary>
      {route.cycle ? <p>{t("explore.cycle")}</p> : route.nodes.length > 1 ? <><p className="hint">{t("explore.routeHint")}</p><ol>{route.nodes.map((n) => <li key={n.id}><button onClick={() => onSelect(n.name)} aria-current={n.id === node?.id ? "step" : undefined}><i className={"status-dot " + n.status} /><span>{n.name}</span>{n.status === "learned" && <span title={t("status.learned")}>✓</span>}</button></li>)}</ol></> : <p className="hint">{t("explore.noRoute")}</p>}
    </details>
    {mentions.length > 0 && <details><summary>{t("panel.sources")} · {mentions.length}</summary><Sources mentions={mentions} /></details>}
  </section>;
}
