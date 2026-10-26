"""Chunked, parallel concept extraction over long transcripts.

Phases: blocks -> segmentation by content -> parallel extraction per chunk (with
overlapping preceding context) -> global merge on embeddings -> importance -> one
relations call. Stores nothing; /learn does that later."""
import asyncio, json, logging, math, re

from . import llm, jobs
from .provider_errors import ProviderError

log = logging.getLogger("uvicorn.error")

CONCURRENCY = 6
WPM = 150                      # words per minute: makes untimed text comparable to speech
BLOCK_SEC = 40                 # target size of a label block
BLOCK_WORDS = 90
CHUNK_TARGET_SEC = 11 * 60     # 8-15 minuten spraak per chunk
CHUNK_MAX_SEC = 15 * 60
CHUNK_MIN_SEC = 3 * 60
CHAPTER_SPLIT_SEC = 12 * 60
CHAPTER_MERGE_SEC = 3 * 60
OVERLAP_FRACTION = 0.10
SEGMENT_CONDENSE_CHARS = 60000
SIM_SAME = 0.90
SIM_MAYBE = 0.80
MAX_RELATION_CANDIDATES = 80

EXTRACT_SYSTEM = """You are an expert who structures technical knowledge.
You get part of a transcript, split into numbered blocks such as [b12 @ 4:45] or [b12].
Extract the most important technical concepts from this part.
Rules:
- Only concepts the reader has to understand; no names of people, companies or products unless it is a technical concept.
- Canonical English name (e.g. "transformer architecture", not "transformers" or "the transformer").
- definition: 1-2 sentences, neutral, independent of the source, written in {language}.
- context: how this part of the source uses the concept (1 sentence, in {language}).
- quote: a literal quotation of 1-2 sentences from this part where the concept is discussed. Literal, not paraphrased.
- block: the block number (e.g. "b12") of the block that holds the quote.
- importance 1-5: how central it is in this part.
- Text between "[preceding context, do not extract]" and "[end of preceding context]" is for orientation only: extract no concepts from it.
- No relations; only concepts.
Answer with JSON only:
{{"concepts":[{{"name":"","aliases":[],"definition":"","domain":"","context":"","quote":"","block":"b0","importance":3}}]}}"""

SEGMENT_SYSTEM = """You get a transcript as numbered blocks with timestamps.
Point out the blocks where a NEW topic starts, so that the transcript falls into coherent parts of about {target_min} to {target_max} minutes.
Rules:
- Choose boundaries at real topic changes, not at fixed distances.
- Parts shorter than {min_min} minutes or longer than {target_max} minutes only when the content really asks for it.
- Block 0 is always the start of the first part; do not list it.
Answer with JSON only: {{"boundaries":[<block numbers where a new part starts>]}}"""

CONFIRM_SYSTEM = """You get pairs of concepts from one source. Decide per pair whether it is the same concept (same notion, at most named differently) or two different concepts.
Answer with JSON only: {"same":[true,false,...]} with exactly one boolean per pair, in the same order."""

RELATIONS_SYSTEM = """You get a list of technical concepts (name + definition) from one source.
Lay out the relations between these concepts. Types:
- PREREQUISITE_OF: A has to be understood before B can be understood.
- PART_OF: A is a part of B.
- RELATED_TO: strongly related, neither of the above.
Rules: only names from the list, spelled exactly; only relations that really matter; strength 0.5-1.0.
Answer with JSON only: {"relations":[{"from":"","to":"","type":"PREREQUISITE_OF","strength":0.8}]}"""

VALID_RELS = {"PREREQUISITE_OF", "PART_OF", "RELATED_TO"}


def warning(code: str, error: Exception | None = None, **params) -> dict:
    """A warning the frontend translates: {"code", "params"}. `reason` is the provider error code, when known."""
    if error is not None:
        params["reason"] = error.code if isinstance(error, ProviderError) else None
    return {"code": code, "params": params}

# The language for definitions and context, set per request by extract.suggest(); the pipeline
# itself is deep async code, so a context variable beats threading one more argument everywhere.
import contextvars
LANGUAGE = contextvars.ContextVar("extract_language", default="en")


def extract_system() -> str:
    from . import languages
    return EXTRACT_SYSTEM.format(language=languages.name(LANGUAGE.get()))


