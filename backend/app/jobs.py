"""Progress of running analyses. The client picks a job id, sends it with the ingest
call and polls GET /ingest/status/{id}. In memory: one process, and an analysis that
does not survive a restart need not be followed either."""
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
