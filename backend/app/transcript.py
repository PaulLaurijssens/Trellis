"""Parse transcripts into segments with timestamps and chapter markers.

Timestamps are kept as structured data (start_sec) instead of thrown away: the
extraction turns them into "jump to moment" links."""
import json, re, urllib.request

# 4:45 / 1:02:33 / 00:00:04,000 - with or without surrounding brackets.
_TS = r"(?:\d{1,2}:)?\d{1,2}:\d{2}(?:[.,]\d{1,3})?"
_TS_WRAPPED = rf"[\[(]?(?P<ts>{_TS})[\])]?"
# A line that is only a timestamp or a timestamp range (SRT/VTT).
_TS_ONLY = re.compile(rf"^{_TS_WRAPPED}(?:\s*(?:-->|[-–—])\s*[\[(]?{_TS}[\])]?)?\s*$")
# A line that starts with a timestamp, followed by text.
_TS_PREFIX = re.compile(rf"^{_TS_WRAPPED}\s*[-–—:)\]]?\s*(?P<rest>.+)$")
_SRT_INDEX = re.compile(r"^\d{1,5}$")


def parse_ts(ts: str) -> float:
    ts = ts.strip("[]() ").replace(",", ".")
    parts = ts.split(":")
    sec = 0.0
    for p in parts:
        sec = sec * 60 + float(p)
    return sec


def is_chapter_title(rest: str) -> bool:
    """Tells a chapter title after a timestamp apart from spoken text. A title is
    short, has no sentence punctuation and does not start mid-sentence. Auto-captions
    ("12:30 so the trick here is") start with a lowercase letter and stay that way."""
    return (len(rest.split()) <= 8
            and not any(c in rest for c in ".!?")
            and not rest[:1].islower())


