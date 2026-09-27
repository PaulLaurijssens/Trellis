"""Runs the bundled lesson in headless Chromium, inside the same sandbox + CSP as production.

This is the ONLY place where generated code executes on the server side. The container around it has
no network, no secrets and a read-only root filesystem; every request the page makes is aborted and
reported. Chromium runs with --no-sandbox because the container (cap_drop ALL, non-root, no userns)
is the boundary here."""
import base64
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from bundle import csp

ORIGIN = "http://trellis.invalid"
HARNESS = (Path(__file__).parent / "harness.html").read_text()
READY_TIMEOUT_MS = 5000

PROBE = """() => {
  const visible = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const targets = [...document.querySelectorAll('button, a[href], input, select, textarea, [role=button], [role=slider], [data-dl-action]')]
    .filter(visible).map((el) => { const r = el.getBoundingClientRect();
      return { tag: el.tagName.toLowerCase(), label: (el.getAttribute('aria-label') || el.textContent || el.name || '').trim().slice(0, 40),
               w: Math.round(r.width), h: Math.round(r.height), type: el.type || '' }; });
  return {
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    activities: [...document.querySelectorAll('[data-dl-activity]')].map((el) => ({ id: el.getAttribute('data-dl-activity'), visible: visible(el) })),
    objective: !!document.querySelector('[data-dl-objective]'),
    primarySource: !!document.querySelector('[data-dl-source][data-dl-primary]'),
    sources: [...document.querySelectorAll('[data-dl-source]')].map((el) => el.getAttribute('data-dl-source')),
    askMentor: !!document.querySelector('[data-dl-ask-mentor]'),
    lang: document.documentElement.lang || '',
    title: document.title || '',
    targets,
    textLength: (document.body.innerText || '').length,
  };
}"""


TARGETS = """() => [...document.querySelectorAll('button, a[href], input, select, textarea, [role=button], [role=slider], [data-dl-action]')]
  .filter((el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && !el.closest('[hidden]'); })
  .map((el) => { const r = el.getBoundingClientRect(); return { tag: el.tagName.toLowerCase(), label: (el.getAttribute('aria-label') || el.textContent || el.name || '').trim().slice(0, 40), w: Math.round(r.width), h: Math.round(r.height), type: el.type || '' }; })"""

# Readability of the step that is visible now: text colour against the first opaque background behind it.
CONTRAST = """() => {
  const parse = (c) => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(',').map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const over = (top, under) => ({ r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1 });
  const background = (el) => { const layers = []; for (let n = el; n; n = n.parentElement) { const c = parse(getComputedStyle(n).backgroundColor); if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; } }
    let base = { r: 7, g: 11, b: 17, a: 1 }; for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base); return base; };
  const bad = []; const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.nodeValue.trim(); const el = node.parentElement;
    if (text.length < 2 || !el || seen.has(el) || el.closest('[hidden], script, style, svg')) continue;
    const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    if (!r.width || !r.height || cs.visibility === 'hidden' || Number(cs.opacity) < 0.3) continue;
    seen.add(el);
    const fg = parse(cs.color); if (!fg) continue;
    const bg = background(el); const color = over(fg, bg);
    const a = lum(color), b = lum(bg); const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    if (ratio < 3) bad.push({ text: text.slice(0, 40), ratio: Math.round(ratio * 10) / 10, light_background: lum(bg) > 0.5 });
  }
  const steps = document.querySelectorAll('main.dl-lesson > section').length;
  const lightBoxes = [...document.querySelectorAll('main.dl-lesson *')].filter((el) => { if (el.closest('[hidden], svg')) return false; const c = parse(getComputedStyle(el).backgroundColor); const r = el.getBoundingClientRect(); return c && c.a > 0.5 && lum(c) > 0.6 && r.width > 12 && r.height > 12; }).length;
  return { bad: bad.slice(0, 6), steps, lightBoxes };
}"""


