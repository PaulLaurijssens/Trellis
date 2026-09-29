"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { LearningHome } from "../components/LearningDirection";
import LearningPath from "../components/LearningPath";
import CommandBar from "../components/CommandBar";
import MentorPanel from "../components/MentorPanel";
import ConceptPreview from "../components/ConceptPreview";
import Profile from "../components/Profile";
import ProfileMenu from "../components/ProfileMenu";
import Toasts from "../components/Toasts";
import ReviewPanel from "../components/ReviewPanel";
import { api } from "../lib/api";
import { buildIndex, findNode, subtree } from "../lib/tree";
import { LangContext, DICTS, LANGS } from "../lib/i18n";
import { readTrail, visitTrail } from "../lib/learningTrail.mjs";
import { usePlan, nextInPlan } from "../lib/curriculum";
import { teach } from "../lib/teach";
import Gate from "../components/Gate";
import { session, subscribe, getPerson, getPersonInfo } from "../lib/session";

const GraphView = dynamic(() => import("../components/GraphView"), { ssr: false });

const FALLBACK_LEVELS = { 1: "kind", 2: "scholier", 3: "professional", 4: "developer", 5: "expert" };
const LANG_KEY = "trellis.lang";
const APPEAR_MS = 2000;
const trailKey = () => "trellis.learningTrail." + (getPerson() || "anon");

const Brand = () => (
  <div className="brand" aria-label="Trellis">
    <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
      <line x1="11" y1="19" x2="11" y2="10" stroke="#54A9FF" strokeWidth="1.4" />
      <line x1="11" y1="10" x2="5" y2="5" stroke="#54A9FF" strokeWidth="1.4" />
      <line x1="11" y1="10" x2="17" y2="6" stroke="#54A9FF" strokeWidth="1.4" />
      <circle cx="11" cy="19" r="2" fill="#54A9FF" />
      <circle cx="5" cy="5" r="1.6" fill="none" stroke="#54A9FF" strokeWidth="1.3" />
      <circle cx="17" cy="6" r="1.6" fill="none" stroke="#5FCE9E" strokeWidth="1.3" />
    </svg>
    <span>Trellis</span>
  </div>
);

// The app renders only with a session. Before that: first-run setup or login (Gate). Splitting the
// two keeps every data-loading effect of the app from firing (and failing with 401) before login.
export default function Page() {
  const [status, setStatus] = useState(null);
  const [gateLang, setGateLang] = useState("en");
  useEffect(() => {
    try { const l = localStorage.getItem(LANG_KEY); if (l && DICTS[l]) setGateLang(l); } catch {}
    session.status().then(setStatus).catch(() => setStatus({ unavailable: true }));
    // A 401 later (expired cookie, restarted server) drops the person: back to the gate.
    return subscribe((person) => { if (!person) session.status().then(setStatus).catch(() => {}); });
  }, []);
  if (!status) return null;
  if (status.unavailable) return <div className="gate-screen"><div className="gate"><h1>Trellis</h1><p className="gate-lead">The API is not reachable. Is the server running? <button className="textlink" onClick={() => location.reload()}>Retry</button></p></div></div>;
  if (!status.authenticated) {
    const setLang = (l) => { setGateLang(l); try { localStorage.setItem(LANG_KEY, l); } catch {} };
    return <LangContext.Provider value={{ lang: gateLang, setLang }}><Gate status={status} onDone={() => session.status().then(setStatus)} /></LangContext.Provider>;
  }
  return <App key={status.person.id} onLogout={() => session.logout().then(() => session.status().then(setStatus))} />;
}

