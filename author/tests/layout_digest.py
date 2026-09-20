"""Layout regression check: the app with interactive lessons switched OFF must be pixel-identical to
the previous release. Captures tag, classes, rounded getBoundingClientRect and computed
display/position of every element (outside the animated graph), at 1440 and 768, on the learning
home and inside the mentor panel, for two running frontends, and diffs them.

  docker exec -i -e OLD=http://localhost:3002 -e NEW=http://localhost:3001 mentor-author python - < author/tests/layout_digest.py"""
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

OLD, NEW = os.getenv("OLD"), os.getenv("NEW")
SNAPSHOT = """() => [...document.querySelectorAll('body *')].filter((el) => !el.closest('svg, canvas, .living-graph, script, style, nextjs-portal'))
  .map((el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return [el.tagName, el.className && el.className.baseVal === undefined ? String(el.className) : '', Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height), s.display, s.position].join('|'); })"""


def capture(browser, base, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    page.goto(base, wait_until="networkidle")
    page.wait_for_timeout(2500)
    out = {"home": page.evaluate(SNAPSHOT)}
    if not page.locator(".learn-workspace").count():
        page.get_by_role("button", name=re.compile("Resume|Hervat|Continue learning|Verder leren")).first.click()
    page.wait_for_selector(".learn-workspace", timeout=15000)
    page.wait_for_timeout(3500)
    out["panel"] = page.evaluate(SNAPSHOT)
    context.close()
    return out


with sync_playwright() as p:
    # Inside the container "localhost" must mean the Mac, because the old frontend calls localhost:8000.
    browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage", "--host-resolver-rules=MAP localhost host.docker.internal"])
    failed = False
    for width, height in ((1440, 900), (768, 1024)):
        old, new = capture(browser, OLD, width, height), capture(browser, NEW, width, height)
        for view in ("home", "panel"):
            same = old[view] == new[view]
            failed |= not same
            print(f"{'PASS' if same else 'FAIL'} {width}px {view}: {len(old[view])} elements old, {len(new[view])} new")
            if not same:
                a, b = set(old[view]), set(new[view])
                for line in sorted(a - b)[:6]:
                    print("   only old:", line[:160])
                for line in sorted(b - a)[:6]:
                    print("   only new:", line[:160])
    browser.close()
sys.exit(1 if failed else 0)
