import test from "node:test";
import assert from "node:assert/strict";
import { counts, openItems, personStatus, provenance, relativeDate, visible } from "../lib/memoryView.mjs";

const c = (concept, extra = {}) => ({ concept, concept_status: "learned", covered: [], evidence: [], observations: [], ...extra });

test("the learner's own status follows intent and self-assessment, not the shared concept status", () => {
  assert.equal(personStatus(c("A", { intent: "learning" })), "learning");
  assert.equal(personStatus(c("A", { intent: "queued" })), "queued");
  assert.equal(personStatus(c("A", { intent: "interested" })), "suggested");
  assert.equal(personStatus(c("A", { intent: "queued", self_assessment: { value: "understood" } })), "learned");
  assert.equal(personStatus(c("A", { intent: "learning", self_assessment: { value: "partial" } })), "learning");
});

test("needs attention counts only active difficulties; older states fall back to the lists", () => {
  const withObservations = c("A", { observations: [{ id: "1", kind: "struggles", text: "x", state: "active" }, { id: "2", kind: "struggles", text: "y", state: "resolved" }] });
  assert.equal(openItems(withObservations).length, 1);
  const legacy = { concept: "B", struggles: ["s"], misconceptions: ["m"] };
  assert.deepEqual(openItems(legacy).map((o) => [o.kind, o.fallback]), [["struggles", true], ["misconceptions", true]]);
});

test("search is accent and case insensitive and looks in summary and discussed items", () => {
  const list = [c("Café latte", { summary: "milk" }), c("Attention", { covered: ["Softmax weighting"] }), c("Other")];
  assert.deepEqual(visible(list, { query: "cafe" }).map((x) => x.concept), ["Café latte"]);
  assert.deepEqual(visible(list, { query: "SOFTMAX" }).map((x) => x.concept), ["Attention"]);
  assert.equal(visible(list, { query: "  " }).length, 3);
});

test("filters, counts and sorting", () => {
  const list = [
    c("Beta", { intent: "learning", last_session: "2026-10-01", evidence: [{ outcome: "demonstrated" }, { outcome: "demonstrated" }] }),
    c("Alpha", { intent: "learning", self_assessment: { value: "understood" }, last_session: "2026-10-20", evidence: [{ outcome: "demonstrated" }] }),
    c("Gamma", { intent: "queued", since: "2026-10-10", observations: [{ id: "o", kind: "misconceptions", text: "z", state: "active" }] }),
  ];
  assert.deepEqual(counts(list), { all: 3, learning: 1, learned: 1, attention: 1, planned: 1 });
  assert.deepEqual(visible(list).map((x) => x.concept), ["Alpha", "Gamma", "Beta"]);
  assert.deepEqual(visible(list, { sort: "name" }).map((x) => x.concept), ["Alpha", "Beta", "Gamma"]);
  assert.deepEqual(visible(list, { sort: "evidence" }).map((x) => x.concept), ["Beta", "Alpha", "Gamma"]);
  assert.deepEqual(visible(list, { filter: "planned" }).map((x) => x.concept), ["Gamma"]);
});

test("provenance comes from the ledger when present, else from the evidence", () => {
  assert.deepEqual(provenance({ memory_v2: { sessions: { a: {}, b: {} }, runs: { r: {} } } }), { conversations: 2, exercises: 1 });
  assert.deepEqual(provenance({ evidence: [{ session_id: "a" }, { session_id: "a" }, { origin: "exercise" }] }), { conversations: 1, exercises: 1 });
});

test("relative dates in the interface language", () => {
  const now = Date.parse("2026-10-26T12:00:00Z");
  assert.equal(relativeDate("2026-10-24T12:00:00Z", "en", now), "2 days ago");
  assert.equal(relativeDate("2026-10-26T12:00:00Z", "nl", now), "vandaag");
  assert.equal(relativeDate(null, "en", now), null);
  assert.equal(relativeDate("not a date", "en", now), null);
});
