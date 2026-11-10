"""Workspace file operations: deleting, normalizing, snapshotting and comparing stores."""

from __future__ import annotations

import os
import shutil
import socket
import stat
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
