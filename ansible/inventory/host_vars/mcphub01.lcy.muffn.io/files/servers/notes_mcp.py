# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "mcp==1.30.0",
# ]
# ///
"""Shared Markdown notes for voice assistants and Claude clients.

Each bucket is a git repository at $NOTES_ROOT/<bucket> (plants, printers, ...).
You push the notes in from your own machine; the repo accepts pushes with
receive.denyCurrentBranch=updateInstead, so its working tree follows.

Three tools only, because a voice model picks badly from long tool lists:
  search_notes  find lines mentioning the words in a question
  read_note     read a note, or list a folder
  add_note      record an update as a NEW file in <bucket>/INBOX/, one commit

add_note never edits an existing file, so a misheard entry is undone with one
`git revert`. Whoever curates the bucket folds INBOX files into the real notes.

Env: NOTES_BUCKETS (comma separated, first is the default), NOTES_ROOT, NOTES_TZ.
"""

import fcntl
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

ROOT = Path(os.environ.get("NOTES_ROOT", "/opt/notes"))
BUCKETS = [b.strip() for b in os.environ.get("NOTES_BUCKETS", "plants").split(",") if b.strip()]
TZ = ZoneInfo(os.environ.get("NOTES_TZ", "Europe/London"))

MAX_READ_CHARS = 6000
MAX_HITS = 8
MAX_LINE_CHARS = 220
MAX_NOTE_CHARS = 1000
HIDDEN_DIRS = {".git", "images"}
# Top-level files about the notes, not notes: they would crowd out real matches.
SEARCH_SKIP_FILES = {"CLAUDE.md", "README.md", "AGENTS.md"}
STOPWORDS = {
    "the", "and", "did", "when", "what", "was", "were", "have", "has", "how",
    "last", "for", "with", "that", "this", "from", "are", "you", "does", "much",
}
GIT_ENV = {
    "GIT_AUTHOR_NAME": "Voice notes",
    "GIT_AUTHOR_EMAIL": "notes@mcphub01.lcy.muffn.io",
    "GIT_COMMITTER_NAME": "Voice notes",
    "GIT_COMMITTER_EMAIL": "notes@mcphub01.lcy.muffn.io",
}

mcp = FastMCP("notes")


def _bucket_dir(bucket: str) -> Path | str:
    """Return the bucket's directory (repo created on first use) or an error string."""
    bucket = bucket.strip().lower() or BUCKETS[0]
    if bucket not in BUCKETS:
        return f"Unknown bucket '{bucket}'. Available: {', '.join(BUCKETS)}."
    path = ROOT / bucket
    path.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        _git(path, "init", "-q", "-b", "main")
    # Lets a push from another machine update the working tree in place.
    _git(path, "config", "receive.denyCurrentBranch", "updateInstead")
    return path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", f"safe.directory={repo}", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=15,
        env={**os.environ, **GIT_ENV},
    )


def _safe_path(repo: Path, rel: str) -> Path | None:
    """Resolve rel inside repo, or None if it escapes or touches hidden dirs."""
    target = (repo / rel.strip().lstrip("/")).resolve()
    try:
        parts = target.relative_to(repo.resolve()).parts
    except ValueError:
        return None
    if any(p in HIDDEN_DIRS for p in parts):
        return None
    return target


def _clip(line: str) -> str:
    line = line.strip()
    return line if len(line) <= MAX_LINE_CHARS else line[: MAX_LINE_CHARS - 1] + "…"


