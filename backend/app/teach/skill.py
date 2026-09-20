"""Loads the adapted /teach skill for the orchestrator and fingerprints it.

Every lesson version records both revisions, so a trace shows which instructions made it.
Changing the upstream commit or any file in skill/ is an explicit release."""
import hashlib
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL_DIR = ROOT / "skill"
VENDOR_DIR = ROOT / "vendor" / "mattpocock-teach"
UPSTREAM_COMMIT = "321658273cb1d20b76026717d027d505790106d4"
FORMATS = ("MISSION-FORMAT.md", "LEARNING-RECORD-FORMAT.md", "RESOURCES-FORMAT.md", "GLOSSARY-FORMAT.md")
INSTRUCTION_FILES = ("SKILL.md", *FORMATS)


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


@lru_cache(maxsize=1)
def adaptation_revision() -> str:
    """sha256 over the instruction files the model actually receives."""
    digest = hashlib.sha256()
    for name in INSTRUCTION_FILES:
        digest.update(name.encode() + b"\0" + (SKILL_DIR / name).read_bytes() + b"\0")
    return digest.hexdigest()[:16]


@lru_cache(maxsize=1)
def system_prompt() -> str:
    """The adapted SKILL.md with its referenced formats appended, so every agent step has them."""
    parts = [(SKILL_DIR / "SKILL.md").read_text()]
    for name in FORMATS:
        parts.append(f"\n\n---\n<!-- file: {name} -->\n" + (SKILL_DIR / name).read_text())
    return "".join(parts)


def provenance() -> dict:
    return {"skill_upstream_commit": UPSTREAM_COMMIT, "skill_adaptation_revision": adaptation_revision()}


def sections(*headings: str) -> str:
    """Named sections of the adapted SKILL.md, verbatim. The running lesson (mentor questions inside a
    lesson) loads the skill's own text for how to teach, not a paraphrase of it."""
    import re
    text = (SKILL_DIR / "SKILL.md").read_text()
    parts = re.split(r"(?m)^(?=#{2,3} )", text)
    wanted = [p.strip() for p in parts if any(p.startswith(("## " + h, "### " + h)) for h in headings)]
    return "\n\n".join(wanted)
