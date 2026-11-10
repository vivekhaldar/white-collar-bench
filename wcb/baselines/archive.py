"""Archive-only ingestion: the ingest half of the raw-retrieval baseline (docs/plan.md §7).

During an ingestion session this copies every input from ``inbox/<date>/`` into
``sources/<date>/``, unchanged except for redacting obvious secrets, and appends a daily log
that lists what was archived. It does no curation: people, projects and loops are never
created or updated. Paired with a search-only query agent, it shows how much curation adds
over keeping raw inputs and searching them at question time.

Run as ``python -m wcb.baselines.archive`` with the runner's ``WCB_*`` environment.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from wcb.util.io import read_json

TEXT_SUFFIXES = {".eml", ".md", ".txt", ".json", ".vtt", ".ics", ".csv"}

_SECRET_PATTERNS = [
    re.compile(r"https?://[^\s\"'<>]*?/j/[^\s\"'<>]+", re.I),  # meeting join links
    re.compile(r"https?://(?:meet|join|zoom|video)[\w.-]*\.[a-z]+/[^\s\"'<>]+", re.I),
    re.compile(r"(?i)\b(pass(?:code|word)|pwd|pin|access code)\b(\s*[:=]?\s*)(\S+)"),
    re.compile(r"\b(?:sk|pk|api|key)[-_][A-Za-z0-9_-]{16,}\b"),
]


def redact(text: str) -> str:
    """Replace join links, passcodes, passwords and key-like tokens with [redacted]."""
    for pat in _SECRET_PATTERNS:
        if pat.groups == 3:
            text = pat.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", text)
        else:
            text = pat.sub("[redacted]", text)
    return text


def archive_inbox(workspace: Path, date: str) -> list[dict]:
    """Copy inbox/<date>/ into sources/<date>/ and return the manifest entries archived."""
    inbox = workspace / "inbox" / date
    if not inbox.is_dir():
        return []
    manifest_path = inbox / "manifest.json"
    entries = read_json(manifest_path).get("artifacts", []) if manifest_path.exists() else []
    dest = workspace / "sources" / date
    dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(inbox.iterdir()):
        if not f.is_file():
            continue
        if f.suffix.lower() in TEXT_SUFFIXES:
            (dest / f.name).write_text(
                redact(f.read_text(encoding="utf-8", errors="replace")), encoding="utf-8"
            )
        else:
            shutil.copy2(f, dest / f.name)
    return entries


def write_daily_log(workspace: Path, date: str, entries: list[dict]) -> None:
    log = workspace / "logs" / f"{date}.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"---\nid: logs/{date}\ntype: log\ndate: {date}\n---\n"]
    for e in entries:
        lines.append(
            f"- {e['id']} ({e.get('channel', '?')}): archived to sources/{date}/{e.get('path', '')}; {e.get('title', '')}"
        )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    phase = os.environ.get("WCB_PHASE", "ingest")
    workspace = Path(os.environ.get("WCB_WORKSPACE", "."))
    if phase != "ingest":
        print(
            "wcb.baselines.archive only handles ingestion; use a query agent for questions",
            file=sys.stderr,
        )
        return 2
    inbox_root = workspace / "inbox"
    dates = (
        sorted(p.name for p in inbox_root.iterdir() if p.is_dir()) if inbox_root.is_dir() else []
    )
    for date in dates:
        write_daily_log(workspace, date, archive_inbox(workspace, date))
    print(f"archived {len(dates)} inbox date(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
