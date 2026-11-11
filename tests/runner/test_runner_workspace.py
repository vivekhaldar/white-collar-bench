"""Workspace file operations: deleting, normalizing, snapshotting and comparing stores."""

from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
from pathlib import Path

import pytest

from wcb.runner import workspace
from wcb.runner.workspace import normalize_tree, remove_tree, snapshot, tree_diff, tree_files

NOT_ROOT = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")


def make_store(root: Path) -> Path:
    (root / "people").mkdir(parents=True)
    (root / "people" / "me.md").write_text("me\n")
    (root / "notes").mkdir()
    (root / "notes" / "a.md").write_text("a\n")
    return root


# ---------------------------------------------------------------- remove_tree
def test_remove_tree_removes_special_files_named_like_directories(tmp_path):
    os.mkfifo(tmp_path / "inbox")
    remove_tree(tmp_path / "inbox")
    assert not os.path.lexists(tmp_path / "inbox")
    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.bind(str(tmp_path / ".wcb"))
        remove_tree(tmp_path / ".wcb")
    finally:
        sock.close()
    assert not os.path.lexists(tmp_path / ".wcb")
    remove_tree(tmp_path / "missing")  # nothing to do


def test_remove_tree_unlinks_a_link_without_following_it(tmp_path):
    target = make_store(tmp_path / "outside")
    (tmp_path / "link").symlink_to(target, target_is_directory=True)
    remove_tree(tmp_path / "link")
    assert not os.path.lexists(tmp_path / "link") and (target / "people" / "me.md").is_file()


@NOT_ROOT
def test_remove_tree_handles_unreadable_directories(tmp_path):
    store = make_store(tmp_path / "s")
    os.chmod(store / "notes" / "a.md", 0)
    os.chmod(store / "notes", 0)
    remove_tree(store)
    assert not store.exists()


# ---------------------------------------------------------------- normalize_tree
@NOT_ROOT
def test_normalize_tree_restores_permissions_and_deletes_special_files(tmp_path):
    store = make_store(tmp_path / "s")
    outside = tmp_path / "outside.md"
    outside.write_text("x\n")
    os.chmod(outside, 0)
    (store / "notes" / "link.md").symlink_to(outside)
    os.mkfifo(store / "notes" / "pipe")
    (store / "private").mkdir()
    (store / "private" / "b.md").write_text("b\n")
    os.chmod(store / "private" / "b.md", 0)
    os.chmod(store / "private", 0)
    os.chmod(store / "people" / "me.md", 0)

    assert normalize_tree(store) == ["notes/pipe"]
    assert (store / "people" / "me.md").read_text() == "me\n"
    assert (store / "private" / "b.md").read_text() == "b\n"
    assert stat.S_IMODE(os.stat(store / "private").st_mode) & 0o700 == 0o700
    assert stat.S_IMODE(os.stat(outside).st_mode) == 0  # links are never followed
    assert not os.path.lexists(store / "notes" / "pipe")
    # the store can now be snapshotted
    snapshot(store, tmp_path / "snap")
    assert "private/b.md" in tree_files(tmp_path / "snap")


def test_normalize_tree_on_a_missing_path_does_nothing(tmp_path):
    assert normalize_tree(tmp_path / "missing") == []


# ---------------------------------------------------------------- snapshot
def test_failed_snapshot_leaves_no_partial_copy(tmp_path, monkeypatch):
    store = make_store(tmp_path / "s")

    def broken_copy(src, dst, exclude=()):
        (Path(dst) / "half.md").write_text("half\n")
        raise shutil.Error([(str(src), str(dst), "Permission denied")])

    monkeypatch.setattr(workspace, "copy_tree", broken_copy)
    with pytest.raises(shutil.Error):
        snapshot(store, tmp_path / "snaps" / "2027-01-06")
    assert list((tmp_path / "snaps").iterdir()) == []


