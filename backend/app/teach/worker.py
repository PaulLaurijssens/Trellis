"""Client for trellis-author (the lesson workbench). Internal HTTP, never through the egress proxy:
the API's environment has HTTP(S)_PROXY set, so the proxy is switched off explicitly here."""
import json
import os
import urllib.error
import urllib.request

BASE = os.getenv("AUTHOR_URL", "http://trellis-author:8700").rstrip("/")
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class WorkerError(RuntimeError):
    """The workbench refused the request (422) or is unavailable. The message is safe to show the agent."""


def _call(method: str, path: str, body: dict | None = None, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(BASE + path, method=method, data=json.dumps(body or {}).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with _opener.open(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        try:
            detail = json.loads(error.read() or b"{}").get("error") or f"workbench error {error.code}"
        except ValueError:
            detail = f"workbench error {error.code}"
        raise WorkerError(detail) from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise WorkerError("The lesson workbench is not available.") from error


def healthy() -> bool:
    try:
        return bool(_call("GET", "/health", timeout=3).get("ok"))
    except WorkerError:
        return False


def write_file(job_id, path, content):
    return _call("POST", f"/jobs/{job_id}/write", {"path": path, "content": content})


def read_file(job_id, path):
    return _call("POST", f"/jobs/{job_id}/read", {"path": path})["content"]


def list_files(job_id):
    return _call("POST", f"/jobs/{job_id}/list")["files"]


def validate(job_id, manifest, screenshot=True):
    return _call("POST", f"/jobs/{job_id}/validate", {"manifest": manifest, "screenshot": screenshot}, timeout=120)


def bundle(job_id):
    return _call("POST", f"/jobs/{job_id}/bundle", timeout=60)


def lint_files(job_id, paths):
    return _call("POST", f"/jobs/{job_id}/lint", {"paths": paths})


def delete_job(job_id):
    try:
        _call("DELETE", f"/jobs/{job_id}", timeout=10)
    except WorkerError:
        pass
