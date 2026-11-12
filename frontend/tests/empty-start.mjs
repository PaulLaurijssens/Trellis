// A new, empty map: one clear first step (Add), no clutter, and a Learning path that says why it is off.
// With topics: the map explanation and legend can be hidden, and that choice is kept.
import assert from "node:assert/strict";
import { mockApi, launch, shot } from "./mock-api.mjs";

const browser = await launch();
try {
  const page = await browser.newPage({ viewport: { width: 1500, height: 950 } }), errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.setDefaultTimeout(12000);
  await page.addInitScript(() => localStorage.setItem("trellis.lang", "en"));
  let nodes = [];
  await mockApi(page, (path) => {
    if (path === "/graph") return { nodes, edges: nodes.length > 1 ? [{ source: "v", target: "a", type: "PREREQUISITE_OF" }] : [] };
    if (path.startsWith("/memory/")) return { ui_language: "en", ambient_motion: false, learning_profile: {}, concepts: [] };
    if (path === "/journey/paul") return { active_goal: null, goals: [], recent: null, review: [], sources: [] };
    if (path.startsWith("/concept/")) return { ...nodes.find((n) => n.name === path.slice(9)), definition: "A useful topic.", mentions: [] };
    if (path.startsWith("/chat/")) return { session_id: null, messages: [], state: {}, suggestions: [] };
    if (path.startsWith("/curriculum/plan") || path === "/plan") return { plan: null };
  });

  // Empty map
  await page.goto("http://localhost:3000");
  await page.getByRole("heading", { name: "Your curiosity starts the map" }).waitFor();
  assert.equal(await page.getByText("Start with a concept you want to understand").count(), 0, "no extra hint box");
  assert.equal(await page.getByText("Topic overview").count(), 0, "no map explanation on an empty map");
  assert.equal(await page.locator(".map-legend").count(), 0, "no legend on an empty map");
  assert.ok(await page.locator(".cmd-row .cta.attention").count(), "Add draws attention");

  const path = page.getByRole("button", { name: "Learning path", exact: true });
  assert.equal(await path.getAttribute("aria-disabled"), "true");
  await path.hover();
  await page.getByRole("tooltip").filter({ hasText: "Add a topic first" }).waitFor();
  await shot(page, "empty-home-path-hint.png");
  await path.click({ force: true });
  assert.equal(await page.getByText("Organizing all your topics").count(), 0, "the path view does not open");
  assert.equal(await path.getAttribute("aria-pressed"), "false");

  await page.mouse.move(700, 900);
  await shot(page, "empty-home.png");

  // "Add a topic" opens the input card on the Topic tab, without the level picker.
  await page.getByRole("button", { name: "Add a topic", exact: true }).click();
  await page.getByLabel("Topic", { exact: true }).waitFor();
  assert.equal(await page.locator(".cmd-card .levels").count(), 0, "no level picker in the input card");
  assert.equal(await page.locator(".atlas-empty").isVisible(), false, "the invitation steps aside for the card");
  await page.waitForTimeout(400);
  await shot(page, "empty-home-add.png");

  // With topics: Add is calm, the explanation and legend show, and "i" hides them for good.
  nodes = [{ id: "v", name: "Vectors", status: "learning" }, { id: "a", name: "Attention", status: "queued" }];
  await page.reload();
  await page.locator(".detail-explainer").waitFor();
  assert.equal(await page.locator(".cmd-row .cta.attention").count(), 0);
  assert.ok(await page.locator(".map-legend").count());
  const info = page.getByRole("button", { name: "Map info" });
  assert.equal(await info.getAttribute("aria-pressed"), "true");
  await info.click();
  assert.equal(await page.locator(".detail-explainer").count(), 0);
  assert.equal(await page.locator(".map-legend").count(), 0);
  await page.reload();
  await page.getByRole("button", { name: "Map info" }).waitFor();
  assert.equal(await page.locator(".detail-explainer").count(), 0, "hidden after a reload");
  await page.getByRole("button", { name: "Map info" }).click();
  await page.locator(".detail-explainer").waitFor();
  assert.equal(await path.getAttribute("aria-disabled"), null, "Learning path is on with topics");

  assert.deepEqual(errors, []);
  console.log("empty start ok");
} finally {
  await browser.close();
}
