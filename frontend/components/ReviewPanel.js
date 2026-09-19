"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { buildReviewTree, descendants } from "../lib/reviewTree";
import { fmtTs } from "../lib/time";
import { useT } from "../lib/i18n";

const Stars = ({ n }) => <span className="stars" aria-label={n + "/5"}>{"★".repeat(n)}{"☆".repeat(5 - n)}</span>;

function Item({ node, depth, selected, linked, open, highlight, toggle, toggleLink, toggleOpen, onHover, chunksTotal, existingByName, t }) {
  const c = node.cand;
  const first = (c.mentions || []).find((m) => m.quote || m.start_sec != null) || null;
  // Alleen selecteerbare nakomelingen tellen mee (bestaande concepten hebben
  // geen checkbox maar een koppelknop).
  const kids = descendants(node).filter((k) => !existingByName.has(k));
  const kidsChecked = kids.filter((k) => selected.has(k)).length;
  const selfChecked = selected.has(c.name);
  const all = selfChecked && kidsChecked === kids.length;
  const some = (selfChecked || kidsChecked > 0) && !all;
  const box = useRef(null);
  useEffect(() => { if (box.current) box.current.indeterminate = some; }, [some]);
  const existing = c.existing;
  const isOpen = open.has(c.name);
  return (
    <li className={"rv-item" + (highlight === c.name ? " hl" : "") + (existing ? " existing" : "")} style={{ "--depth": depth }}
        onMouseEnter={() => existing && onHover(existing.name)} onMouseLeave={() => existing && onHover(null)}>
      <div className="rv-row">
        {existing ? (
          <button className={"rv-link" + (linked.has(c.name) ? " on" : "")} onClick={() => toggleLink(c.name)}
                  title={t("review.linkTitle")}>{linked.has(c.name) ? "✓ " : ""}{t("review.link")}</button>
        ) : (
          <input ref={box} type="checkbox" checked={all} onChange={() => toggle(node)} aria-label={c.name} />
        )}
        <button className="rv-main" onClick={() => toggleOpen(c.name)} aria-expanded={isOpen}>
          <span className="rv-line">
            <span className={"rv-name" + (node.kind === "main" ? " main" : "")}>
              {node.kind === "related" && <i className="rv-rel" title={t("tree.related")}>~</i>}{c.name}
            </span>
            <span className="rv-meta">
              <Stars n={Math.max(0, Math.min(5, c.importance || 0))} />
              {chunksTotal > 1 && <span>{t("ghost.parts", { n: c.chunk_count || 1, m: chunksTotal })}</span>}
              {first?.start_sec != null && <span className="ts">{fmtTs(first.start_sec)}</span>}
            </span>
            <i className="rv-chev">{isOpen ? "▾" : "▸"}</i>
          </span>
          {existing && <span className="rv-line sub"><span className={"badge " + existing.status}>{t("review.existing")} · {existing.status}</span></span>}
        </button>
      </div>
      {isOpen && (
        <div className="rv-detail">
          {c.definition && <p className="def">{c.definition}</p>}
          {first?.quote && <p className="quote">{first.start_sec != null && <b>{fmtTs(first.start_sec)}</b>}“{first.quote}”</p>}
        </div>
      )}
      {node.children.length > 0 && (
        <ul className="rv-kids">
          {node.children.map((k) => (
            <Item key={k.cand.name} node={k} depth={depth + 1} selected={selected} linked={linked} open={open} highlight={highlight}
                  toggle={toggle} toggleLink={toggleLink} toggleOpen={toggleOpen} onHover={onHover} chunksTotal={chunksTotal} existingByName={existingByName} t={t} />
          ))}
        </ul>
      )}
    </li>
  );
}

