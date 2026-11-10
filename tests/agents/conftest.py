"""Fixtures for the agents tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    """A small workspace with a store, an inbox and a .git directory."""
    root = tmp_path / "ws"
    (root / "people").mkdir(parents=True)
    (root / "people" / "me.md").write_text("---\nid: people/me\n---\nAda Quist\n")
    (root / "inbox" / "2027-01-04").mkdir(parents=True)
    (root / "inbox" / "2027-01-04" / "em-0001.eml").write_text(
        "From: Cora <cora@tessellate.example>\nSubject: Questionnaire\n\nPlease return it by Tuesday.\n"
    )
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    return root