def fmt_ts(sec: float | None) -> str:
    if sec is None:
        return ""
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


# ---------------------------------------------------------------- blokken

def make_blocks(segments: list[dict], timed: bool) -> list[dict]:
    """Joins segments into label blocks of ~40 s / ~90 words.
    Each block: {idx, start_sec, text, words, dur} with dur in seconds
    (untimed: words / WPM)."""
    blocks, cur, cur_words = [], [], 0
    cur_start = None

    cur_segs = []

    def close():
        nonlocal cur, cur_words, cur_start, cur_segs
        if cur:
            text = " ".join(cur)
            blocks.append({"idx": len(blocks), "start_sec": cur_start, "text": text,
                           "words": cur_words, "segs": cur_segs})
        cur, cur_words, cur_start, cur_segs = [], 0, None, []

    for s in segments:
        words = len(s["text"].split())
        if not words:
            continue
        if cur and (
            (timed and s["start_sec"] is not None and cur_start is not None
             and s["start_sec"] - cur_start >= BLOCK_SEC and cur_words >= BLOCK_WORDS // 3)
            or (not timed and cur_words >= BLOCK_WORDS)
            or cur_words >= BLOCK_WORDS * 2
        ):
            close()
        if not cur:
            cur_start = s["start_sec"] if timed else None
        cur.append(s["text"])
        cur_words += words
        cur_segs.append(s)
    close()
    # duration per block: until the next block starts, otherwise by word count
    for i, b in enumerate(blocks):
        nxt = blocks[i + 1]["start_sec"] if i + 1 < len(blocks) else None
        if timed and b["start_sec"] is not None and nxt is not None and nxt > b["start_sec"]:
            b["dur"] = nxt - b["start_sec"]
        else:
            b["dur"] = b["words"] / WPM * 60
    return blocks


def _split_long(run: list[dict], max_sec: float) -> list[list[dict]]:
    """A run of blocks in roughly equal pieces of at most max_sec."""
    total = sum(b["dur"] for b in run)
    parts = max(1, math.ceil(total / max_sec))
    target = total / parts
    out, cur, acc = [], [], 0.0
    for b in run:
        cur.append(b)
        acc += b["dur"]
        if acc >= target and len(out) < parts - 1:
            out.append(cur)
            cur, acc = [], 0.0
    if cur:
        out.append(cur)
    return out


def _runs_from_boundaries(blocks: list[dict], boundaries: list[int]) -> list[list[dict]]:
    bounds = sorted({b for b in boundaries if 0 < b < len(blocks)})
    runs, start = [], 0
    for b in bounds:
        runs.append(blocks[start:b])
        start = b
    runs.append(blocks[start:])
    return [r for r in runs if r]


def _normalize_runs(runs: list[list[dict]], min_sec: float, max_sec: float) -> list[list[dict]]:
    """Splits parts that are too long and joins parts that are too short with a neighbour."""
    split = []
    for r in runs:
        split.extend(_split_long(r, max_sec))
    merged: list[list[dict]] = []
    for r in split:
        dur = sum(b["dur"] for b in r)
        if merged and (dur < min_sec or sum(b["dur"] for b in merged[-1]) < min_sec):
            merged[-1] = merged[-1] + r
        else:
            merged.append(r)
    # Joining may have made it too long again; split once more.
    out = []
    for r in merged:
        out.extend(_split_long(r, max_sec * 1.15))
    return out


def chapter_runs(blocks: list[dict], chapters: list[dict]) -> list[list[dict]]:
    """Chapters are the primary boundaries: split above 12 min, join below 3 min."""
    starts = sorted(c["start_sec"] for c in chapters)
    boundaries = []
    for st in starts:
        idx = next((b["idx"] for b in blocks if b["start_sec"] is not None and b["start_sec"] >= st - 1), None)
        if idx:
            boundaries.append(idx)
    return _normalize_runs(_runs_from_boundaries(blocks, boundaries), CHAPTER_MERGE_SEC, CHAPTER_SPLIT_SEC)


def fixed_runs(blocks: list[dict]) -> list[list[dict]]:
    """Fallback: fixed parts of ~11 minutes; block boundaries fall on sentence
    boundaries as far as the transcript has them."""
    return _normalize_runs([blocks], CHUNK_MIN_SEC, CHUNK_MAX_SEC)


async def topic_runs(blocks: list[dict], usage: llm.Usage, warnings: list) -> list[list[dict]]:
    """One cheap EXTRACT_MODEL call that points out topic changes."""
    total_chars = sum(len(b["text"]) for b in blocks)
    condense = total_chars > SEGMENT_CONDENSE_CHARS
    lines = []
    for b in blocks:
        txt = b["text"]
        if condense:
            txt = " ".join(txt.split()[:40]) + " …"
        ts = f" @ {fmt_ts(b['start_sec'])}" if b["start_sec"] is not None else ""
        lines.append(f"[b{b['idx']}{ts}] {txt}")
    system = SEGMENT_SYSTEM.format(target_min=8, target_max=15, min_min=3)
    try:
        data = await llm.acomplete_json(system, "\n".join(lines), llm.EXTRACT_MODEL, usage, "segment")
        raw = data.get("boundaries", []) if isinstance(data, dict) else []
        boundaries = []
        for x in raw:
            m = re.search(r"\d+", str(x))
            if m:
                boundaries.append(int(m.group()))
        if not boundaries:
            raise ValueError("no boundaries")
        return _normalize_runs(_runs_from_boundaries(blocks, boundaries), CHUNK_MIN_SEC, CHUNK_MAX_SEC)
    except Exception as e:
        warnings.append(warning("extract.segmentFailed", e))
        return fixed_runs(blocks)


def build_chunks(runs: list[list[dict]]) -> list[dict]:
    """Chunks with the last ~10% of the previous chunk as preceding context."""
    chunks = []
    for i, run in enumerate(runs):
        pre = ""
        if i > 0:
            prev = runs[i - 1]
            words = sum(b["words"] for b in prev)
            take, acc = [], 0
            for b in reversed(prev):
                take.insert(0, b["text"])
                acc += b["words"]
                if acc >= words * OVERLAP_FRACTION:
                    break
            pre = " ".join(take)
        chunks.append({
            "idx": i,
            "start_sec": run[0]["start_sec"],
            "end_sec": (run[-1]["start_sec"] + run[-1]["dur"]) if run[-1]["start_sec"] is not None else None,
            "blocks": run,
            "pre": pre,
            "words": sum(b["words"] for b in run),
        })
    return chunks


def chunk_prompt(chunk: dict) -> str:
    parts = []
    if chunk["pre"]:
        parts.append("[preceding context, do not extract]\n" + chunk["pre"] + "\n[end of preceding context]\n")
    for b in chunk["blocks"]:
        ts = f" @ {fmt_ts(b['start_sec'])}" if b["start_sec"] is not None else ""
        parts.append(f"[b{b['idx']}{ts}] {b['text']}")
    return "\n".join(parts)


# ---------------------------------------------------------------- extractie

def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(s).lower())


