"""Workspace and snapshot file operations for the episode runner.

A **workspace** is the directory an agent works in: the store plus, during a session, ``inbox/``
(ingestion) or ``.wcb/`` (queries and usage reports). Workspaces live outside the run directory
and the repository (by default in the system temp directory), so an agent that looks around with
``..`` finds neither gold nor earlier results.

A **snapshot** is a plain copy of the store at the end of an ingestion day, written to
``<run>/<world>/r<k>/snapshots/<date>/``. Snapshots exclude ``.git``, ``inbox/`` and ``.wcb/``.
They are what the store grader reads, and they are how the runner restores a store after a failed
session or rebuilds a workspace on ``--resume``.

Copies preserve symbolic links as links (they are never followed) and skip special files such as
FIFOs and sockets, so an agent cannot make the runner hang or read files outside the workspace.
After every session the runner calls :func:`normalize_tree`, which undoes permission changes and
deletes special files, so nothing an agent leaves behind can stop the runner from copying or
deleting the store.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

SNAPSHOT_EXCLUDE = (".git", "inbox", ".wcb")
"""Top-level workspace entries that are never part of a snapshot or of the final store."""

WORKSPACE_PREFIX = "wcb-ws-"
QUERY_PREFIX = "wcb-q-"

GIT_USER_NAME = "wcb runner"
GIT_USER_EMAIL = "runner@wcb.example"


# ---------------------------------------------------------------- directories
def new_temp_dir(root: Path | None, prefix: str = WORKSPACE_PREFIX) -> Path:
    """Create a fresh, empty directory under ``root`` (default: the system temp directory)."""
    if root is not None:
        root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(root) if root else None)).resolve()


def is_within(path: Path, parent: Path) -> bool:
    """True if ``path`` is ``parent`` or inside it (after resolving symlinks)."""
    p, q = Path(path).resolve(), Path(parent).resolve()
    return p == q or q in p.parents


def copy_tree(src: Path, dst: Path, exclude: Iterable[str] = ()) -> None:
    """Copy the contents of ``src`` into ``dst`` (created if needed; existing files are kept).

    ``exclude`` names top-level entries of ``src`` to skip. Symbolic links are copied as links;
    FIFOs, sockets and device files are skipped.
    """
    src, dst = Path(src), Path(dst)
    if not src.is_dir():
        raise FileNotFoundError(f"cannot copy {src}: not a directory")
    top = os.path.normpath(str(src))
    excluded = set(exclude)

    def ignore(directory: str, names: list[str]) -> set[str]:
        skip = set()
        at_top = os.path.normpath(directory) == top
        for n in names:
            if at_top and n in excluded:
                skip.add(n)
                continue
            try:
                mode = os.lstat(os.path.join(directory, n)).st_mode
            except OSError:
                skip.add(n)
                continue
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode) or stat.S_ISLNK(mode)):
                skip.add(n)
        return skip

    shutil.copytree(src, dst, symlinks=True, ignore=ignore, dirs_exist_ok=True)


def remove_tree(path: Path) -> None:
    """Delete a file, link, special file or directory tree, even if the agent removed permissions.

    Anything that is not a directory (checked without following links) is unlinked, so a FIFO or
    socket named like a directory is removed too.
    """
    path = Path(path)
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(st.st_mode):
        try:
            os.unlink(path)
        except OSError:
            _clear_flags(str(path), st)
            os.unlink(path)
        return
    try:
        shutil.rmtree(path)
    except OSError:
        normalize_tree(path)
        shutil.rmtree(path)


def clear_dir(path: Path, keep: Iterable[str] = ()) -> None:
    """Delete every top-level entry of ``path`` except the names in ``keep``."""
    kept = set(keep)
    for entry in Path(path).iterdir():
        if entry.name not in kept:
            remove_tree(entry)


def normalize_tree(top: Path) -> list[str]:
    """Make everything under ``top`` readable and deletable by the runner.

    Directories get owner ``rwx`` and regular files owner ``r``; BSD file flags such as macOS's
    ``uchg`` are cleared; FIFOs, sockets and device files are deleted. Symbolic links are left
    alone and never followed. Returns the relative paths of the deleted special files.
    """
    top_s = str(top)
    removed: list[str] = []
    try:
        st = os.lstat(top_s)
    except OSError:
        return removed
    if not stat.S_ISDIR(st.st_mode):
        return removed
    _add_mode(top_s, st, stat.S_IRWXU)
    stack = [top_s]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                entries = [e.path for e in it]
        except OSError:
            continue
        for full in entries:
            try:
                st = os.lstat(full)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                continue
            if stat.S_ISDIR(st.st_mode):
                _add_mode(full, st, stat.S_IRWXU)
                stack.append(full)
            elif stat.S_ISREG(st.st_mode):
                _add_mode(full, st, stat.S_IRUSR)
            else:
                try:
                    os.unlink(full)
                except OSError:
                    continue
                removed.append(os.path.relpath(full, top_s).replace(os.sep, "/"))
    return sorted(removed)


def _add_mode(path: str, st: os.stat_result, bits: int) -> None:
    _clear_flags(path, st)
    if st.st_mode & bits != bits:
        with contextlib.suppress(OSError):
            os.chmod(path, stat.S_IMODE(st.st_mode) | bits)


def _clear_flags(path: str, st: os.stat_result) -> None:
    """Clear BSD file flags (immutable, append-only, ...) where the platform has them."""
    if getattr(st, "st_flags", 0) and hasattr(os, "chflags"):
        with contextlib.suppress(OSError):
            os.chflags(path, 0, follow_symlinks=False)


# ---------------------------------------------------------------- snapshots
def snapshot(workspace: Path, dest: Path) -> None:
    """Write the store in ``workspace`` to ``dest``, replacing any previous snapshot there.

    The copy is written next to ``dest`` and renamed into place, so an interrupted run never
    leaves a half-written snapshot under the final name.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.parent / f".{dest.name}.partial"
    remove_tree(partial)
    partial.mkdir()
    try:
        copy_tree(workspace, partial, exclude=SNAPSHOT_EXCLUDE)
    except BaseException:
        with contextlib.suppress(OSError):
            remove_tree(partial)
        raise
    remove_tree(dest)
    partial.rename(dest)