def parse(text: str) -> dict:
    """-> {"segments": [{"start_sec": float|None, "text": str}],
           "chapters": [{"start_sec": float, "title": str}], "timed": bool}

    Supports YouTube transcripts ("4:45 text", or a timestamp on its own line followed
    by text), SRT/VTT ranges and "[00:12]" prefixes. Without timestamps, paragraphs
    become segments without start_sec.

    Chapter markers ("0:45 The KV cache") only count as such when the timed lines are
    sparse (a chapter list: median gap >= 30 s) or when they stand in a block of >= 3
    title-like lines. In a dense caption transcript, short capitalised lines are just
    spoken text."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    # Pass 1: classify the lines.
    items = []   # ("ts", sec) | ("timed", sec, rest, title_like) | ("text", line) | ("blank",)
    for raw in lines:
        line = raw.strip()
        if not line:
            items.append(("blank",))
            continue
        if _SRT_INDEX.match(line):
            continue
        m = _TS_ONLY.match(line)
        if m:
            items.append(("ts", parse_ts(m.group("ts"))))
            continue
        m = _TS_PREFIX.match(line)
        if m:
            rest = m.group("rest").strip()
            items.append(("timed", parse_ts(m.group("ts")), rest, is_chapter_title(rest)))
            continue
        items.append(("text", line))

    times = [it[1] for it in items if it[0] in ("ts", "timed")]
    gaps = sorted(b - a for a, b in zip(times, times[1:]) if b > a)
    sparse = bool(gaps) and gaps[len(gaps) // 2] >= 30

    # Which timed lines are chapter markers?
    chapter_idx = set()
    if sparse:
        chapter_idx = {i for i, it in enumerate(items) if it[0] == "timed" and it[3]}
    else:
        run = []
        for i, it in enumerate(items):
            if it[0] == "timed" and it[3] and (not run or it[1] > items[run[-1]][1]):
                run.append(i)
            else:
                if len(run) >= 3:
                    chapter_idx.update(run)
                run = [] if it[0] != "blank" else run
        if len(run) >= 3:
            chapter_idx.update(run)

    # Pas 2: segmenten bouwen.
    segments, chapters = [], []
    pending_ts = None          # timestamp on its own line: belongs to the next text
    untimed = []               # current paragraph without a timestamp

    def flush_untimed():
        if untimed:
            segments.append({"start_sec": None, "text": " ".join(untimed)})
            untimed.clear()

    for i, it in enumerate(items):
        kind = it[0]
        if kind == "blank":
            flush_untimed()
        elif kind == "ts":
            flush_untimed()
            pending_ts = it[1]
        elif kind == "timed":
            flush_untimed()
            _, ts, rest, _ = it
            if i in chapter_idx:
                chapters.append({"start_sec": ts, "title": rest})
                pending_ts = ts       # the text below belongs to this moment
            else:
                segments.append({"start_sec": ts, "text": rest})
                pending_ts = None
        else:
            line = it[1]
            if pending_ts is not None:
                segments.append({"start_sec": pending_ts, "text": line})
                pending_ts = None
            else:
                untimed.append(line)
    flush_untimed()

    timed = any(s["start_sec"] is not None for s in segments)
    if timed:
        # Loose lines without a timestamp between timed lines are joined to the
        # previous timed line; they continue the same utterance.
        merged = []
        for s in segments:
            if s["start_sec"] is None and merged:
                merged[-1] = {**merged[-1], "text": merged[-1]["text"] + " " + s["text"]}
            else:
                merged.append(s)
        segments = merged
        chapters.sort(key=lambda c: c["start_sec"])
    else:
        chapters = []
    return {"segments": segments, "chapters": chapters, "timed": timed}


def from_youtube(fetched) -> list[dict]:
    """Segments straight from youtube-transcript-api, without joining them first."""
    out = []
    for s in fetched:
        start = getattr(s, "start", None)
        txt = getattr(s, "text", None)
        if start is None and isinstance(s, dict):
            start, txt = s.get("start"), s.get("text")
        txt = " ".join(str(txt or "").split())
        if txt:
            out.append({"start_sec": float(start or 0), "text": txt})
    return out


def youtube_meta(video_id: str, timeout: float = 10.0) -> dict:
    """Title and chapters of a YouTube video. Chapters are lines "mm:ss Title" in the
    description; the transcript API does not return them. Best effort: on an error,
    simply no chapters."""
    try:
        req = urllib.request.Request(
            f"https://www.youtube.com/watch?v={video_id}&hl=en",
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.8"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception:
        return {"title": None, "chapters": [], "duration_sec": None}
    title = None
    m = re.search(r'"videoDetails":\{.*?"title":"((?:[^"\\]|\\.)*)"', html)
    if m:
        title = json.loads('"' + m.group(1) + '"')
    duration = None
    m = re.search(r'"lengthSeconds":"(\d+)"', html)
    if m:
        duration = float(m.group(1))
    chapters = []
    m = re.search(r'"shortDescription":"((?:[^"\\]|\\.)*)"', html)
    if m:
        desc = json.loads('"' + m.group(1) + '"')
        for line in desc.split("\n"):
            mm = re.match(rf"^\s*[\[(]?({_TS})[\])]?\s*[-–—:]?\s*(.+?)\s*$", line)
            if mm:
                chapters.append({"start_sec": parse_ts(mm.group(1)), "title": mm.group(2)})
        chapters.sort(key=lambda c: c["start_sec"])
        # A real chapter list starts at 0:00 and has at least three.
        if len(chapters) < 3 or chapters[0]["start_sec"] > 30:
            chapters = []
    return {"title": title, "chapters": chapters, "duration_sec": duration}


def youtube_id(url):
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url.strip())
    host = (parsed.hostname or '').lower()
    parts = parsed.path.strip('/').split('/')
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('Invalid YouTube URL')
    if host == 'youtu.be':
        video_id = parts[0]
    elif host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        video_id = parse_qs(parsed.query).get('v', [''])[0] if parsed.path == '/watch' else (parts[1] if len(parts) == 2 and parts[0] in ('shorts', 'embed', 'live') else '')
    else:
        video_id = ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('Invalid YouTube URL')
    return video_id


def fetch_error(error):
    blocked = type(error).__name__ in ('RequestBlocked', 'IpBlocked')
    return ('YouTube is blocking automatic transcript retrieval. ' if blocked else 'The transcript could not be retrieved automatically. ') + 'Open the video on YouTube, choose Show transcript and copy the text. Use Paste transcript below; timestamps can stay in place.'
