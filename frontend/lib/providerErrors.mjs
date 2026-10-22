// Pure helpers for model-provider errors, import warnings, the setup key test and the problem report.
// No React and no module state: every function takes the translate function `t(key, vars)`, so the
// same code runs in components, in api.js and in node tests.

export const PROVIDER_CODES = ["provider.auth", "provider.quota", "provider.quotaZero", "provider.busy", "provider.notFound",
  "provider.network", "provider.timeout", "provider.badRequest", "provider.embedDim", "provider.unknown"];
export const STAGES = ["fetch", "extract", "embed", "mentor", "lesson", "setup"];
export const CUSTOM = "custom";
export const EMPTY_CUSTOM = { key_env: "", mentor_model: "", extract_model: "", embed_model: "", embed_dim: "", api_base: "", api_version: "" };
export const ISSUES_URL = "https://github.com/PaulLaurijssens/Trellis/issues/new";

const LABELS = { openai: "OpenAI", gemini: "Google Gemini", anthropic: "Anthropic Claude", mistral: "Mistral", ollama: "Ollama",
  azure: "Azure OpenAI", azure_ai: "Microsoft Foundry", openrouter: "OpenRouter", groq: "Groq", deepseek: "DeepSeek" };

const has = (t, key) => t(key) !== key;

// "openai" -> "OpenAI"; no id -> "model provider" (translated). A model id like "azure/gpt-4o" gives its prefix.
export function providerLabel(t, id, model) {
  const name = id && id !== CUSTOM ? id : (model && model.includes("/") ? model.split("/")[0] : "");
  return name ? LABELS[name] || name : t("provider.someProvider");
}

// Seconds -> "30 seconds" / "2 minutes".
export function fmtWait(t, seconds) {
  const s = Math.max(1, Math.round(Number(seconds) || 0));
  if (s < 90) return t(s === 1 ? "wait.second" : "wait.seconds", { n: s });
  return t("wait.minutes", { n: Math.ceil(s / 60) });
}

// A provider error code with its params -> one plain sentence in the current language.
// opts.check: the text for the setup test (no "check your settings" pointer, no stage).
// opts.fallback: the backend's English sentence, used for a code this frontend does not know.
export function errorText(t, code, params, opts = {}) {
  const p = params || {};
  const vars = { provider: providerLabel(t, p.provider, p.model), model: p.model || t("provider.thisModel"),
    time: p.retry_after ? fmtWait(t, p.retry_after) : "" };
  let key = code === "provider.quota" && p.retry_after ? "provider.quotaRetry" : code === "provider.embedDim" && p.got && p.expected ? "provider.embedDimSizes" : code;
  if (p.got) vars.got = p.got;
  if (p.expected) vars.expected = p.expected;
  if (opts.check && has(t, key + ".check")) key += ".check";
  if (!code || !has(t, key)) {
    if (opts.fallback) return opts.fallback;
    return String(code || "").startsWith("provider.") ? t("provider.unknown", vars) : String(code || "");
  }
  let text = t(key, vars);
  if (!opts.check && p.stage && has(t, "stage." + p.stage)) text += " " + t("provider.stage", { stage: t("stage." + p.stage) });
  return text;
}

// Import warnings: legacy strings stay as they are; {code, params} objects are translated.
// params.reason is itself a code (usually provider.*).
export function warningText(t, w) {
  if (w == null) return "";
  if (typeof w === "string") return w;
  if (typeof w !== "object") return String(w);
  const params = { ...(w.params || {}) };
  if (!w.code || !has(t, w.code)) return w.message || String(w.code || "");
  params.reason = params.reason ? errorText(t, params.reason, {}) : "";
  return t(w.code, params).trim();
}

// key_hint from the check -> text. providers: {mentor: id, embed: id}; params.field "embed_key" means the second key.
export function keyHintText(t, hint, providers = {}) {
  if (!hint || !hint.code) return "";
  const p = hint.params || {};
  const embed = p.field === "embed_key";
  const text = t(hint.code, { ...p, provider: providerLabel(t, embed ? providers.embed : providers.mentor), looks_like: providerLabel(t, p.looks_like) });
  return embed ? t("key.embedField", { text }) : text;
}

// The result of POST /auth/check-provider -> can the person go on? Busy-only failures may continue anyway.
export function checkVerdict(result) {
  if (!result || !Array.isArray(result.checks)) return { state: "none", canProceed: false };
  if (result.ok) return { state: "ok", canProceed: true };
  const failed = result.checks.filter((c) => !c.ok);
  const busyOnly = failed.length > 0 && failed.every((c) => c.code === "provider.busy");
  return { state: busyOnly ? "busy" : "failed", canProceed: busyOnly };
}

