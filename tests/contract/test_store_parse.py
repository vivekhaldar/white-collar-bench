"""Tests for wcb.store.parse: loading a store into records."""

from pathlib import Path

import pytest

from wcb.store.parse import (
    RECORD_DIRS,
    load_store,
    normalize_ref,
    parse_record,
    parse_sections,
)
from wcb.util import frontmatter


def test_load_sample_store(sample_store_dir):
    store = load_store(sample_store_dir)
    counts = {t: len(store.of_type(t)) for t in RECORD_DIRS.values()}
    assert counts == {"person": 5, "org": 2, "project": 2, "loop": 6, "log": 2}
    assert store.other_files == ["CONTRACT.md"]
    assert list(store.records) == sorted(store.records)
    assert all(r.error is None for r in store.records.values())


def test_record_fields(sample_store_dir):
    me = load_store(sample_store_dir).get("people/me")
    assert me.id == "people/me" == me.expected_id
    assert me.path == "people/me.md"
    assert me.type == "person" == me.dir_type
    assert me.stem == "me"
    assert me.meta["name"] == "Ada Quist"
    assert me.meta["updated"] == "2027-01-07"  # YAML dates become ISO strings
    assert list(me.sections) == ["Context", "Threads", "Log"]
    assert me.section("log").startswith("- 2027-01-04:")  # case-insensitive lookup
    assert me.section("Knowledge") is None
    assert me.body.startswith("The worker.")


def test_loop_meta_types(sample_store_dir):
    store = load_store(sample_store_dir)
    loop = store.get("loops/review-sam-patel-ingestion-design-doc")
    assert loop.meta["accepted"] is False
    assert loop.meta["project"] is None
    assert loop.meta["evidence"][0] == {
        "source": "em-0002",
        "basis": "received",
        "date": "2027-01-06",
        "note": "Asked, 'no rush'; I have not agreed yet",
    }


@pytest.mark.parametrize(
    "ref",
    [
        "loops/limit-quillon-pilot-to-reno",
        "loops/limit-quillon-pilot-to-reno.md",
        "./loops/limit-quillon-pilot-to-reno.md",
        "/loops/limit-quillon-pilot-to-reno",
        "[[loops/limit-quillon-pilot-to-reno]]",
        "[[loops/limit-quillon-pilot-to-reno|the Reno decision]]",
        " loops/limit-quillon-pilot-to-reno#log ",
    ],
)
def test_get_accepts_reference_forms(sample_store_dir, ref):
    rec = load_store(sample_store_dir).get(ref)
    assert rec is not None and rec.expected_id == "loops/limit-quillon-pilot-to-reno"


def test_get_missing_and_case_sensitive(sample_store_dir):
    store = load_store(sample_store_dir)
    assert store.get("loops/nope") is None
    assert store.get("Loops/Limit-Quillon-Pilot-To-Reno") is None


@pytest.mark.parametrize(
    "ref, expected",
    [
        ("loops/x", "loops/x"),
        ("loops/x.md", "loops/x"),
        ("./loops/x", "loops/x"),
        ("././loops/x.md", "loops/x"),
        ("[[loops/x]]", "loops/x"),
        ("[[loops/x|label]]", "loops/x"),
        ("loops\\x.md", "loops/x"),
        ("people/me#log", "people/me"),
        ("em-0193", "em-0193"),
    ],
)
def test_normalize_ref(ref, expected):
    assert normalize_ref(ref) == expected


def test_of_type_follows_directory(tmp_path):
    (tmp_path / "loops").mkdir()
    (tmp_path / "loops" / "x.md").write_text("---\nid: loops/x\ntype: task\n---\nbody\n")
    store = load_store(tmp_path)
    assert [r.expected_id for r in store.of_type("loop")] == ["loops/x"]
    assert store.get("loops/x").type == "task"


