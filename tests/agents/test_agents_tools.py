"""Workspace sandbox and file tools (wcb.agents.tools)."""

from __future__ import annotations

import os

import pytest
from agents_office_files import make_docx, make_xlsx

from wcb.agents.tools import (
    MAX_SEARCH_MATCHES,
    TOOL_NAMES,
    TOOL_SPECS,
    Toolbox,
    ToolError,
    Workspace,
)


def tb(root, **kw) -> Toolbox:
    return Toolbox(Workspace(root, **kw))


# ---------------------------------------------------------------- sandbox
@pytest.mark.parametrize(
    "path",
    ["/etc/passwd", "~/secrets", "../outside.md", "people/../../x", "a/../b", "C:/x", "a\x00b"],
)
def test_escaping_paths_are_rejected(ws, path):
    with pytest.raises(ToolError):
        Workspace(ws).resolve(path)
    r = tb(ws).call("read_file", {"path": path})
    assert r.is_error


def test_symlinks_pointing_outside_are_rejected(ws, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("gold answer")
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "f.md").write_text("hidden")
    os.symlink(secret, ws / "link.txt")
    os.symlink(outside_dir, ws / "linkdir")
    t = tb(ws)
    for name, args in [
        ("read_file", {"path": "link.txt"}),
        ("read_document", {"path": "link.txt"}),
        ("read_file", {"path": "linkdir/f.md"}),
        ("list_files", {"path": "linkdir"}),
        ("write_file", {"path": "linkdir/new.md", "content": "x"}),
        ("write_file", {"path": "link.txt", "content": "overwritten"}),
        ("edit_file", {"path": "link.txt", "old": "gold", "new": "x"}),
        ("delete_file", {"path": "link.txt"}),
        ("move_file", {"src": "people/me.md", "dst": "linkdir/me.md"}),
        ("search", {"pattern": "hidden", "path": "linkdir"}),
    ]:
        r = t.call(name, args)
        assert r.is_error, (name, args, r.content)
        assert "outside the workspace" in r.content
    assert secret.read_text() == "gold answer"
    assert sorted(p.name for p in outside_dir.iterdir()) == ["f.md"]
    # A recursive search from the root does not follow the links either.
    assert "gold answer" not in t.call("search", {"pattern": "gold|hidden"}).content


def test_symlink_inside_workspace_is_allowed(ws):
    os.symlink(ws / "people" / "me.md", ws / "me-link.md")
    assert "Ada Quist" in tb(ws).call("read_file", {"path": "me-link.md"}).content


def test_git_is_hidden_and_protected(ws):
    t = tb(ws)
    assert ".git" not in t.call("list_files", {"recursive": True}).content
    assert t.call("search", {"pattern": "refs/heads"}).content.startswith("no matches")
    r = t.call("write_file", {"path": ".git/HEAD", "content": "x"})
    assert r.is_error and "managed by the runner" in r.content
    assert t.call("delete_file", {"path": ".git/HEAD"}).is_error
    assert (ws / ".git" / "HEAD").read_text().startswith("ref:")


def test_read_only_workspace_allows_only_wcb(ws):
    t = tb(ws, read_only=True)
    r = t.call("write_file", {"path": "people/me.md", "content": "changed"})
    assert r.is_error and "read-only" in r.content and ".wcb/" in r.content
    assert t.call("edit_file", {"path": "people/me.md", "old": "Ada", "new": "Bo"}).is_error
    assert t.call("delete_file", {"path": "people/me.md"}).is_error
    assert t.call("move_file", {"src": "people/me.md", "dst": ".wcb/me.md"}).is_error
    assert (ws / "people" / "me.md").read_text().endswith("Ada Quist\n")
    ok = t.call("write_file", {"path": ".wcb/answers.json", "content": "{}"})
    assert not ok.is_error and (ws / ".wcb" / "answers.json").read_text() == "{}"
    # A link inside .wcb/ that points into the store does not open a way around the rule.
    os.symlink(ws / "people", ws / ".wcb" / "people")
    assert t.call("write_file", {"path": ".wcb/people/x.md", "content": "x"}).is_error
    assert t.call("read_file", {"path": "people/me.md"}).is_error is False


# ---------------------------------------------------------------- tools
def test_tool_specs_are_well_formed():
    assert TOOL_NAMES == (
        "list_files", "read_file", "read_document", "write_file", "edit_file",
        "delete_file", "move_file", "search", "finish",
    )  # fmt: skip
    for spec in TOOL_SPECS:
        assert spec["description"] and spec["parameters"]["type"] == "object"
        assert set(spec["parameters"].get("required", [])) <= set(spec["parameters"]["properties"])


def test_list_files(ws):
    t = tb(ws)
    top = t.call("list_files", {}).content.splitlines()
    assert top == ["inbox/", "people/"]
    rec = t.call("list_files", {"path": ".", "recursive": True}).content
    assert "inbox/2027-01-04/em-0001.eml" in rec and "people/me.md" in rec
    assert t.call("list_files", {"path": "people/me.md"}).is_error
    assert t.call("list_files", {"path": "nope"}).is_error


