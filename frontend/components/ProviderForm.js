"use client";
// The model provider form, shared by first-run setup (Gate) and the AI provider card in Settings,
// plus the connection test that both run before they save anything.
import { useRef, useState } from "react";
import { useT } from "../lib/i18n";
import { session } from "../lib/session";
import { CUSTOM, EMPTY_CUSTOM, errorText, keyHintText, checkVerdict } from "../lib/providerErrors.mjs";

const PROVIDERS_DOC = "https://github.com/PaulLaurijssens/Trellis/blob/main/docs/PROVIDERS.md";
const keyEnvFor = (model) => { const prefix = (model || "").split("/")[0]; return model.includes("/") && /^[a-z0-9_]+$/i.test(prefix) ? `${prefix.toUpperCase()}_API_KEY` : ""; };

export const emptyForm = (provider = "") => ({ provider, key: "", embedProvider: "", embedKey: "", mentorModel: "", custom: { ...EMPTY_CUSTOM } });

export function Field({ label, hint, children }) {
  return <label className="gate-field"><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>;
}

// value/onChange: the form value (see emptyForm). stored (Settings only): GET /auth/settings, for "keep the stored key".
export default function ProviderForm({ value, onChange, providers = {}, embeddingProviders = [], allowKeepEnv = false, stored = null }) {
  const { t } = useT();
  const v = value;
  const custom = { ...EMPTY_CUSTOM, ...v.custom };
  const isCustom = v.provider === CUSTOM;
  const spec = isCustom ? { key_env: custom.key_env } : providers[v.provider];
  const needsEmbed = !isCustom && !!spec && !spec.embed;
  const set = (patch) => onChange({ ...v, ...patch });
  const setCustomField = (field, val) => {
    const next = { ...custom, [field]: val };
    // Suggest the key variable from the model prefix (openrouter/... -> OPENROUTER_API_KEY) until the person types one.
    if (field === "mentor_model" && (!custom.key_env || custom.key_env === keyEnvFor(custom.mentor_model))) next.key_env = keyEnvFor(val);
    set({ custom: next });
  };
  const choose = (provider) => {
    const p = providers[provider];
    onChange({ ...v, provider, key: "", embedKey: "", mentorModel: "",
      embedProvider: p && !p.embed ? (stored?.embed_provider && providers[stored.embed_provider]?.embed ? stored.embed_provider : embeddingProviders[0] || "") : "" });
  };
  const noEmbed = Object.entries(providers).filter(([, p]) => !p.embed).map(([, p]) => p.label);
  const embedders = embeddingProviders.map((id) => providers[id]?.label).filter(Boolean);
  const list = (names) => (names.length < 2 ? names.join("") : names.slice(0, -1).join(", ") + " " + t("gate.or") + " " + names.at(-1));
  const keepHint = (field, same) => (stored && stored[field + "_set"] && same ? t("gate.keyKeep", { tail: stored[field + "_tail"] }) : null);
  const mentorKeep = keepHint("mentor_key", stored?.provider === v.provider);
  const embedKeep = keepHint("embed_key", stored?.embed_provider === v.embedProvider);

  return <>
    <Field label={t("gate.provider")}><select value={v.provider} onChange={(e) => choose(e.target.value)}>
      {allowKeepEnv && <option value="">{t("gate.keepEnv")}</option>}
      {Object.entries(providers).map(([id, p]) => <option key={id} value={id}>{p.label}{p.embed ? "" : " (" + t("gate.secondKeyOption") + ")"}</option>)}
      <option value={CUSTOM}>{t("gate.custom")}</option></select></Field>
    {!isCustom && <p className="gate-hint">{t("gate.presetHint")}</p>}
    {!isCustom && noEmbed.length > 0 && embedders.length > 0 && <p className="gate-hint">{t("gate.secondKey", { name: list(noEmbed), others: list(embedders) })}</p>}
    {isCustom && <>
      <p className="gate-hint">{t("gate.customHint")} <a href="https://docs.litellm.ai/docs/providers" target="_blank" rel="noopener noreferrer">{t("gate.customList")} ↗</a></p>
      <Field label={t("gate.mentorModel")}><input autoComplete="off" spellCheck={false} placeholder="openrouter/…" value={custom.mentor_model} onChange={(e) => setCustomField("mentor_model", e.target.value)} /></Field>
      <Field label={t("gate.extractModel")} hint={t("gate.extractHint")}><input autoComplete="off" spellCheck={false} value={custom.extract_model} onChange={(e) => setCustomField("extract_model", e.target.value)} /></Field>
      <Field label={t("gate.embedModel")}><input autoComplete="off" spellCheck={false} value={custom.embed_model} onChange={(e) => setCustomField("embed_model", e.target.value)} /></Field>
      <Field label={t("gate.embedDim")} hint={t("gate.embedDimHint")}><input inputMode="numeric" value={custom.embed_dim} onChange={(e) => setCustomField("embed_dim", e.target.value.replace(/\D/g, ""))} /></Field>
      <Field label={t("gate.keyEnv")} hint={t("gate.keyEnvHint")}><input autoComplete="off" spellCheck={false} placeholder="OPENROUTER_API_KEY" value={custom.key_env} onChange={(e) => setCustomField("key_env", e.target.value.toUpperCase())} /></Field>
      <Field label={t("gate.apiBase")} hint={t("gate.apiBaseHint")}><input type="url" autoComplete="off" spellCheck={false} placeholder="https://…" value={custom.api_base} onChange={(e) => setCustomField("api_base", e.target.value.trim())} /></Field>
      <Field label={t("gate.apiVersion")} hint={t("gate.apiVersionHint")}><input autoComplete="off" spellCheck={false} placeholder="2024-10-21" value={custom.api_version} onChange={(e) => setCustomField("api_version", e.target.value.trim())} /></Field>
      <p className="gate-hint"><a href={PROVIDERS_DOC} target="_blank" rel="noopener noreferrer">{t("gate.azureGuide")} ↗</a></p>
    </>}
    {spec && <>
      {!isCustom && <p className="gate-hint">{spec.key_hint} {spec.key_url && <a href={spec.key_url} target="_blank" rel="noopener noreferrer">{t("gate.getKey")} ↗</a>}</p>}
      {spec.key_env && <Field label={t("gate.key")} hint={mentorKeep || t("gate.keyHint")}><input type="password" autoComplete="off" value={v.key} onChange={(e) => set({ key: e.target.value })} /></Field>}
      {!isCustom && v.mentorModel && <p className="gate-hint">{t("gate.mentorOverride", { model: v.mentorModel })} <button type="button" className="textlink" onClick={() => set({ mentorModel: "" })}>{t("gate.useDefault")}</button></p>}
      {needsEmbed && <>
        <Field label={t("gate.embedProvider")} hint={t("gate.embedHint")}><select value={v.embedProvider} onChange={(e) => set({ embedProvider: e.target.value, embedKey: "" })}>{embeddingProviders.map((id) => <option key={id} value={id}>{providers[id]?.label || id}</option>)}</select></Field>
        {providers[v.embedProvider]?.key_env && <Field label={t("gate.embedKey")} hint={embedKeep}><input type="password" autoComplete="off" value={v.embedKey} onChange={(e) => set({ embedKey: e.target.value })} /></Field>}
      </>}
    </>}
  </>;
}