@mcp.tool()
def search_notes(query: str, bucket: str = "") -> str:
    """Find notes that mention the words in the query, e.g. 'monstera watered'.

    Use this first to locate a plant or topic, then read_note for detail.
    Returns up to 8 matching lines as 'path:line: text'. `bucket` defaults to plants.
    """
    repo = _bucket_dir(bucket)
    if isinstance(repo, str):
        return repo
    terms = {t for t in re.findall(r"[a-z0-9]{3,}", query.lower()) if t not in STOPWORDS}
    if not terms:
        return "Give at least one specific word to search for."
    hits: list[tuple[int, str, int, str]] = []
    for path in repo.rglob("*.md"):
        rel = path.relative_to(repo)
        if any(p in HIDDEN_DIRS or p.startswith("_") for p in rel.parts):
            continue
        if len(rel.parts) == 1 and rel.name in SEARCH_SKIP_FILES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(lines, 1):
            low = line.lower()
            score = sum(1 for t in terms if t in low)
            if score:
                hits.append((score, str(rel), n, line))
    if not hits:
        return f"No notes in '{repo.name}' mention: {', '.join(sorted(terms))}."
    # Best match first. Among equals: newest inbox entries (timestamped filenames),
    # then other notes by path with later lines first (logs are newest-at-bottom).
    hits.sort(key=lambda h: (h[1], -h[2]))
    inbox = [h for h in hits if h[1].startswith("INBOX/")][::-1]
    hits = inbox + [h for h in hits if not h[1].startswith("INBOX/")]
    hits.sort(key=lambda h: -h[0])  # stable: keeps the order above within a score
    return "\n".join(f"{rel}:{n}: {_clip(line)}" for _, rel, n, line in hits[:MAX_HITS])


@mcp.tool()
def read_note(path: str = "INDEX.md", bucket: str = "") -> str:
    """Read one note, or list a folder when the path is a folder (e.g. 'plants').

    Default is INDEX.md, the table of everything in the bucket with next actions.
    Plant history is in plants/<name>/LOG.md (newest entries at the bottom).
    """
    repo = _bucket_dir(bucket)
    if isinstance(repo, str):
        return repo
    target = _safe_path(repo, path or "INDEX.md")
    if target is None or not target.exists():
        return f"No note at '{path}'. Try search_notes or read_note('.') to list the bucket."
    if target.is_dir():
        names = sorted(
            p.name + ("/" if p.is_dir() else "")
            for p in target.iterdir()
            if p.name not in HIDDEN_DIRS and not p.name.startswith(".")
        )
        return "\n".join(names) or "(empty folder)"
    if target.suffix != ".md":
        return "Only Markdown notes can be read."
    try:
        text = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "That note could not be read."
    if len(text) > MAX_READ_CHARS:
        return "[earlier part omitted]\n" + text[-MAX_READ_CHARS:]
    return text


@mcp.tool()
def add_note(text: str, topic: str, bucket: str = "") -> str:
    """Record something the user says they did or noticed, e.g. 'I repotted the fern'.

    `text` is their words, lightly tidied; `topic` is the plant or subject ('fern').
    This only adds a new dated entry to the inbox; it cannot change existing notes.
    Do not use it for questions.
    """
    text = text.strip()
    if not text:
        return "Nothing to record."
    if len(text) > MAX_NOTE_CHARS:
        return f"Too long to record (limit {MAX_NOTE_CHARS} characters)."
    repo = _bucket_dir(bucket)
    if isinstance(repo, str):
        return repo
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:40] or "note"
    now = datetime.now(TZ)
    with open(repo / ".git" / "notes-mcp.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _git(repo, "rev-parse", "--verify", "-q", "HEAD").returncode != 0:
            return f"The '{repo.name}' notes have not been loaded yet, so nothing was recorded."
        inbox = repo / "INBOX"
        inbox.mkdir(exist_ok=True)
        stem = f"{now:%Y-%m-%d_%H%M%S}_{slug}"
        note = inbox / f"{stem}.md"
        try:
            # "x" fails instead of overwriting if two notes share a second and topic.
            with note.open("x", encoding="utf-8") as fh:
                fh.write(
                    f"---\ndate: {now:%Y-%m-%d %H:%M} ({TZ.key})\ntopic: {topic.strip()[:60]}\n"
                    f"source: user-reported (voice; transcript unverified)\n---\n{text}\n"
                )
        except FileExistsError:
            return "Please say that again in a moment; nothing was recorded."
        rel = f"INBOX/{note.name}"
        _git(repo, "add", "--", rel)
        done = _git(repo, "commit", "-q", "-m", f"inbox: {slug} (voice)", "--", rel)
        if done.returncode != 0:
            note.unlink(missing_ok=True)
            return "Could not save that note, so nothing was recorded."
    return f"Recorded under {repo.name} for {topic.strip()} on {now:%d %B}."


if __name__ == "__main__":
    # Create every bucket repo at startup so the first push has somewhere to land.
    for _bucket in BUCKETS:
        _bucket_dir(_bucket)
    mcp.run()