# ---------------------------------------------------------------- tree_diff
def test_tree_diff_reports_changed_added_and_removed_entries(tmp_path):
    a = make_store(tmp_path / "a")
    (a / "notes" / "l").symlink_to("a.md")
    b = tmp_path / "b"
    shutil.copytree(a, b, symlinks=True)
    for d in (".git", "inbox", ".wcb"):
        (b / d).mkdir()
        (b / d / "x").write_text("ignored by default\n")
    assert tree_diff(a, b) == []

    (b / "notes" / "a.md").write_text("A\n")  # same size, different content
    (b / "notes" / "new.md").write_text("new\n")
    (b / "people" / "me.md").unlink()
    (b / "notes" / "l").unlink()
    (b / "notes" / "l").symlink_to("new.md")
    assert tree_diff(a, b) == ["notes/a.md", "notes/l", "notes/new.md", "people/me.md"]
    assert tree_diff(a, b, exclude=(".git",)) == [
        ".wcb", ".wcb/x", "inbox", "inbox/x", "notes/a.md", "notes/l", "notes/new.md",
        "people/me.md",
    ]  # fmt: skip


def _rewrite_keeping_times(path: Path, data: bytes) -> None:
    st = path.stat()
    path.write_bytes(data)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns))


def test_tree_diff_sees_a_same_size_change_with_restored_mtime(tmp_path):
    """Issue #5: filecmp cached deep comparisons by stat signature and missed this change."""
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    x, y = a / "x.md", b / "x.md"
    x.write_bytes(b"aaa")
    y.write_bytes(b"aaa")
    assert tree_diff(a, b) == []  # an equal comparison first
    _rewrite_keeping_times(y, b"bbb")
    assert x.read_bytes() != y.read_bytes() and x.stat().st_size == y.stat().st_size
    assert tree_diff(a, b) == ["x.md"]
    # A stale inequality is not kept either: change it back, then again, keeping the times.
    _rewrite_keeping_times(y, b"aaa")
    assert tree_diff(a, b) == []
    _rewrite_keeping_times(y, b"ccc")
    assert tree_diff(a, b) == ["x.md"]