def run(html: str, hashes: list[str], manifest: dict, screenshot: bool = True) -> dict:
    errors, warnings, blocked, console = [], [], [], []
    started = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"])
        try:
            report = {}
            for name, viewport, touch in (("phone", {"width": 390, "height": 844}, True),
                                          ("desktop", {"width": 1440, "height": 900}, False)):
                context = browser.new_context(viewport=viewport, has_touch=touch, is_mobile=touch,
                                              java_script_enabled=True, service_workers="block", locale="en-US")
                page = context.new_page()

                def route(r):
                    url = r.request.url
                    if url == ORIGIN + "/":
                        r.fulfill(status=200, content_type="text/html; charset=utf-8", body=HARNESS)
                    elif url == ORIGIN + "/lesson":
                        r.fulfill(status=200, body=html, headers={"Content-Type": "text/html; charset=utf-8",
                                                                   "Content-Security-Policy": csp(hashes),
                                                                   "X-Content-Type-Options": "nosniff"})
                    else:
                        if not url.startswith(("data:", "blob:")):
                            blocked.append(url[:200])
                        r.abort()
                page.route("**/*", route)
                page.on("console", lambda m: console.append(m.text[:300]) if m.type == "error" else None)
                page.on("pageerror", lambda e: console.append(str(e)[:300]))
                page.goto(ORIGIN + "/", wait_until="load", timeout=15000)
                t0 = time.monotonic()
                try:
                    page.wait_for_function("window.__ready === true", timeout=READY_TIMEOUT_MS)
                except Exception:
                    errors.append("lesson.ready was not received within 5 s: load the SDK and call TrellisLesson.start()")
                ready_ms = int((time.monotonic() - t0) * 1000)
                page.wait_for_timeout(300)
                frame = next((f for f in page.frames if f.url == ORIGIN + "/lesson"), None)
                probe = frame.evaluate(PROBE) if frame else None
                host = page.evaluate("() => ({ events: window.__events, loads: window.__loads, rejected: window.__rejected })")
                report[name] = {"probe": probe, "host": host, "ready_ms": ready_ms}
                if name == "phone" and frame and probe:
                    # Walk through every step like a learner: each one is measured and photographed.
                    shots, steps = [], []
                    count = min(frame.evaluate("() => document.querySelectorAll('main.dl-lesson > section').length") or 1, 8)
                    for index in range(count):
                        frame.evaluate("(i) => window.TrellisLesson && window.TrellisLesson.goTo(i)", index)
                        page.wait_for_timeout(250)
                        steps.append({"step": index + 1, **frame.evaluate(CONTRAST), "targets": frame.evaluate(TARGETS),
                                      "overflow": frame.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")})
                        if screenshot:
                            shots.append(base64.b64encode(page.screenshot(type="jpeg", quality=55, full_page=False)).decode())
                    frame.evaluate("() => window.TrellisLesson && window.TrellisLesson.goTo(0)")
                    report["steps"], report["screenshots_jpeg_b64"] = steps, shots
                context.close()
        finally:
            browser.close()

    declared = [a["id"] for a in manifest.get("activities", [])]
    for name in ("phone", "desktop"):
        view = report.get(name) or {}
        probe, host = view.get("probe"), view.get("host") or {}
        if not probe:
            errors.append(f"{name}: the lesson did not load")
            continue
        if probe["overflow"] > 1:
            errors.append(f"{name}: the page scrolls horizontally by {probe['overflow']} px")
        if (host.get("loads") or 0) > 1:
            errors.append(f"{name}: the lesson navigated or reloaded itself")
        if host.get("rejected"):
            errors.append(f"{name}: the host rejected {host['rejected']} malformed message(s) from the lesson")
        ready = next((e for e in host.get("events") or [] if e.get("type") == "lesson.ready"), None)
        if ready and sorted(ready.get("activities") or []) != sorted(declared):
            errors.append(f"{name}: lesson.ready announced activities {ready.get('activities')} but the manifest declares {declared}")
    phone = (report.get("phone") or {}).get("probe")
    if phone:
        found = [a["id"] for a in phone["activities"]]
        for missing in [a for a in declared if a not in found]:
            errors.append(f'activity "{missing}" is in the manifest but has no <section data-dl-activity="{missing}">')
        if sum(a["visible"] for a in phone["activities"]) > 1:
            errors.append("phone: more than one activity is visible at the same time; the SDK stepper shows one")
        if not phone["objective"]:
            errors.append("the lesson does not show its outcome: add an element with data-dl-objective")
        if not phone["askMentor"]:
            errors.append("the reminder to ask the mentor is missing: add data-dl-ask-mentor (the SDK shell adds one)")
        if manifest.get("sources") and not phone["primarySource"]:
            errors.append("no primary source is recommended: mark one source link with data-dl-primary")
        allowed = {s["source_id"] for s in manifest.get("sources", [])}
        for ref in phone["sources"]:
            if ref not in allowed:
                errors.append(f"the lesson cites source {ref!r}, which is not in the manifest")
        if phone["lang"] != manifest.get("language"):
            errors.append(f'<html lang="{phone["lang"]}"> does not match the manifest language {manifest.get("language")!r}')
        if phone["textLength"] < 200:
            errors.append("the lesson has almost no text")
        for step in report.get("steps") or []:
            for t in step["targets"]:
                if t["type"] in ("range", "checkbox", "radio"):
                    continue
                if min(t["w"], t["h"]) < 32:
                    errors.append(f"step {step['step']}: touch target too small ({t['w']}x{t['h']} px): {t['tag']} {t['label']!r}; use .dl-btn / .dl-input (44 px)")
                elif min(t["w"], t["h"]) < 44:
                    warnings.append(f"step {step['step']}: touch target under 44 px ({t['w']}x{t['h']}): {t['tag']} {t['label']!r}")
    for step in report.get("steps") or []:
        for item in step["bad"]:
            where = "on a light background; lessons are dark: use var(--card), var(--figure) or var(--code-bg)" if item["light_background"] else "use var(--text-1) or var(--text-2) for text"
            errors.append(f"step {step['step']}: unreadable text {item['text']!r} (contrast {item['ratio']}:1, need 3:1) - {where}")
        if step["lightBoxes"] and not any(i["light_background"] for i in step["bad"]):
            warnings.append(f"step {step['step']}: {step['lightBoxes']} light-coloured box(es) in a dark lesson; use the theme tokens")
        if step["overflow"] > 1:
            errors.append(f"step {step['step']}: scrolls horizontally by {step['overflow']} px on a phone")
    if (report.get("phone") or {}).get("ready_ms", 0) > 3000:
        warnings.append("the lesson needs more than 3 s to become ready")
    if blocked:
        errors.append("the lesson tried to load from the network (blocked): " + ", ".join(sorted(set(blocked))[:5]))
    for line in list(dict.fromkeys(console))[:8]:
        hint = ""
        if "NaN" in line or "Expected number" in line or "Expected length" in line:
            hint = (" -> a coordinate is not a number. Draw with TrellisLesson.plane helpers (they name the bad argument), pass points as "
                    "[[x, y], ...] arrays of numbers, check every division (sigma = 0?) and every value read from state or an input (Number(...)).")
        errors.append("browser error: " + line + hint)
    return {"ok": not errors, "errors": errors[:25], "warnings": warnings[:15],
            "screenshots_jpeg_b64": report.get("screenshots_jpeg_b64") or [],
            "ready_ms": (report.get("phone") or {}).get("ready_ms"),
            "seconds": round(time.monotonic() - started, 1),
            "events": ((report.get("phone") or {}).get("host") or {}).get("events")}
