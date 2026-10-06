"""Turns a lesson directory into ONE self-contained HTML file, and lints it.

What is validated is exactly what is shipped: the validator loads this bundle, and the API stores it.
Pure functions over files; no browser here."""
import base64
import hashlib
import mimetypes
import re
from pathlib import Path

MAX_FILE = 512 * 1024
MAX_FILES = 40
MAX_BUNDLE = 10 * 1024 * 1024        # the shared components are ~0.3 MB; the rest is the lesson's own code and media
ASSET_REF = re.compile(r"^assets/([a-z0-9][a-z0-9-]{0,63})/(\d+\.\d+\.\d+)/([A-Za-z0-9][A-Za-z0-9._/-]{0,200})$")
IMAGE_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".gif": "image/gif"}

LINK = re.compile(r"<link\b[^>]*>", re.I)
SCRIPT_SRC = re.compile(r"<script\b([^>]*)\bsrc\s*=\s*([\"'])(.*?)\2([^>]*)>\s*</script\s*>", re.I | re.S)
IMG = re.compile(r"(<img\b[^>]*?\bsrc\s*=\s*)([\"'])(.*?)\2", re.I | re.S)
INLINE_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.I | re.S)
ATTR = lambda name: re.compile(r"\b" + name + r"\s*=\s*([\"'])(.*?)\1", re.I | re.S)

# Heuristic lint. The CSP in the browser is the real enforcement; this gives the author a clear
# message before the browser silently blocks something.
FORBIDDEN_JS = [
    (r"\beval\s*\(", "eval() is not allowed"),
    (r"\bnew\s+Function\b", "new Function is not allowed"),
    (r"\bfetch\s*\(", "fetch() is not allowed: lessons have no network"),
    (r"\bXMLHttpRequest\b|\bWebSocket\b|\bEventSource\b|\bsendBeacon\b", "network APIs are not allowed"),
    (r"\bimportScripts\b|\bimport\s*\(", "dynamic imports are not allowed"),
    (r"\bwindow\.open\b|\bopen\s*\(\s*[\"']https?:", "window.open is not allowed: use TrellisLesson.openSource"),
    (r"(?<![\w.$])(?:(?:window|document|top|parent|self)\s*\.\s*)?location\s*(?:\.\s*(?:href|assign|replace|reload)\b|=[^=])",
     "navigation is not allowed: use TrellisLesson.openSource / openLesson"),
    (r"\bdocument\.cookie\b|\blocalStorage\b|\bsessionStorage\b|\bindexedDB\b", "browser storage is not available: use TrellisLesson state"),
    (r"\bparent\.postMessage\b|\btop\.postMessage\b", "talk to Trellis through the TrellisLesson SDK only"),
]
FORBIDDEN_HTML = [
    (r"<\s*(iframe|object|embed|form|base|frame|frameset|portal)\b", "element <{0}> is not allowed"),
    (r"<meta\b[^>]*http-equiv", "<meta http-equiv> is not allowed"),
    (r"\son[a-z]+\s*=\s*[\"']", "inline event handlers (onclick=...) are blocked: use addEventListener"),
    (r"(?:href|src|action|xlink:href)\s*=\s*[\"']\s*javascript:", "javascript: URLs are not allowed"),
    (r"<script\b[^>]*\btype\s*=\s*[\"']module[\"']", "module scripts are not supported: use classic scripts"),
]
EXTERNAL_REF = re.compile(r"(?:src|href|poster|xlink:href)\s*=\s*([\"'])\s*(?:https?:)?//", re.I)
CSS_EXTERNAL = re.compile(r"url\(\s*[\"']?\s*(?:https?:)?//|@import", re.I)


class BundleError(ValueError):
    pass


def safe_job_path(job_dir: Path, rel: str) -> Path:
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or "\\" in rel or "\0" in rel:
        raise BundleError(f"invalid path: {rel!r}")
    target = (job_dir / rel).resolve()
    if job_dir.resolve() not in target.parents:
        raise BundleError(f"path leaves the lesson directory: {rel}")
    if target.parts[len(job_dir.resolve().parts)] == "assets":
        raise BundleError("assets/ is read-only: propose a new component with asset_propose")
    return target


def _read(job_dir: Path, assets_dir: Path, ref: str, used: set) -> bytes:
    ref = ref.strip().split("#")[0].split("?")[0]
    if ref.startswith("./"):
        ref = ref[2:]
    match = ASSET_REF.match(ref)
    if match:
        path = (assets_dir / match.group(1) / match.group(2) / match.group(3)).resolve()
        if assets_dir.resolve() not in path.parents or not path.is_file():
            raise BundleError(f"unknown asset: {ref} (read assets/README.md for what exists)")
        used.add(f"{match.group(1)}@{match.group(2)}")
        return path.read_bytes()
    path = safe_job_path(job_dir, ref)
    if not path.is_file():
        raise BundleError(f"file not found: {ref}")
    return path.read_bytes()


