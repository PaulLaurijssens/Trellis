"use client";
// First run and login. Shown instead of the app until the API has a session for this browser.
// Setup: name + language -> model provider + key (tested live) -> password. Nothing is stored until the last step.
import { useState } from "react";
import { useT, LANGS } from "../lib/i18n";
import { session } from "../lib/session";
import ProviderForm, { Field, ProviderTest, emptyForm, useProviderCheck } from "./ProviderForm";
import { applySuggestion, formReady, providerBody } from "../lib/providerErrors.mjs";

export function Login({ status, onDone }) {
  const { t } = useT();
  const [personId, setPersonId] = useState(status.profiles?.[0]?.id || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError("");
    try { await session.login({ person_id: personId || null, password }); onDone(); }
    catch (err) { setError(err.status === 401 ? t("gate.wrongPassword") : err.status === 429 ? t("gate.tooMany") : t("gate.noServer")); }
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
  const [form, setForm] = useState(() => emptyForm(status.configured ? "" : "gemini"));
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const check = useProviderCheck();
  // Any edit makes the last test meaningless.
  const edit = (next) => { setForm(next); check.reset(); };
  const ready = formReady(form, providers);
  const test = (value = form) => check.run(providerBody(value, providers, "check"));
  const suggest = (model) => { const next = applySuggestion(form, model); setForm(next); test(next); };
  // "Keep the server settings" cannot be tested here: the key lives in .env.
  const canGo = !form.provider || check.verdict.canProceed;

  const finish = async () => {
    setBusy(true); setError("");
    try {
      await session.setup({ name: name.trim(), language: lang, password, ...providerBody(form, providers, "setup") });
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
      <ProviderForm value={form} onChange={edit} providers={providers} embeddingProviders={status.embedding_providers || []} allowKeepEnv={!!status.configured} />
      {form.provider && <p className="gate-hint">{t("gate.costNote")}</p>}
      {form.provider && <ProviderTest check={check} provider={form.provider} embedProvider={form.embedProvider} disabled={!ready} onTest={() => test()} onSuggest={suggest} />}
      {form.provider && check.verdict.state === "none" && !check.testing && <p className="gate-hint">{t("gate.testFirst")}</p>}
      <div className="gate-row"><button className="btn ghost" onClick={() => setStep(0)}>{t("gate.back")}</button>
        <button className="btn primary" disabled={!canGo || check.testing} onClick={() => setStep(2)}>{check.verdict.state === "busy" ? t("gate.continueAnyway") : t("gate.next")}</button></div>
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