// The form value (ProviderForm) -> the request body. mode: "check" | "setup" | "save".
// Empty key fields are left out, so the stored key stays (settings) or the backend reports it missing.
export function providerBody(v, providers, mode, opts = {}) {
  const isCustom = v.provider === CUSTOM;
  const spec = isCustom ? null : (providers || {})[v.provider];
  const needsEmbed = !!spec && !spec.embed;
  const body = { provider: v.provider || null };
  if (v.key && v.key.trim()) body.mentor_key = v.key.trim();
  if (needsEmbed) {
    body.embed_provider = v.embedProvider || null;
    if (v.embedKey && v.embedKey.trim()) body.embed_key = v.embedKey.trim();
  } else if (mode === "save" && v.provider) body.embed_provider = v.provider;   // own embeddings, not a leftover second provider
  if (isCustom) {
    const c = { ...EMPTY_CUSTOM, ...(v.custom || {}) };
    Object.assign(body, { mentor_model: c.mentor_model.trim(), extract_model: c.extract_model.trim(), embed_model: c.embed_model.trim(),
      embed_dim: Number(c.embed_dim), key_env: c.key_env.trim() || null, api_base: c.api_base.trim() || null, api_version: c.api_version.trim() || null });
  } else if (spec) {
    if (v.mentorModel) body.mentor_model = v.mentorModel;
    // Settings: store the models of the chosen preset, so a model of the previous provider never lingers.
    if (mode === "save") { body.mentor_model = v.mentorModel || spec.mentor; body.extract_model = spec.extract; }
  }
  if (mode === "check" && opts.useStoredKeys) body.use_stored_keys = true;
  return body;
}

// Is the form complete enough to test? `stored` (settings only): {provider, embed_provider, mentor_key_set, embed_key_set}.
export function formReady(v, providers, stored) {
  if (!v.provider) return false;
  const keepsKey = (field, same) => !!(stored && stored[field] && same);
  if (v.provider === CUSTOM) {
    const c = { ...EMPTY_CUSTOM, ...(v.custom || {}) };
    if (!c.mentor_model.trim() || !c.extract_model.trim() || !c.embed_model.trim() || !(Number(c.embed_dim) > 0)) return false;
    return !c.key_env.trim() || !!v.key || keepsKey("mentor_key_set", stored?.provider === CUSTOM);
  }
  const spec = (providers || {})[v.provider];
  if (!spec) return false;
  if (spec.key_env && !v.key && !keepsKey("mentor_key_set", stored?.provider === v.provider)) return false;
  if (!spec.embed) {
    const espec = (providers || {})[v.embedProvider];
    if (!espec) return false;
    if (espec.key_env && v.embedProvider !== v.provider && !v.embedKey && !keepsKey("embed_key_set", stored?.embed_provider === v.embedProvider)) return false;
  }
  return true;
}

// "Use the extract model as mentor": for Other it fills the mentor field, for a preset it overrides the preset.
export function applySuggestion(v, model) {
  return v.provider === CUSTOM ? { ...v, custom: { ...EMPTY_CUSTOM, ...v.custom, mentor_model: model } } : { ...v, mentorModel: model };
}

// GET /auth/settings -> form value. Keys are never sent back, so the key fields start empty.
export function settingsToForm(s, providers) {
  const provider = (s && s.provider) || "";
  const spec = (providers || {})[provider];
  if (provider === CUSTOM) return { provider, key: "", embedProvider: "", embedKey: "", mentorModel: "",
    custom: { key_env: s.key_env || "", mentor_model: s.mentor_model || "", extract_model: s.extract_model || "", embed_model: s.embed_model || "",
      embed_dim: s.embed_dim ? String(s.embed_dim) : "", api_base: s.api_base || "", api_version: s.api_version || "" } };
  return { provider, key: "", embedKey: "", custom: { ...EMPTY_CUSTOM },
    embedProvider: spec && !spec.embed ? s.embed_provider || "" : "",
    mentorModel: spec && s.mentor_model && s.mentor_model !== spec.mentor ? s.mentor_model : "" };
}

// The embedding size the form would use, or null when unknown.
export function formEmbedDim(v, providers) {
  if (v.provider === CUSTOM) return Number(v.custom?.embed_dim) || null;
  const spec = (providers || {})[v.provider];
  if (!spec) return null;
  return (spec.embed ? spec.embed_dim : (providers[v.embedProvider] || {}).embed_dim) || null;
}

// "Chrome 130 on Windows": enough to reproduce, nothing personal.
export function uaSummary(ua) {
  ua = ua || "";
  const browser = [[/Edg\/(\d+)/, "Edge"], [/OPR\/(\d+)/, "Opera"], [/Firefox\/(\d+)/, "Firefox"], [/Chrome\/(\d+)/, "Chrome"], [/Version\/(\d+).*Safari/, "Safari"]]
    .map(([re, name]) => { const m = ua.match(re); return m && name + " " + m[1]; }).find(Boolean) || "Unknown browser";
  const os = /Windows/.test(ua) ? "Windows" : /Android/.test(ua) ? "Android" : /iPhone|iPad/.test(ua) ? "iOS" : /Mac OS X/.test(ua) ? "macOS" : /Linux/.test(ua) ? "Linux" : "unknown OS";
  return browser + " on " + os;
}

// Link to a prefilled bug report (template fields `version` and `environment`). Never keys.
export function reportUrl({ version, commit, ua, provider, model }) {
  const v = (version || "dev") + (commit ? " (" + String(commit).slice(0, 7) + ")" : "");
  const env = ["Browser: " + uaSummary(ua), provider ? "Provider: " + provider + (model ? " (" + model + ")" : "") : ""].filter(Boolean).join("\n");
  const q = { template: "bug_report.yml", version: v, environment: env };
  return ISSUES_URL + "?" + Object.entries(q).map(([k, val]) => k + "=" + encodeURIComponent(val)).join("&");
}