// Review van een analyse: boom van kandidaten met selectie, bestaande
// concepten koppelbaar, onderaan "Voeg toe aan mijn kaart".
export default function ReviewPanel({ analysis, highlight, busy, onCommit, onHoverExisting, onClose }) {
  const { t } = useT();
  const [selected, setSelected] = useState(new Set());
  const [linked, setLinked] = useState(new Set());
  const [open, setOpen] = useState(new Set());
  const listRef = useRef(null);

  const cands = analysis?.candidates || [];
  const tree = useMemo(() => buildReviewTree(cands, analysis?.relations || []), [cands, analysis?.relations]);
  const chunksTotal = analysis?.meta?.chunks || 1;
  const existingByName = useMemo(() => new Set(cands.filter((c) => c.existing).map((c) => c.name)), [cands]);

  useEffect(() => { setSelected(new Set()); setLinked(new Set()); setOpen(new Set()); }, [analysis?.source_id]);
  useEffect(() => {
    if (!highlight) return;
    setOpen((o) => new Set([...o, highlight]));
    const el = listRef.current?.querySelector('[data-name="' + CSS.escape(highlight) + '"]');
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [highlight]);

  if (!analysis) return null;

  const selectable = (n) => !n.cand.existing;
  const toggle = (node) => {
    const names = [node.cand.name, ...descendants(node)].filter((n) => !cands.find((c) => c.name === n)?.existing);
    setSelected((s) => {
      const next = new Set(s);
      const allOn = names.every((n) => next.has(n));
      for (const n of names) { if (allOn) next.delete(n); else next.add(n); }
      return next;
    });
  };
  const toggleLink = (name) => setLinked((s) => { const n = new Set(s); n.has(name) ? n.delete(name) : n.add(name); return n; });
  const toggleOpen = (name) => setOpen((s) => { const n = new Set(s); n.has(name) ? n.delete(name) : n.add(name); return n; });
  const selectAll = () => setSelected(new Set(cands.filter((c) => !c.existing).map((c) => c.name)));
  const selectMains = () => setSelected(new Set(tree.roots.filter(selectable).map((r) => r.cand.name)));
  const selectNone = () => { setSelected(new Set()); setLinked(new Set()); };
  const count = selected.size + linked.size;

  const commit = () => {
    const sel = cands.filter((c) => selected.has(c.name));
    const link = cands.filter((c) => linked.has(c.name)).map((c) => ({ name: c.existing.name, mentions: c.mentions, context: c.context, importance: c.importance }));
    onCommit(sel, link);
  };

  const renderItem = (node, depth) => (
    <Item key={node.cand.name} node={node} depth={depth} selected={selected} linked={linked} open={open} highlight={highlight}
          toggle={toggle} toggleLink={toggleLink} toggleOpen={toggleOpen} onHover={onHoverExisting} chunksTotal={chunksTotal} existingByName={existingByName} t={t} />
  );

  return (
    <aside className="panel review" aria-label={t("review.title")}>
      <div className="panel-head">
        <div className="title">
          <div>
            <div className="eyebrow">{t("review.title")}</div>
            <h2>{analysis.title}</h2>
            {analysis.meta?.analysis_method === "ai_video_analysis" && <p className="hint">{t("video.provenance")}</p>}
          </div>
          <div className="tools">
            <button className="icon-btn x" onClick={onClose} aria-label={t("common.close")}>×</button>
          </div>
        </div>
      </div>

      <div className="rv-bar">
        <div className="rv-quick">
          <button className="textlink" onClick={selectAll}>{t("review.all")}</button>
          <button className="textlink" onClick={selectMains}>{t("review.mains")}</button>
          <button className="textlink" onClick={selectNone}>{t("review.none")}</button>
        </div>
        <span className="hint" >
          {t("review.count", { n: cands.length })}
          {analysis.meta?.chunks > 1 ? " · " + t("review.parts", { n: analysis.meta.chunks }) : ""}
        </span>
      </div>

      <div className="rv-scroll" ref={listRef}>
        {tree.roots.length > 0 && (
          <ul className="rv-list">
            {tree.roots.map((r) => <div key={r.cand.name} data-name={r.cand.name}>{renderItem(r, 0)}</div>)}
          </ul>
        )}
        {tree.loose.length > 0 && (
          <>
            <div className="sect-title" style={{ margin: "14px 0 6px" }}>{t("review.loose")}</div>
            <ul className="rv-list">
              {tree.loose.map((c) => <div key={c.name} data-name={c.name}>{renderItem({ cand: c, kind: "loose", children: [] }, 0)}</div>)}
            </ul>
          </>
        )}
        {!cands.length && <p className="hint">{t("review.empty")}</p>}
      </div>

      <div className="rv-foot">
        <span>{t("review.selected", { n: count })}</span>
        <button className="btn primary review-commit" disabled={!count || busy} onClick={commit}>
          {busy ? <><span className="spinner" /> {t("review.committing")}</> : t("review.commit")}
        </button>
      </div>
    </aside>
  );
}
