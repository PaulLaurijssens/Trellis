import test from "node:test";
import assert from "node:assert/strict";
import { safeUrl, momentLink } from "../lib/time.js";

test("only web links become clickable", () => {
  assert.equal(safeUrl("https://example.com/a"), "https://example.com/a");
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("data:text/html,x"), null);
  assert.equal(safeUrl("not a url"), null);
  assert.equal(momentLink("javascript:alert(1)", 10), null);
  assert.equal(momentLink("https://youtu.be/abcdefghijk", 75), "https://youtu.be/abcdefghijk?t=75s");
});
