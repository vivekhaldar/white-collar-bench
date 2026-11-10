"""Standard prompts: verbatim texts, Track B variants and rendering."""

from __future__ import annotations

import re

import pytest

from wcb.paths import repo_root
from wcb.runner import prompts


def _doc_prompts() -> list[str]:
    root = repo_root()
    assert root is not None
    text = (root / "docs" / "scoring.md").read_text(encoding="utf-8")
    section = text.split("### Standard prompts", 1)[1].split("\n## ", 1)[0]
    return [m.group(1).strip() for m in re.finditer(r"^> (.+)$", section, re.M)]


def test_track_a_prompts_match_docs_verbatim():
    ingest, query = _doc_prompts()
    assert prompts.INGEST_A == ingest
    assert prompts.QUERY_A == query


def test_track_b_prompts_replace_contract_and_store():
    for t in (prompts.INGEST_B, prompts.SEED_B, prompts.QUERY_B):
        assert "CONTRACT.md" not in t and "the store" not in t
    assert "GOALS.md" in prompts.INGEST_B and "GOALS.md" in prompts.SEED_B
    # "the store does not" becomes "your files do not" (verb agreement), otherwise word for word.
    assert prompts.QUERY_B == prompts.QUERY_A.replace("the store does", "your files do").replace(
        "the store", "your files"
    )
    assert prompts.INGEST_B == prompts.INGEST_A.replace(
        "into the store following `CONTRACT.md`", "into your files following `GOALS.md`"
    )


def test_render_fills_date():
    assert prompts.ingest_prompt("A", "2027-03-01") == (
        "Today is 2027-03-01. New inputs are in `inbox/2027-03-01/` (see `manifest.json`). "
        "Incorporate them into the store following `CONTRACT.md`. "
        "Inputs will not be available after this session."
    )
    assert prompts.query_prompt("B", "2027-03-02").startswith("Today is 2027-03-02. ")
    assert "{" not in prompts.query_prompt("A", "2027-03-02")


def test_seed_prompt_lists_every_date():
    p = prompts.seed_prompt("2027-02-26", ["2027-02-16", "2027-02-15", "2027-02-26"])
    assert p.startswith("Today is 2027-02-26. ")
    assert "`inbox/2027-02-15/`, `inbox/2027-02-16/` and `inbox/2027-02-26/`" in p
    assert "`inbox/2027-02-15/` and `inbox/2027-02-16/`" in prompts.seed_prompt(
        "2027-02-16", ["2027-02-15", "2027-02-16"]
    )
    assert "in `inbox/2027-02-15/`, one directory" in prompts.seed_prompt(
        "2027-02-15", ["2027-02-15"]
    )
    with pytest.raises(ValueError):
        prompts.seed_prompt("2027-02-15", [])


def test_render_rejects_missing_and_unused_values():
    with pytest.raises(ValueError, match="needs values for: date"):
        prompts.render(prompts.INGEST_A)
    with pytest.raises(ValueError, match="no placeholder for: extra"):
        prompts.render(prompts.INGEST_A, date="2027-03-01", extra="x")
    with pytest.raises(ValueError, match="unknown track"):
        prompts.ingest_prompt("C", "2027-03-01")


def test_prompts_have_no_world_specific_content():
    # Only generic benchmark vocabulary: no names, no example.* domains, no dates.
    for t in (prompts.INGEST_A, prompts.INGEST_B, prompts.SEED_B, prompts.QUERY_A, prompts.QUERY_B):
        assert not re.search(r"\d{4}-\d{2}-\d{2}|\.example|@", t)
