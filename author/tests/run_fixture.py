"""Sends the fixture lesson to a running workbench and prints the validation report.
Usage: python3 author/tests/run_fixture.py [http://127.0.0.1:8700] [--shot out.jpg]"""
import base64
import json
import sys
import urllib.request
from pathlib import Path

BASE = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8700")
FIXTURE = Path(__file__).parent / "fixture"
JOB = "fixture-0001"


def call(method, path, body=None):
    request = urllib.request.Request(BASE + path, method=method, data=json.dumps(body or {}).encode(),
                                     headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=120) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        return {"http_error": error.code, **json.loads(error.read() or b"{}")}


if __name__ == "__main__":
    call("DELETE", f"/jobs/{JOB}")
    for name in ("index.html", "lesson.js"):
        print(call("POST", f"/jobs/{JOB}/write", {"path": name, "content": (FIXTURE / name).read_text()}))
    print("escape attempt:", call("POST", f"/jobs/{JOB}/write", {"path": "../evil.js", "content": "x"}))
    print("asset write attempt:", call("POST", f"/jobs/{JOB}/write", {"path": "assets/x.js", "content": "x"}))
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    report = call("POST", f"/jobs/{JOB}/validate", {"manifest": manifest})
    shot = report.pop("screenshot_jpeg_b64", None)
    print(json.dumps(report, indent=1)[:3000])
    if shot and "--shot" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--shot") + 1])
        out.write_bytes(base64.b64decode(shot))
        print("screenshot:", out)
