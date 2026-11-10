"""Fixtures for store-parser and contract-validator tests."""

import shutil
from pathlib import Path

import pytest

SAMPLE_STORE = Path(__file__).resolve().parents[1] / "fixtures" / "sample-store"


@pytest.fixture
def sample_store_dir() -> Path:
    """The hand-written, fully valid sample store (read-only: copy it before editing)."""
    return SAMPLE_STORE


@pytest.fixture
def store_copy(tmp_path) -> Path:
    """A writable copy of the sample store, for building deliberately broken variants."""
    dst = tmp_path / "store"
    shutil.copytree(SAMPLE_STORE, dst)
    return dst
