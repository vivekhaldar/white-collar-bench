"""Read a Track A store directory into records (see contract/CONTRACT.md, sections 1 and 2).

A store is a directory of Markdown files. Every `.md` file under one of the record directories
(`people/`, `orgs/`, `projects/`, `loops/`, `logs/`) is a **record**: YAML front matter plus a
Markdown body. Everything else (`CONTRACT.md`, `sources/`, `notes/`, ...) is kept as a list of
"other files" so that privacy checks can still scan it.

The parser is deliberately forgiving: it never raises on a malformed record. A record whose
front matter is missing or does not parse gets `meta == {}` and an `error` message, and the
validator (`wcb.contract.validate`) turns that into an issue. Graders can therefore read the
rest of a partly broken store.

Example::

    store = load_store(Path("my-store"))
    for loop in store.of_type("loop"):
        print(loop.id, loop.meta.get("status"), loop.section("Log"))
    store.get("[[projects/thistledown]]")      # same as store.get("projects/thistledown.md")
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from wcb.util import frontmatter

#: Record directory -> the record `type` its files must declare.
RECORD_DIRS = {
    "people": "person",
    "orgs": "org",
    "projects": "project",
    "loops": "loop",
    "logs": "log",
}

#: Top-level directories that are not part of the store's content: version control, the
#: session inbox (removed after each session) and the runner's scratch directory.
EXCLUDED_TOP_DIRS = frozenset({".git", "inbox", ".wcb"})

#: Extensions never read as text (archived attachments and similar binary files).
BINARY_EXTENSIONS = frozenset(
    ".pdf .docx .doc .xlsx .xls .pptx .ppt .zip .gz .png .jpg .jpeg .gif .webp .mp3 .mp4 .wav .m4a".split()
)

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")


@dataclass
class Record:
    """One record file, as parsed. Field values are taken as written; nothing is validated here."""

    id: str | None  # front matter 'id' (None if absent)
    expected_id: str  # path without .md, e.g. 'people/marisol-teague'
    path: str  # posix path relative to the store root, e.g. 'people/marisol-teague.md'
    type: str | None  # front matter 'type'
    meta: dict  # parsed front matter ({} if missing or invalid); dates are ISO strings
    body: str  # Markdown after the front matter
    sections: dict[str, str] = field(default_factory=dict)  # '## Title' -> section text
    error: str | None = None  # why the front matter could not be read, if it could not

    @property
    def dir_type(self) -> str:
        """The record type implied by the record's directory, e.g. 'loop' for 'loops/x.md'."""
        return RECORD_DIRS[self.expected_id.split("/", 1)[0]]

    @property
    def stem(self) -> str:
        """File name without directory or extension, e.g. 'marisol-teague'."""
        return self.expected_id.rsplit("/", 1)[-1]

    def section(self, title: str) -> str | None:
        """Text of the `## <title>` section, matched case-insensitively; None if absent."""
        want = title.strip().lower()
        for name, text in self.sections.items():
            if name.strip().lower() == want:
                return text
        return None


@dataclass
class Store:
    """A parsed store. `records` is keyed by `expected_id` (the ID implied by the file path)."""

    root: Path
    records: dict[str, Record]  # only .md files under RECORD_DIRS
    other_files: list[str]  # every other file, posix-relative; excludes .git/, inbox/, .wcb/

    def of_type(self, type_: str) -> list[Record]:
        """Records in the directory for `type_` ('person', 'org', 'project', 'loop' or 'log').

        Membership follows the directory, not the declared `type` field, so a record in
        `loops/` with a wrong `type` is still returned here (the validator reports the mismatch).
        """
        return [r for r in self.records.values() if r.dir_type == type_]

    def get(self, id_or_path: str) -> Record | None:
        """Look up a record by ID or path: 'loops/x', 'loops/x.md', './loops/x.md', '[[loops/x]]'."""
        return self.records.get(normalize_ref(id_or_path))

    def iter_text(self) -> Iterator[tuple[str, str]]:
        """Yield `(relative path, text)` for every text file in the store, in path order.

        Covers records and other files. Binary files (by extension, or containing NUL bytes)
        are skipped. Text is decoded as UTF-8 with replacement characters for bad bytes.
        """
        paths = sorted([r.path for r in self.records.values()] + list(self.other_files))
        for rel in paths:
            text = read_text_file(self.root / rel)
            if text is not None:
                yield rel, text

    def all_text(self) -> str:
        """Concatenated text of all text files (records and other files), for privacy checks."""
        return "\n".join(text for _, text in self.iter_text())


