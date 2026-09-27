"use client";
// Who is logged in. The API decides from its cookie; this module only remembers the answer so the
// request helpers can build URLs, and it tells the app whether to show setup, login or the app.
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
let person = null;
const listeners = new Set();

export function getPerson() { return person ? person.id : null; }
export function getPersonInfo() { return person; }
export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }
// Listeners fire only on a real change (a session appearing or ending), never on a repeated status
// call: the app refetches status when a listener fires, so firing on every call would loop.
function set(next) {
  const before = person ? person.id : null, after = next ? next.id : null;
  person = next;
  if (before !== after) listeners.forEach((fn) => fn(person));
}

async function call(path, body, method = "POST") {
  const res = await fetch(BASE + path, { method: body === undefined ? method : method, credentials: "include",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  let data = null;
  try { data = await res.json(); } catch {}
  if (!res.ok) { const err = new Error((data && data.detail) || "HTTP " + res.status); err.status = res.status; throw err; }
  return data;
}

export const session = {
  status: () => call("/auth/status", undefined, "GET").then((s) => { set(s.authenticated ? s.person : null); return s; }),
  setup: (body) => call("/auth/setup", body).then((d) => { set(d.person); return d; }),
  login: (body) => call("/auth/login", body).then((d) => { set(d.person); return d; }),
  logout: () => call("/auth/logout", {}).then(() => set(null)),
  me: () => call("/auth/me", undefined, "GET"),
  settings: () => call("/auth/settings", undefined, "GET"),
  saveSettings: (body) => call("/auth/settings", body, "PUT"),
};

// A 401 anywhere means the session ended (expired cookie, server restart with a new secret): back to login.
export function handleUnauthorized(err) { if (err && err.status === 401 && person) set(null); }