def test_read_file_paging_and_binary(ws, tmp_path):
    (ws / "long.md").write_text("".join(f"line {i}\n" for i in range(1, 11)))
    t = tb(ws)
    r = t.call("read_file", {"path": "long.md", "offset": 2, "limit": 3}).content
    assert r.splitlines()[0] == "[long.md: lines 3-5 of 10]"
    assert r.splitlines()[1:4] == ["line 3", "line 4", "line 5"]
    assert "call read_file with offset=5" in r
    assert "more lines" not in t.call("read_file", {"path": "long.md"}).content
    assert (
        "offset=4" in t.call("read_file", {"path": "long.md", "offset": "2", "limit": "2"}).content
    )
    assert t.call("read_file", {"path": "long.md", "offset": 50}).is_error
    assert t.call("read_file", {"path": "long.md", "offset": -1}).is_error
    make_docx(ws / "dc-0001.docx")
    r = t.call("read_file", {"path": "dc-0001.docx"})
    assert r.is_error and "read_document" in r.content
    assert t.call("read_file", {"path": "missing.md"}).is_error
    assert t.call("read_file", {}).is_error  # required argument


def test_read_document(ws):
    make_docx(ws / "dc-0001.docx")
    make_xlsx(ws / "dc-0002.xlsx")
    t = tb(ws)
    doc = t.call("read_document", {"path": "dc-0001.docx"})
    assert not doc.is_error and "Hosting | 1200" in doc.content
    assert "2027-03-01" in t.call("read_document", {"path": "dc-0002.xlsx"}).content
    eml = t.call("read_document", {"path": "inbox/2027-01-04/em-0001.eml"}).content
    assert "Subject: Questionnaire" in eml and "Please return it by Tuesday." in eml


def test_write_edit_delete_move(ws):
    t = tb(ws)
    r = t.call("write_file", {"path": "loops/new/a.md", "content": "one\ntwo two\n"})
    assert not r.is_error and r.content.startswith("created loops/new/a.md")
    assert (ws / "loops" / "new" / "a.md").read_text() == "one\ntwo two\n"
    assert t.call("write_file", {"path": "loops/new/a.md", "content": "x"}).content.startswith(
        "overwrote"
    )
    (ws / "loops" / "new" / "a.md").write_text("alpha beta beta\n")
    amb = t.call("edit_file", {"path": "loops/new/a.md", "old": "beta", "new": "gamma"})
    assert amb.is_error and "2 times" in amb.content
    miss = t.call("edit_file", {"path": "loops/new/a.md", "old": "delta", "new": "x"})
    assert miss.is_error and "not found" in miss.content
    assert t.call("edit_file", {"path": "loops/new/a.md", "old": "", "new": "x"}).is_error
    ok = t.call("edit_file", {"path": "loops/new/a.md", "old": "alpha beta", "new": "alpha gamma"})
    assert not ok.is_error
    assert (ws / "loops" / "new" / "a.md").read_text() == "alpha gamma beta\n"

    assert t.call("move_file", {"src": "loops/new/a.md", "dst": "people/me.md"}).is_error
    mv = t.call("move_file", {"src": "loops/new/a.md", "dst": "sources/2027-01-04/a.md"})
    assert not mv.is_error and (ws / "sources" / "2027-01-04" / "a.md").exists()
    assert t.call("move_file", {"src": "sources", "dst": "sources/inner"}).is_error
    assert t.call("move_file", {"src": "missing", "dst": "x"}).is_error

    assert t.call("delete_file", {"path": "sources"}).is_error  # not empty
    assert not t.call("delete_file", {"path": "sources/2027-01-04/a.md"}).is_error
    assert not t.call("delete_file", {"path": "sources/2027-01-04"}).is_error
    assert t.call("delete_file", {"path": "nothing-here"}).is_error
    assert t.call("delete_file", {"path": "."}).is_error
    assert t.counts["edit_file"] == 4


def test_search(ws):
    make_docx(ws / "dc-0001.docx")
    t = tb(ws)
    r = t.call("search", {"pattern": "tuesday"}).content
    assert r == "inbox/2027-01-04/em-0001.eml:4: Please return it by Tuesday."
    assert t.call("search", {"pattern": "tuesday", "ignore_case": False}).content.startswith(
        "no matches"
    )
    assert "dc-0001.docx" in t.call("search", {"pattern": r"Hosting \| 1200"}).content
    assert "dc-0001.docx" in t.call("search", {"pattern": "Hosting | 1200", "regex": False}).content
    bad = t.call("search", {"pattern": "(unclosed"})
    assert bad.is_error and "regex=false" in bad.content
    assert "people/me.md:4" in t.call("search", {"pattern": "Ada", "path": "people/me.md"}).content
    (ws / "many.md").write_text("hit\n" * (MAX_SEARCH_MATCHES + 5))
    many = t.call("search", {"pattern": "hit", "path": "many.md"}).content.splitlines()
    assert len(many) == MAX_SEARCH_MATCHES + 1 and "5 more matches" in many[-1]


def test_bad_arguments_and_unknown_tools(ws):
    t = tb(ws)
    r = t.call("read_file", {"file_path": "people/me.md"})
    assert r.is_error and "requires argument(s): path" in r.content and "file_path" in r.content
    assert t.call("read_file", {"path": "people/me.md", "offset": "x"}).is_error
    assert t.call("list_files", {"recursive": "maybe"}).is_error
    assert t.call("write_file", {"path": "a.md", "content": ["x"]}).is_error
    assert t.call("write_file", "not a dict").is_error
    unknown = t.call("run_shell", {"cmd": "ls"})
    assert unknown.is_error and "list_files" in unknown.content
    assert t.call("finish", {"summary": "done"}).content == "finished"
