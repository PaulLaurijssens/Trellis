// Shared API mock for the browser flows. The app calls the API with credentials, so CORS must
// name the origin (never "*"), and every screen first asks /auth/status. A flow answers its own
// paths in `handle(path, ctx)`: return data for a 200, or reply(status, data) for anything else.
// Returning undefined falls back to the defaults below; a path nobody answers fails the flow.
export const ORIGIN = "http://localhost:3000";
export const API = "http://localhost:8000";
export const CORS = { "Access-Control-Allow-Origin": ORIGIN, "Access-Control-Allow-Credentials": "true" };

export const reply = (status, data, type = "application/json") => ({ __reply: true, status, data, type });

export const PERSON = { id: "paul", name: "Paul", language: "en", is_admin: true };

const DEFAULTS = {
  "/auth/status": () => ({ setup_needed: false, authenticated: true, person: PERSON, profiles: [], configured: true }),
  "/auth/settings": () => ({ provider: "gemini", lesson_cost_limit: 0 }),
  "/health": () => ({ ok: true, version: "test" }),
  "/levels": () => ({ 1: "First steps", 2: "Foundations", 3: "Practical", 4: "Technical", 5: "Advanced" }),
  "/journey/paul/examples": () => [],
  "/curriculum": () => ({ groups: [], conflicts: [], coverage: 0 }),
  "/admin/backups": () => ({ available: true, keep: 7, nightly_hour_utc: 3, backups: [] }),
};

export async function mockApi(page, handle, { calls = [], translations = true } = {}) {
  await page.route(API + "/**", async (route) => {
    const req = route.request(), url = new URL(req.url()), path = decodeURIComponent(url.pathname), method = req.method();
    if (method === "OPTIONS") {
      await route.fulfill({ status: 204, headers: { ...CORS, "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE" } });
      return;
    }
    let body = {};
    try { body = req.postData() ? JSON.parse(req.postData()) : {}; } catch { body = req.postData(); }
    calls.push([method, path + url.search, body]);
    let out = await handle(path, { method, body, url, req });
    if (out === undefined && path.startsWith("/teach/")) out = { enabled: false, cached: 0, cost_limit: 0, estimated_usd: 0, lessons: 0, total: 0, price_per_mtok: { input: 0, output: 0 } };
    if (out === undefined && translations && path === "/translations") out = { texts: body.texts };
    if (out === undefined && DEFAULTS[path]) out = DEFAULTS[path]();
    if (out === undefined) throw Error("Unexpected request " + method + " " + path);
    const r = out && out.__reply ? out : { status: 200, data: out, type: "application/json" };
    await route.fulfill({ status: r.status, contentType: r.type, headers: CORS, body: typeof r.data === "string" ? r.data : JSON.stringify(r.data) });
  });
}

export async function launch() {
  const { chromium } = await import(process.env.MENTOR_PLAYWRIGHT_MODULE || "playwright");
  return chromium.launch({ headless: true, ...(process.env.MENTOR_BROWSER_PATH ? { executablePath: process.env.MENTOR_BROWSER_PATH } : {}) });
}

// For flows with their own route handler: the default data for a path, or undefined.
export function fallback(path, body = {}) {
  if (path.startsWith("/teach/")) return { enabled: false, cached: 0, cost_limit: 0, estimated_usd: 0, lessons: 0, total: 0, price_per_mtok: { input: 0, output: 0 } };
  if (path === "/translations") return { texts: body.texts };
  return DEFAULTS[path] ? DEFAULTS[path]() : undefined;
}

// Screenshots only when MENTOR_SHOTS names a folder, so the flows run anywhere (CI included).
export async function shot(page, name, options = {}) {
  if (!process.env.MENTOR_SHOTS) return;
  await page.screenshot({ ...options, path: process.env.MENTOR_SHOTS.replace(/\/$/, "") + "/" + name });
}