def locate_quote(quote: str, chunk: dict, blk: dict) -> float | None:
    """Precise timestamp: the segment (caption line) where the quote starts. Looks
    for the quote's first 5 words in the given block and its neighbours; falls back
    to the block start."""
    q = _words(quote)
    if len(q) < 3:
        return blk["start_sec"]
    head = q[:5]
    by_idx = {b["idx"]: b for b in chunk["blocks"]}
    for off in (0, -1, 1):
        b = by_idx.get(blk["idx"] + off)
        if not b or not b.get("segs"):
            continue
        segs = b["segs"]
        # Segments are short (a few words); a quote can span several segments, so
        # search over a sliding window of segments.
        for i, seg in enumerate(segs):
            window = []
            j = i
            while j < len(segs) and len(window) < len(head) + 12:
                window.extend(_words(segs[j]["text"]))
                j += 1
            for k in range(0, max(1, len(window) - len(head) + 1)):
                if window[k:k + len(head)] == head:
                    return seg["start_sec"] if seg["start_sec"] is not None else blk["start_sec"]
    return blk["start_sec"]


async def extract_chunk(chunk: dict, sem: asyncio.Semaphore, usage: llm.Usage,
                        progress) -> list[dict] | None:
    """One chunk through the extract model; one retry on an error, then None.
    A provider error is not repeated here: llm already retried busy and rate limits."""
    prompt = chunk_prompt(chunk)
    by_idx = {b["idx"]: b for b in chunk["blocks"]}
    last_err = None
    for attempt in range(2):
        try:
            async with sem:
                data = await llm.acomplete_json(extract_system(), prompt, llm.EXTRACT_MODEL, usage, "extract")
            concepts = data.get("concepts", []) if isinstance(data, dict) else []
            out = []
            for c in concepts:
                name = str(c.get("name", "")).strip()
                if not name:
                    continue
                m = re.search(r"\d+", str(c.get("block", "")))
                blk = by_idx.get(int(m.group())) if m else None
                if blk is None:
                    blk = chunk["blocks"][0]
                try:
                    imp = int(c.get("importance", 3))
                except (TypeError, ValueError):
                    imp = 3
                out.append({
                    "name": name,
                    "aliases": [str(a) for a in (c.get("aliases") or []) if a],
                    "definition": str(c.get("definition", "")).strip(),
                    "domain": str(c.get("domain", "")).strip(),
                    "context": str(c.get("context", "")).strip(),
                    "quote": " ".join(str(c.get("quote", "")).split()),
                    "importance": max(1, min(5, imp)),
                    "chunk_idx": chunk["idx"],
                    "start_sec": locate_quote(str(c.get("quote", "")), chunk, blk),
                })
            progress()
            return out
        except Exception as e:      # timeout, ongeldige JSON, API-fout
            last_err = e
            log.warning("Chunk %d poging %d mislukt: %s", chunk["idx"], attempt + 1, e)
            if isinstance(e, ProviderError):
                break
    progress()
    chunk["error"] = last_err.code if isinstance(last_err, ProviderError) else type(last_err).__name__
    return None


