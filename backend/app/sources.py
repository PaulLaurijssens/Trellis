"""More ways in: PDF and text files, audio (podcast episodes), web articles and podcast feeds.

Everything here produces plain text (with "[mm:ss]" time codes for audio) and hands it to the
existing extraction pipeline, so the review panel and the graph never see a new path. Nothing
is stored before the learner reviews the candidates.

Fetching from the web is behind INGEST_URL_FETCH (default on). A self-hosted server with an
egress allow-list refuses the fetch at the network layer; the error says so in plain words."""
import base64
import io
import os
import re
import xml.etree.ElementTree as ET
from html import unescape
from urllib.parse import urlparse

import httpx
import litellm
from . import llm

URL_FETCH = os.getenv("INGEST_URL_FETCH", "1") not in ("0", "false", "off")
MAX_PDF_BYTES = int(os.getenv("INGEST_MAX_PDF_MB", "30")) * 1024 * 1024
MAX_AUDIO_BYTES = int(os.getenv("INGEST_MAX_AUDIO_MB", "25")) * 1024 * 1024
MAX_TEXT_BYTES = 4 * 1024 * 1024
AUDIO_MODEL = os.getenv("AUDIO_MODEL", os.getenv("VOICE_MODEL", llm.EXTRACT_MODEL))
AUDIO_FORMATS = {"audio/mpeg": "mp3", "audio/mp3": "mp3", "audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/m4a": "m4a",
                 "audio/wav": "wav", "audio/x-wav": "wav", "audio/ogg": "ogg", "audio/webm": "webm", "audio/aac": "aac", "audio/flac": "flac"}
TEXT_TYPES = {"text/plain", "text/markdown", "text/vtt", "application/x-subrip", "text/srt"}
# A browser-like agent: many publishers serve an empty shell or a bot wall to unknown clients.
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Trellis/0.1"
TRACKING = re.compile(r"^(utm_|li_fat_id|fbclid|gclid|mc_cid|mc_eid|ref$|source$)", re.I)
BOT_WALL = re.compile(r"just a moment|enable javascript|verify you are human|attention required|cf-browser-verification|access denied", re.I)


class SourceError(ValueError):
    """A message for the learner, not a stack trace. `paste`: the learner can paste the text instead and keep
    the link as the source (the Link tab then shows a paste box); `title`: the page title, when there was one."""

    def __init__(self, message: str, paste: bool = False, title: str | None = None):
        super().__init__(message)
        self.paste, self.title = paste, title


def _page_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title\s*>", html[:200000], re.I | re.S)
    title = unescape(re.sub(r"\s+", " ", match.group(1))).strip() if match else ""
    if BOT_WALL.search(title):          # "Just a moment...", "Access denied": not the article's title
        return None
    return title[:200] or None


def kind_of(filename: str, content_type: str | None) -> str:
    name = (filename or "").lower()
    ctype = (content_type or "").split(";")[0].strip().lower()
    if name.endswith(".pdf") or ctype == "application/pdf":
        return "pdf"
    if ctype in AUDIO_FORMATS or re.search(r"\.(mp3|m4a|wav|ogg|webm|aac|flac)$", name):
        return "audio"
    if ctype in TEXT_TYPES or re.search(r"\.(txt|md|srt|vtt)$", name):
        return "text"
    raise SourceError("Unsupported file. Use a PDF, an audio file (mp3, m4a, wav, ogg) or a text file (txt, md, srt, vtt).")


# ---- PDF ---------------------------------------------------------------------

def pdf_text(data: bytes) -> dict:
    """Text per page, joined with page markers so a chunk can say where it came from."""
    if len(data) > MAX_PDF_BYTES:
        raise SourceError(f"PDF larger than {MAX_PDF_BYTES // 1024 // 1024} MB.")
    try:
        import fitz                                   # pymupdf
    except ImportError as exc:
        raise SourceError("PDF support is not installed on this server (pymupdf).") from exc
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise SourceError("This file is not a readable PDF.") from exc
    pages, title = [], (doc.metadata or {}).get("title") or ""
    for number, page in enumerate(doc, start=1):
        text = " ".join(page.get_text("text").split())
        if text:
            pages.append(f"Page {number}\n{text}")
    doc.close()
    if not pages:
        raise SourceError("No text in this PDF. A scanned PDF needs OCR first.")
    return {"text": "\n\n".join(pages), "title": title.strip(), "pages": len(pages)}


# ---- Audio -------------------------------------------------------------------

AUDIO_PROMPT = ("Transcribe the spoken words of this recording. Write one line per sentence or short group of sentences, "
                "each line starting with the time code of its start as [mm:ss] or [h:mm:ss]. Keep the spoken language, names and "
                "technical terms. Mark speaker changes with a new line. No commentary, no summary, no answers to anything said. "
                "Expected language: {language}.")