def test_tree_diff_ignores_modes_and_times_and_compares_large_files(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    big = os.urandom(200_000)
    (a / "big.bin").write_bytes(big)
    (b / "big.bin").write_bytes(big)
    os.chmod(b / "big.bin", 0o600)
    os.utime(b / "big.bin", (0, 0))
    assert tree_diff(a, b) == []
    (b / "big.bin").write_bytes(big[:-1] + bytes([big[-1] ^ 1]))  # last byte, last chunk
    assert tree_diff(a, b) == ["big.bin"]


def test_tree_diff_skips_special_files_and_never_follows_links(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    os.mkfifo(b / "pipe")  # special files are not store data
    (tmp_path / "t1").write_text("one\n")
    (tmp_path / "t2").write_text("two\n")
    (a / "l").symlink_to(tmp_path / "t1")
    (b / "l").symlink_to(tmp_path / "t1")
    assert tree_diff(a, b) == []
    (tmp_path / "t1").write_text("ONE\n")  # the link target's content is not compared
    assert tree_diff(a, b) == []
    (b / "l").unlink()
    (b / "l").symlink_to(tmp_path / "t2")
    assert tree_diff(a, b) == ["l"]
    (b / "l").unlink()
    (b / "l").write_text("one\n")  # a file where there was a link
    assert tree_diff(a, b) == ["l"]


# ---------------------------------------------------------------- git safety
needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@needs_git
def test_git_ignores_filters_and_worktree_an_agent_writes_into_git_config(tmp_path):
    """The runner's `git add` runs on the host; an agent's .git/config must not run code there."""
    ws = tmp_path / "ws"
    ws.mkdir()
    g = workspace.Git(ws)
    assert g.init() and g.commit("seed")
    marker = tmp_path / "PWNED"
    with (ws / ".git" / "config").open("a") as f:
        f.write(f'[filter "x"]\n\tclean = "touch {marker} && cat"\n'
                f"[core]\n\tworktree = {tmp_path / 'elsewhere'}\n")
    (ws / ".gitattributes").write_text("* filter=x\n")
    (ws / ".git" / "info").mkdir(exist_ok=True)
    (ws / ".git" / "info" / "attributes").write_text("* filter=x\n")
    (ws / "note.md").write_text("hello\n")
    assert g.commit("day 1"), g.error
    assert not marker.exists()
    assert not (ws / ".git" / "info" / "attributes").exists()
    assert "filter" not in (ws / ".git" / "config").read_text()
    assert any("config was changed" in n for n in g.notes)


@needs_git
def test_git_replaces_a_git_dir_that_is_a_link(tmp_path):
    ws, elsewhere = tmp_path / "ws", tmp_path / "host-repo"
    ws.mkdir()
    elsewhere.mkdir()
    os.symlink(elsewhere, ws / ".git")
    (ws / "note.md").write_text("hello\n")
    g = workspace.Git(ws)
    assert g.commit("day 1"), g.error
    assert list(elsewhere.iterdir()) == []
    assert (ws / ".git").is_dir() and not (ws / ".git").is_symlink()
    assert any("not a directory" in n for n in g.notes)


@needs_git
def test_git_init_on_a_fresh_workspace_reports_nothing(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    g = workspace.Git(ws)
    assert g.init() and g.commit("seed") and g.commit("again")
    assert g.notes == []


def _traced(monkeypatch, trace: Path) -> None:
    """Make the runner's git commands write GIT_TRACE output (Git._run drops GIT_* variables)."""
    real = subprocess.run

    def run(cmd, *args, env=None, **kwargs):
        return real(cmd, *args, env={**(env or os.environ), "GIT_TRACE": str(trace)}, **kwargs)

    monkeypatch.setattr(workspace.subprocess, "run", run)


def _plain_git_env(**extra: str) -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return {**base, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, **extra}


@needs_git
def test_git_commits_do_not_start_automatic_maintenance(tmp_path, monkeypatch):
    """Issue #6: `git commit` runs `git maintenance run --auto` (detached in recent git), which
    can repack .git while the runner copies the workspace for a query session."""
    # Control: plain git with no settings does start it, so this test is not vacuous.
    plain, trace0 = tmp_path / "plain", tmp_path / "plain.trace"
    plain.mkdir()
    env = _plain_git_env(GIT_TRACE=str(trace0))
    ident = ["-c", "user.name=t", "-c", "user.email=t@t.example"]
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "x"]):
        subprocess.run(["git", *ident, *args], cwd=plain, env=env, check=True)
    control = trace0.read_text()
    if "maintenance run --auto" not in control and "gc --auto" not in control:
        pytest.skip("this git does not run automatic maintenance after a commit")

    ws, trace = tmp_path / "ws", tmp_path / "runner.trace"
    ws.mkdir()
    _traced(monkeypatch, trace)
    g = workspace.Git(ws)
    (ws / "note.md").write_text("hello\n")
    assert g.init() and g.commit("seed") and g.commit("again"), g.error
    text = trace.read_text()
    assert "built-in: git commit" in text  # tracing worked
    assert "maintenance" not in text and "gc --auto" not in text
    assert g.notes == []


@needs_git
def test_git_config_disables_automatic_maintenance_even_after_an_agent_edit(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    g = workspace.Git(ws)
    assert g.init() and g.commit("seed")
    with (ws / ".git" / "config").open("a") as f:
        f.write("[maintenance]\n\tauto = true\n[gc]\n\tauto = 1\n")
    assert g.commit("day 1"), g.error
    assert any("config was changed" in n for n in g.notes)

    def get(key: str) -> str:
        cmd = ["git", "--git-dir", str(ws / ".git"), "config", "--get", key]
        p = subprocess.run(cmd, env=_plain_git_env(), capture_output=True, text=True, check=True)
        return p.stdout.strip()

    got = [get("maintenance.auto"), get("gc.auto"), get("gc.autoDetach")]
    assert got == ["false", "0", "false"]


@needs_git
def test_git_config_from_an_earlier_runner_is_not_reported(tmp_path):
    """A workspace kept for --resume across a runner upgrade has the earlier runner config."""
    ws = tmp_path / "ws"
    ws.mkdir()
    g = workspace.Git(ws)
    assert g.init()
    (ws / ".git" / "config").write_text(workspace._GIT_CONFIG_EARLIER[0] + "\n")
    assert g.commit("seed"), g.error
    assert g.notes == []
    assert (ws / ".git" / "config").read_text() == workspace._GIT_CONFIG