# ---------------------------------------------------------------- merge

def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


async def merge_candidates(raw: list[dict], usage: llm.Usage, warnings: list) -> list[dict]:
    """Deduplicates across chunks: equal names, embedding clustering (cos > 0.90)
    and LLM confirmation for the grey zone (0.80-0.90)."""
    if not raw:
        return []
    texts = [f"{c['name']}: {c['definition']}" for c in raw]
    try:
        embs = await llm.aembed(texts, usage, "embed", CONCURRENCY)
    except Exception as e:
        warnings.append(warning("extract.embedFailed", e))
        embs = [None] * len(raw)

    clusters: list[dict] = []          # {members: [i], names: set, emb: list|None}
    pending_pairs = []                 # (cand_idx, cluster_idx)

    for i, c in enumerate(raw):
        names = {_norm(c["name"]), *(_norm(a) for a in c["aliases"])}
        hit = next((k for k, cl in enumerate(clusters) if names & cl["names"]), None)
        if hit is None and embs[i] is not None:
            best, best_sim = None, 0.0
            for k, cl in enumerate(clusters):
                if cl["emb"] is None:
                    continue
                sim = _cos(embs[i], cl["emb"])
                if sim > best_sim:
                    best, best_sim = k, sim
            if best is not None and best_sim > SIM_SAME:
                hit = best
            elif best is not None and best_sim > SIM_MAYBE:
                pending_pairs.append((i, best))
        if hit is not None:
            _join(clusters[hit], i, names, embs[i])
        else:
            clusters.append({"members": [i], "names": names, "emb": embs[i], "n": 1})

    # Confirm doubtful cases in batches; the candidate is already its own cluster
    # in the list, and "same" merges it after all.
    if pending_pairs:
        decisions = await _confirm_pairs(raw, clusters, pending_pairs, usage, warnings)
        for (i, k), same in zip(pending_pairs, decisions):
            if not same:
                continue
            own = next((j for j, cl in enumerate(clusters) if i in cl["members"]), None)
            if own is None or own == k:
                continue
            src, dst = clusters[own], clusters[k]
            for m in src["members"]:
                _join(dst, m, {_norm(raw[m]["name"]), *(_norm(a) for a in raw[m]["aliases"])}, embs[m])
            src["members"] = []
        clusters = [cl for cl in clusters if cl["members"]]

    merged = []
    for cl in clusters:
        members = [raw[m] for m in cl["members"]]
        chunk_ids = sorted({m["chunk_idx"] for m in members})
        best = max(members, key=lambda m: (m["importance"], len(m["definition"])))
        mentions = sorted(
            ({"start_sec": m["start_sec"], "quote": m["quote"], "chunk_idx": m["chunk_idx"]}
             for m in members if m["quote"]),
            key=lambda x: (x["chunk_idx"], x["start_sec"] if x["start_sec"] is not None else 0))
        aliases = []
        for m in members:
            for a in [m["name"], *m["aliases"]]:
                if _norm(a) != _norm(best["name"]) and _norm(a) not in {_norm(x) for x in aliases}:
                    aliases.append(a)
        merged.append({
            "name": best["name"],
            "aliases": aliases,
            "definition": best["definition"],
            "domain": best["domain"],
            "context": best["context"],
            "chunk_count": len(chunk_ids),
            "chunk_ids": chunk_ids,
            "llm_importance": round(sum(m["importance"] for m in members) / len(members), 2),
            "mentions": mentions,
        })
    return merged