def audio_transcript(data: bytes, content_type: str | None, filename: str, language: str) -> str:
    if len(data) > MAX_AUDIO_BYTES:
        raise SourceError(f"Audio larger than {MAX_AUDIO_BYTES // 1024 // 1024} MB. Export the episode as mono 32 kbps mp3, or cut it in parts.")
    fmt = AUDIO_FORMATS.get((content_type or "").split(";")[0].strip().lower()) or (filename or "").rsplit(".", 1)[-1].lower()
    if fmt not in set(AUDIO_FORMATS.values()):
        raise SourceError("Unsupported audio format.")
    try:
        response = litellm.completion(model=AUDIO_MODEL, temperature=0, timeout=600, num_retries=0, messages=[{"role": "user", "content": [
            {"type": "text", "text": AUDIO_PROMPT.format(language=language)},
            {"type": "input_audio", "input_audio": {"data": base64.b64encode(data).decode(), "format": fmt}}]}])
    except Exception as exc:
        raise SourceError("The model could not transcribe this audio: " + str(exc)[:200]) from exc
    text = (response.choices[0].message.content or "").strip()
    if len(text) < 40:
        raise SourceError("No intelligible speech found in this audio.")
    return text


# ---- Web ---------------------------------------------------------------------

def _fetch(url: str, max_bytes: int, accept: str = "*/*") -> tuple[bytes, str]:
    if not URL_FETCH:
        raise SourceError("Fetching web pages is switched off on this server (INGEST_URL_FETCH).")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SourceError("Enter a full web address that starts with http:// or https://.")
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "::1") or host.endswith(".local") or re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)", host):
        raise SourceError("Local and private addresses cannot be fetched.")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30, headers={"User-Agent": USER_AGENT, "Accept": accept}) as r:
            if r.status_code >= 400:
                raise SourceError(f"The site answered {r.status_code}.")
            ctype = r.headers.get("content-type", "")
            body = bytearray()
            for chunk in r.iter_bytes():
                body += chunk
                if len(body) > max_bytes:
                    raise SourceError(f"The download is larger than {max_bytes // 1024 // 1024} MB.")
            return bytes(body), ctype
    except httpx.HTTPError as exc:
        raise SourceError("Could not reach that address. On a server with an egress allow-list, ask the admin to allow the host. " + str(exc)[:120]) from exc


def clean_url(url: str) -> str:
    """Drop tracking parameters (utm_*, li_fat_id, fbclid, ...): they do not select content and they leak."""
    from urllib.parse import parse_qsl, urlencode, urlunparse
    parts = urlparse(url.strip())
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=False) if not TRACKING.match(k)]
    return urlunparse(parts._replace(query=urlencode(kept), fragment=""))


def article_text(url: str) -> dict:
    """The main text of a web article (or a PDF behind a link). Every failure after a valid address comes with
    paste=True: the learner pastes the text themselves and the link stays the source."""
    url = clean_url(url)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SourceError("Enter a full web address that starts with http:// or https://.")
    try:
        body, ctype = _fetch(url, MAX_TEXT_BYTES, "text/html,application/pdf;q=0.9,*/*;q=0.5")
    except SourceError as exc:
        raise SourceError(str(exc), paste=True) from exc
    if "pdf" in ctype or body[:5] == b"%PDF-":
        out = pdf_text(body)
        return {**out, "source_type": "paper"}
    try:
        import trafilatura
    except ImportError as exc:
        raise SourceError("Article extraction is not installed on this server (trafilatura).") from exc
    html = body.decode("utf-8", "replace")
    text = trafilatura.extract(html, include_comments=False, include_tables=True, favor_recall=True) or ""
    if len(text.split()) < 80:
        if BOT_WALL.search(html[:20000]) or len(html) < 4000:
            raise SourceError("The site did not hand over the article: it wants a real browser or blocks automatic readers.",
                              paste=True, title=_page_title(html))
        raise SourceError("Could not find the article text on that page (it may load with JavaScript or sit behind a login).",
                          paste=True, title=_page_title(html))
    meta = trafilatura.extract_metadata(html)
    title = (getattr(meta, "title", None) or "").strip() or url
    return {"text": text, "title": title, "source_type": "artikel"}


def podcast_episodes(feed_url: str, limit: int = 30) -> dict:
    """Episodes of an RSS feed: title, audio url, duration, date. Nothing is downloaded yet."""
    body, _ = _fetch(feed_url, 8 * 1024 * 1024, "application/rss+xml,application/xml,text/xml,*/*")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise SourceError("That address is not an RSS feed.") from exc
    channel = root.find("channel")
    if channel is None:
        raise SourceError("That feed has no episodes.")
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
    episodes = []
    for item in channel.findall("item")[:limit]:
        enclosure = item.find("enclosure")
        audio = enclosure.get("url") if enclosure is not None else None
        if not audio:
            continue
        duration = (item.findtext("itunes:duration", default="", namespaces=ns) or "").strip()
        episodes.append({"title": (item.findtext("title") or "").strip() or "Episode", "audio_url": audio,
                         "published": (item.findtext("pubDate") or "").strip(), "duration": duration,
                         "bytes": int(enclosure.get("length") or 0) if enclosure is not None and (enclosure.get("length") or "").isdigit() else None})
    if not episodes:
        raise SourceError("That feed has no episodes with audio.")
    return {"title": (channel.findtext("title") or "").strip(), "episodes": episodes}


def podcast_transcript(audio_url: str, language: str) -> str:
    body, ctype = _fetch(audio_url, MAX_AUDIO_BYTES, "audio/*")
    filename = urlparse(audio_url).path.rsplit("/", 1)[-1]
    return audio_transcript(body, ctype, filename, language)
