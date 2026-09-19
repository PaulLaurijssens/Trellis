import test from "node:test";
import assert from "node:assert/strict";
import { readTrail, visitTrail } from "../lib/learningTrail.mjs";

test("returning from nested topics preserves the origin and trims the detour", () => {
  const path = ["Transformers", "Attention", "Dot products"];
  assert.deepEqual(visitTrail(path, "Transformers"), ["Transformers"]);
  assert.deepEqual(visitTrail(path, "Attention"), ["Transformers", "Attention"]);
});

test("revisiting with a different case does not create cycles", () => {
  assert.deepEqual(visitTrail(["Attention", "Vectors"], "attention"), ["Attention"]);
});

test("a tab restores only a valid path and tolerates corrupt browser storage", () => {
  assert.deepEqual(readTrail('["Attention", "Vectors", "Attention"]'), ["Attention"]);
  for (const value of [null, "bad json", '{}', '["Attention", null]', '[""]']) {
    assert.deepEqual(readTrail(value), []);
  }
});

test("very long paths are bounded while keeping the current topic", () => {
  const trail = Array.from({ length: 30 }, (_, i) => `Concept ${i}`);
  const result = readTrail(JSON.stringify(trail));
  assert.equal(result.length, 24);
  assert.equal(result.at(-1), "Concept 29");
});
