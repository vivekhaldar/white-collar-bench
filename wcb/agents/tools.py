"""File tools for the simple harness, confined to the session's workspace.

The simple harness (:mod:`wcb.agents.simple`) gives a model exactly these tools and nothing else:
no shell, no network, no access outside the workspace.

==============  ===========================================================================
Tool            Behaviour
==============  ===========================================================================
list_files      ``list_files(path=".", recursive=false)``: entries under a directory.
read_file       ``read_file(path, offset=0, limit=400)``: a window of lines of a text file.
read_document   ``read_document(path, offset=0, limit=400)``: extracted text of .docx, .xlsx,
                .pptx, .pdf, .eml and .ics files (see :mod:`wcb.agents.docs_text`).
write_file      ``write_file(path, content)``: create or overwrite a file (parents created).
edit_file       ``edit_file(path, old, new)``: replace one exact, unique occurrence of ``old``.
delete_file     ``delete_file(path)``: delete a file or an empty directory.
move_file       ``move_file(src, dst)``: rename a file or directory; ``dst`` must not exist.
search          ``search(pattern, path=".", regex=true, ignore_case=true)``: grep-like search
                over text files and extracted document text, with capped output.
finish          ``finish(summary)``: end the session (handled by the harness loop).
==============  ===========================================================================

Sandbox rules, enforced by :meth:`Workspace.resolve` for every path argument:

- Paths are relative to the workspace root. Absolute paths, ``~`` paths, ``..`` components and
  NUL bytes are rejected.
- After resolving symbolic links the target must still be inside the workspace, so a link
  pointing outside cannot be read, written or listed through.
- ``.git/`` is hidden from listings and searches and cannot be modified (the runner manages it).
- In a read-only workspace (query sessions) only paths under ``.wcb/`` can be modified.

Every tool returns text for the model. Mistakes (a missing file, an ambiguous edit) come back as
:class:`ToolOutput` with ``is_error=True`` and a message that says how to fix the call, so the
model can recover instead of the session crashing.
"""

from __future__ import annotations

import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from wcb.agents.docs_text import (
    BINARY_SUFFIXES,
    DOCUMENT_SUFFIXES,
    OFFICE_SUFFIXES,
    DocumentError,
    extract_text,
)

DEFAULT_READ_LIMIT = 400
MAX_READ_LIMIT = 2000
MAX_LINE_CHARS = 2000
MAX_LIST_ENTRIES = 1000
MAX_SEARCH_MATCHES = 200
MAX_SEARCH_LINE_CHARS = 300
MAX_SEARCH_FILE_BYTES = 5 * 1024 * 1024
MAX_WRITE_BYTES = 5 * 1024 * 1024
HIDDEN = (".git",)
"""Top-level names never listed or searched, and never writable."""

FINISH = "finish"


class ToolError(Exception):
    """A tool call that cannot be carried out. The message is shown to the model."""


@dataclass
class ToolOutput:
    """What a tool call returns to the model."""

    content: str
    is_error: bool = False


