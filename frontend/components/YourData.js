"use client";
// "Your data": take the memory out (export), bring it in (import), let another AI read it (MCP
// access keys) and rebuild it from the saved conversations.
import { useEffect, useRef, useState } from "react";
import { useT } from "../lib/i18n";
import { api, mcpUrl } from "../lib/api";

const MCP_DOC = "https://github.com/PaulLaurijssens/Trellis/blob/main/docs/MCP.md";
const FORMAT_DOC = "https://github.com/PaulLaurijssens/Trellis/blob/main/docs/MEMORY-FORMAT.md";
// What an import would add or change; concepts_matched is context, shown only next to real changes.
const CHANGE_KEYS = ["concepts_new", "understanding_new", "understanding_merged", "conversations_new", "conversations_updated", "exercises_new", "goals_new", "examples_new"];

function Status({ note }) {
  if (!note) return null;
  return <p className={"data-note" + (note.err ? " err" : "")} role={note.err ? "alert" : "status"}>{note.text}</p>;
}

function Export() {
  const { t } = useT();
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const run = async () => {
    setBusy(true); setNote(null);
    try {
      const { blob, name } = await api.exportMemory();
      const url = URL.createObjectURL(blob);
      const a = Object.assign(document.createElement("a"), { href: url, download: name });
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setNote({ text: t("data.exported", { name }) });
    } catch (e) { setNote({ text: e.message, err: true }); }
    finally { setBusy(false); }
  };
  return <section className="card data-card" aria-labelledby="data-export">
    <h4 id="data-export">{t("data.exportTitle")}</h4>
    <p>{t("data.exportHint")}</p>
    <p className="hint">{t("data.exportExcludes")} <a href={FORMAT_DOC} target="_blank" rel="noopener noreferrer">{t("data.formatLink")} ↗</a></p>
    <div className="row"><button className="btn primary" disabled={busy} onClick={run}>{busy ? <><span className="spinner" /> {t("data.exporting")}</> : t("data.export")}</button></div>
    <Status note={note} />
  </section>;
}