def _join(cluster: dict, i: int, names: set, emb):
    cluster["members"].append(i)
    cluster["names"] |= names
    if emb is not None:
        if cluster["emb"] is None:
            cluster["emb"], cluster["n"] = list(emb), 1
        else:
            n = cluster["n"]
            cluster["emb"] = [(a * n + b) / (n + 1) for a, b in zip(cluster["emb"], emb)]
            cluster["n"] = n + 1


async def _confirm_pairs(raw, clusters, pairs, usage, warnings) -> list[bool]:
    batches = [pairs[i:i + 20] for i in range(0, len(pairs), 20)]
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(batch):
        lines = []
        for n, (i, k) in enumerate(batch):
            rep = raw[clusters[k]["members"][0]]
            lines.append(f"{n + 1}. A: {raw[i]['name']}: {raw[i]['definition']}\n   B: {rep['name']}: {rep['definition']}")
        try:
            async with sem:
                data = await llm.acomplete_json(CONFIRM_SYSTEM, "\n".join(lines), llm.EXTRACT_MODEL, usage, "resolve")
            same = data.get("same", []) if isinstance(data, dict) else []
            return [bool(x) for x in same][:len(batch)] + [False] * max(0, len(batch) - len(same))
        except Exception as e:
            warnings.append(warning("extract.confirmFailed", e, count=len(batch)))
            return [False] * len(batch)

    results = await asyncio.gather(*(one(b) for b in batches))
    return [x for r in results for x in r]


def score(merged: list[dict], n_chunks: int) -> None:
    """Importance 1-5: chunk_count dominates, the LLM score is the second vote.
    With one chunk, chunk_count says nothing and only the LLM score counts."""
    if not merged:
        return
    max_cc = max(c["chunk_count"] for c in merged)
    for c in merged:
        llm_part = (c["llm_importance"] - 1) / 4
        if n_chunks <= 1 or max_cc <= 1:
            s = llm_part
        else:
            cc_part = math.log(1 + c["chunk_count"]) / math.log(1 + max_cc)
            s = 0.65 * cc_part + 0.35 * llm_part
        c["importance"] = max(1, min(5, int(round(1 + 4 * s))))
    merged.sort(key=lambda c: (-c["importance"], -c["chunk_count"], -c["llm_importance"], c["name"]))


async def relations(merged: list[dict], usage: llm.Usage, warnings: list) -> list[dict]:
    """Eén afsluitende call over namen + definities."""
    if len(merged) < 2:
        return []
    top = merged[:MAX_RELATION_CANDIDATES]
    names = {_norm(c["name"]): c["name"] for c in top}
    for c in top:
        for a in c["aliases"]:
            names.setdefault(_norm(a), c["name"])
    user = "\n".join(f"- {c['name']}: {c['definition']}" for c in top)
    try:
        data = await llm.acomplete_json(RELATIONS_SYSTEM, user, llm.EXTRACT_MODEL, usage, "relations")
    except Exception as e:
        warnings.append(warning("extract.relationsFailed", e))
        return []
    out, seen = [], set()
    for r in (data.get("relations", []) if isinstance(data, dict) else []):
        a, b = names.get(_norm(r.get("from", ""))), names.get(_norm(r.get("to", "")))
        t = str(r.get("type", "")).upper()
        if not a or not b or a == b or t not in VALID_RELS or (a, b, t) in seen:
            continue
        seen.add((a, b, t))
        try:
            strength = max(0.0, min(1.0, float(r.get("strength", 0.8))))
        except (TypeError, ValueError):
            strength = 0.8
        out.append({"from": a, "to": b, "type": t, "strength": strength})
    return out


