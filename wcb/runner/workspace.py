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
"""

from __future__ import annotations

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
    """Delete a file or directory tree, even if the agent removed write permissions."""
    path = Path(path)
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except OSError:
        _make_tree_writable(path)
        shutil.rmtree(path)


def clear_dir(path: Path, keep: Iterable[str] = ()) -> None:
    """Delete every top-level entry of ``path`` except the names in ``keep``."""
    kept = set(keep)
    for entry in Path(path).iterdir():
        if entry.name not in kept:
            remove_tree(entry)


def _make_tree_writable(top: Path) -> None:
    """Give the owner rwx on every directory under ``top`` (symlinks are not followed)."""
    if top.is_symlink():
        return
    try:
        os.chmod(top, os.stat(top).st_mode | stat.S_IRWXU)
    except OSError:
        pass
    for root, dirs, _files in os.walk(top):
        for d in dirs:
            full = os.path.join(root, d)
            if not os.path.islink(full):
                try:
                    os.chmod(full, os.stat(full).st_mode | stat.S_IRWXU)
                except OSError:
                    pass


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
    copy_tree(workspace, partial, exclude=SNAPSHOT_EXCLUDE)
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
class Git:
    """Minimal git bookkeeping for a workspace: init, local identity, commit.

    Git history is a convenience for agents and for people inspecting a run; snapshots, not git,
    are the source of truth. Every git failure is therefore non-fatal: methods return ``False`` and
    :attr:`error` keeps the first problem so the runner can report it once and carry on.

    Commands run with hooks and fsmonitor disabled and without the user's global or system git
    config, so content an agent writes into ``.git/`` cannot make the runner execute code.
    """

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.enabled = shutil.which("git") is not None
        self.error: str | None = None if self.enabled else "git is not installed"

    def _run(self, *args: str) -> bool:
        if not self.enabled:
            return False
        sub = next((a for a in args if not a.startswith("-") and "=" not in a), "?")
        env = {
            **os.environ,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        cmd = [
            "git",
            "-c", "core.hooksPath=" + os.devnull,
            "-c", "core.fsmonitor=false",
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

    def init(self) -> bool:
        """Create the repository if needed and set a local user name and email."""
        if not self.enabled:
            return False
        if not (self.workspace / ".git").exists() and not self._run("init", "-q"):
            return False
        return self._run("config", "user.name", GIT_USER_NAME) and self._run(
            "config", "user.email", GIT_USER_EMAIL
        )

    def commit(self, message: str) -> bool:
        """Stage everything and commit (an empty commit if nothing changed)."""
        if not self.enabled:
            return False
        if not (self.workspace / ".git").is_dir() and not self.init():
            return False
        identity = ("-c", f"user.name={GIT_USER_NAME}", "-c", f"user.email={GIT_USER_EMAIL}")
        return self._run("add", "-A") and self._run(
            *identity, "commit", "-q", "--no-verify", "--allow-empty", "-m", message
        )
