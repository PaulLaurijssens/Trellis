"use client";
import { useMemo } from "react";
import { buildIndex, findNode, subtree } from "../lib/tree";
import { useT } from "../lib/i18n";

const check = (n) => (n.status === "learned" ? " ✓" : "");

// Compacte variant: de node zelf, voorkennis eronder, verwanten ernaast.
function Compact({ tree, onSelect, onConnections, busy }) {
  const { t } = useT();
  const { node, prereqs, dependents, related } = tree;
  const rows = [];
  if (prereqs.length) rows.push({ key: "pre", label: t("tree.buildsOn"), items: prereqs.map((p) => p.node) });
  if (dependents.length) rows.push({ key: "dep", label: t("tree.leadsTo"), items: dependents.map((p) => p.node) });
  if (related.length) rows.push({ key: "rel", label: t("tree.related"), items: related, dashed: true });
  if (tree.parts.length) rows.push({ key: "parts", label: t("tree.parts"), items: tree.parts, dashed: true });
  if (tree.wholes.length) rows.push({ key: "wholes", label: t("relation.PART_OF"), items: tree.wholes, dashed: true });
  return (
    <div className="tree-rows">
      <div className="tree-row">
        <span className={"chip here " + node.status}>{node.name}</span>
        <span className="lbl">{t("tree.here")}</span>
      </div>
      {rows.map((r) => (
        <div key={r.key} className={"tree-row sub" + (r.dashed ? " dashed" : "")}>
          <span className="lbl">{r.label}</span>
          {r.items.map((n) => (
            <button key={n.id} className={"chip " + n.status} onClick={() => onSelect(n.name)} title={n.name + " — " + n.status}>
              {n.name}{check(n)}
            </button>
          ))}
        </div>
      ))}
      {!rows.length && (
        <div className="tree-empty"><p>{t("tree.empty")}</p>{onConnections && <button className="btn ghost" disabled={busy} onClick={onConnections}>{t("tree.connections")}</button>}</div>
      )}
    </div>
  );
}

function Node({ n, here, onSelect, tag }) {
  const { t } = useT();
  return (
    <button className={"tree-node " + n.status + (here ? " here" : "")} onClick={() => onSelect(n.name)} title={n.name + " — " + n.status}>
      <i />{n.name}{here && <small>{t("tree.here")}</small>}{tag}
    </button>
  );
}

// Fullscreen-variant: boomstructuur twee niveaus diep, zoals in het ontwerp.
function Big({ tree, onSelect, onConnections, busy }) {
  const { t } = useT();
  const { node, prereqs, dependents, related } = tree;
  const renderDown = (items) => items.length ? (
    <div className="tree-kids">
      {items.map(({ node: n, kids }) => (
        <div key={n.id}>
          <Node n={n} onSelect={onSelect} />
          {renderDown(kids)}
        </div>
      ))}
    </div>
  ) : null;
  // Boven de node: waar dit concept naartoe leidt, geneste ouders eerst.
  const renderUp = (items, inner) => {
    if (!items.length) return inner;
    const [first, ...rest] = items;
    return (
      <>
        {renderUp(first.parents, null)}
        <div style={first.parents.length ? { marginLeft: 11, borderLeft: "1px solid rgba(130,160,200,0.18)", paddingLeft: 14 } : undefined}>
          <Node n={first.node} onSelect={onSelect} />
          <div className="tree-kids">
            {inner}
            {rest.map((d) => <Node key={d.node.id} n={d.node} onSelect={onSelect} />)}
          </div>
        </div>
      </>
    );
  };
  const core = (
    <div>
      <Node n={node} here onSelect={onSelect} />
      {renderDown(prereqs)}
      {related.length > 0 && (
        <div className="tree-kids dashed">
          <div className="tree-tag">{t("tree.related")}</div>
          {related.map((r) => <Node key={r.id} n={r} onSelect={onSelect} />)}
        </div>
      )}
      {tree.parts.length > 0 && <div className="tree-kids dashed"><div className="tree-tag">{t("tree.parts")}</div>{tree.parts.map((n) => <Node key={n.id} n={n} onSelect={onSelect} />)}</div>}
      {tree.wholes.length > 0 && <div className="tree-kids dashed"><div className="tree-tag">{t("relation.PART_OF")}</div>{tree.wholes.map((n) => <Node key={n.id} n={n} onSelect={onSelect} />)}</div>}
    </div>
  );
  return (
    <div className="tree-big">
      {dependents.length ? <><div className="tree-tag">{t("tree.leadsTo")}</div>{renderUp(dependents, core)}</> : core}
      {!prereqs.length && !related.length && !dependents.length && !tree.parts.length && !tree.wholes.length && (
        <div className="tree-empty"><p>{t("tree.empty")}</p>{onConnections && <button className="btn ghost" disabled={busy} onClick={onConnections}>{t("tree.connections")}</button>}</div>
      )}
    </div>
  );
}

export default function MiniTree({ graph, name, status, big, onSelect, onConnections, busy }) {
  const { t } = useT();
  const tree = useMemo(() => {
    const index = buildIndex(graph);
    const node = findNode(index, name) || { id: "self", name, status: status || "learning", degree: 0 };
    return subtree(index, node, big ? 2 : 1);
  }, [graph, name, status, big]);
  if (!tree) return null;
  return (
    <div className="tree">
      <div className="sect-title">{t("panel.tree")}</div>
      {big ? <Big tree={tree} onSelect={onSelect} onConnections={onConnections} busy={busy} /> : <Compact tree={tree} onSelect={onSelect} onConnections={onConnections} busy={busy} />}
    </div>
  );
}
