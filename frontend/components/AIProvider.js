"use client";
// Owner's AI provider card in Settings: what is in use, a live test, and a change that is tested
// before it is saved. Keys never come back from the server: only "•••• last4".
import { useEffect, useState } from "react";
import { useT } from "../lib/i18n";
import { session } from "../lib/session";
import ProviderForm, { ProviderTest, useProviderCheck } from "./ProviderForm";
import { CUSTOM, applySuggestion, formEmbedDim, formReady, providerBody, settingsToForm } from "../lib/providerErrors.mjs";

export default function AIProvider() {
  const { t } = useT();
  const [settings, setSettings] = useState(null);
  const [status, setStatus] = useState(null);     // provider presets, from /auth/status
  const [form, setForm] = useState(null);         // null: showing the current settings
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState(null);         // {text, err}
  const check = useProviderCheck();
  useEffect(() => {
    Promise.all([session.settings(), session.status()]).then(([s, st]) => { setSettings(s); setStatus(st); })
      .catch((e) => setNote({ text: e.message, err: true }));
  }, []);
  if (!settings || !status) return note ? <div className="card provider-card"><h4>{t("ai.title")}</h4><p className="hint error" role="alert">{note.text}</p></div> : null;

  const providers = status.providers || {};
  const models = settings.models || {};
  const currentDim = models.embed_dim || null;
  const label = (id) => (id === CUSTOM ? t("gate.custom") : providers[id]?.label || id);
  const tail = (field) => (settings[field + "_set"] ? "•••• " + settings[field + "_tail"] : t("ai.noKey"));
  const ownEmbed = !settings.embed_provider || settings.embed_provider === settings.provider;

  const edit = (next) => { setForm(next); check.reset(); setNote(null); };
  const test = (value) => check.run(providerBody(value, providers, "check", { useStoredKeys: true }));
  const testCurrent = () => { setNote(null); test(settingsToForm(settings, providers)); };
  const startChange = () => { const f = settingsToForm(settings, providers); edit(f.provider ? f : { ...f, provider: Object.keys(providers)[0] || CUSTOM }); };
  const suggest = (model) => { const base = form || settingsToForm(settings, providers); const next = applySuggestion(base, model); setForm(next); test(next); };
  const save = async () => {
    setSaving(true); setNote(null);
    try {
      const s = await session.saveSettings(providerBody(form, providers, "save"));
      setSettings(s); setForm(null); check.reset(); setNote({ text: t("ai.saved") });
    } catch (e) {
      // 409: the vector index has another size and the map already has embeddings.
      setNote({ text: e.status === 409 ? t("ai.dimRefused", { dim: currentDim || "?" }) : e.message, err: true });
    } finally { setSaving(false); }
  };

  const nextDim = form ? formEmbedDim(form, providers) : null;
  return <div className="card provider-card">
    <h4>{t("ai.title")}</h4>
    <p className="hint">{t("ai.lead")}</p>
    {!form && <>
      {settings.provider ? <dl className="provider-facts">
        <dt>{t("ai.provider")}</dt><dd>{label(settings.provider)}</dd>
        <dt>{t("gate.mentorModel")}</dt><dd><code>{models.mentor}</code></dd>
        <dt>{t("gate.extractModel")}</dt><dd><code>{models.extract}</code></dd>
        <dt>{t("gate.embedModel")}</dt><dd><code>{t("ai.embedSize", { model: models.embed, dim: models.embed_dim })}</code>{!ownEmbed && <> · {label(settings.embed_provider)}</>}</dd>
        {(providers[settings.provider]?.key_env || settings.provider === CUSTOM) && <><dt>{t("ai.key")}</dt><dd>{tail("mentor_key")}</dd></>}
        {!ownEmbed && providers[settings.embed_provider]?.key_env && <><dt>{t("ai.embedKey")}</dt><dd>{tail("embed_key")}</dd></>}
        {settings.provider === CUSTOM && settings.api_base && <><dt>{t("gate.apiBase")}</dt><dd><code>{settings.api_base}</code></dd></>}
        {settings.provider === CUSTOM && settings.api_version && <><dt>{t("gate.apiVersion")}</dt><dd><code>{settings.api_version}</code></dd></>}
      </dl> : <p className="hint">{t("ai.fromEnv")}</p>}
      {settings.provider && <ProviderTest check={check} provider={settings.provider} embedProvider={settings.embed_provider} onTest={testCurrent} onSuggest={suggest} label={t("ai.testAgain")} />}
      <div className="row"><button className="btn ghost" onClick={startChange}>{t("ai.change")}</button></div>
    </>}
    {form && <div className="provider-edit">
      <ProviderForm value={form} onChange={edit} providers={providers} embeddingProviders={status.embedding_providers || []} stored={settings} />
      {currentDim && nextDim && nextDim !== currentDim && <p className="provider-warn">{t("ai.dimWarn", { next: nextDim, current: currentDim })}</p>}
      <ProviderTest check={check} provider={form.provider} embedProvider={form.embedProvider} disabled={!formReady(form, providers, settings)} onTest={() => test(form)} onSuggest={suggest} />
      <div className="row">
        <button className="btn primary" disabled={saving || check.testing || !check.verdict.canProceed} onClick={save}>{saving ? <span className="spinner" /> : check.verdict.state === "busy" ? t("gate.continueAnyway") : t("ai.save")}</button>
        <button className="btn ghost" disabled={saving} onClick={() => { setForm(null); check.reset(); setNote(null); }}>{t("ai.cancel")}</button>
      </div>
    </div>}
    {note && <p className={"hint" + (note.err ? " error" : "")} role={note.err ? "alert" : "status"}>{note.text}</p>}
  </div>;
}