def test_parse_sections():
    body = """Intro line, not in any section.

## Current state

As of 2027-01-07: one paragraph.

## Knowledge
### Background
Deeper headings stay inside.
```
## not a heading (fenced)
```

# Title resets

Text under a level-1 heading belongs to no section.

## Log ##
- 2027-01-04: first

## Log
- 2027-01-05: second
"""
    s = parse_sections(body)
    assert list(s) == ["Current state", "Knowledge", "Log"]
    assert s["Current state"] == "As of 2027-01-07: one paragraph."
    assert "### Background" in s["Knowledge"] and "## not a heading" in s["Knowledge"]
    assert "level-1" not in s["Knowledge"]
    assert s["Log"] == "- 2027-01-04: first\n\n- 2027-01-05: second"


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("No front matter here.\n", "missing YAML front matter"),
        ("---\nid: loops/x\ntype: loop\n", "never closed"),
        ("---\nid: [unclosed\n---\nbody\n", "invalid YAML"),
        ("---\n- a list\n---\nbody\n", "mapping"),
        ("---\nid: loops/x\ndue: 2027-02-30\n---\nbody\n", "invalid YAML front matter"),
    ],
)
def test_parse_record_errors_do_not_raise(text, fragment):
    rec = parse_record(text, "loops/x.md")
    assert rec.error and fragment in rec.error
    assert rec.meta == {} and rec.id is None and rec.type is None
    assert rec.expected_id == "loops/x"


def test_parse_record_stringifies_non_string_id():
    rec = parse_record("---\nid: 42\ntype: loop\n---\n", "loops/x.md")
    assert rec.id == "42" and rec.error is None


def test_round_trip_through_frontmatter_dump(sample_store_dir, tmp_path):
    """Writing every record back with frontmatter.dump and re-parsing preserves its content."""
    store = load_store(sample_store_dir)
    for rec in store.records.values():
        out = tmp_path / rec.path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(frontmatter.dump(rec.meta, rec.body), encoding="utf-8")
    again = load_store(tmp_path)
    assert list(again.records) == list(store.records)
    for rid, rec in store.records.items():
        rec2 = again.records[rid]
        assert (rec2.id, rec2.type, rec2.meta, rec2.sections, rec2.error) == (
            rec.id,
            rec.type,
            rec.meta,
            rec.sections,
            None,
        )
        assert rec2.body.strip() == rec.body.strip()


def test_excluded_and_other_files(tmp_path):
    files = {
        ".git/config": "x",
        "inbox/2027-01-11/em-0001.eml": "x",
        ".wcb/questions.json": "{}",
        "CONTRACT.md": "contract",
        "notes/inbox/todo.md": "nested inbox dirs are kept",
        "sources/em-0001.eml": "Subject: hi",
        "loops/readme.txt": "stray",
        "loops/x.md": "---\nid: loops/x\ntype: loop\n---\n",
        "people/archive/old.md": "---\nid: people/archive/old\n---\n",
    }
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    store = load_store(tmp_path)
    assert list(store.records) == ["loops/x", "people/archive/old"]
    assert store.other_files == [
        "CONTRACT.md",
        "loops/readme.txt",
        "notes/inbox/todo.md",
        "sources/em-0001.eml",
    ]


def test_all_text_covers_front_matter_and_other_files_but_not_binaries(tmp_path):
    (tmp_path / "people").mkdir()
    (tmp_path / "people" / "me.md").write_text("---\nid: people/me\nname: FRONTMATTER-TEXT\n---\nBODY-TEXT\n")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "n.md").write_text("NOTE-TEXT")
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources" / "dc-0001.pdf").write_bytes(b"%PDF PDF-TEXT")
    (tmp_path / "sources" / "blob.bin").write_bytes(b"BIN-TEXT\x00\x01")
    text = load_store(tmp_path).all_text()
    for frag in ("FRONTMATTER-TEXT", "BODY-TEXT", "NOTE-TEXT"):
        assert frag in text
    assert "PDF-TEXT" not in text and "BIN-TEXT" not in text


def test_load_store_missing_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_store(tmp_path / "nope")


def test_store_root_is_a_path(sample_store_dir):
    assert load_store(str(sample_store_dir)).root == Path(sample_store_dir)


def test_symbolic_links_are_listed_but_never_read(tmp_path):
    """A store is graded on the host, so a planted link must not pull in outside files."""
    import os

    from wcb.contract.validate import validate_store
    from wcb.store.parse import load_store

    outside = tmp_path / "outside.md"
    outside.write_text("---\nid: loops/x\ntype: loop\n---\nsecret text\n")
    store = tmp_path / "store"
    (store / "loops").mkdir(parents=True)
    (store / "people").mkdir()
    os.symlink(outside, store / "loops" / "x.md")
    os.symlink(tmp_path, store / "people" / "elsewhere")
    s = load_store(store)
    assert s.records == {} and s.links == ["loops/x.md", "people/elsewhere"]
    assert "secret" not in s.all_text()
    codes = [i.code for i in validate_store(store)]
    assert codes.count("file.symlink") == 2
