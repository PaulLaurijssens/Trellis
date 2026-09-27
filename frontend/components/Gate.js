"use client";
// First run and login. Shown instead of the app until the API has a session for this browser.
// Setup: name + language -> model provider + key -> password. Nothing is stored until the last step.
import { useEffect, useState } from "react";
import { useT, LANGS } from "../lib/i18n";
import { session } from "../lib/session";

function Field({ label, hint, children }) {
  return <label className="gate-field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

export function Login({ status, onDone }) {
  const { t } = useT();
  const [personId, setPersonId] = useState(status.profiles?.[0]?.id || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError("");
    try { await session.login({ person_id: personId || null, password }); onDone(); }
    catch (err) { setError(err.status === 429 ? t("gate.tooMany") : t("gate.wrongPassword")); }
    finally { setBusy(false); }
  };
  return <form className="gate" onSubmit={submit}>
    <h1>{t("gate.welcomeBack")}</h1>
    {status.profiles?.length > 1 && <Field label={t("gate.who")}><select value={personId} onChange={(e) => setPersonId(e.target.value)}>{status.profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></Field>}
    <Field label={t("gate.password")}><input type="password" autoComplete="current-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
    {error && <p className="gate-error" role="alert">{error}</p>}
    <button className="btn primary" disabled={busy || !password}>{busy ? <span className="spinner" /> : t("gate.login")}</button>
    <p className="gate-hint">{t("gate.forgot")}</p>
  </form>;
}

export function Setup({ status, onDone }) {
  const { t, lang, setLang } = useT();
  const providers = status.providers || {};
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [provider, setProvider] = useState(status.configured ? "" : "gemini");
  const [key, setKey] = useState("");
  const [embedProvider, setEmbedProvider] = useState("");
  const [embedKey, setEmbedKey] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const spec = providers[provider];
  const needsEmbed = spec && !spec.embed;
  useEffect(() => { if (needsEmbed && !embedProvider) setEmbedProvider(status.embedding_providers?.[0] || ""); }, [needsEmbed]); // eslint-disable-line react-hooks/exhaustive-deps

  const finish = async () => {
    setBusy(true); setError("");
    try {
      await session.setup({ name: name.trim(), language: lang, password, provider: provider || null, mentor_key: key || null,
        embed_provider: needsEmbed ? embedProvider : null, embed_key: needsEmbed ? embedKey || null : null });
      onDone();
    } catch (err) { setError(err.message || "error"); }
    finally { setBusy(false); }
  };
  const steps = [
    <>
      <h1>{t("gate.setupTitle")}</h1><p className="gate-lead">{t("gate.setupLead")}</p>
      <Field label={t("gate.name")} hint={t("gate.nameHint")}><input autoFocus maxLength={80} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label={t("gate.language")} hint={t("gate.languageHint")}><div className="seg">{LANGS.map(([code, label]) => <button type="button" key={code} className={code === lang ? "on" : ""} onClick={() => setLang(code)}>{label}</button>)}</div></Field>
      <button className="btn primary" disabled={!name.trim()} onClick={() => setStep(1)}>{t("gate.next")}</button>
    </>,
    <>
      <h1>{t("gate.modelTitle")}</h1><p className="gate-lead">{t("gate.modelLead")}</p>
      {status.configured && <p className="gate-hint">{t("gate.modelFromEnv")}</p>}
      <Field label={t("gate.provider")}><select value={provider} onChange={(e) => { setProvider(e.target.value); setKey(""); }}>
        {status.configured && <option value="">{t("gate.keepEnv")}</option>}
        {Object.entries(providers).map(([id, p]) => <option key={id} value={id}>{p.label}</option>)}</select></Field>
      {spec && <>
        <p className="gate-hint">{spec.key_hint} {spec.key_url && <a href={spec.key_url} target="_blank" rel="noopener noreferrer">{t("gate.getKey")} ↗</a>}</p>
        {spec.key_env && <Field label={t("gate.key")} hint={t("gate.keyHint")}><input type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} /></Field>}
        {needsEmbed && <>
          <Field label={t("gate.embedProvider")} hint={t("gate.embedHint")}><select value={embedProvider} onChange={(e) => setEmbedProvider(e.target.value)}>{(status.embedding_providers || []).map((id) => <option key={id} value={id}>{providers[id].label}</option>)}</select></Field>
          {providers[embedProvider]?.key_env && <Field label={t("gate.embedKey")}><input type="password" autoComplete="off" value={embedKey} onChange={(e) => setEmbedKey(e.target.value)} /></Field>}
        </>}
        <p className="gate-hint">{t("gate.costNote")}</p>
      </>}
      <div className="gate-row"><button className="btn ghost" onClick={() => setStep(0)}>{t("gate.back")}</button>
        <button className="btn primary" disabled={!!spec && !!spec.key_env && !key} onClick={() => setStep(2)}>{t("gate.next")}</button></div>
    </>,
    <>
      <h1>{t("gate.passwordTitle")}</h1><p className="gate-lead">{t("gate.passwordLead")}</p>
      <Field label={t("gate.password")} hint={t("gate.passwordHint")}><input type="password" autoComplete="new-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
      <Field label={t("gate.repeat")}><input type="password" autoComplete="new-password" value={repeat} onChange={(e) => setRepeat(e.target.value)} /></Field>
      {error && <p className="gate-error" role="alert">{error}</p>}
      <div className="gate-row"><button className="btn ghost" onClick={() => setStep(1)}>{t("gate.back")}</button>
        <button className="btn primary" disabled={busy || password.length < 8 || password !== repeat} onClick={finish}>{busy ? <span className="spinner" /> : t("gate.finish")}</button></div>
    </>,
  ];
  return <div className="gate"><div className="gate-steps">{[0, 1, 2].map((i) => <i key={i} className={i <= step ? "on" : ""} />)}</div>{steps[step]}</div>;
}

export default function Gate({ status, onDone }) {
  return <div className="gate-screen">{status.setup_needed ? <Setup status={status} onDone={onDone} /> : <Login status={status} onDone={onDone} />}</div>;
}
