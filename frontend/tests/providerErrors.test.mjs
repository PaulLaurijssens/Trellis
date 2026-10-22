import test from "node:test";
import assert from "node:assert/strict";
import en from "../lib/en.js";
import nl from "../lib/nl.js";
import { PROVIDER_CODES, STAGES, errorText, warningText, keyHintText, checkVerdict, providerBody, formReady, applySuggestion, settingsToForm, reportUrl, uaSummary, fmtWait } from "../lib/providerErrors.mjs";

const tFor = (dict) => (key, vars) => {
  let s = dict[key] ?? en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll("{" + k + "}", String(v ?? ""));
  return s;
};
const tEn = tFor(en), tNl = tFor(nl);
const PROVIDERS = {
  gemini: { label: "Google Gemini", key_env: "GEMINI_API_KEY", mentor: "gemini/pro", extract: "gemini/flash", embed: "gemini/emb", embed_dim: 3072 },
  anthropic: { label: "Anthropic Claude", key_env: "ANTHROPIC_API_KEY", mentor: "anthropic/sonnet", extract: "anthropic/haiku", embed: null, embed_dim: null },
  ollama: { label: "Ollama", key_env: null, mentor: "ollama/a", extract: "ollama/b", embed: "ollama/e", embed_dim: 768 },
};

