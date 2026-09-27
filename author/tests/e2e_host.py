"""End-to-end check of the M1 gate against a running app, in real Chromium at phone size.

Run it with the workbench image (it has Playwright):
  docker exec -i -e APP=http://host.docker.internal:3001 -e CONCEPT="Matrix (mathematics)" mentor-author python - < author/tests/e2e_host.py
Needs: a published lesson for CONCEPT. ASK=1 also sends one real mentor question (one model call)."""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

APP = os.getenv("APP", "http://host.docker.internal:3001")
CONCEPT = os.getenv("CONCEPT", "Matrix (mathematics)")
ASK = os.getenv("ASK") == "1"
checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""), flush=True)


def open_lesson(page):
    page.goto(APP, wait_until="networkidle")
    page.evaluate("(name) => localStorage.setItem('trellis.e2e', name)", CONCEPT)
    # The learning home offers the last conversation; otherwise search by name.
    page.wait_for_timeout(1500)
    if not page.locator(".learn-workspace").count():     # after a reload the app reopens the topic itself
        page.get_by_role("button", name=re.compile("Resume|Hervat|Continue learning|Verder leren")).first.click()
    page.wait_for_selector(".learn-workspace", timeout=15000)
    page.wait_for_selector(".teach-dock", timeout=15000)
    # Never the "make a lesson" button: that would start a paid authoring job.
    resume = page.locator(".teach-start > .btn").filter(has_text=re.compile("Continue|Ga verder"))
    if resume.count():
        resume.first.click()
    else:
        page.locator(".teach-more summary").click()
        page.locator(".teach-more .teach-row").first.click()
    page.wait_for_selector("iframe.teach-frame", timeout=15000)
    frame = page.frame_locator("iframe.teach-frame")
    frame.locator(".dl-nav").wait_for(timeout=15000)
    return frame


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    context = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    # A fresh run, so the test is repeatable: any open run of this concept is abandoned first.
    page.goto(APP, wait_until="networkidle")
    closed = page.evaluate("""async (name) => {
      const graph = await (await fetch('/api/graph')).json();
      const node = graph.nodes.find((n) => n.name === name); if (!node) return 'concept not found';
      const post = (url, method, body) => fetch(url, {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).then((r) => r.json());
      const ctx = await post('/api/teach/paul/concepts/' + node.id + '/context', 'POST', {});
      for (const l of ctx.lessons) if (l.open_run_id) { const run = await (await fetch('/api/teach/paul/runs/' + l.open_run_id)).json();
        await post('/api/teach/paul/runs/' + l.open_run_id, 'PATCH', {expected_revision: run.state_revision, status: 'abandoned'}); }
      return ctx.lessons.length; }""", CONCEPT)
    check("the concept has a published lesson", isinstance(closed, int) and closed > 0, closed)
    frame = open_lesson(page)
    check("lesson opens in a sandboxed frame on a phone", True)
    sandbox = page.locator("iframe.teach-frame").get_attribute("sandbox")
    check("frame sandbox is allow-scripts only", sandbox == "allow-scripts", sandbox)
    lesson_frame = next(f for f in page.frames if "/artifact" in f.url)
    origin = lesson_frame.evaluate("() => window.origin")
    check("frame has an opaque origin", origin == "null", origin)
    storage = lesson_frame.evaluate("() => { try { localStorage.setItem('x','1'); return 'writable'; } catch (e) { return 'blocked'; } }")
    check("frame cannot use storage", storage == "blocked", storage)
    net = lesson_frame.evaluate("async () => { try { await fetch('/api/memory/paul'); return 'reached'; } catch (e) { return 'blocked'; } }")
    check("frame cannot call the API", net == "blocked", net)

    # 1. prediction -> the SERVER checks it
    first_activity = frame.locator("section[data-dl-activity]:not([hidden])")
    options = first_activity.locator(".dl-option")
    for _ in range(6):
        if options.count():
            break
        frame.locator(".dl-nav .dl-btn-primary").click()
        page.wait_for_timeout(300)
    check("prediction activity is visible", options.count() >= 2)
    options.nth(0).click()
    first_activity.locator("button.dl-btn-primary").click()
    feedback = first_activity.locator(".dl-feedback")
    page.wait_for_timeout(2500)
    outcome = feedback.get_attribute("data-outcome")
    check("server feedback arrives in the frame", outcome in ("demonstrated", "needs_practice"), outcome)

    # 2. manipulate
    number = frame.locator("section[data-dl-activity]:not([hidden]) input[type=number]").first
    for _ in range(6):                                   # knowledge steps may sit between the activities
        if number.count():
            break
        frame.locator(".dl-nav .dl-btn-primary").click()
        page.wait_for_timeout(300)
    check("a manipulate activity is reachable", number.count() == 1)
    number.fill("2.5")
    number.press("Tab")
    page.wait_for_timeout(1800)                         # debounce (0.5 s) + checkpoint
    progress_before = frame.locator(".dl-progress").inner_text()

    # 3. ask the mentor from inside the lesson: the frame must stay mounted
    frame.locator("[data-dl-ask-mentor]").click()
    page.wait_for_timeout(500)
    check("ask-mentor switches to the mentor pane", "pane-mentor" in (page.locator(".learn-workspace").get_attribute("class") or ""))
    if ASK:
        page.locator(".lesson-main .chat-input textarea").fill("Why did the output change when I changed that weight?")
        with page.expect_response(lambda r: "/questions" in r.url, timeout=120000) as response:
            page.locator(".lesson-main .chat-input .send").click()
        check("contextual question answered through the lesson route", response.value.ok, response.value.status)
    page.locator(".teach-tabs button").first.click()
    check("activity is unchanged after the question", number.input_value() == "2.5" and frame.locator(".dl-progress").inner_text() == progress_before)

    # 4. forged events
    forged = page.evaluate("""() => { window.postMessage({v:1,type:'lesson.ready',activities:[]}, '*'); window.postMessage({v:1,type:'activity.answer_submitted',seq:9999,activity_id:'x',payload:{score:100}}, '*'); return true; }""")
    check("forged window messages are ignored (no crash, lesson still running)", forged and page.locator("iframe.teach-frame").count() == 1)

    # 5. close and reopen: exact resume
    page.wait_for_timeout(1200)
    page.reload(wait_until="networkidle")
    frame = open_lesson(page)
    page.wait_for_timeout(1500)
    resumed = frame.locator("section[data-dl-activity]:not([hidden]) input[type=number]").first
    check("reopen resumes on the same step", frame.locator(".dl-progress").inner_text() == progress_before, frame.locator(".dl-progress").inner_text())
    check("reopen restores the manipulated value", resumed.count() == 1 and resumed.input_value() == "2.5", resumed.input_value() if resumed.count() else "missing")
    committed = frame.locator("section[data-dl-activity]:not([hidden]) .dl-option input").first
    for _ in range(6):
        if committed.count():
            break
        frame.locator(".dl-nav .dl-btn-ghost").first.click()
        page.wait_for_timeout(300)
    check("reopen restores the committed prediction", committed.is_disabled() and committed.is_checked())

    overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    check("no horizontal scroll on the phone", overflow <= 1, overflow)
    # The test's own fetch() from inside the frame is SUPPOSED to be refused by the CSP; that message is expected.
    unexpected = [e for e in errors if "Content Security Policy" not in e and "/api/memory/paul" not in e]
    check("no browser errors", not unexpected, unexpected[:3])
    browser.close()

failed = [name for name, ok in checks if not ok]
print(json.dumps({"passed": len(checks) - len(failed), "failed": failed}))
sys.exit(1 if failed else 0)
