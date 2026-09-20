"""Lesson files on the artifact volume. Content-addressed and immutable.

Paths are never taken from a client: callers pass IDs and hashes that were read from Neo4j, and every
part is checked against a strict pattern before it touches the file system."""
import base64
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(os.getenv("TEACH_ARTIFACT_DIR", "/artifacts"))
SEED = Path(__file__).resolve().parent / "assets"
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
ASSET_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
ASSET_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
ASSET_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
INLINE_SCRIPT = re.compile(r"<script\b([^>]*)>(.*?)</script\s*>", re.I | re.S)
TYPE_ATTR = re.compile(r"\btype\s*=\s*([\"'])(.*?)\1", re.I | re.S)
MAX_READ = 64 * 1024


def available() -> bool:
    return ROOT.is_dir() and os.access(ROOT, os.W_OK)


def seed_assets() -> list[str]:
    """Copies the components that ship with the app onto the volume, once per version. A version
    directory is never overwritten: a changed component is a new version."""
    done = []
    if not available():
        return done
    for name_dir in sorted(p for p in SEED.iterdir() if p.is_dir()):
        for version_dir in sorted(p for p in name_dir.iterdir() if p.is_dir()):
            target = ROOT / "assets" / name_dir.name / version_dir.name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(version_dir, target)
                for path in [target, *target.rglob("*")]:
                    path.chmod(0o755 if path.is_dir() else 0o644)
                for parent in (ROOT / "assets", target.parent):
                    parent.chmod(0o755)
                done.append(f"{name_dir.name}@{version_dir.name}")
    return done


def list_assets() -> list[dict]:
    out = []
    base = ROOT / "assets"
    if not base.is_dir():
        return out
    for name_dir in sorted(p for p in base.iterdir() if p.is_dir() and ASSET_NAME.match(p.name)):
        for version_dir in sorted(p for p in name_dir.iterdir() if p.is_dir() and ASSET_VERSION.match(p.name)):
            files = sorted(f.name for f in version_dir.iterdir() if f.is_file())
            out.append({"name": name_dir.name, "version": version_dir.name, "files": files})
    return out


def read_asset(name: str, version: str, file: str) -> str:
    if not (ASSET_NAME.match(name) and ASSET_VERSION.match(version) and ASSET_FILE.match(file)):
        raise ValueError("Unknown asset")
    path = ROOT / "assets" / name / version / file
    if not path.is_file():
        raise ValueError("Unknown asset")
    if path.stat().st_size > MAX_READ:
        return f"({file} is {path.stat().st_size // 1024} KB and is not shown. Link it; do not read it.)"
    return path.read_text(encoding="utf-8")


def store_asset(name: str, files: dict) -> dict:
    """A component proposed by the teaching agent, after the workbench linted it. Versions are
    immutable: the next free patch version is used, an existing directory is never touched."""
    if not ASSET_NAME.match(name or "") or name.startswith("dendrite-"):
        raise ValueError("component name: lowercase letters, digits and dashes; 'dendrite-' is reserved")
    if not files or len(files) > 8 or any(not ASSET_FILE.match(f) for f in files) or sum(len(v.encode()) for v in files.values()) > 512 * 1024:
        raise ValueError("a component has 1-8 flat files (no folders), 512 KB in total")
    if not any(f.lower() == "readme.md" for f in files):
        raise ValueError("a component needs a README.md that says how a lesson uses it")
    base = ROOT / "assets" / name
    taken = [tuple(map(int, p.name.split("."))) for p in base.iterdir()] if base.is_dir() else []
    version = "1.0.%d" % (max(v[2] for v in taken) + 1) if taken else "1.0.0"
    target = base / version
    target.mkdir(parents=True)
    for file, text in files.items():
        (target / file).write_text(text, encoding="utf-8")
        (target / file).chmod(0o644)
    for path in (base, target):
        path.chmod(0o755)
    digest = hashlib.sha256("".join(f + "\0" + files[f] for f in sorted(files)).encode()).hexdigest()
    return {"name": name, "version": version, "sha256": digest, "files": sorted(files)}


def script_hashes(html: str) -> list[str]:
    out = []
    for attrs, body in INLINE_SCRIPT.findall(html):
        kind = TYPE_ATTR.search(attrs)
        if kind and kind.group(2).lower() not in ("", "text/javascript", "application/javascript"):
            continue
        out.append("sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode())
    return list(dict.fromkeys(out))


def csp(hashes: list[str]) -> str:
    """Identical to author/bundle.py csp(): the lesson is validated under the policy it ships with.
    Hashes instead of 'unsafe-inline' for scripts: only the validated scripts can run. Styles may be
    inline; with default-src 'none' and img/font limited to data:, CSS has nothing to talk to."""
    scripts = " ".join(f"'{h}'" for h in hashes) or "'none'"
    return ("sandbox allow-scripts; default-src 'none'; script-src " + scripts + "; style-src 'unsafe-inline'; "
            "img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; "
            "form-action 'none'; base-uri 'none'; frame-ancestors 'self'")


def store_lesson(lesson_id: str, html: str, manifest: dict) -> dict:
    """The API hashes what it stores itself; it does not reuse hashes computed by the workbench."""
    if not UUID.match(lesson_id):
        raise ValueError("Invalid lesson id")
    data = html.encode("utf-8")
    content_hash = hashlib.sha256(data).hexdigest()
    target = ROOT / "lessons" / lesson_id / content_hash
    if not target.exists():
        target.mkdir(parents=True)
        (target / "index.html").write_bytes(data)
        (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        for path in (target / "index.html", target / "manifest.json"):
            path.chmod(0o440)
    return {"content_hash": content_hash, "bytes": len(data), "script_hashes": script_hashes(html)}


def read_lesson(lesson_id: str, content_hash: str) -> str:
    if not (UUID.match(lesson_id) and SHA.match(content_hash)):
        raise FileNotFoundError("lesson")
    path = ROOT / "lessons" / lesson_id / content_hash / "index.html"
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != content_hash:
        raise FileNotFoundError("lesson file does not match its recorded hash")
    return data.decode("utf-8")
