"""Voortgang van lopende analyses. De client kiest een job-id, stuurt die mee
met de ingest-call en pollt GET /ingest/status/{id}. In-memory: één proces,
en een analyse die de herstart niet overleeft hoeft ook niet gevolgd te worden."""
import time

_JOBS: dict[str, dict] = {}
TTL = 900  # seconden


def update(job_id: str | None, phase: str, done: int = 0, total: int = 0, message: str = ""):
    if not job_id:
        return
    now = time.time()
    for k in [k for k, v in _JOBS.items() if now - v["updated"] > TTL]:
        _JOBS.pop(k, None)
    _JOBS[job_id] = {"phase": phase, "done": done, "total": total, "message": message, "updated": now}


def get(job_id: str) -> dict | None:
    j = _JOBS.get(job_id)
    if not j:
        return None
    return {k: v for k, v in j.items() if k != "updated"}