def restore(workspace: Path, snapshot_dir: Path) -> None:
    """Reset the store in ``workspace`` to ``snapshot_dir``. ``.git`` is kept as it is."""
    clear_dir(workspace, keep=(".git",))
    copy_tree(snapshot_dir, workspace)


def make_read_only(root: Path, keep: Iterable[str] = (".wcb",)) -> None:
    """Remove write permission from every regular file under ``root``.

    Top-level entries named in ``keep`` stay writable. Directories stay writable so the agent can
    still create scratch files; the runner discards the whole copy after a query session anyway.
    """
    kept = set(keep)
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.normpath(dirpath) == os.path.normpath(str(root)):
            dirnames[:] = [d for d in dirnames if d not in kept]
            filenames = [f for f in filenames if f not in kept]
        for f in filenames:
            full = os.path.join(dirpath, f)
            if os.path.islink(full):
                continue
            try:
                mode = os.stat(full).st_mode
                os.chmod(full, mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            except OSError:
                pass


def tree_diff(a: Path, b: Path, exclude: Iterable[str] = SNAPSHOT_EXCLUDE) -> list[str]:
    """Sorted relative paths that differ between the trees ``a`` and ``b``.

    Compares entry types, regular-file contents and link targets; ignores modes, timestamps,
    special files and the top-level names in ``exclude``. An empty list means the same store.
    """
    ea, eb = _entries(Path(a), exclude), _entries(Path(b), exclude)
    out = set(ea) ^ set(eb)
    for rel in set(ea) & set(eb):
        if ea[rel] != eb[rel]:
            out.add(rel)
        elif ea[rel][0] == "file" and not _same_bytes(Path(a) / rel, Path(b) / rel):
            out.add(rel)
    return sorted(out)


_CHUNK = 1 << 16


def _same_bytes(p: Path, q: Path) -> bool:
    """True if the regular files ``p`` and ``q`` hold the same bytes right now.

    Reads both files on every call. Unlike :func:`filecmp.cmp`, nothing is cached, so a change
    that keeps the size and modification time is still seen. Links are not followed and only
    regular files are read (a file swapped for a link or FIFO since it was listed counts as
    different); any error counts as different.
    """
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fa = os.open(p, flags)
    except OSError:
        return False
    try:
        fb = os.open(q, flags)
    except OSError:
        os.close(fa)
        return False
    try:
        with os.fdopen(fa, "rb") as x, os.fdopen(fb, "rb") as y:
            if not (stat.S_ISREG(os.fstat(fa).st_mode) and stat.S_ISREG(os.fstat(fb).st_mode)):
                return False
            while True:
                ca, cb = x.read(_CHUNK), y.read(_CHUNK)
                if ca != cb:
                    return False
                if not ca:
                    return True
    except OSError:
        return False


def _entries(root: Path, exclude: Iterable[str]) -> dict[str, tuple]:
    """Relative path -> ('dir',) | ('file', size) | ('link', target) for a tree (links not followed)."""
    excluded = set(exclude)
    top = os.path.normpath(str(root))
    out: dict[str, tuple] = {}
    for dirpath, dirnames, filenames in os.walk(top):
        if os.path.normpath(dirpath) == top:
            dirnames[:] = [d for d in dirnames if d not in excluded]
            filenames = [f for f in filenames if f not in excluded]
        for name in (*dirnames, *filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, top).replace(os.sep, "/")
            try:
                st = os.lstat(full)
                if stat.S_ISLNK(st.st_mode):
                    out[rel] = ("link", os.readlink(full))
                elif stat.S_ISDIR(st.st_mode):
                    out[rel] = ("dir",)
                elif stat.S_ISREG(st.st_mode):
                    out[rel] = ("file", st.st_size)
            except OSError:
                out[rel] = ("unreadable",)
    return out


def tree_files(root: Path, exclude: Iterable[str] = SNAPSHOT_EXCLUDE) -> list[str]:
    """Sorted relative paths of the files under ``root`` (handy for logs and tests)."""
    root = Path(root)
    excluded = set(exclude)
    out = []
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if rel.parts[0] in excluded or p.is_dir():
            continue
        out.append(rel.as_posix())
    return sorted(out)


# ---------------------------------------------------------------- git
#: The only `.git/config` the runner's git commands ever read.
_GIT_CONFIG = f"""[core]
\trepositoryformatversion = 0
\tfilemode = true
\tbare = false
\tlogallrefupdates = true
[user]
\tname = {GIT_USER_NAME}
\temail = {GIT_USER_EMAIL}
"""
#: What `git init` writes, so replacing it right after init is not reported as a change.
_GIT_CONFIG_BARE_INIT = (
    "[core]\n\trepositoryformatversion = 0\n\tfilemode = true\n\tbare = false\n"
    "\tlogallrefupdates = true"
)
#: Files in `.git` that make git read or write elsewhere, or apply attributes (filters).
_GIT_DROP = (
    "info/attributes",
    "objects/info/alternates",
    "objects/info/http-alternates",
    "commondir",
    "config.worktree",
)


class Git:
    """Minimal git bookkeeping for a workspace: init, local identity, commit.

    Git history is a convenience for agents and for people inspecting a run; snapshots, not git,
    are the source of truth. Every git failure is therefore non-fatal: methods return ``False`` and
    :attr:`error` keeps the first problem so the runner can report it once and carry on.

    The runner's git commands run on the host, outside any container the agent is confined to,
    on a ``.git`` directory the agent can write. So before each command :meth:`_sanitize`
    replaces ``.git/config`` with the runner's own (dropping filters, ``core.worktree``,
    includes and anything else an agent added), removes files that point git elsewhere
    (alternates, ``commondir``, ``info/attributes``), and starts a new repository if ``.git``
    is a link, a file or contains links. Commands also run with hooks and fsmonitor disabled,
    without the user's global or system config, and with ``GIT_DIR`` and ``GIT_WORK_TREE``
    fixed to the workspace. Content an agent writes into ``.git/`` therefore cannot make the
    runner execute code or touch files outside the workspace. What was removed is recorded in
    :attr:`notes`.
    """

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.enabled = shutil.which("git") is not None
        self.error: str | None = None if self.enabled else "git is not installed"
        self.notes: list[str] = []

    def _run(self, *args: str) -> bool:
        if not self.enabled:
            return False
        sub = next((a for a in args if not a.startswith("-") and "=" not in a), "?")
        env = {
            **{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_DIR": str(self.workspace / ".git"),
            "GIT_WORK_TREE": str(self.workspace),
        }
        cmd = [
            "git",
            "-c", "core.hooksPath=" + os.devnull,
            "-c", "core.fsmonitor=false",
            "-c", "core.attributesFile=" + os.devnull,
            "-c", "commit.gpgsign=false",
            "-c", "init.defaultBranch=main",
            *args,
        ]  # fmt: skip
        try:
            p = subprocess.run(
                cmd,
                cwd=self.workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (OSError, subprocess.SubprocessError) as e:
            self._fail(f"git {sub}: {e}")
            return False
        if p.returncode != 0:
            self._fail(f"git {sub} exited {p.returncode}: {(p.stderr or p.stdout).strip()[:300]}")
            return False
        return True

    def _fail(self, msg: str) -> None:
        if self.error is None:
            self.error = msg

    def _sanitize(self) -> None:
        """Make ``.git`` safe for the runner's own git commands (see the class docstring)."""
        git = self.workspace / ".git"
        if git.is_symlink() or (git.exists() and not git.is_dir()):
            remove_tree(git)
            self.notes.append(".git was not a directory; started a new git repository")
            return
        if not git.is_dir():
            return
        for dirpath, dirnames, filenames in os.walk(git):
            if any(os.path.islink(os.path.join(dirpath, n)) for n in dirnames + filenames):
                remove_tree(git)
                self.notes.append(".git contained symbolic links; started a new git repository")
                return
        config = git / "config"
        try:
            old = config.read_text(encoding="utf-8", errors="replace")
        except OSError:
            old = None
        if old != _GIT_CONFIG:
            if old is not None and old.strip() != _GIT_CONFIG_BARE_INIT:
                self.notes.append(".git/config was changed; replaced it with the runner's")
            config.unlink(missing_ok=True)
            config.write_text(_GIT_CONFIG, encoding="utf-8")
        for rel in _GIT_DROP:
            p = git / rel
            if p.exists() or p.is_symlink():
                remove_tree(p)
                self.notes.append(f"removed .git/{rel}")

    def init(self) -> bool:
        """Create the repository if needed and set a local user name and email."""
        if not self.enabled:
            return False
        self._sanitize()
        if not (self.workspace / ".git").exists() and not self._run("init", "-q"):
            return False
        self._sanitize()  # writes the runner's config, which includes the identity
        return True

    def commit(self, message: str) -> bool:
        """Stage everything and commit (an empty commit if nothing changed)."""
        if not self.enabled:
            return False
        self._sanitize()
        if not (self.workspace / ".git").is_dir() and not self.init():
            return False
        identity = ("-c", f"user.name={GIT_USER_NAME}", "-c", f"user.email={GIT_USER_EMAIL}")
        return self._run("add", "-A") and self._run(
            *identity, "commit", "-q", "--no-verify", "--allow-empty", "-m", message
        )
