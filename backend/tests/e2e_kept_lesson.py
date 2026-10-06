"""Makes a lesson fail its checks on purpose, without the AI, to see the "kept lesson" screen on a dev install.

    docker compose -f compose.dev.yaml exec backend python tests/e2e_kept_lesson.py            # quality problem: Fix these + Open it anyway
    docker compose -f compose.dev.yaml exec backend python tests/e2e_kept_lesson.py --unsafe   # safety problem: only Fix these

It runs the real lesson job: workbench, checks, the free final re-check, the kept draft and the job record.
Only the model is replaced, by a script that writes a small lesson with one defect and stops without
publishing. It uses the concept of your newest lesson job. Costs no tokens; "Fix these" on the screen does."""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import graph                                   # noqa: E402
from app.teach import lessons, orchestrator             # noqa: E402

UNSAFE = "--unsafe" in sys.argv

INDEX = """<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test lesson that fails a check</title>
<link rel="stylesheet" href="assets/trellis-lesson/1.1.0/fonts.css">
<link rel="stylesheet" href="assets/trellis-lesson/1.1.0/lesson.css">
<script src="assets/trellis-lesson/1.1.0/sdk.js"></script>
<script src="lesson.js"></script>
</head><body><main class="dl-lesson">
<header class="dl-header"><p class="dl-eyebrow">Test · 5 min</p><h1>Test lesson that fails a check</h1>
<p data-dl-objective>After this lesson you can predict where a 2x2 matrix sends the unit square.</p></header>
<section data-dl-title="The idea"><p>A 2x2 matrix moves every point of the plane. It is enough to know where the two basis vectors land: the columns of the matrix are those landing points. Everything else follows, because the grid stays a grid of parallel, evenly spaced lines.</p>
<p style="color:#20252b">This sentence is dark grey on a dark background on purpose, so the readability check fails.</p></section>
<section data-dl-activity="predict-1" data-dl-title="Predict"><div data-dl-mount></div><p data-dl-hint hidden>Look at the first column only.</p></section>
<section data-dl-title="Recap"><p>The columns of a matrix are where the basis vectors land.</p></section>
</main></body></html>
"""
LESSON_JS = """document.addEventListener('DOMContentLoaded', function () {
  var DL = window.TrellisLesson;
  DL.predict('predict-1', { question: 'The matrix has columns (2,0) and (0,1). What happens to the unit square?',
    options: [{ id: 'a', label: 'It becomes twice as tall' }, { id: 'b', label: 'It becomes twice as wide' }, { id: 'c', label: 'It turns a quarter turn' }] });
});
"""
MANIFEST = {"title": "Test lesson that fails a check", "outcome": "Predict where a 2x2 matrix sends the unit square.", "language": "en",
            "duration_min": 5, "illustrative_values": True, "assets": ["trellis-lesson@1.1.0"], "sources": [],
            "activities": [{"id": "predict-1", "type": "predict", "title": "Predict", "state_fields": ["choice", "committed"],
                            "events": ["activity.state_changed", "activity.answer_submitted"], "check": {"kind": "choice", "expected": "b"}}]}


def main():
    owner = graph.run("MATCH (p:Person) WHERE p.password_hash IS NOT NULL RETURN p.id AS id ORDER BY p.created_at LIMIT 1")
    if not owner:
        sys.exit("No account yet: finish the setup screen first.")
    pid = owner[0]["id"]
    last = graph.run("MATCH (j:LessonJob {person_id:$pid}) RETURN j.request_json AS r ORDER BY j.created_at DESC LIMIT 1", pid=pid)
    if not last:
        sys.exit("Make one normal lesson first: this script reuses its concept.")
    base = json.loads(last[0]["r"])
    lang = base.get("language") or "en"
    request = {"topic_id": base["topic_id"], "concept_id": base["concept_id"], "objective_id": base.get("objective_id"),
               "language": lang, "time_budget_min": 10, "intent": None, "note": None, "device": "desktop", "repair_of": None}
    job, created = lessons.create_job(pid, request, "e2e-kept-" + uuid.uuid4().hex[:12])
    if not created:
        sys.exit(f"A lesson job is already running ({job['id'][:8]}). Wait for it, then run this again.")

    files = {"index.html": INDEX.replace("{lang}", lang), "manifest.json": json.dumps({**MANIFEST, "language": lang}),
             "lesson.js": ("eval('1');\n" if UNSAFE else "") + LESSON_JS}

    def scripted_author(system, task, tools, handler, model, **kwargs):
        for path, content in files.items():
            handler("lesson_write_file", {"path": path, "content": content})
        result, _ = handler("lesson_validate", {})
        print("check by the workbench:", "passed" if result.get("ok") else "failed", "|", "; ".join(result.get("errors") or [])[:300])
        return "scripted author: stopped without publishing"

    orchestrator.llm.tool_loop = scripted_author           # only in this process; the running app is not touched
    orchestrator.PLAN_STEP = False
    orchestrator.Job(pid, job["id"], request).run()

    done = lessons.get_job(pid, job["id"])
    concept = graph.run("MATCH (c:Concept {id:$cid}) RETURN c.name AS name", cid=request["concept_id"])
    print("job:", done["id"][:8], "| stage:", done["stage"], "| error:", done.get("error"))
    print("kept lesson:", json.dumps(done.get("draft")))
    expect_open = not UNSAFE
    ok = done["stage"] == "failed" and done.get("draft") and done["draft"]["can_open"] is expect_open
    print("RESULT:", "as expected" if ok else "NOT as expected")
    print(f"Now open '{concept[0]['name'] if concept else request['concept_id']}' on the dev app and reload the page.")


if __name__ == "__main__":
    main()