// Runs POST /auth/check-provider. A result that arrives after the form changed is dropped.
export function useProviderCheck() {
  const [result, setResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState("");
  const seq = useRef(0);
  const reset = () => { seq.current++; setResult(null); setError(""); setTesting(false); };
  const run = async (body) => {
    const mine = ++seq.current;
    setTesting(true); setError(""); setResult(null);
    try { const r = await session.checkProvider(body); if (mine === seq.current) setResult(r); }
    catch (e) { if (mine === seq.current) setError(e.message || "error"); }
    finally { if (mine === seq.current) setTesting(false); }
  };
  return { result, testing, error, run, reset, verdict: checkVerdict(result) };
}

// The test button and its outcome: the key hint, one line per check, and the "use the extract model" offer.
export function ProviderTest({ check, onTest, disabled, provider, embedProvider, onSuggest, label }) {
  const { t } = useT();
  const { result, testing, error, verdict } = check;
  const hint = result?.key_hint;
  return <div className="provider-test">
    <button type="button" className="btn" disabled={disabled || testing} onClick={onTest}>{testing ? <><span className="spinner" /> {t("gate.testing")}</> : label || t("gate.testConnection")}</button>
    {hint?.code && <p className="provider-warn" role="status">{keyHintText(t, hint, { mentor: provider, embed: embedProvider })}</p>}
    {error && <p className="gate-error" role="alert">{t("gate.checkFailed", { reason: error })}</p>}
    {result?.checks && <ul className="provider-checks" aria-live="polite">{result.checks.map((c) => {
      const cls = c.ok ? "ok" : c.code === "provider.busy" ? "warn" : "fail";
      return <li key={c.name} className={cls}>
        <span className="mark" aria-hidden="true">{c.ok ? "✓" : c.code === "provider.busy" ? "!" : "×"}</span>
        <span><b>{t({ extract: "gate.extractModel", mentor: "gate.mentorModel", embed: "gate.embedModel" }[c.name] || c.name)}</b>
          {c.model && <> <code>{c.model}</code></>}
          {": "}{c.ok ? t("gate.checkOk") : errorText(t, c.code, { provider: c.name === "embed" ? embedProvider || provider : provider !== CUSTOM ? provider : null, model: c.model, ...(c.params || {}) }, { check: true, fallback: c.message })}
          {!c.ok && c.params?.detail && <small className="provider-detail">{c.params.detail}</small>}</span>
      </li>;
    })}</ul>}
    {verdict.state === "ok" && <p className="provider-ok" role="status">{t("gate.allOk")}</p>}
    {verdict.state === "busy" && <p className="gate-hint">{t("gate.busyOnly")}</p>}
    {result?.suggest?.mentor_model && onSuggest && <button type="button" className="btn ghost provider-suggest" disabled={testing} onClick={() => onSuggest(result.suggest.mentor_model)}>{t("gate.useSuggest", { model: result.suggest.mentor_model })}</button>}
  </div>;
}