function App({ onLogout }) {
  const [searchRequest,setSearchRequest] = useState(0);
  const [clusterRequest,setClusterRequest] = useState(null);
  const [clusters,setClusters] = useState([]);
  const [clusterScope,setClusterScope] = useState("");
  const [reviewTopic,setReviewTopic] = useState(null);
  const [journey, setJourney] = useState(null);
  const [journeyError, setJourneyError] = useState(false);
  const [examples, setExamples] = useState([]);
  const [journeyBusy, setJourneyBusy] = useState(false);
  const [levels, setLevels] = useState(FALLBACK_LEVELS);
  const [exploreView, setExploreView] = useState("graph");
  const [legendOpen, setLegendOpen] = useState(false);
  const [graph, setGraph] = useState({ nodes: [], links: [] });
  const [loaded, setLoaded] = useState(false);
  const [analysis, setAnalysis] = useState(null);  // laatste analyse: {source_id, title, candidates, relations, meta}
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewHighlight, setReviewHighlight] = useState(null);
  const [hoverName, setHoverName] = useState(null); // bestaande node oplichten vanuit het review-paneel
  const [fresh, setFresh] = useState(new Map());     // net toegevoegde nodes -> verschijn-glow
  const [query, setQuery] = useState("");          // zoekterm uit de command bar: filtert/highlight de graph
  const [lang, setLangState] = useState(getPersonInfo()?.language || "en");
  const [selected, setSelected] = useState(null);  // concept-detail uit /concept/{name}
  const [chat, setChat] = useState(null);          // {session_id, messages, state}
  const [teachEnabled, setTeachEnabled] = useState(false);   // feature flag, asked at runtime (no rebuild to flip)
  useEffect(() => { teach.flags().then((f) => setTeachEnabled(!!f.enabled)); }, []);
  const [trail, setTrail] = useState([]);
  const [level, setLevel] = useState(3);
  const [expanded, setExpanded] = useState(false);
  const [ambientMotion, setAmbientMotion] = useState(true);
  const [motionSaving, setMotionSaving] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const [busy, setBusy] = useState({});            // {analyze, learn, commit, explain, chat, ending, mark, rebuild}

  const graphRef = useRef({ nodes: [], links: [] });
  const navigationRef = useRef(0);
  const trailRef = useRef([]);
  const activeNameRef = useRef(null);
  const sourceRef = useRef(null);                  // {source_id, title, payload} — de gebruiker ziet het id nooit
  const flag = (k, v) => setBusy((b) => ({ ...b, [k]: v }));

  const t = useCallback((key, vars) => {
    let str = (DICTS[lang] && DICTS[lang][key]) ?? DICTS.nl[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) str = str.replaceAll("{" + k + "}", String(v));
    return str;
  }, [lang]);

  // Taal: localStorage én Person.ui_language, zodat de backend hem kent.
  const setLang = useCallback(async (l) => {
    if (!DICTS[l]) return;
    await api.patchProfile({ ui_language: l });
    setLangState(l);
    try { localStorage.setItem(LANG_KEY, l); } catch {}
  }, []);
  useEffect(() => {
    // Geen lokale keuze: de voorkeur op de server volgen.
    let local = null;
    try { local = localStorage.getItem(LANG_KEY); } catch {}
    if (local && DICTS[local]) setLangState(local);
    api.memory().then((m) => { if (m.ui_language && DICTS[m.ui_language]) {setLangState(m.ui_language);try {localStorage.setItem(LANG_KEY,m.ui_language);}catch{}} }).catch(() => {});
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update(); media.addEventListener("change", update);
    try { const value = localStorage.getItem("trellis.ambientMotion"); if (value !== null) setAmbientMotion(value !== "false"); } catch {}
    api.memory().then((m) => { if (typeof m.ambient_motion === "boolean") { setAmbientMotion(m.ambient_motion); try { localStorage.setItem("trellis.ambientMotion", String(m.ambient_motion)); } catch {} } }).catch(() => {});
    return () => media.removeEventListener("change", update);
  }, []);

  // ---- meldingen ----
  const closeToast = useCallback((id) => {
    setToasts((ts) => {
      const t = ts.find((x) => x.id === id);
      t?.onDismiss?.();
      return ts.filter((x) => x.id !== id);
    });
  }, []);
  const toast = useCallback((t) => {
    const id = Date.now() + Math.random();
    setToasts((ts) => [...ts, { id, ...t }]);
    if (t.ttl) setTimeout(() => setToasts((ts) => ts.filter((x) => x.id !== id)), t.ttl);
    return id;
  }, []);
  // Backend-fouten kunnen lange stacktrace-achtige teksten zijn; de toast
  // toont de kern, de volledige tekst zit in de tooltip.
  const fail = useCallback((e) => {
    const full = e?.message || String(e);
    const short = full.length > 180 ? full.slice(0, 177).replace(/\s+\S*$/, "") + "…" : full;
    toast({ type: "error", text: short, title: full });
  }, [toast]);

  const refreshJourney = useCallback(async () => {
    try { const [data,saved] = await Promise.all([api.journey(),api.examples()]);setJourney(data);setExamples(saved);setJourneyError(false); }
    catch { setJourneyError(true); }
  }, []);
  useEffect(() => { refreshJourney(); }, [refreshJourney, expanded, chat?.session_id, chat?.messages?.length]);
  const journeyAction = async action => {
    if(journeyBusy)return false;
    setJourneyBusy(true);
    try {await action();await refreshJourney();return true;}
    catch(e){fail(e);return false;}
    finally{setJourneyBusy(false);}
  };

  // Dismiss disclosure menus on outside pointer/focus or Escape; keep ancestor
  // disclosures open while interacting with nested content.
  useEffect(()=>{
    const dismiss=e=>document.querySelectorAll("details[open]").forEach(el=>{if(!el.contains(e.target))el.open=false;});
    const escape=e=>{if(e.key==="Escape")document.querySelectorAll("details[open]").forEach(el=>{el.open=false;});};
    document.addEventListener("click",dismiss,true);document.addEventListener("keydown",escape);
    return()=>{document.removeEventListener("click",dismiss,true);document.removeEventListener("keydown",escape);};
  },[]);
  const focusSearch=()=>{setExpanded(false);setSearchRequest(n=>n+1);};

  const changeAmbientMotion = async (enabled) => {
    if (motionSaving) return;
    const previous = ambientMotion;
    setMotionSaving(true); setAmbientMotion(enabled);
    try { await api.patchProfile({ ambient_motion: enabled }); try { localStorage.setItem("trellis.ambientMotion", String(enabled)); } catch {} }
    catch (e) { setAmbientMotion(previous); fail(e); }
    finally { setMotionSaving(false); }
  };

  // Posities van bestaande nodes bewaren, anders springt de hele graph
  // bij elke verversing terug naar een nieuwe simulatie.
  const refreshGraph = useCallback(async () => {
    const g = await api.graph();
    const prev = new Map(graphRef.current.nodes.map((n) => [n.id, n]));
    // Nieuwe nodes starten bij een bestaande buur (via de eerste link), zodat
    // ze niet vanaf de rand komen aanvliegen.
    const nodes = g.nodes.map((n) => {
      const p = prev.get(n.id);
      if (p) return { ...n, x: p.x, y: p.y, vx: 0, vy: 0 };
      const link = g.edges.find((e) => e.source === n.id || e.target === n.id);
      const other = link && prev.get(link.source === n.id ? link.target : link.source);
      return other && other.x != null
        ? { ...n, x: other.x + (Math.random() - 0.5) * 60, y: other.y + (Math.random() - 0.5) * 60 }
        : n;
    });
    const next = { nodes, links: g.edges };
    graphRef.current = next;
    setGraph(next);
  }, []);

  useEffect(() => {
    api.levels().then(setLevels).catch(() => {});
    refreshGraph().catch(fail).finally(() => setLoaded(true));
  }, [refreshGraph, fail]);

  const loadChat = useCallback(async (name, navigation = navigationRef.current) => {
    try {
      const h = await api.chatHistory(name);
      if (navigation !== navigationRef.current) return;
      setChat(h);
      setLevel(h.level || h.state?.level || 3);
    } catch {
      if (navigation === navigationRef.current) setChat(null);
    }
  }, []);

  const saveTrail = useCallback((path) => {
    trailRef.current = path;
    setTrail(path);
    try { sessionStorage.setItem(trailKey(), JSON.stringify(path)); } catch {}
  }, []);

  const openConcept = useCallback(async (name, options = {}) => {
    const navigation = ++navigationRef.current;
    const base = options.path || (options.branch ? trailRef.current : []);
    setReviewOpen(false);          // mentor- en review-paneel sluiten elkaar uit
    setChat(null);
    try {
      const detail = await api.concept(name);
      if (navigation !== navigationRef.current) return;
      activeNameRef.current = detail.name;
      setSelected(detail);
      setExpanded(!!(options.learn || options.branch));
      setLevel(3);
      saveTrail(visitTrail(base, detail.name));
      await loadChat(detail.name, navigation);
    } catch (e) {
      if (navigation === navigationRef.current) fail(e);
    }
  }, [loadChat, fail, saveTrail]);

  useEffect(() => {
    let path = [];
    try { path = readTrail(sessionStorage.getItem(trailKey())); } catch {}
    if (path.length) openConcept(path[path.length - 1], { path, learn: true });
  }, [openConcept]);

  const closePanel = () => {
    navigationRef.current++;
    activeNameRef.current = null;
    saveTrail([]);
    setSelected(null); setChat(null); setExpanded(false);
  };

  // ---- kandidaten-review ----
  const showCandidates = (res, payload) => {
    sourceRef.current = { source_id: res.source_id, title: res.title, payload,
                          relations: res.candidate_relations || [], meta: res.meta || {} };
    if (!res.candidates.length) {
      setAnalysis(null);
      toast({ type: "info", text: t("toast.none", { title: res.title }), ttl: 8000 });
      return;
    }
    setAnalysis({ source_id: res.source_id, title: res.title, candidates: res.candidates,
                  relations: res.candidate_relations || [], meta: res.meta || {} });
    setReviewHighlight(null);
    navigationRef.current++;
    activeNameRef.current = null;
    saveTrail([]);
    setSelected(null); setChat(null); setExpanded(false);   // review vervangt het mentorpaneel
    setReviewOpen(true);
  };
  const revealCandidate = (name) => {
    if (!analysis) return;
    navigationRef.current++;
    activeNameRef.current = null;
    saveTrail([]);
    setSelected(null); setChat(null); setExpanded(false);
    setReviewOpen(true);
    setReviewHighlight(name);
  };
  const markFresh = (names) => {
    const now = Date.now();
    setFresh((m) => { const n = new Map(m); for (const x of names) n.set(x, now); return n; });
    setTimeout(() => setFresh((m) => { const n = new Map(m); for (const x of names) n.delete(x); return n; }), APPEAR_MS + 100);
  };
  const commitCandidates = async (selectedCands, linkItems) => {
    if (!analysis) return;
    flag("commit", true);
    try {
      const r = await api.commitCandidates({
        source_id: analysis.source_id, selected: selectedCands, link_existing: linkItems,
        relations: analysis.relations,
      });
      await refreshGraph();
      markFresh([...r.created, ...r.linked]);
      const done = new Set([...selectedCands.map((c) => c.name), ...linkItems.map((l) => l.name)]);
      setAnalysis((a) => a && { ...a, candidates: a.candidates.filter((c) => !done.has(c.name) && !done.has(c.existing?.name)) });
      setReviewOpen(false);
      toast({ type: "ok", ttl: 8000,
              text: t("toast.committed", { created: r.created.length, linked: r.linked.length, rels: r.relations_applied.length }) });
    } catch (e) {
      if (e.status === 404 && /source_id/i.test(e.message)) {
        toast({ type: "error", text: t("toast.sourceExpired"),
                action: sourceRef.current?.payload ? { label: t("toast.retry"), onClick: retryAnalyze } : null });
        setReviewOpen(false);
      } else {
        fail(e);
      }
    } finally {
      flag("commit", false);
    }
  };

  // ---- analyseren ----
  // De client kiest een job-id en pollt de voortgang: "deel 4 van 9".
  const pollProgress = (jobId, label, hint) => {
    const phaseText = (st) => {
      if (!st) return "";
      if (st.phase === "extract" && st.total) return t("busy.part", { done: st.done, total: st.total });
      if (["segment", "merge", "relations", "fetch", "video"].includes(st.phase)) return t("busy." + st.phase);
      return "";
    };
    const timer = setInterval(async () => {
      try {
        const st = await api.ingestStatus(jobId);
        flag("analyze", { label: label + phaseText(st) + "…", hint, progress: st });
      } catch {}
    }, 1000);
    return () => clearInterval(timer);
  };
  const runAnalyze = async (label, hint, call, payload) => {
    const jobId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()));
    flag("analyze", { label: label + "…", hint });
    const stop = pollProgress(jobId, label, hint);
    try {
      const res = await call(jobId);
      showCandidates(res, payload);
      for (const w of res.meta?.warnings || []) toast({ type: "error", text: w });
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      stop();
      flag("analyze", false);
    }
  };
  const handleAnalyze = (payload) => runAnalyze(
    t("busy.analyze", { title: payload.title }), t("busy.analyzeHint"),
    (jobId) => api.analyze(payload, jobId), payload);
  const handleFile = (file, title) => runAnalyze(
    t("busy.file", { name: file.name }), t("busy.fileHint"),
    (jobId) => api.analyzeFile(file, title, jobId), { file: file.name });
  const handleUrl = (url) => runAnalyze(
    t("busy.url"), t("busy.urlHint"),
    (jobId) => api.analyzeUrl(url, jobId), { url });
  const handlePodcast = (episode) => runAnalyze(
    t("busy.podcast", { title: episode.title }), t("busy.podcastHint"),
    (jobId) => api.analyzePodcast(episode, jobId), { podcast: episode });
  const handleYoutube = (url) => runAnalyze(
    t("busy.youtube"), t("busy.youtubeHint"),
    (jobId) => api.analyzeYoutube(url, jobId, lang), { youtube: url });
  // "Genereer bron over dit onderwerp": het model schrijft bronmateriaal,
  // de kandidaten daaruit gaan naar het review-paneel.
  const handleGenerate = (topic, depth) => runAnalyze(
    t("busy.topic", { topic }), t("busy.topicHint"),
    () => api.ingestTopic(topic, depth), { topic, depth });
  const retryAnalyze = () => {
    const p = sourceRef.current?.payload;
    if (!p) return;
    if (p.youtube) handleYoutube(p.youtube); else if (p.url) handleUrl(p.url); else if (p.podcast) handlePodcast(p.podcast); else if (p.topic) handleGenerate(p.topic, p.depth); else if (!p.file) handleAnalyze(p);
  };

  // ---- leren: elke /learn loopt hier langs ----
  const runLearn = async (body, busyKey, busyVal = true) => {
    const navigation = ++navigationRef.current;
    const base = busyKey === "learn" ? [] : trailRef.current;
    flag(busyKey, busyVal);
    try {
      const res = await api.learn(body);
      await refreshGraph();
      const detail = await api.concept(res.concept);
      if (navigation !== navigationRef.current) return res;
      activeNameRef.current = detail.name;
      setSelected(detail);
      setExpanded(true);
      saveTrail(visitTrail(base, detail.name));
      await loadChat(res.concept, navigation);
      return res;
    } catch (e) {
      if (e.status === 404 && /source_id/i.test(e.message)) {
        toast({
          type: "error",
          text: t("toast.sourceExpired"),
          action: sourceRef.current?.payload ? { label: t("toast.retry"), onClick: retryAnalyze } : null,
        });
      } else {
        fail(e);
      }
      return null;
    } finally {
      flag(busyKey, false);
    }
  };

  const learnFromBar = (concept, lvl, context = "") => {
    setLevel(lvl);
    return runLearn({ concept, level: lvl, context: context || "" }, "learn",
      { label: t("busy.learn", { concept }) + "…", hint: t("busy.learnHint") });
  };

  // ---- chat ----
  // lessonCtx = {run, activity_id, params} when the question comes from inside an interactive lesson:
  // same mentor pipeline, plus what the learner is looking at.
  const sendChat = async (message, lvl = level, lessonCtx = null) => {
    if (!selected) return;
    const name = selected.name;
    const navigation = navigationRef.current;
    // Eigen bericht meteen tonen; de backend kent de echte seq wel.
    setChat((c) => ({
      ...(c || { messages: [] }),
      messages: [...((c && c.messages) || []), { seq: "tmp-" + Date.now(), role: "user", content: message }],
    }));
    flag("chat", true);
    try {
      if (lessonCtx?.run) await teach.ask(lessonCtx.run.id, { message, level: lvl, concept: name, activity_id: lessonCtx.activity_id || null, params: lessonCtx.params || {} });
      else await api.chat({ concept: name, message, level: lvl });
      await loadChat(name, navigation);
    } catch (e) {
      fail(e);
      await loadChat(name, navigation);
    } finally {
      flag("chat", false);
    }
  };

  // Niveauklik in de paneelheader: niveau zetten én meteen een nieuwe uitleg
  // vragen, als kort gebruikersbericht zodat de historie klopt.
  const changeLevel = (lvl) => {
    if (lvl === level && !selected) return;
    setLevel(lvl);
    if (selected && lvl !== level && !busy.chat) sendChat(t("chat.levelRequest", { n: lvl }), lvl);
  };

  const newChat = async () => {
    if (!selected) return;
    const navigation = navigationRef.current;
    flag("chat", true);
    try {
      await api.newChat(selected.name, level);
      await loadChat(selected.name, navigation);
    } catch (e) {
      fail(e);
    } finally {
      flag("chat", false);
    }
  };

  const endChat = async () => {
    if (!selected) return;
    const navigation = navigationRef.current;
    flag("ending", true);
    try {
      const r = await api.endChat(selected.name);
      await loadChat(selected.name, navigation);
      toast({ type: "ok", text: r.consolidated ? t("toast.ended") : t("toast.endedPlain"), ttl: 6000 });
    } catch (e) {
      await loadChat(selected.name, navigation);
      fail(e);
    } finally {
      flag("ending", false);
    }
  };

  const removeMemory = async (field, nextList) => {
    if (!selected) return;
    const navigation = navigationRef.current;
    try {
      const state = await api.patchConceptMemory(selected.name, { [field]: nextList });
      if (navigation === navigationRef.current) setChat((c) => ({ ...c, state }));
    } catch (e) {
      fail(e);
    }
  };

  const updateLearningMemory = async (action) => {
    if(!selected)return;
    const navigation=navigationRef.current;
    try { const state=await action(selected.name); await refreshGraph(); const detail=await api.concept(selected.name); if(navigation===navigationRef.current){setChat(c=>({...c,state}));setSelected(detail);} }
    catch(e){fail(e);}
  };

  const markLearned = async (name) => {
    const navigation = navigationRef.current;
    flag("mark", true);
    try {
      await api.markLearned(name);
      await refreshGraph();
      const detail = await api.concept(name);
      if (navigation === navigationRef.current) setSelected(detail);
    } catch (e) {
      fail(e);
    } finally {
      flag("mark", false);
    }
  };

  const handleSuggestion = async (suggestion, action) => {
    if (busy.suggestion) return;
    const origin = activeNameRef.current;
    const navigation = navigationRef.current;
    flag("suggestion", suggestion.id);
    try {
      if (action === "dismiss") {
        await api.dismissSuggestion(suggestion.id);
        if (origin) await loadChat(origin, navigation);
      } else {
        const result = await api.acceptSuggestion(suggestion.id, action);
        await refreshGraph();
        if (action === "explore" && navigation === navigationRef.current) {
          await openConcept(result.concept, { branch: true });
        } else {
          if (origin) await loadChat(origin, navigation);
          if (action === "save") toast({ type: "ok", text: t("suggestions.saved", { name: result.concept }), ttl: 5000 });
        }
      }
    } catch (e) {
      fail(e);
    } finally {
      flag("suggestion", false);
    }
  };

  const rebuild = async () => {
    flag("rebuild", true);
    try {
      const r = await api.rebuildMemory();
      toast({ type: "ok", text: t("toast.rebuilt", { sessions: r.sessions, done: r.verwerkt }), ttl: 8000 });
      if (selected) await loadChat(selected.name);
    } catch (e) {
      fail(e);
    } finally {
      flag("rebuild", false);
    }
  };

  // Escape: chip dicht, fullscreen terug naar paneel.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Escape" || profileOpen) return;
      if (expanded) setExpanded(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded, profileOpen]);

  const sidePanel = (!!selected && !expanded) || reviewOpen;
  const treeNeighbors = useMemo(() => {
    if (!selected) return null;
    const index = buildIndex(graph);
    const node = findNode(index, selected.name);
    const tr = node ? subtree(index, node, 1) : null;
    const names = new Set([selected.name]);
    if (tr) {
      tr.prereqs.forEach((p) => names.add(p.node.name));
      tr.dependents.forEach((d) => names.add(d.node.name));
      tr.related.forEach((r) => names.add(r.name));
    }
    return names;
  }, [selected, graph]);
  const empty = loaded && graph.nodes.length === 0;
  // "Volgend onderwerp" in de les volgt het leerpad. Alleen ophalen in de lesweergave; het
  // plan is gedeeld met de Leerpad-weergave en wordt server-side bewaard.
  const { plan: learningPlan } = usePlan(graph, lang, !!(selected && expanded));
  const next = useMemo(() => (selected && expanded ? nextInPlan(learningPlan, graph, selected.name) : null), [learningPlan, graph, selected, expanded]);

  return (
    <LangContext.Provider value={{ lang, setLang }}>
    <div className={"stage redesigned" + (expanded && selected ? " is-learning" : "") + (!reviewOpen ? " has-learning-sidebar" : "") + (selected ? " has-selection" : "")}>
      <header className="workspace-header"><Brand /><nav aria-label={t("nav.label")}><button className={!expanded ? "active" : ""} onClick={() => setExpanded(false)} aria-current={!expanded ? "page" : undefined}>{t("nav.explore")}</button><button className={expanded ? "active" : ""} disabled={!selected} onClick={() => setExpanded(true)} aria-current={expanded ? "page" : undefined}>{t("nav.learn")}</button></nav><button className="profile-trigger" onClick={() => setProfileOpen(true)}>{t("profile.title")}</button></header>
      <div className="explore-workspace" aria-hidden={expanded || undefined} inert={expanded ? "" : undefined}>
      {!reviewOpen && <div className="explore-view-switch" role="group" aria-label={t("explore.viewLabel")}><button aria-pressed={exploreView==='graph'} onClick={()=>setExploreView('graph')}>{t("explore.graph")}</button><button aria-pressed={exploreView==='path'} onClick={()=>setExploreView('path')}>{t("explore.path")}</button></div>}
      <div className="atlas-surface">

      {exploreView==='path' && !reviewOpen && <LearningPath graph={graph} recent={journey?.recent?.concept} goal={journey?.active_goal} due={journey?.review} onCreateGoal={body=>journeyAction(()=>api.createGoal(body))} onLearn={name=>openConcept(name,{learn:true})} onGraph={name=>{setExploreView('graph');openConcept(name);}} />}
      <div style={{display:exploreView==='path'&&!reviewOpen?'none':'contents'}}>
      <GraphView
        data={graph}
        focusRequest={clusterRequest} onGroupsChange={setClusters} onScopeChange={setClusterScope}
        selectedName={selected?.name}
        mentorMode={!!selected}
        treeNeighbors={treeNeighbors}
        highlightQuery={query}
        hoverName={hoverName}
        fresh={fresh}
        empty={empty}
        onSelect={(name) => openConcept(name, { learn: true })}
        onStartLearning={(name) => runLearn({ concept: name, level: 3 }, "learn", { label: t("busy.learn", { concept: name }) + "…" })}
        starting={!!busy.learn}
        ambientMotion={ambientMotion}
        reducedMotion={reducedMotion}
        hidden={expanded || exploreView==='path'}
      />
      </div>
      </div>

      <CommandBar
        clusters={clusters} clusterScope={clusterScope} focusRequest={searchRequest}
        onCluster={key=>setClusterRequest({key,serial:Date.now()})}
        levels={levels}
        level={level}
        nodes={graph.nodes}
        busy={busy.analyze || busy.learn || null}
        empty={empty}
        shifted={false}
        candidates={analysis?.candidates || []}
        onCandidate={revealCandidate}
        onSearch={setQuery}
        onOpen={openConcept}
        onLearn={learnFromBar}
        onGenerate={handleGenerate}
        onAnalyze={handleAnalyze}
        onAnalyzeYoutube={handleYoutube}
        onAnalyzeFile={handleFile} onAnalyzeUrl={handleUrl} onPodcastEpisodes={api.podcastEpisodes} onAnalyzePodcast={handlePodcast}
      />

      {/* Op de telefoon ingeklapt achter één knop (die knop is op desktop verborgen). */}
      <div className={"map-legend" + (legendOpen ? " open" : "")}><button type="button" className="legend-toggle" aria-expanded={legendOpen} onClick={() => setLegendOpen((o) => !o)}><span className="legend-dots" aria-hidden="true">{["learned","learning","queued","suggested"].map((status) => <i key={status} className={"status-dot " + status} />)}</span>{t("legend.title")} {legendOpen ? "▴" : "▾"}</button>{["learned","learning","queued","suggested"].map((status) => <span key={status}><i className={"status-dot " + status} />{t("status." + status)}</span>)}</div>


      {reviewOpen && analysis && !selected && (
        <ReviewPanel
          analysis={analysis}
          highlight={reviewHighlight}
          busy={!!busy.commit}
          onCommit={commitCandidates}
          onHoverExisting={setHoverName}
          onClose={() => { setReviewOpen(false); setHoverName(null); }}
        />
      )}

      {!reviewOpen && <LearningHome data={journey} error={journeyError} nodes={graph.nodes} busy={journeyBusy}
        selectedName={selected?.name} onSearch={focusSearch} onRetry={refreshJourney}
        onOpen={(name,review)=>{setReviewTopic(review?name:null);openConcept(name,{learn:true});}}
        onCreate={body=>journeyAction(()=>api.createGoal(body))} onUpdate={(id,body)=>journeyAction(()=>api.updateGoal(id,body))}>
        {selected && <ConceptPreview concept={selected} graph={graph} recent={journey?.recent?.concept===selected.name} onLearn={()=>setExpanded(true)} onSelect={openConcept} onClose={closePanel} />}
      </LearningHome>}
      </div>

      <Toasts items={toasts} onClose={closeToast} shifted={false} />
      {selected && expanded && (
        <MentorPanel
          concept={selected}
          goal={journey?.active_goal}
          review={reviewTopic===selected.name}
          examples={examples.filter(e=>e.concept===selected.name)}
          journeyBusy={journeyBusy}
          onGoalUpdate={(id,body)=>journeyAction(()=>api.updateGoal(id,body))}
          onSaveExample={seq=>journeyAction(()=>api.saveExample(chat.session_id,seq))}
          onEditExample={(id,text)=>journeyAction(()=>api.editExample(id,text))}
          onDeleteExample={id=>journeyAction(()=>api.deleteExample(id))}
          chat={chat}
          graph={graph}
          levels={levels}
          level={level}
          expanded={expanded}
          busy={{ chat: busy.chat, ending: busy.ending, explain: busy.explain, mark: busy.mark, suggestion: busy.suggestion }}
          trail={trail}
          onReturn={(index) => openConcept(trail[index], { path: trail.slice(0, index + 1), learn: true })}
          onSuggestion={handleSuggestion}
          onLevel={changeLevel}
          onSend={(m, lessonCtx) => sendChat(m, level, lessonCtx)}
          teachEnabled={teachEnabled}
          plan={learningPlan}
          onExploreTopic={(topic) => handleGenerate(topic, level)}
          onNewChat={newChat}
          onEndChat={endChat}
          onRemoveMemory={removeMemory}
          onObservation={(id,state)=>updateLearningMemory(name=>api.correctObservation(name,id,state))}
          onPosition={body=>updateLearningMemory(name=>api.setLearningPosition(name,body))}
          onExplain={(name, lvl) => runLearn({ concept: name, level: lvl }, "explain")}
          onMarkLearned={markLearned}
          onSelect={(name) => openConcept(name, { branch: true })}
          onToggleExpand={() => setExpanded(!expanded)}
          onClose={() => setExpanded(false)}
          nextTopic={next ? { name: next.name, go: () => openConcept(next.name, { learn: true }) } : null}
        />
      )}

      {profileOpen && (
        <div className="overlay" onMouseDown={(e) => { if (e.target === e.currentTarget) setProfileOpen(false); }}>
          <Profile
            ambientMotion={ambientMotion}
            onAmbientMotion={changeAmbientMotion}
            motionSaving={motionSaving}
            reducedMotion={reducedMotion}
            person={{
              load: () => api.memory(),
              patch: (body) => api.patchProfile(body),
              rebuild: () => api.rebuildMemory(),
            }}
            account={getPersonInfo()}
            onLogout={onLogout}
            onClose={() => setProfileOpen(false)}
            onRebuilt={() => selected && loadChat(selected.name)}
          />
        </div>
      )}
    </div>
    </LangContext.Provider>
  );
}
