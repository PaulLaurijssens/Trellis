"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import LevelPills from "./LevelPills";
import { matchNodes } from "../lib/detect";
import { useT } from "../lib/i18n";

const SOURCE_TYPES = ["podcast", "youtube", "paper", "artikel", "tekst"];
const TYPES = ["topic", "youtube", "file", "link", "transcript", "paper"];
const DOT = { learning: "#54A9FF", learned: "#5FCE9E", suggested: "#5B6673", queued: "#C99A3B" };

const SearchIcon = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" aria-hidden="true">
    <circle cx="6.5" cy="6.5" r="5" fill="none" stroke="rgba(160,180,210,0.6)" strokeWidth="1.4" />
    <line x1="10.5" y1="10.5" x2="14" y2="14" stroke="rgba(160,180,210,0.6)" strokeWidth="1.4" />
  </svg>
);
const SpinIcon = () => (
  <svg width="15" height="15" viewBox="0 0 15 15" style={{ animation: "spin 1.6s linear infinite", transformOrigin: "center" }} aria-hidden="true">
    <circle cx="7.5" cy="7.5" r="6" fill="none" stroke="rgba(84,169,255,0.6)" strokeWidth="1.6" strokeDasharray="26 12" />
  </svg>
);

// Zoekveld (standaard) + "Toevoegen": een invoerkaart met vier types.
export default function CommandBar({
  levels, level, nodes, candidates = [], busy, empty, shifted,
  clusters = [], clusterScope = "", onCluster, focusRequest,
  onSearch, onOpen, onLearn, onGenerate, onAnalyze, onAnalyzeYoutube, onCandidate,
  onAnalyzeFile, onAnalyzeUrl, onPodcastEpisodes, onAnalyzePodcast,
}) {
  const { t, lang } = useT();
  const [elapsed, setElapsed] = useState(0);
  const processing = !!busy;
  useEffect(() => {
    if (!processing) { setElapsed(0); return; }
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now()-started)/1000)), 1000);
    return () => clearInterval(timer);
  }, [processing]);
  const [browseMode,setBrowseMode] = useState("topics");
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const [adding, setAdding] = useState(false);
  const [type, setType] = useState("topic");
  const [lvl, setLvl] = useState(level || 3);
  // invoerkaart
  const [term, setTerm] = useState("");
  const [context, setContext] = useState("");
  const [paste, setPaste] = useState("");
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("podcast");
  const [url, setUrl] = useState("");
  const [youtubeFailed,setYoutubeFailed] = useState(false);
  const [file, setFile] = useState(null);
  const [feed, setFeed] = useState(null);          // {title, episodes} of a podcast feed
  const [feedBusy, setFeedBusy] = useState(false);
  const [linkError, setLinkError] = useState("");
  const input = useRef(null);
  const firstField = useRef(null);
  const wrap = useRef(null);

  useEffect(() => { setLvl(level || 3); }, [level]);
  useEffect(() => { onSearch?.(text.trim()); }, [text]);   // graph filteren terwijl je typt

  // Sneltoetsen: "/" of ⌘K naar het zoekveld, ⌘N opent de invoerkaart.
  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      const meta = e.metaKey || e.ctrlKey;
      if (meta && e.key.toLowerCase() === "n") { e.preventDefault(); openCard(); return; }
      if ((meta && e.key.toLowerCase() === "k") || (e.key === "/" && !typing)) {
        e.preventDefault();
        setAdding(false);
        input.current?.focus();setFocused(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onOutside = e => { if (wrap.current && !wrap.current.contains(e.target)) {setFocused(false);setAdding(false);} };
    document.addEventListener("pointerdown",onOutside);document.addEventListener("focusin",onOutside);
    return()=>{document.removeEventListener("pointerdown",onOutside);document.removeEventListener("focusin",onOutside);};
  }, []);
  useEffect(()=>{if(focusRequest){setAdding(false);setBrowseMode("topics");setText("");setFocused(true);requestAnimationFrame(()=>input.current?.focus());}},[focusRequest]);

  useEffect(() => { if (adding) setTimeout(() => firstField.current?.focus(), 30); }, [adding, type]);

  const openCard = () => { setAdding(true); setFocused(false); };
  const closeCard = () => { setAdding(false); setTimeout(() => input.current?.focus(), 30); };
  const resetSearch = () => { setText(""); setFocused(false); input.current?.blur(); };

  const q = text.trim();
  const matches = useMemo(() => (q ? matchNodes(nodes, q) : { exact: null, partial: [] }), [nodes, q]);
  const candMatches = useMemo(() => {
    if (!q || !candidates.length) return [];
    const lq = q.toLowerCase();
    return candidates.filter((g) => g.name.toLowerCase().includes(lq)).slice(0, 5);
  }, [candidates, q]);
  const open = focused && !busy && !adding;
  const activeCluster = clusters.find(g=>g.key===clusterScope);
  const browseNodes = q ? [matches.exact,...matches.partial].filter(Boolean) : [...nodes].sort((a,b)=>a.name.localeCompare(b.name));
  const browseClusters = clusters.filter(g=>!q || g.name.toLowerCase().includes(q.toLowerCase()));

  const submitSearch = () => {
    if (!q) return;
    if (matches.exact) { onOpen(matches.exact.name); resetSearch(); return; }
    onLearn(q, lvl, "");
    resetSearch();
  };
  const onSearchKey = (e) => {
    if (e.key === "Escape") { e.stopPropagation(); setFocused(false); input.current?.blur(); return; }
    if(e.key === "ArrowDown"){e.preventDefault();wrap.current?.querySelector(".cmd-item")?.focus();return;}
    if (e.key === "Enter") { e.preventDefault(); if(browseMode==="clusters"){if(browseClusters[0]){onCluster?.(browseClusters[0].key);resetSearch();}}else submitSearch(); }
  };

  // ---- invoerkaart ----
  const isRss = (u) => /\/(feed|rss)(\/|$)|\.(rss|xml)(\?|$)|feeds?\./i.test(u);
  const canSubmit = type === "topic" ? !!term.trim()
    : type === "youtube" ? /(?:youtube\.com|youtu\.be)\//i.test(url.trim())
    : type === "file" ? !!file
    : type === "link" ? /^https?:\/\/\S+$/i.test(url.trim())
    : !!paste.trim() && !!title.trim();
  const submitCard = async () => {
    if (!canSubmit || busy) return;
    if (type === "topic") onLearn(term.trim(), lvl, context.trim());
    else if (type === "youtube") {
      setYoutubeFailed(false);
      const success = await onAnalyzeYoutube(url.trim());
      if (!success) { setYoutubeFailed(true); return; }
    }
    else if (type === "file") { const ok = await onAnalyzeFile(file, title.trim()); if (!ok) return; }
    else if (type === "link") {
      setLinkError("");
      if (isRss(url.trim()) && !feed) {           // a podcast feed: list the episodes first, the learner picks one
        setFeedBusy(true);
        try { setFeed(await onPodcastEpisodes(url.trim())); } catch (e) { setLinkError(e.message); } finally { setFeedBusy(false); }
        return;
      }
      const ok = await onAnalyzeUrl(url.trim()); if (!ok) return;
    }
    else onAnalyze({ text: paste, title: title.trim(), source_type: sourceType, url: url.trim() });
    clearCard();
    setAdding(false);
  };
  const generate = () => {
    if (!term.trim() || busy) return;
    onGenerate(term.trim(), lvl);
    clearCard();
    setAdding(false);
  };
  const clearCard = () => { setTerm(""); setContext(""); setPaste(""); setTitle(""); setUrl(""); setFile(null); setFeed(null); setLinkError(""); };
  const onCardKey = (e) => {
    if (e.key === "Escape") { e.stopPropagation(); closeCard(); return; }
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submitCard(); return; }
    if (e.key === "Enter" && e.target.tagName === "INPUT") { e.preventDefault(); submitCard(); }
  };
  const pickType = (ty) => {
    setType(ty);
    setSourceType(ty === "paper" ? "paper" : ty === "youtube" ? "youtube" : "podcast");
  };

  return (
    <div className={"cmd-wrap" + (shifted ? " shifted" : "")} ref={wrap}>
      <div className={"cmd" + (focused ? " focus" : "") + (busy ? " busy" : "") + (open || adding ? " open" : "")}>
        {adding ? (
          <div className="cmd-card" aria-busy={processing} onKeyDown={onCardKey} role="dialog" aria-label={t("cmd.add")}>
            <div className="cmd-card-head">
              <div className="seg" role="tablist">
                {TYPES.map((ty) => (
                  <button key={ty} role="tab" aria-selected={type === ty} className={type === ty ? "on" : ""} onClick={() => pickType(ty)}>
                    {t("cmd.type." + ty)}
                  </button>
                ))}
              </div>
              <button className="icon-btn x" onClick={closeCard} aria-label={t("cmd.close")} title="Esc">×</button>
            </div>

            {busy && <div className="import-progress" role="status" aria-live="polite">
              <svg className="extraction-orbit" viewBox="0 0 160 70" aria-hidden="true"><path d="M20 35L60 15L100 40L140 20M20 35L70 60L100 40L140 60"/><circle cx="20" cy="35" r="6"/><circle cx="60" cy="15" r="5"/><circle cx="70" cy="60" r="4"/><circle cx="100" cy="40" r="8"/><circle cx="140" cy="20" r="5"/><circle cx="140" cy="60" r="4"/></svg>
              <div><span className="spinner" /><strong>{busy.label}</strong></div>
              <p>{t("import.running")}</p>
              <span className="import-elapsed" aria-live="off">{Math.floor(elapsed/60)}:{String(elapsed%60).padStart(2,"0")} {t("import.elapsed")}</span>
              <div className="import-activity" aria-hidden="true" />
            </div>}
            {type === "topic" && (
              <div className="cmd-form one">
                <div className="field">
                  <label htmlFor="add-term">{t("cmd.topic.term")}</label>
                  <input id="add-term" ref={firstField} value={term} placeholder={t("cmd.topic.termPh")} onChange={(e) => setTerm(e.target.value)} />
                </div>
                <div className="field">
                  <label htmlFor="add-context">{t("cmd.topic.context")}</label>
                  <textarea id="add-context" rows={2} value={context} placeholder={t("cmd.topic.contextPh")} onChange={(e) => setContext(e.target.value)} />
                </div>
                <div className="cmd-actions">
                  <LevelPills levels={levels} value={lvl} onChange={setLvl} label={t("common.level")} />
                  <span style={{ flex: 1 }} />
                  <button className="btn ghost" disabled={!term.trim() || !!busy} onClick={generate} title={t("cmd.topic.generateHint")}>{t("cmd.topic.generate")}</button>
                  <button className="btn" disabled={!canSubmit || !!busy} onClick={submitCard}>{t("cmd.topic.learn")} ↵</button>
                </div>
              </div>
            )}

            {(type === "transcript" || type === "paper") && (
              <div className="cmd-form one">
                <textarea ref={firstField} className="paste" value={paste} placeholder={t(type === "paper" ? "cmd.paste.paper" : "cmd.paste.transcript")}
                          onChange={(e) => setPaste(e.target.value)} aria-label={t("cmd.type." + type)} />
                <div className="cmd-form">
                  <div className="field">
                    <label htmlFor="add-title">{t("cmd.title")}</label>
                    <input id="add-title" value={title} placeholder={t("cmd.titlePh")} onChange={(e) => setTitle(e.target.value)} />
                  </div>
                  <div className="field">
                    <label htmlFor="add-type">{t("cmd.sourceType")}</label>
                    <select id="add-type" value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
                      {SOURCE_TYPES.map((s) => <option key={s} value={s}>{t("src." + s)}</option>)}
                    </select>
                  </div>
                  <div className="field span2">
                    <label htmlFor="add-url">{t("cmd.url")}</label>
                    <input id="add-url" value={url} placeholder="https://…" onChange={(e) => setUrl(e.target.value)} />
                  </div>
                </div>
                <div className="cmd-actions">
                  <span className="meta">{t("cmd.chars", { n: paste.length.toLocaleString() })}</span>
                  <button className="btn" disabled={!canSubmit || !!busy} onClick={submitCard}>{t("cmd.analyze")} ⌘↵</button>
                </div>
              </div>
            )}

            {type === "file" && (
              <div className="cmd-form one">
                <div className="field">
                  <label htmlFor="add-file">{t("cmd.file")}</label>
                  <input id="add-file" ref={firstField} type="file" accept=".pdf,.mp3,.m4a,.wav,.ogg,.txt,.md,.srt,.vtt,application/pdf,audio/*,text/plain" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                </div>
                <div className="field">
                  <label htmlFor="add-file-title">{t("cmd.title")}</label>
                  <input id="add-file-title" value={title} placeholder={t("cmd.fileTitlePh")} onChange={(e) => setTitle(e.target.value)} />
                </div>
                <p className="hint">{t("cmd.fileHint")}</p>
                <div className="cmd-actions">
                  <button className="btn primary" disabled={!canSubmit || !!busy} onClick={submitCard}>{busy ? <><span className="spinner" /> {t("import.analyzing")}</> : <>{t("cmd.analyze")} ↵</>}</button>
                </div>
              </div>
            )}

            {type === "link" && (
              <div className="cmd-form one">
                <div className="field">
                  <label htmlFor="add-link">{t("cmd.link")}</label>
                  <input id="add-link" ref={firstField} value={url} placeholder="https://…" onChange={(e) => { setUrl(e.target.value); setFeed(null); }} />
                </div>
                <p className="hint">{t("cmd.linkHint")}</p>
                {linkError && <p role="alert" className="hint">{linkError}</p>}
                {feed && <div className="episode-list"><strong>{feed.title}</strong>
                  {feed.episodes.slice(0, 12).map((ep) => <button key={ep.audio_url} type="button" className="episode" disabled={!!busy} onClick={async () => { const ok = await onAnalyzePodcast({ audio_url: ep.audio_url, title: ep.title, feed_title: feed.title }); if (ok) { clearCard(); setAdding(false); } }}>
                    <span>{ep.title}</span><small>{ep.duration}{ep.bytes ? " · " + (ep.bytes / 1e6).toFixed(0) + " MB" : ""}</small></button>)}
                  <p className="hint">{t("cmd.episodeHint")}</p></div>}
                {!feed && <div className="cmd-actions">
                  <button className="btn primary" disabled={!canSubmit || !!busy || feedBusy} onClick={submitCard}>{busy || feedBusy ? <><span className="spinner" /> {t("import.analyzing")}</> : <>{isRss(url.trim()) ? t("cmd.listEpisodes") : t("cmd.analyze")} ↵</>}</button>
                </div>}
              </div>
            )}

            {type === "youtube" && (
              <div className="cmd-form one">
                <div className="field">
                  <label htmlFor="add-yt">{t("cmd.youtubeUrl")}</label>
                  <input id="add-yt" ref={firstField} value={url} placeholder="https://www.youtube.com/watch?v=…" onChange={(e) => setUrl(e.target.value)} />
                </div>
                {youtubeFailed && <p role="alert" className="hint">{t("import.youtubeFailed")}</p>}
                <button type="button" className="textlink" disabled={!!busy} onClick={()=>{setType("transcript");setSourceType("youtube");setYoutubeFailed(false);}}>{t("import.pasteTranscript")}</button>
                <p className="hint">{t("import.transcriptHint")}</p>
                <div className="cmd-actions">
                  <button className="btn primary" disabled={!canSubmit || !!busy} onClick={submitCard}>{busy ? <><span className="spinner" /> {t("import.analyzing")}</> : <>{t("cmd.analyze")} ↵</>}</button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="cmd-row">
            {busy ? <SpinIcon /> : <SearchIcon />}
            {busy ? (
              <span className="busy-text shimmer" aria-live="polite">{busy.label}</span>
            ) : (
              <input
                ref={input}
                type="text"
                value={text}
                placeholder={t("cmd.placeholder")}
                aria-label={t("cmd.searchLabel")}
                onChange={(e) => setText(e.target.value)}
                aria-expanded={open}
                aria-controls="knowledge-navigation"
                onClick={()=>setFocused(true)}
                onFocus={() => setFocused(true)}
                onKeyDown={onSearchKey}
              />
            )}
            {!busy && activeCluster && <button className="scope-chip chip" onClick={()=>onCluster?.("")} aria-label={t("search.clearCluster",{name:activeCluster.name})}>{activeCluster.name} ×</button>}
            {!busy && text && <button className="icon-btn x" onClick={resetSearch} aria-label={t("cmd.clear")} style={{ fontSize: 16 }}>×</button>}
            {!busy && !text && <span className="kbd" title="Sneltoets">/</span>}
            <button className="cta" onClick={openCard} disabled={!!busy} title="⌘N">{t("cmd.add")} +</button>
          </div>
        )}

        {open && (
          <div className="cmd-body" id="knowledge-navigation" onKeyDown={e=>{if(e.key==="Escape"){e.stopPropagation();input.current?.focus();setFocused(false);}}}>
            <div className="search-modes" role="group" aria-label={t("search.browse")}><button aria-pressed={browseMode==="topics"} onClick={()=>setBrowseMode("topics")}>{t("search.topics")} · {nodes.length}</button><button aria-pressed={browseMode==="clusters"} onClick={()=>setBrowseMode("clusters")}>{t("search.clusters")} · {clusters.length}</button></div>
            <p className="search-guide">{t(q ? "search.resultsHint" : "search.hint")}</p>
            <div className="cmd-list">
              {browseMode==="clusters" ? <><button className="cmd-item" onClick={()=>{onCluster?.("");resetSearch();}}>{t("explore.allTopics")}</button>{browseClusters.map(g=><button key={g.key} className="cmd-item" onClick={()=>{onCluster?.(g.key);resetSearch();}}><span className="cluster-search-icon" aria-hidden="true">◌</span>{g.name}<span className="st">{t("search.count",{n:g.count})}</span></button>)}{!browseClusters.length && <p className="search-guide">{t("search.noClusters")}</p>}</> : <>

              {browseNodes.length > 0 && (
                <>
                  <div className="sect">{t("cmd.inMap")}</div>
                  {browseNodes.map((n, i) => (
                    <button key={n.id} className={"cmd-item" + (i === 0 && matches.exact ? " active" : "")} onMouseDown={(e) => e.preventDefault()} onClick={() => { onOpen(n.name); resetSearch(); }}>
                      <span className="dot" style={{ background: DOT[n.status] || DOT.suggested }} />
                      {n.name}
                      <span className="st">{t("status."+n.status)}{i === 0 && matches.exact ? " · ↵" : ""}</span>
                    </button>
                  ))}
                </>
              )}
              {candMatches.length > 0 && (
                <>
                  <div className="sect">{t("cmd.candidates")}</div>
                  {candMatches.map((g) => (
                    <button key={"g" + g.name} className="cmd-item" onMouseDown={(e) => e.preventDefault()} onClick={() => { onCandidate?.(g.name); resetSearch(); }}>
                      <span className="dot" style={{ background: "rgba(201,154,59,0.15)", border: "1px solid #C99A3B" }} />
                      <i style={{ fontStyle: "italic" }}>{g.name}</i>
                      <span className="st">{t("cmd.notSaved")}</span>
                    </button>
                  ))}
                </>
              )}
              {!browseNodes.length && !candMatches.length && (
                <div className="sect" style={{ letterSpacing: 0, textTransform: "none", fontSize: 16 }}>{t("cmd.noMatch")}</div>
              )}
              {q && <div className="cmd-learn">
                <span className="what">
                  {matches.exact ? t("cmd.learnAgain", { q }) : t("cmd.learnNew", { q })}
                </span>
                <LevelPills levels={levels} value={lvl} onChange={setLvl} small label={null} />
                <button className="btn" onMouseDown={(e) => e.preventDefault()} onClick={() => { onLearn(q, lvl, ""); resetSearch(); }}>
                  {t("cmd.learnThis")}{matches.exact ? "" : " ↵"}
                </button>
              </div>}
              </>}
            </div>
          </div>
        )}
      </div>

      {busy && !adding && <div className="cmd-hint">{busy.hint}</div>}

      {empty && !busy && !text && !adding && (
        <>
          <div className="empty-line" />
          <div className="empty-hint">{t("empty.hint")}</div>
        </>
      )}
    </div>
  );
}