# ====================================================================== tool specs
TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "list_files",
        "description": (
            "List files and directories under a directory of the workspace. Directories end "
            "with '/'. Paths are relative to the workspace root."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory to list. Default '.'."},
                "recursive": {
                    "type": "boolean",
                    "description": "List the whole tree below path. Default false.",
                },
            },
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read lines of a text file. Returns at most `limit` lines starting at line `offset` "
            "(0-based). For .docx, .xlsx, .pptx, .pdf, .eml and .ics use read_document."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer", "description": "First line, 0-based. Default 0."},
                "limit": {
                    "type": "integer",
                    "description": f"Maximum lines to return. Default {DEFAULT_READ_LIMIT}.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "read_document",
        "description": (
            "Extract readable text from a document: Word (.docx), Excel (.xlsx), PowerPoint "
            "(.pptx), PDF, email (.eml) or calendar (.ics). Other files are returned as text. "
            "Supports the same offset/limit paging as read_file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer", "description": "First line, 0-based. Default 0."},
                "limit": {
                    "type": "integer",
                    "description": f"Maximum lines to return. Default {DEFAULT_READ_LIMIT}.",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Create or overwrite a text file with the given content. Parent directories are "
            "created as needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string", "description": "The complete new file content."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": (
            "Replace one exact occurrence of `old` with `new` in a text file. `old` must match "
            "the file exactly (including whitespace) and occur exactly once; include more "
            "surrounding text if it is not unique."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string", "description": "Exact text to replace."},
                "new": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old", "new"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file, or an empty directory.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "move_file",
        "description": (
            "Move or rename a file or directory. The destination must not exist; parent "
            "directories are created as needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
            "required": ["src", "dst"],
        },
    },
    {
        "name": "search",
        "description": (
            "Search file contents under a path, like grep. Returns 'path:line: text' for each "
            "matching line (documents such as .docx and .pdf are searched by their extracted "
            f"text). Output is capped at {MAX_SEARCH_MATCHES} matches."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regular expression or literal text."},
                "path": {"type": "string", "description": "File or directory. Default '.'."},
                "regex": {
                    "type": "boolean",
                    "description": "Treat pattern as a Python regular expression. Default true.",
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case-insensitive matching. Default true.",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": FINISH,
        "description": (
            "Call this once the task is complete, with a short summary of what you did. "
            "The session ends after this call."
        ),
        "parameters": {
            "type": "object",
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    },
]
"""Provider-neutral tool definitions: ``name``, ``description`` and a JSON Schema ``parameters``."""

TOOL_NAMES = tuple(spec["name"] for spec in TOOL_SPECS)


# ====================================================================== workspace
class Workspace:
    """The directory the tools may touch, with the sandbox rules from the module docs.

    ``read_only=True`` (query sessions) allows modifications only under ``writable_dirs``.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        read_only: bool = False,
        writable_dirs: tuple[str, ...] = (".wcb",),
    ):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"workspace {self.root} does not exist or is not a directory")
        self.read_only = read_only
        self.writable_dirs = writable_dirs

    def resolve(self, path: Any, *, write: bool = False) -> Path:
        """Turn a model-supplied relative path into an absolute path inside the workspace.

        Raises :class:`ToolError` with an explanation if the path breaks a sandbox rule.
        """
        if path is None or path == "":
            path = "."
        if not isinstance(path, str):
            raise ToolError(f"path must be a string, got {type(path).__name__}")
        if "\x00" in path:
            raise ToolError("path contains a NUL byte")
        norm = path.replace("\\", "/")
        if norm.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", norm):
            raise ToolError(
                f"{path!r} is not allowed: use a path relative to the workspace root, "
                "e.g. 'people/me.md' or '.'"
            )
        parts = [p for p in PurePosixPath(norm).parts if p not in ("", ".")]
        if ".." in parts:
            raise ToolError(f"{path!r} is not allowed: '..' cannot be used in paths")
        full = self.root.joinpath(*parts)
        try:
            real = full.resolve()
        except (OSError, RuntimeError) as e:  # symlink loops
            raise ToolError(f"cannot resolve {path!r}: {e}") from e
        if real != self.root and self.root not in real.parents:
            raise ToolError(f"{path!r} is a symbolic link that points outside the workspace")
        if write:
            # Check both the path as written and its symlink-resolved target.
            if not parts or real == self.root:
                raise ToolError("the workspace root itself cannot be modified")
            tops = {parts[0], real.relative_to(self.root).parts[0]}
            if tops & set(HIDDEN):
                raise ToolError(f"{path!r} is managed by the runner and cannot be modified")
            if self.read_only and not tops <= set(self.writable_dirs):
                allowed = ", ".join(f"{d}/" for d in self.writable_dirs)
                raise ToolError(
                    f"{path!r} is read-only in this session: the store must not be modified "
                    f"while answering questions; only files under {allowed} may be written"
                )
        return full

    def rel(self, p: Path) -> str:
        """The workspace-relative POSIX path of ``p`` ('.' for the root)."""
        r = p.relative_to(self.root).as_posix()
        return r or "."


# ====================================================================== toolbox
class Toolbox:
    """Dispatches tool calls by name and keeps per-tool call counts in :attr:`counts`."""

    def __init__(self, workspace: Workspace):
        self.ws = workspace
        self.counts: Counter[str] = Counter()
        self._doc_cache: dict[tuple[str, float, int], str] = {}

    # ---------------------------------------------------------------- dispatch
    def call(self, name: str, args: Any) -> ToolOutput:
        """Run tool ``name`` with ``args`` (a dict). Never raises for model mistakes."""
        self.counts[name] += 1
        if name not in TOOL_NAMES:
            return ToolOutput(
                f"unknown tool {name!r}; available tools: {', '.join(TOOL_NAMES)}", True
            )
        if name == FINISH:
            return ToolOutput("finished")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return ToolOutput(f"arguments for {name} must be a JSON object", True)
        spec = next(s for s in TOOL_SPECS if s["name"] == name)
        try:
            kwargs = _coerce_args(name, spec["parameters"], args)
            return ToolOutput(getattr(self, name)(**kwargs))
        except ToolError as e:
            return ToolOutput(f"error: {e}", True)
        except PermissionError as e:
            return ToolOutput(f"error: permission denied: {e.filename or e}", True)
        except OSError as e:
            where = f" ({e.filename})" if e.filename else ""
            return ToolOutput(f"error: {e.strerror or e}{where}", True)
        except Exception as e:  # a harness bug must not end the session; report it instead
            return ToolOutput(f"error: {name} failed unexpectedly: {type(e).__name__}: {e}", True)

    # ---------------------------------------------------------------- read tools
    def list_files(self, path: str = ".", recursive: bool = False) -> str:
        d = self.ws.resolve(path)
        if not d.exists():
            raise ToolError(f"{path!r} does not exist")
        if not d.is_dir():
            raise ToolError(f"{path!r} is a file, not a directory; use read_file to read it")
        lines: list[str] = []
        total = 0
        for p in self._walk(d, recursive):
            total += 1
            if len(lines) < MAX_LIST_ENTRIES:
                lines.append(_describe(self.ws.rel(p), p))
        if not lines:
            return f"{self.ws.rel(d)}/ is empty"
        if total > len(lines):
            lines.append(
                f"[... {total - len(lines)} more entries not shown; list a subdirectory instead]"
            )
        return "\n".join(lines)

    def read_file(self, path: str, offset: int = 0, limit: int = DEFAULT_READ_LIMIT) -> str:
        f = self._existing_file(path)
        if f.suffix.lower() in BINARY_SUFFIXES or _looks_binary(f):
            hint = (
                "use read_document"
                if f.suffix.lower() in DOCUMENT_SUFFIXES
                else "it cannot be read as text"
            )
            raise ToolError(f"{path!r} is a binary file; {hint}")
        text = f.read_text(encoding="utf-8", errors="replace")
        return _window(self.ws.rel(f), text, offset, limit, tool="read_file")

    def read_document(self, path: str, offset: int = 0, limit: int = DEFAULT_READ_LIMIT) -> str:
        f = self._existing_file(path)
        return _window(self.ws.rel(f), self._document_text(f), offset, limit, tool="read_document")

    def search(
        self, pattern: str, path: str = ".", regex: bool = True, ignore_case: bool = True
    ) -> str:
        if not pattern:
            raise ToolError("pattern must not be empty")
        flags = re.IGNORECASE if ignore_case else 0
        try:
            rx = re.compile(pattern if regex else re.escape(pattern), flags)
        except re.error as e:
            raise ToolError(
                f"invalid regular expression {pattern!r}: {e}; pass regex=false to search for "
                "the literal text"
            ) from e
        base = self.ws.resolve(path)
        if not base.exists():
            raise ToolError(f"{path!r} does not exist")
        files = [base] if base.is_file() else [p for p in self._walk(base, True) if p.is_file()]
        out: list[str] = []
        total = 0
        for f in files:
            if f.is_symlink() or f.stat().st_size > MAX_SEARCH_FILE_BYTES:
                continue
            text = self._searchable_text(f)
            if text is None:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    total += 1
                    if len(out) < MAX_SEARCH_MATCHES:
                        shown = line.strip()
                        if len(shown) > MAX_SEARCH_LINE_CHARS:
                            shown = shown[:MAX_SEARCH_LINE_CHARS] + " [...]"
                        out.append(f"{self.ws.rel(f)}:{n}: {shown}")
        if not out:
            return f"no matches for {pattern!r} under {self.ws.rel(base)}"
        if total > len(out):
            out.append(
                f"[... {total - len(out)} more matches not shown; use a narrower pattern or path]"
            )
        return "\n".join(out)

    # ---------------------------------------------------------------- write tools
    def write_file(self, path: str, content: str) -> str:
        f = self.ws.resolve(path, write=True)
        if f.is_dir():
            raise ToolError(f"{path!r} is a directory")
        data = content.encode("utf-8")
        if len(data) > MAX_WRITE_BYTES:
            raise ToolError(f"content is too large ({len(data)} bytes; limit {MAX_WRITE_BYTES})")
        existed = f.exists()
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        verb = "overwrote" if existed else "created"
        return f"{verb} {self.ws.rel(f)} ({content.count(chr(10)) + 1} lines, {len(data)} bytes)"

    def edit_file(self, path: str, old: str, new: str) -> str:
        f = self.ws.resolve(path, write=True)
        if not f.is_file():
            raise ToolError(f"{path!r} does not exist or is not a file")
        if old == "":
            raise ToolError("`old` must not be empty; use write_file to create or replace a file")
        text = f.read_text(encoding="utf-8", errors="replace")
        n = text.count(old)
        if n == 0:
            raise ToolError(
                f"`old` was not found in {path!r}; read the file again and copy the exact text, "
                "including whitespace and line breaks"
            )
        if n > 1:
            raise ToolError(
                f"`old` occurs {n} times in {path!r}; include more surrounding text so it matches "
                "exactly once"
            )
        f.write_text(text.replace(old, new, 1), encoding="utf-8")
        return f"edited {self.ws.rel(f)}"

    def delete_file(self, path: str) -> str:
        f = self.ws.resolve(path, write=True)
        if f.is_symlink() or f.is_file():
            f.unlink()
            return f"deleted {self.ws.rel(f)}"
        if f.is_dir():
            if any(f.iterdir()):
                raise ToolError(
                    f"{path!r} is a directory that is not empty; delete its files first"
                )
            f.rmdir()
            return f"deleted empty directory {self.ws.rel(f)}"
        raise ToolError(f"{path!r} does not exist")

    def move_file(self, src: str, dst: str) -> str:
        s = self.ws.resolve(src, write=True)
        d = self.ws.resolve(dst, write=True)
        if not (s.exists() or s.is_symlink()):
            raise ToolError(f"{src!r} does not exist")
        if d.exists() or d.is_symlink():
            raise ToolError(f"{dst!r} already exists; delete it first or choose another name")
        if s.is_dir() and (d == s or s in d.parents):
            raise ToolError(f"cannot move {src!r} into itself")
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(s), str(d))
        return f"moved {self.ws.rel(s)} -> {self.ws.rel(d)}"

    # ---------------------------------------------------------------- helpers
    def _existing_file(self, path: str) -> Path:
        f = self.ws.resolve(path)
        if not f.exists():
            raise ToolError(f"{path!r} does not exist; use list_files to see what is there")
        if f.is_dir():
            raise ToolError(f"{path!r} is a directory; use list_files")
        return f

    def _walk(self, d: Path, recursive: bool):
        """Entries under ``d`` in sorted order, skipping hidden top-level names.

        Symbolic links are listed but never followed.
        """
        try:
            entries = sorted(d.iterdir(), key=lambda p: p.name)
        except OSError as e:
            raise ToolError(f"cannot list {self.ws.rel(d)}: {e.strerror or e}") from e
        for p in entries:
            if p.parent == self.ws.root and p.name in HIDDEN:
                continue
            yield p
            if recursive and p.is_dir() and not p.is_symlink():
                yield from self._walk(p, True)

    def _document_text(self, f: Path) -> str:
        st = f.stat()
        key = (str(f), st.st_mtime, st.st_size)
        if key not in self._doc_cache:
            try:
                self._doc_cache[key] = extract_text(f)
            except DocumentError as e:
                raise ToolError(str(e)) from e
            except Exception as e:  # malformed documents must not end the session
                raise ToolError(f"could not extract text from {f.name}: {e}") from e
        return self._doc_cache[key]

    def _searchable_text(self, f: Path) -> str | None:
        suffix = f.suffix.lower()
        if suffix in OFFICE_SUFFIXES or suffix == ".pdf":
            try:
                return self._document_text(f)
            except ToolError:
                return None
        if suffix in BINARY_SUFFIXES or _looks_binary(f):
            return None
        try:
            return f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


# ====================================================================== module helpers
def _coerce_args(name: str, schema: dict, args: dict) -> dict:
    """Check required arguments and types, coercing common model slips ("10" -> 10)."""
    props: dict = schema.get("properties", {})
    missing = [k for k in schema.get("required", []) if k not in args or args[k] is None]
    if missing:
        unknown = sorted(set(args) - set(props))
        got = f" (got unexpected: {', '.join(unknown)})" if unknown else ""
        raise ToolError(f"{name} requires argument(s): {', '.join(missing)}{got}")
    out = {}
    for k, v in args.items():
        if k not in props or v is None:
            continue  # unknown or null arguments are ignored
        kind = props[k].get("type")
        if kind == "integer":
            if isinstance(v, bool) or not isinstance(v, (int, float, str)):
                raise ToolError(f"{name}: argument {k!r} must be an integer")
            try:
                v = int(v)
            except ValueError as e:
                raise ToolError(f"{name}: argument {k!r} must be an integer, got {v!r}") from e
        elif kind == "boolean":
            if isinstance(v, str) and v.lower() in ("true", "false"):
                v = v.lower() == "true"
            elif not isinstance(v, bool):
                raise ToolError(f"{name}: argument {k!r} must be true or false")
        elif kind == "string" and not isinstance(v, str):
            if isinstance(v, (int, float)):
                v = str(v)
            else:
                raise ToolError(f"{name}: argument {k!r} must be a string")
        out[k] = v
    return out


def _describe(rel: str, p: Path) -> str:
    if p.is_symlink():
        return f"{rel} (symbolic link)"
    if p.is_dir():
        return f"{rel}/"
    try:
        return f"{rel}  ({p.stat().st_size} bytes)"
    except OSError:
        return rel


def _looks_binary(f: Path) -> bool:
    try:
        with open(f, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return False


def _window(rel: str, text: str, offset: int, limit: int, *, tool: str) -> str:
    if offset < 0:
        raise ToolError("offset must be 0 or more")
    if limit < 1:
        raise ToolError("limit must be 1 or more")
    limit = min(limit, MAX_READ_LIMIT)
    lines = text.splitlines()
    n = len(lines)
    if n == 0:
        return f"[{rel}: empty]"
    if offset >= n:
        raise ToolError(f"offset {offset} is past the end of {rel!r}, which has {n} lines")
    chunk = lines[offset : offset + limit]
    body = [
        line if len(line) <= MAX_LINE_CHARS else line[:MAX_LINE_CHARS] + " [line truncated]"
        for line in chunk
    ]
    end = offset + len(chunk)
    head = f"[{rel}: lines {offset + 1}-{end} of {n}]"
    tail = []
    if end < n:
        tail = [f"[... {n - end} more lines; call {tool} with offset={end} to continue]"]
    return "\n".join([head, *body, *tail])
