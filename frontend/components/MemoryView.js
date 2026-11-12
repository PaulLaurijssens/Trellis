"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { useT } from "../lib/i18n";
import MemoryDetail, { StatusBadge } from "./MemoryDetail";
import { counts, demonstrated, lastActivity, openItems, relativeDate, visible } from "../lib/memoryView.mjs";

const FILTER_KEYS = ["all", "learning", "learned", "attention", "planned"];

function useNarrow(query = "(max-width: 760px)") {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setNarrow(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return narrow;
}

// The Memory tab: every concept this learner has memory for, searchable, with one concept's full
// memory beside it (on a phone: list first, the detail replaces it with a Back button).
export default function MemoryView({ concepts, onPosition, onObservation, onPatch, onOpen }) {
  const { t, lang } = useT();
  const narrow = useNarrow();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("recent");
  const [selected, setSelected] = useState(null);
  const [opened, setOpened] = useState(false);       // phone: the detail is showing
  const listRef = useRef(null);
  const detailRef = useRef(null);

  const totals = useMemo(() => counts(concepts), [concepts]);
  const rows = useMemo(() => visible(concepts, { query, filter, sort }), [concepts, query, filter, sort]);
  const current = concepts.find((c) => c.concept === selected) || (!narrow ? rows[0] : null);

  useEffect(() => { if (opened) detailRef.current?.focus(); }, [opened]);
  // Desktop: pin the concept on show, so a correction that moves it out of the filter keeps it open.
  useEffect(() => { if (!narrow && !selected && rows[0]) setSelected(rows[0].concept); }, [narrow, selected, rows]);
  // Phone detail: Escape goes back to the list even when focus was lost with a control that vanished.
  useEffect(() => {
    if (!narrow || !opened) return;
    const onKey = (e) => {
      const active = document.activeElement;
      if (e.key !== "Escape" || (active && active !== document.body && !detailRef.current?.contains(active))) return;
      if (active?.matches?.("textarea, input")) return;      // an open edit handles its own Escape
      e.preventDefault();
      e.stopPropagation();
      back();
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  });

  const open = (name) => {
    setSelected(name);
    if (narrow) setOpened(true);
  };
  const back = () => {
    setOpened(false);
    setTimeout(() => listRef.current?.querySelector(`[data-name="${CSS.escape(selected || "")}"]`)?.focus(), 0);
  };
  const onListKey = (e) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) return;
    const buttons = [...listRef.current.querySelectorAll("button[data-name]")];
    const index = buttons.indexOf(document.activeElement);
    const next = e.key === "Home" ? 0 : e.key === "End" ? buttons.length - 1 : Math.max(0, Math.min(buttons.length - 1, index + (e.key === "ArrowDown" ? 1 : -1)));
    if (!buttons[next]) return;
    e.preventDefault();
    buttons[next].focus();
    if (!narrow) setSelected(buttons[next].dataset.name);
  };

  if (!concepts.length) return <div className="memory-view-empty">
    <h3>{t("memory.emptyTitle")}</h3>
    <p>{t("memory.emptyHint")}</p>
  </div>;

  const meta = (c) => {
    const parts = [];
    const shown = demonstrated(c), open = openItems(c).length, when = relativeDate(lastActivity(c), lang);
    if (shown) parts.push(t("memory.metaShown", { n: shown }));
    if (open) parts.push(t("memory.metaOpen", { n: open }));
    parts.push(c.last_session ? t("memory.metaStudied", { when }) : when ? t("memory.metaAdded", { when }) : t("memory.metaNever"));
    return parts.join(" · ");
  };

  const showList = !narrow || !opened;
  const showDetail = current && (!narrow || opened);

  return <div className={"memory-view" + (narrow && opened ? " drilled" : "")}
>
    <p className="memory-intro">{t("memory.intro")}</p>
    {showList && <div className="memory-master">
      <div className="memory-toolbar">
        <label className="memory-search">
          <span className="sr-only">{t("memory.search")}</span>
          <input type="search" placeholder={t("memory.search")} value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label className="memory-sort">
          <span>{t("memory.sort")}</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {["recent", "name", "evidence"].map((key) => <option key={key} value={key}>{t("memory.sort." + key)}</option>)}
          </select>
        </label>
      </div>
      <div className="memory-filters" role="group" aria-label={t("memory.show")}>
        {FILTER_KEYS.map((key) => <button key={key} aria-pressed={filter === key} className={filter === key ? "on" : ""} onClick={() => setFilter(key)}>
          {t("memory.filter." + key)} <span className="memory-filter-count">{totals[key]}</span>
        </button>)}
      </div>
      <p className="sr-only" aria-live="polite">{t("memory.resultCount", { n: rows.length })}</p>
      {rows.length ? <ul className="memory-rows" ref={listRef} onKeyDown={onListKey} aria-label={t("memory.listLabel")}>
        {rows.map((c) => <li key={c.concept}>
          <button data-name={c.concept} aria-current={current?.concept === c.concept && !narrow ? "true" : undefined} onClick={() => open(c.concept)}>
            <span className="memory-row-top"><b>{c.concept}</b><StatusBadge concept={c} /></span>
            <span className="memory-row-meta">{meta(c)}</span>
          </button>
        </li>)}
      </ul> : <div className="memory-no-match">
        <p>{t("memory.noMatch")}</p>
        <button className="btn ghost" onClick={() => { setQuery(""); setFilter("all"); }}>{t("memory.clearFilters")}</button>
      </div>}
    </div>}
    {showDetail && <div className="memory-pane" ref={detailRef} tabIndex={-1} aria-label={current.concept}>
      {narrow && <button className="textlink memory-back" onClick={back}>← {t("memory.back")}</button>}
      <MemoryDetail key={current.concept} name={current.concept} state={current}
                    onPosition={(body) => onPosition(current.concept, body)}
                    onObservation={(id, state) => onObservation(current.concept, id, state)}
                    onPatch={(field, value) => onPatch(current.concept, { [field]: value })}
                    onOpen={onOpen ? () => onOpen(current.concept) : null} />
    </div>}
  </div>;
}