def lint(html_own: str, js_own: str, css_own: str) -> list[str]:
    errors = []
    for pattern, message in FORBIDDEN_HTML:
        for found in re.finditer(pattern, html_own, re.I):
            errors.append(message.format(*(found.groups() or ("",))))
    if EXTERNAL_REF.search(html_own):
        errors.append("external URLs in src/href are not allowed: cite sources with data-dl-source, bundle everything else")
    for pattern, message in FORBIDDEN_JS:
        if re.search(pattern, js_own):
            errors.append(message)
    if CSS_EXTERNAL.search(css_own) or CSS_EXTERNAL.search(html_own):
        errors.append("external CSS (@import, url(http...)) is not allowed")
    return sorted(set(errors))


def bundle(job_dir: Path, assets_dir: Path) -> dict:
    index = job_dir / "index.html"
    if not index.is_file():
        raise BundleError("index.html is missing: write the lesson entrypoint first")
    files = [p for p in job_dir.rglob("*") if p.is_file()]
    if len(files) > MAX_FILES or any(p.stat().st_size > MAX_FILE for p in files):
        raise BundleError(f"at most {MAX_FILES} files of {MAX_FILE // 1024} KB each")
    html = index.read_text(encoding="utf-8", errors="strict")
    used, own_js, own_css = set(), [], []

    def is_asset(ref):
        return bool(ASSET_REF.match(ref.strip().removeprefix("./")))

    def link(match):
        tag = match.group(0)
        rel, href = ATTR("rel").search(tag), ATTR("href").search(tag)
        if not rel or rel.group(2).lower() != "stylesheet":
            raise BundleError("only <link rel=\"stylesheet\"> is allowed")
        if not href:
            raise BundleError("<link> without href")
        css = _read(job_dir, assets_dir, href.group(2), used).decode("utf-8")
        if not is_asset(href.group(2)):
            own_css.append(css)
        return f'<style data-src="{href.group(2)}">\n{css}\n</style>'

    def script(match):
        ref = match.group(3)
        js = _read(job_dir, assets_dir, ref, used).decode("utf-8")
        if not is_asset(ref):
            own_js.append(js)
        return f'<script data-src="{ref}">\n' + re.sub(r"</(script)", r"<\\/\1", js, flags=re.I) + "\n</script>"

    def image(match):
        ref = match.group(3)
        if ref.startswith("data:"):
            return match.group(0)
        kind = IMAGE_TYPES.get(Path(ref.split("?")[0]).suffix.lower())
        if not kind:
            raise BundleError(f"unsupported image type: {ref}")
        data = base64.b64encode(_read(job_dir, assets_dir, ref, used)).decode()
        return f"{match.group(1)}{match.group(2)}data:{kind};base64,{data}{match.group(2)}"

    own_html = html
    html = LINK.sub(link, html)
    html = SCRIPT_SRC.sub(script, html)
    html = IMG.sub(image, html)
    for attrs, body in INLINE_SCRIPT.findall(own_html):
        if "src" not in attrs.lower():
            own_js.append(body)
    own_css += re.findall(r"<style\b[^>]*>(.*?)</style\s*>", own_html, re.I | re.S)
    errors = lint(own_html, "\n".join(own_js), "\n".join(own_css))
    if len(html.encode()) > MAX_BUNDLE:
        errors.append(f"the bundled lesson is larger than {MAX_BUNDLE // 1024} KB")
    return {"html": html, "errors": errors, "assets": sorted(used), "script_hashes": script_hashes(html),
            "sha256": hashlib.sha256(html.encode()).hexdigest(), "bytes": len(html.encode())}


def script_hashes(html: str) -> list[str]:
    """CSP hashes of every executable inline script, in document order."""
    out = []
    for attrs, body in INLINE_SCRIPT.findall(html):
        kind = ATTR("type").search(attrs)
        if kind and kind.group(2).lower() not in ("", "text/javascript", "application/javascript"):
            continue            # data blocks (application/json) never execute
        out.append("sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode())
    return list(dict.fromkeys(out))


def csp(hashes: list[str]) -> str:
    """The production policy. Kept identical in backend/app/teach/artifacts.py (test compares them)."""
    scripts = " ".join(f"'{h}'" for h in hashes) or "'none'"
    return ("sandbox allow-scripts; default-src 'none'; script-src " + scripts + "; style-src 'unsafe-inline'; "
            "img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; "
            "form-action 'none'; base-uri 'none'; frame-ancestors 'self'")
