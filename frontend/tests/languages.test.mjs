import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import en from "../lib/en.js";

// Checks every dictionary registered in lib/languages.js, so a language someone adds stays in step
// with English: no unknown keys, and the same {placeholders} as the English text.
const registry = readFileSync(new URL("../lib/languages.js", import.meta.url), "utf8");
const files = [...registry.matchAll(/import (\w+) from "\.\/(\w[\w-]*)"/g)].map((m) => m[2]);
const placeholders = (s) => [...String(s).matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

test("English is the default and is registered", () => {
  assert.match(registry, /DEFAULT_LANGUAGE = "en"/);
  assert.ok(files.includes("en"));
});

for (const file of files.filter((f) => f !== "en")) {
  test(`${file}: keys and placeholders match English`, async () => {
    const dict = (await import(`../lib/${file}.js`)).default;
    for (const [key, text] of Object.entries(dict)) {
      assert.ok(key in en, `${file}.js has a key English does not have: ${key}`);
      assert.deepEqual(placeholders(text), placeholders(en[key]), `${file}.js ${key}: placeholders differ from English`);
    }
    const missing = Object.keys(en).filter((k) => !(k in dict));
    if (missing.length) console.log(`${file}.js: ${missing.length} keys fall back to English`);
  });
}
