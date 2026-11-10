"""Fixtures for world check/build/stats and oracle-store tests.

Tests that modify a world work on a copy of tests/fixtures/mini-world in tmp_path (without
its derived gold/ and manifests), so the shared fixture is never touched.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from wcb.world.check import check_world


@pytest.fixture
def world_copy(tmp_path: Path, mini_world_dir: Path) -> Path:
    """A fresh copy of the mini world without derived files."""
    dst = tmp_path / "mini-world"
    shutil.copytree(mini_world_dir, dst, ignore=shutil.ignore_patterns("gold", "manifest.json"))
    return dst


class WorldEditor:
    """Small helpers to break a copied world in targeted ways."""

    def __init__(self, root: Path):
        self.root = root

    # world.jsonl
    def events(self) -> list[dict[str, Any]]:
        lines = (self.root / "world.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def save(self, events: list[dict[str, Any]]) -> None:
        text = "".join(json.dumps(e) + "\n" for e in events)
        (self.root / "world.jsonl").write_text(text, encoding="utf-8")

    def edit(self, eid: str, **fields: Any) -> None:
        """Set fields on event `eid`; a value of `...` deletes the field."""
        events = self.events()
        for e in events:
            if e["id"] == eid:
                for k, v in fields.items():
                    if v is ...:
                        e.pop(k, None)
                    else:
                        e[k] = v
                break
        else:
            raise KeyError(eid)
        self.save(events)

    def get(self, eid: str) -> dict[str, Any]:
        return next(e for e in self.events() if e["id"] == eid)

    # world.yaml / questions.yaml
    def meta(self) -> dict[str, Any]:
        return yaml.safe_load((self.root / "world.yaml").read_text(encoding="utf-8"))

    def save_meta(self, meta: dict[str, Any]) -> None:
        (self.root / "world.yaml").write_text(
            yaml.safe_dump(meta, sort_keys=False), encoding="utf-8"
        )

    def save_questions(self, specs: list[dict[str, Any]]) -> None:
        (self.root / "questions.yaml").write_text(
            yaml.safe_dump(specs, sort_keys=False), encoding="utf-8"
        )

    # results
    def codes(self, severity: str = "error") -> set[str]:
        return {i.code for i in check_world(self.root) if i.severity == severity}


@pytest.fixture
def editor(world_copy: Path) -> WorldEditor:
    return WorldEditor(world_copy)
