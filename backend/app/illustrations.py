"""Small declarative teaching diagrams. No model-provided markup or code runs."""
import math
import json

INSTRUCTIONS = '''
Where a visual materially improves this explanation, include one optional
illustration. Omit it (null) for greetings, simple answers, or if a diagram would
be misleading. Match the learner's language. Use only information supported by
your explanation. A schematic is not a measured result. Never invent empirical
numbers. Use a worked example explicitly labelled as an example when appropriate.
Schema: illustration = {"type":"flow"|"comparison"|"vectors"|"bars",
 "title":"short title", "caption":"what to notice", ...}.
flow: "nodes":[{"id":"a","label":"short text"}],
      "edges":[{"from":"a","to":"b","label":"short relationship"}].
      2–6 nodes, at most 8 edges. Only use for actual processes/relationships.
comparison: "columns":[{"label":"case", "items":["point"]}].
      2–3 columns, 1–4 concise points each.
vectors: "vectors":[{"label":"q", "x":1, "y":2}, {"label":"k", "x":2, "y":1}].
      Exactly two 2D vectors for an explicitly illustrative worked example.
bars: "items":[{"label":"case", "value":0.5}], "unit":"unit".
      2–6 finite nonnegative values, only from the explanation or a labelled example.
Use readable concise labels. Do not emit SVG, HTML, Mermaid, URLs or code.
'''

def _language_name(code):
    """English name of the language; lazy import so this module also loads standalone in tests."""
    try:
        from .languages import name
    except ImportError:
        from languages import name          # tests load this file by path
    return name(code)


def language_line(code):
    """De taal van de illustratie expliciet noemen. "Match the learner's language" alleen
    was niet genoeg: de rest van de systeemprompt is Nederlands, en het model schreef de
    illustratie dan soms in het Nederlands onder een Engels antwoord (gezien 2026-09-19)."""
    return (f"\nWrite the illustration title, caption and every label in "
            f"{_language_name(code)}, the same language as the answer.")


def _text(value, limit=180):
    return value.strip()[:limit] if isinstance(value, str) else ""


def _number(value, limit=1e6):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and abs(value) <= limit and math.isfinite(value)


def validate(value):
    if not isinstance(value, dict):
        return None
    kind = value.get("type")
    out = {"type": kind, "title": _text(value.get("title"), 100), "caption": _text(value.get("caption"), 400)}
    if not out["title"]:
        return None
    if kind == "flow":
        nodes, edges = value.get("nodes"), value.get("edges")
        if not isinstance(nodes, list) or not 2 <= len(nodes) <= 6 or not isinstance(edges, list) or not 1 <= len(edges) <= 8:
            return None
        if any(not isinstance(n, dict) or not _text(n.get("id"), 40) or not _text(n.get("label"), 80) for n in nodes):
            return None
        out["nodes"] = [{"id": _text(n["id"], 40), "label": _text(n["label"], 80)} for n in nodes]
        ids = {n["id"] for n in out["nodes"]}
        if len(ids) != len(nodes) or any(not isinstance(e, dict) or not isinstance(e.get("from"), str) or not isinstance(e.get("to"), str) or e.get("from") not in ids or e.get("to") not in ids or e.get("from") == e.get("to") for e in edges):
            return None
        out["edges"] = [{"from": e["from"], "to": e["to"], "label": _text(e.get("label"), 60)} for e in edges]
    elif kind == "comparison":
        columns = value.get("columns")
        if not isinstance(columns, list) or not 2 <= len(columns) <= 3:
            return None
        if any(not isinstance(c, dict) or not _text(c.get("label"), 80) or not isinstance(c.get("items"), list) or not 1 <= len(c["items"]) <= 4 or any(not _text(i) for i in c["items"]) for c in columns):
            return None
        out["columns"] = [{"label": _text(c["label"], 80), "items": [_text(i) for i in c["items"]]} for c in columns]
    elif kind == "vectors":
        vectors = value.get("vectors")
        if not isinstance(vectors, list) or len(vectors) != 2 or any(not isinstance(v, dict) or not _text(v.get("label"), 40) or not _number(v.get("x"), 100) or not _number(v.get("y"), 100) for v in vectors):
            return None
        out["vectors"] = [{"label": _text(v["label"], 40), "x": v["x"], "y": v["y"]} for v in vectors]
    elif kind == "bars":
        items = value.get("items")
        if not isinstance(items, list) or not 2 <= len(items) <= 6 or any(not isinstance(i, dict) or not _text(i.get("label"), 80) or not _number(i.get("value")) or i["value"] < 0 for i in items):
            return None
        out["items"] = [{"label": _text(i["label"], 80), "value": i["value"]} for i in items]
        out["unit"] = _text(value.get("unit"), 40)
    else:
        return None
    return out


def message_context(message):
    text = message["content"]
    diagram = validate(message.get("illustration"))
    if diagram:
        text += "\n\n[Teaching diagram shown with this reply]\n" + json.dumps(diagram, ensure_ascii=False)
    return text
