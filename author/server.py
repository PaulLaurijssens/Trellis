"""trellis-author: the lesson workbench. Holds job files, bundles, and test-runs lessons in a browser.

It has NO model key, NO database access and NO network route (its Docker network is internal and has
only the API as the other member). The API calls it; it never calls anything. JSON over HTTP, stdlib only."""
import json
import os
import re
import shutil
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import bundle as bundler

WORK = Path(os.getenv("AUTHOR_WORK_DIR", "/work"))
ASSETS = Path(os.getenv("AUTHOR_ASSETS_DIR", "/assets"))
JOB = re.compile(r"^[A-Za-z0-9-]{8,64}$")
MAX_BODY = 1024 * 1024
MAX_JOB_BYTES = 4 * 1024 * 1024
MAX_JOBS = 8
_browser_lock = threading.Lock()          # one Chromium at a time keeps memory bounded


def job_dir(job_id: str, create: bool = False) -> Path:
    if not JOB.match(job_id or ""):
        raise bundler.BundleError("invalid job id")
    path = WORK / job_id
    if create and not path.exists():
        jobs = sorted((p for p in WORK.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
        for old in jobs[:max(0, len(jobs) - MAX_JOBS + 1)]:
            shutil.rmtree(old, ignore_errors=True)      # a crashed API never fills the tmpfs
        path.mkdir(parents=True)
    if not path.is_dir():
        raise bundler.BundleError("unknown job")
    return path


def op_write(job, body):
    target = bundler.safe_job_path(job, body.get("path"))
    content = body.get("content")
    if not isinstance(content, str) or len(content.encode()) > bundler.MAX_FILE:
        raise bundler.BundleError(f"content must be text of at most {bundler.MAX_FILE // 1024} KB")
    if target.suffix.lower() not in (".html", ".css", ".js", ".json", ".svg", ".md", ".txt"):
        raise bundler.BundleError("allowed file types: .html .css .js .json .svg .md .txt")
    used = sum(p.stat().st_size for p in job.rglob("*") if p.is_file() and p != target)
    if used + len(content.encode()) > MAX_JOB_BYTES:
        raise bundler.BundleError("the lesson directory is full (4 MB)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": body["path"], "bytes": len(content.encode())}


def op_read(job, body):
    target = bundler.safe_job_path(job, body.get("path"))
    if not target.is_file():
        raise bundler.BundleError(f"file not found: {body.get('path')}")
    return {"path": body["path"], "content": target.read_text(encoding="utf-8")}


def op_list(job, body):
    return {"files": sorted(str(p.relative_to(job)) for p in job.rglob("*") if p.is_file())}


def op_bundle(job, body):
    return bundler.bundle(job, ASSETS)


def op_validate(job, body):
    result = bundler.bundle(job, ASSETS)
    report = {"ok": False, "errors": list(result["errors"]), "warnings": [], "bundle": {k: result[k] for k in ("sha256", "bytes", "assets")}}
    if result["errors"]:
        return report                      # never execute a lesson that fails the static rules
    import validate                        # imports Playwright; keep the service startable without it
    with _browser_lock:
        browser = validate.run(result["html"], result["script_hashes"], body.get("manifest") or {},
                               screenshot=body.get("screenshot", True))
    return {**report, **browser}


def op_lint(job, body):
    """Static rules for files proposed as a reusable component (same rules as lesson code)."""
    errors, files = [], {}
    for rel in (body.get("paths") or [])[:8]:
        target = bundler.safe_job_path(job, rel)
        if not target.is_file():
            raise bundler.BundleError(f"file not found: {rel}")
        text = target.read_text(encoding="utf-8")
        kind = target.suffix.lower()
        if kind not in (".js", ".css", ".svg", ".md"):
            raise bundler.BundleError("a component may contain .js, .css, .svg and .md files")
        errors += [f"{rel}: {e}" for e in bundler.lint(text if kind == ".svg" else "", text if kind == ".js" else "", text if kind == ".css" else "")]
        files[rel] = text
    return {"errors": errors, "files": files}


OPS = {"lint": op_lint, "write": op_write, "read": op_read, "list": op_list, "bundle": op_bundle, "validate": op_validate}


class Handler(BaseHTTPRequestHandler):
    server_version = "trellis-author"

    def _send(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            # "assets" is true only when the shared lesson components are really there: a wrong mount
            # used to pass this check, and then every lesson failed on "unknown asset" after paying for it.
            components = sorted(f"{p.parent.parent.name}@{p.parent.name}" for p in ASSETS.glob("*/*/sdk.js"))
            return self._send(200, {"ok": True, "assets": bool(components), "components": components})
        self._send(404, {"error": "not found"})

    def do_DELETE(self):
        match = re.fullmatch(r"/jobs/([^/]+)", self.path)
        if not match or not JOB.match(match.group(1)):
            return self._send(404, {"error": "not found"})
        shutil.rmtree(WORK / match.group(1), ignore_errors=True)
        self._send(200, {"deleted": True})

    def do_POST(self):
        match = re.fullmatch(r"/jobs/([^/]+)/(\w+)", self.path)
        if not match or match.group(2) not in OPS:
            return self._send(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._send(413, {"error": "request too large"})
            body = json.loads(self.rfile.read(length) or b"{}")
            job = job_dir(match.group(1), create=match.group(2) == "write")
            self._send(200, OPS[match.group(2)](job, body if isinstance(body, dict) else {}))
        except bundler.BundleError as exc:
            self._send(422, {"error": str(exc)})
        except UnicodeDecodeError:
            self._send(422, {"error": "files must be UTF-8 text"})
        except Exception as exc:                       # the API shows this to the agent as a tool error
            self._send(500, {"error": f"{type(exc).__name__}: {str(exc)[:300]}"})

    def log_message(self, fmt, *args):
        print("author:", fmt % args, flush=True)


if __name__ == "__main__":
    WORK.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("AUTHOR_PORT", "8700"))), Handler).serve_forever()