# ---------------------------------------------------------------- public functions
def load_store(root: Path) -> Store:
    """Parse the store at `root`. Raises FileNotFoundError if `root` is not a directory."""
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"no store directory at {root}")
    records: dict[str, Record] = {}
    other: list[str] = []
    for rel in _walk_files(root):
        if is_record_path(rel):
            text = read_text_file(root / rel) or ""
            rec = parse_record(text, rel)
            records[rec.expected_id] = rec
        else:
            other.append(rel)
    return Store(root=root, records=dict(sorted(records.items())), other_files=sorted(other))


def is_record_path(rel: str) -> bool:
    """True for a `.md` file anywhere below a record directory, e.g. 'loops/x.md'."""
    top, _, rest = rel.partition("/")
    return top in RECORD_DIRS and bool(rest) and rel.endswith(".md")


def parse_record(text: str, path: str) -> Record:
    """Parse one record file. `path` is posix and relative to the store root. Never raises."""
    expected_id = path[: -len(".md")] if path.endswith(".md") else path
    meta: dict = {}
    error: str | None = None
    try:
        raw, body = frontmatter.split(text)
    except frontmatter.FrontMatterError as e:
        raw, body, error = None, text, str(e)
    if raw is None and error is None:
        error = "missing YAML front matter (the file must start with a '---' line)"
    elif raw is not None:
        try:
            meta = frontmatter.parse(text)[0] or {}
        except Exception as e:  # YAML raises a bare ValueError for dates like 2027-02-30
            error = (
                str(e)
                if isinstance(e, frontmatter.FrontMatterError)
                else f"invalid YAML front matter: {e}"
            )
            meta = {}
    return Record(
        id=_opt_str(meta.get("id")),
        expected_id=expected_id,
        path=path,
        type=_opt_str(meta.get("type")),
        meta=meta,
        body=body,
        sections=parse_sections(body),
        error=error,
    )


def parse_sections(body: str) -> dict[str, str]:
    """Split a Markdown body into its `## ` sections.

    Returns `{heading title: section text}` in document order. A section runs until the next
    level-1 or level-2 heading; deeper headings (`###`) stay inside it. Text before the first
    `## ` heading is not part of any section. Headings inside fenced code blocks are ignored.
    If a heading appears twice, the texts are joined with a blank line, so a duplicated
    `## Current state` reads as two paragraphs. Section text is stripped of surrounding blank
    lines and whitespace.
    """
    chunks: dict[str, list[list[str]]] = {}  # title -> one list of lines per occurrence
    current: list[str] | None = None
    in_fence = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else _HEADING_RE.match(line)
        if m and len(m.group(1)) <= 2:
            current = None
            if len(m.group(1)) == 2:
                current = []
                chunks.setdefault(m.group(2).strip(), []).append(current)
            continue
        if current is not None:
            current.append(line)
    return {
        title: "\n\n".join(t for t in ("\n".join(c).strip() for c in parts) if t)
        for title, parts in chunks.items()
    }


def normalize_ref(ref: str) -> str:
    """Normalize a record reference to a record ID.

    Accepts the forms agents and answers use: 'loops/x', 'loops/x.md', './loops/x.md',
    '/loops/x', '[[loops/x]]', '[[loops/x|label]]' and 'loops/x#log'. Case is preserved, since
    record IDs are lowercase by contract and a wrongly cased reference should not resolve.
    """
    s = str(ref).strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    s = s.split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    s = s.lstrip("/")
    if s.endswith(".md"):
        s = s[: -len(".md")]
    return s


def read_text_file(path: Path) -> str | None:
    """File contents as text, or None for binary files (known extension or NUL bytes)."""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


# ---------------------------------------------------------------- internals
def _walk_files(root: Path) -> Iterator[str]:
    """Posix paths of all files under root, relative to it, skipping excluded directories."""
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        if rel_dir == ".":
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_TOP_DIRS]
            rel_dir = ""
        dirnames[:] = sorted(d for d in dirnames if d != ".git")
        for name in sorted(filenames):
            yield f"{rel_dir}/{name}" if rel_dir else name


def _opt_str(v: object) -> str | None:
    return None if v is None else str(v)