function Import({ onImported }) {
  const { t } = useT();
  const input = useRef(null);
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const reset = () => { setFile(null); setPreview(null); if (input.current) input.current.value = ""; };
  const choose = async (picked) => {
    if (!picked) return;
    setNote(null); setPreview(null); setFile(picked);
    if (picked.size > 24 * 1024 * 1024) { setNote({ text: t("data.tooLarge"), err: true }); reset(); return; }
    setBusy(true);
    try { setPreview(await api.importMemory(picked, "preview")); }
    catch (e) { setNote({ text: e.message, err: true }); reset(); }
    finally { setBusy(false); }
  };
  const apply = async () => {
    setBusy(true); setNote(null);
    try {
      const r = await api.importMemory(file, "apply");
      setNote({ text: t("data.imported", { concepts: r.counts.concepts_new + r.counts.concepts_matched, conversations: r.counts.conversations_new }) });
      reset();
      onImported?.();
    } catch (e) { setNote({ text: e.message, err: true }); }
    finally { setBusy(false); }
  };
  const counts = preview?.counts || {};
  const changes = CHANGE_KEYS.filter((k) => counts[k] > 0);
  return <section className="card data-card" aria-labelledby="data-import">
    <h4 id="data-import">{t("data.importTitle")}</h4>
    <p>{t("data.importHint")}</p>
    <input ref={input} className="sr-only" type="file" tabIndex={-1} aria-label={t("data.chooseFile")} accept=".zip,.json,application/zip,application/json" onChange={(e) => choose(e.target.files?.[0])} />
    {!preview && <div className="row"><button className="btn" disabled={busy} onClick={() => input.current?.click()}>{busy ? <><span className="spinner" /> {t("data.checking")}</> : t("data.chooseFile")}</button></div>}
    <p className="sr-only" role="status">{preview ? t("data.previewTitle", { file: file?.name || "" }) : ""}</p>
    {preview && <div className="data-preview">
      <h5>{t("data.previewTitle", { file: file?.name || "" })}</h5>
      <p className="hint">{t("data.previewFrom", { name: preview.person || "?", date: preview.exported_at ? new Date(preview.exported_at).toLocaleDateString() : "?" })}</p>
      {changes.length > 0 ? <ul className="data-counts">{[...changes, ...(counts.concepts_matched ? ["concepts_matched"] : [])].map((k) => <li key={k}><b>{counts[k]}</b> {t("data.count." + k)}</li>)}</ul>
        : <p>{t("data.nothingNew")}</p>}
      {preview.warnings?.length > 0 && <ul className="data-warnings">{preview.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
      <p className="hint">{t("data.mergeNote")}</p>
      <div className="row">
        <button className="btn primary" disabled={busy} onClick={apply}>{busy ? <><span className="spinner" /> {t("data.importing")}</> : t("data.importConfirm")}</button>
        <button className="btn ghost" disabled={busy} onClick={reset}>{t("menu.cancel")}</button>
      </div>
    </div>}
    <Status note={note} />
  </section>;
}

function Connections() {
  const { t, lang } = useT();
  const [data, setData] = useState(null);
  const [name, setName] = useState("");
  const [conversations, setConversations] = useState(false);
  const [created, setCreated] = useState(null);      // {token, connection}: shown once
  const [confirm, setConfirm] = useState(null);      // id being revoked
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const [copied, setCopied] = useState("");
  const load = () => api.connections().then(setData).catch((e) => setNote({ text: e.message, err: true }));
  useEffect(() => { load(); }, []);
  const url = mcpUrl();
  const command = created && `claude mcp add --transport http trellis ${url} --header "Authorization: Bearer ${created.token}"`;
  const copy = async (text, what) => { try { await navigator.clipboard.writeText(text); setCopied(what); setTimeout(() => setCopied(""), 3000); } catch { setCopied("failed"); } };
  const create = async (e) => {
    e.preventDefault();
    setBusy(true); setNote(null);
    try {
      setCreated(await api.createConnection(name.trim(), conversations ? ["memory:read", "conversations:read"] : ["memory:read"]));
      setName(""); setConversations(false);
      await load();
    } catch (err) { setNote({ text: err.message, err: true }); }
    finally { setBusy(false); }
  };
  const revoke = async (id) => {
    setBusy(true); setNote(null);
    try { await api.revokeConnection(id); setConfirm(null); if (created?.connection.id === id) setCreated(null); await load(); setNote({ text: t("data.revoked") }); document.getElementById("data-connect")?.focus(); }
    catch (err) { setNote({ text: err.message, err: true }); }
    finally { setBusy(false); }
  };
  const when = (v) => v ? new Date(v).toLocaleDateString(lang) : t("data.never");
  return <section className="card data-card" aria-labelledby="data-connect">
    <h4 id="data-connect" tabIndex={-1}>{t("data.connectTitle")}</h4>
    <p>{t("data.connectHint")}</p>
    <p className="hint">{t("data.connectShares")}</p>
    {created && <div className="data-secret" role="status">
      <h5>{t("data.keyCreated", { name: created.connection.name })}</h5>
      <p>{t("data.keyOnce")}</p>
      <div className="data-code"><code>{created.token}</code><button className="btn ghost" onClick={() => copy(created.token, "key")}>{copied === "key" ? t("data.copied") : t("data.copyKey")}</button></div>
      <p className="hint">{t("data.claudeCode")}</p>
      <div className="data-code"><code>{command}</code><button className="btn ghost" onClick={() => copy(command, "command")}>{copied === "command" ? t("data.copied") : t("data.copy")}</button></div>
      <p className="hint">{t("data.otherClients")} <a href={MCP_DOC} target="_blank" rel="noopener noreferrer">{t("data.mcpGuide")} ↗</a></p>
      {copied === "failed" && <p className="data-note err" role="alert">{t("data.copyFailed")}</p>}
      <button className="textlink" onClick={() => setCreated(null)}>{t("data.done")}</button>
    </div>}
    <form className="data-create" onSubmit={create}>
      <label className="data-field"><span>{t("data.connectionName")}</span>
        <input value={name} maxLength={60} placeholder={t("data.connectionPlaceholder")} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="data-check"><input type="checkbox" checked={conversations} onChange={(e) => setConversations(e.target.checked)} /><span>{t("data.includeConversations")}</span></label>
      <div className="row"><button className="btn" disabled={busy || !name.trim()}>{t("data.createKey")}</button></div>
    </form>
    {data?.connections?.length > 0 && <>
      <h5 className="data-subhead">{t("data.activeKeys", { n: data.connections.length })}</h5>
      <ul className="data-keys">{data.connections.map((c) => <li key={c.id}>
        <div><b>{c.name}</b> <code>{c.hint}</code>
          <small>{c.scopes.includes("conversations:read") ? t("data.scopeAll") : t("data.scopeMemory")} · {t("data.created", { date: when(c.created_at) })} · {t("data.lastUsed", { date: when(c.last_used_at) })}</small>
        </div>
        {confirm === c.id
          ? <span className="data-confirm"><button className="btn danger" autoFocus disabled={busy} onClick={() => revoke(c.id)}>{t("data.revokeYes")}</button><button className="btn ghost" onClick={() => { setConfirm(null); setTimeout(() => document.getElementById("revoke-" + c.id)?.focus(), 0); }}>{t("menu.cancel")}</button></span>
          : <button id={"revoke-" + c.id} className="btn ghost" disabled={busy} aria-label={t("data.revokeNamed", { name: c.name })} onClick={() => setConfirm(c.id)}>{t("data.revoke")}</button>}
      </li>)}</ul>
    </>}
    <Status note={note} />
  </section>;
}

function Rebuild({ rebuild, onRebuilt }) {
  const { t } = useT();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);
  const run = async () => {
    setBusy(true); setNote(null);
    try { const r = await rebuild(); setNote({ text: t("profile.rebuilt", { sessions: r.sessions, done: r.verwerkt }) }); onRebuilt?.(); }
    catch (e) { setNote({ text: e.message, err: true }); }
    finally { setBusy(false); setConfirm(false); }
  };
  return <section className="card data-card" aria-labelledby="data-rebuild">
    <h4 id="data-rebuild">{t("menu.rebuild")}</h4>
    <p>{t("data.rebuildHint")}</p>
    <div className="row">{confirm ? <>
      <span>{t("menu.rebuildConfirm")}</span>
      <button className="btn" disabled={busy} onClick={run}>{busy ? <><span className="spinner" /> {t("menu.busy")}</> : t("menu.rebuildYes")}</button>
      <button className="btn ghost" onClick={() => setConfirm(false)}>{t("menu.cancel")}</button>
    </> : <button className="btn ghost" onClick={() => setConfirm(true)}>{t("menu.rebuild")}</button>}</div>
    <Status note={note} />
  </section>;
}

export default function YourData({ rebuild, onChanged }) {
  return <div className="profile-data">
    <Export />
    <Import onImported={onChanged} />
    <Connections />
    <Rebuild rebuild={rebuild} onRebuilt={onChanged} />
  </div>;
}