# ---------------------------------------------------------------- pijplijn

async def run(segments: list[dict], chapters: list[dict], timed: bool,
              job_id: str | None = None, duration_sec: float | None = None) -> dict:
    usage, warnings = llm.Usage(), []
    blocks = make_blocks(segments, timed)
    if not blocks:
        return {"candidates": [], "candidate_relations": [],
                "meta": {"chunks": 0, "skipped_chunks": 0, "duration_sec": 0, "chaptered": False,
                         "candidates_raw": 0, "candidates_merged": 0, "tokens": usage.report(),
                         "warnings": [warning("extract.noText")]}}
    total_sec = sum(b["dur"] for b in blocks)
    if duration_sec is None:
        last = blocks[-1]
        duration_sec = (last["start_sec"] + last["dur"]) if timed and last["start_sec"] is not None else total_sec

    # 1. segmentatie
    jobs.update(job_id, "segment", 0, 0, "Transcript in delen splitsen…")
    chaptered = bool(chapters) and timed and len(chapters) >= 2
    if total_sec <= CHUNK_MAX_SEC:
        runs = [blocks]
    elif chaptered:
        runs = chapter_runs(blocks, chapters)
    else:
        runs = await topic_runs(blocks, usage, warnings)
    chunks = build_chunks(runs)
    n = len(chunks)

    # 2. parallelle extractie
    done = 0
    jobs.update(job_id, "extract", 0, n, f"part 0 of {n}")

    def progress():
        nonlocal done
        done += 1
        jobs.update(job_id, "extract", done, n, f"part {done} of {n}")

    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(extract_chunk(c, sem, usage, progress) for c in chunks))
    raw, skipped = [], []
    for c, r in zip(chunks, results):
        if r is None:
            skipped.append(c["idx"])
        else:
            raw.extend(r)
    if skipped:
        codes = [chunks[i]["error"] for i in skipped if str(chunks[i].get("error", "")).startswith("provider.")]
        warnings.append(warning("extract.partsSkipped", skipped=len(skipped), total=n,
                                parts=", ".join(str(i + 1) for i in skipped),
                                reason=max(set(codes), key=codes.count) if codes else None))

    # 3. merge + score
    jobs.update(job_id, "merge", n, n, f"{len(raw)} kandidaten samenvoegen…")
    merged = await merge_candidates(raw, usage, warnings)
    score(merged, n)

    # 4. relaties
    jobs.update(job_id, "relations", n, n, "Relaties leggen…")
    rels = await relations(merged, usage, warnings)

    candidates = []
    for c in merged:
        first = c["mentions"][0] if c["mentions"] else None
        candidates.append({
            "name": c["name"], "aliases": c["aliases"], "definition": c["definition"],
            "domain": c["domain"], "importance": c["importance"], "llm_importance": c["llm_importance"],
            "chunk_count": c["chunk_count"],
            "mentions": [{"start_sec": m["start_sec"], "quote": m["quote"], "chunk_idx": m["chunk_idx"]}
                         for m in c["mentions"]],
            # context stays the summarising sentence; the quote is the evidence.
            "context": c["context"] or (first["quote"] if first else ""),
        })
    meta = {
        "chunks": n, "skipped_chunks": len(skipped), "duration_sec": round(duration_sec or 0),
        "chaptered": chaptered, "timed": timed,
        "chunk_bounds": [{"idx": c["idx"], "start_sec": c["start_sec"], "end_sec": c["end_sec"], "words": c["words"]}
                         for c in chunks],
        "candidates_raw": len(raw), "candidates_merged": len(merged),
        "tokens": usage.report(), "warnings": warnings,
    }
    jobs.update(job_id, "done", n, n, "Klaar")
    return {"candidates": candidates, "candidate_relations": rels, "meta": meta}
