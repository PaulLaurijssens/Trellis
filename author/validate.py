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

ORIGIN = "http://dendrite.invalid"
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
                    errors.append("lesson.ready was not received within 5 s: load the SDK and call DendriteLesson.start()")
                ready_ms = int((time.monotonic() - t0) * 1000)
                page.wait_for_timeout(300)
                frame = next((f for f in page.frames if f.url == ORIGIN + "/lesson"), None)
                probe = frame.evaluate(PROBE) if frame else None
                host = page.evaluate("() => ({ events: window.__events, loads: window.__loads, rejected: window.__rejected })")
                report[name] = {"probe": probe, "host": host, "ready_ms": ready_ms}
                if name == "phone" and screenshot and frame:
                    shot = page.screenshot(type="jpeg", quality=60, full_page=False)
                    report["screenshot_jpeg_b64"] = base64.b64encode(shot).decode()
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
        for t in phone["targets"]:
            if t["type"] in ("range", "checkbox", "radio"):
                continue
            if min(t["w"], t["h"]) < 32:
                errors.append(f"touch target too small ({t['w']}x{t['h']} px): {t['tag']} {t['label']!r}")
            elif min(t["w"], t["h"]) < 44:
                warnings.append(f"touch target under 44 px ({t['w']}x{t['h']}): {t['tag']} {t['label']!r}")
    if (report.get("phone") or {}).get("ready_ms", 0) > 3000:
        warnings.append("the lesson needs more than 3 s to become ready")
    if blocked:
        errors.append("the lesson tried to load from the network (blocked): " + ", ".join(sorted(set(blocked))[:5]))
    for line in list(dict.fromkeys(console))[:8]:
        errors.append("browser error: " + line)
    return {"ok": not errors, "errors": errors[:25], "warnings": warnings[:15],
            "screenshot_jpeg_b64": report.get("screenshot_jpeg_b64"),
            "ready_ms": (report.get("phone") or {}).get("ready_ms"),
            "seconds": round(time.monotonic() - started, 1),
            "events": ((report.get("phone") or {}).get("host") or {}).get("events")}