test("every provider code, stage and key hint has English and Dutch text", () => {
  const keys = [...PROVIDER_CODES, "provider.quotaRetry", "provider.auth.check", ...STAGES.map((s) => "stage." + s),
    "key.looksAzure", "key.wrongProvider", "key.hasSpaces", "key.embedField", "error.network", "error.http", "provider.embedDimSizes",
    "extract.partsSkipped", "extract.noText", "extract.segmentFailed", "extract.embedFailed", "extract.confirmFailed", "extract.relationsFailed",
    "import.expired", "check.tooMany"];
  for (const k of keys) { assert.ok(en[k], "en " + k); assert.ok(nl[k], "nl " + k); }
});
test("en and nl have the same keys for the new strings", () => {
  const prefixes = ["provider.", "stage.", "key.", "gate.", "ai.", "about.", "wait.", "error.", "nav.learn", "extract.", "import.", "check."];
  const pick = (d) => Object.keys(d).filter((k) => prefixes.some((p) => k.startsWith(p))).sort();
  assert.deepEqual(pick(nl), pick(en));
});
test("provider errors are translated with provider, stage and wait time", () => {
  const msg = errorText(tEn, "provider.auth", { provider: "openai", stage: "extract" });
  assert.match(msg, /Your OpenAI key was refused/); assert.match(msg, /while finding concepts/);
  assert.match(errorText(tNl, "provider.busy", {}), /druk/);
  assert.match(errorText(tEn, "provider.quota", { retry_after: 120 }), /try again in 2 minutes/i);
  assert.match(errorText(tEn, "provider.quota", { retry_after: 20 }), /20 seconds/);
  assert.match(errorText(tEn, "provider.notFound", { model: "azure/gpt-4o" }), /azure\/gpt-4o/);
  assert.match(errorText(tEn, "provider.auth", {}), /model provider key/);
  assert.match(errorText(tEn, "provider.auth", { model: "azure/x" }, { check: true }), /belongs to Azure OpenAI/);
});
test("embedding size and key hints use their params", () => {
  assert.match(errorText(tEn, "provider.embedDim", { got: 768, expected: 3072 }, { check: true }), /size 768.*size 3072/);
  assert.equal(errorText(tEn, "provider.embedDim", {}, { check: true }), en["provider.embedDim"]);
  assert.equal(keyHintText(tEn, { code: "key.wrongProvider", params: { looks_like: "anthropic" } }, { mentor: "openai" }), "This key looks like it belongs to Anthropic Claude, not to OpenAI.");
  assert.match(keyHintText(tEn, { code: "key.hasSpaces", params: { field: "embed_key" } }, { mentor: "anthropic", embed: "gemini" }), /^Embedding key: The key contains spaces/);
  assert.equal(keyHintText(tEn, null), "");
});
test("unknown codes fall back to the backend sentence, then to the generic provider text", () => {
  assert.equal(errorText(tEn, "provider.somethingNew", {}, { fallback: "English fallback" }), "English fallback");
  assert.equal(errorText(tEn, "provider.somethingNew", {}), en["provider.unknown"]);
  assert.equal(errorText(tEn, "other.code", {}), "other.code");
  assert.equal(fmtWait(tEn, 0), "1 second");
  assert.equal(fmtWait(tNl, 600), "10 minuten");
});
test("warnings: strings stay, objects are translated, reasons are codes", () => {
  assert.equal(warningText(tEn, "Geen tekst gevonden."), "Geen tekst gevonden.");
  const w = { code: "extract.partsSkipped", params: { skipped: 1, total: 3, parts: "2", reason: "provider.auth" } };
  const text = warningText(tEn, w);
  assert.match(text, /^1 of 3 parts were skipped \(part 2\)\. Your model provider key was refused/);
  assert.equal(warningText(tEn, { code: "extract.relationsFailed", params: { reason: null } }), "The links between concepts could not be made.");
  assert.equal(warningText(tEn, { code: "extract.noText", params: {} }), en["extract.noText"]);
  assert.match(warningText(tNl, w), /1 van 3 delen overgeslagen/);
  assert.equal(warningText(tEn, { code: "x.new", message: "msg" }), "msg");
  assert.equal(warningText(tEn, null), "");
});
test("key test gating: ok, busy-only may continue, anything else may not", () => {
  const c = (name, ok, code) => ({ name, ok, code });
  assert.deepEqual(checkVerdict(null), { state: "none", canProceed: false });
  assert.equal(checkVerdict({ ok: true, checks: [c("extract", true)] }).canProceed, true);
  assert.deepEqual(checkVerdict({ ok: false, checks: [c("extract", true), c("mentor", false, "provider.busy")] }), { state: "busy", canProceed: true });
  assert.deepEqual(checkVerdict({ ok: false, checks: [c("extract", false, "provider.busy"), c("mentor", false, "provider.auth")] }), { state: "failed", canProceed: false });
  assert.equal(checkVerdict({ ok: false, checks: [] }).canProceed, false);
});
test("request bodies: preset, Claude with a second key, custom with endpoint, settings save", () => {
  const base = { provider: "gemini", key: " k1 ", embedProvider: "", embedKey: "", mentorModel: "", custom: {} };
  assert.deepEqual(providerBody(base, PROVIDERS, "check"), { provider: "gemini", mentor_key: "k1" });
  assert.deepEqual(providerBody({ ...base, key: "" }, PROVIDERS, "check", { useStoredKeys: true }), { provider: "gemini", use_stored_keys: true });
  const claude = { ...base, provider: "anthropic", embedProvider: "gemini", embedKey: "k2" };
  assert.deepEqual(providerBody(claude, PROVIDERS, "setup"), { provider: "anthropic", mentor_key: "k1", embed_provider: "gemini", embed_key: "k2" });
  const custom = { ...base, provider: "custom", custom: { mentor_model: "azure/gpt", extract_model: "azure/mini", embed_model: "azure/emb", embed_dim: "1536", key_env: "AZURE_API_KEY", api_base: "https://x.openai.azure.com", api_version: "2024-10-21" } };
  const body = providerBody(custom, PROVIDERS, "setup");
  assert.equal(body.api_base, "https://x.openai.azure.com"); assert.equal(body.api_version, "2024-10-21"); assert.equal(body.embed_dim, 1536);
  const saved = providerBody({ ...base, key: "" }, PROVIDERS, "save");
  assert.deepEqual(saved, { provider: "gemini", embed_provider: "gemini", mentor_model: "gemini/pro", extract_model: "gemini/flash" });
  assert.equal(providerBody(applySuggestion(base, "gemini/flash"), PROVIDERS, "check").mentor_model, "gemini/flash");
  assert.equal(applySuggestion(custom, "azure/mini").custom.mentor_model, "azure/mini");
});
test("form readiness: keys required unless stored for the same provider", () => {
  const v = { provider: "gemini", key: "", embedProvider: "", embedKey: "", mentorModel: "", custom: {} };
  assert.equal(formReady(v, PROVIDERS), false);
  assert.equal(formReady({ ...v, key: "x" }, PROVIDERS), true);
  assert.equal(formReady(v, PROVIDERS, { provider: "gemini", mentor_key_set: true }), true);
  assert.equal(formReady(v, PROVIDERS, { provider: "anthropic", mentor_key_set: true }), false);
  assert.equal(formReady({ ...v, provider: "ollama" }, PROVIDERS), true);
  assert.equal(formReady({ ...v, provider: "anthropic", key: "x", embedProvider: "gemini" }, PROVIDERS), false);
  assert.equal(formReady({ ...v, provider: "anthropic", key: "x", embedProvider: "gemini", embedKey: "y" }, PROVIDERS), true);
  assert.equal(formReady({ ...v, provider: "" }, PROVIDERS), false);
});
test("settings become a form without keys; a fallback mentor is kept", () => {
  const f = settingsToForm({ provider: "gemini", mentor_model: "gemini/flash", mentor_key_set: true, mentor_key_tail: "abcd" }, PROVIDERS);
  assert.equal(f.key, ""); assert.equal(f.mentorModel, "gemini/flash");
  assert.equal(settingsToForm({ provider: "gemini", mentor_model: "gemini/pro" }, PROVIDERS).mentorModel, "");
  assert.equal(settingsToForm({ provider: "custom", api_base: "https://a", embed_dim: 1024 }, PROVIDERS).custom.embed_dim, "1024");
});
test("problem report link: encoded, version and environment, no keys", () => {
  const ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0";
  assert.equal(uaSummary(ua), "Edge 130 on Windows");
  const url = new URL(reportUrl({ version: "0.4.0", commit: "abcdef1234", ua, provider: "openai", model: "openai/gpt-5.5" }));
  assert.equal(url.searchParams.get("template"), "bug_report.yml");
  assert.equal(url.searchParams.get("version"), "0.4.0 (abcdef1)");
  assert.equal(url.searchParams.get("environment"), "Browser: Edge 130 on Windows\nProvider: openai (openai/gpt-5.5)");
  assert.ok(!url.href.includes(" "));
});
