"""Fixtures for question template and gold-builder tests.

Gold states are computed here with `wcb.world.state.state_at` (never read from the fixture's
`gold/`, which `wcb world build` may be rewriting concurrently). Tests that need extra events
or question specs work on a copy of the mini world in `tmp_path`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from wcb.questions.build import build_questions
from wcb.world.model import World
from wcb.world.state import state_at


@pytest.fixture(scope="module")
def mini_world() -> World:
    return World.load(Path(__file__).parents[1] / "fixtures" / "mini-world")


@pytest.fixture(scope="module")
def mini_states(mini_world: World) -> dict[str, dict]:
    return {d: state_at(mini_world, d) for d in mini_world.all_dates()}


@pytest.fixture(scope="module")
def mini_docs(mini_world: World, mini_states: dict[str, dict]) -> dict[str, dict]:
    return build_questions(mini_world, mini_states)


@pytest.fixture
def question(mini_docs):
    """Look up a built gold question by ID."""

    def get(qid: str) -> dict[str, Any]:
        for doc in mini_docs.values():
            for q in doc["questions"]:
                if q["id"] == qid:
                    return q
        raise KeyError(qid)

    return get


class WorldCopy:
    """A writable copy of the mini world: append events, replace questions, load, build."""

    def __init__(self, root: Path):
        self.root = root

    def add_events(self, events: list[dict[str, Any]]) -> None:
        with open(self.root / "world.jsonl", "a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    def set_questions(self, specs: list[dict[str, Any]]) -> None:
        (self.root / "questions.yaml").write_text(yaml.safe_dump(specs, sort_keys=False))

    def load(self) -> World:
        return World.load(self.root)

    def build(self) -> dict[str, dict]:
        w = self.load()
        return build_questions(w, {d: state_at(w, d) for d in w.all_dates()})


@pytest.fixture
def world_copy(tmp_path: Path, mini_world_dir: Path) -> WorldCopy:
    dst = tmp_path / "mini-world"
    shutil.copytree(mini_world_dir, dst, ignore=shutil.ignore_patterns("gold", "manifest.json"))
    return WorldCopy(dst)


@pytest.fixture
def merge_events() -> list[dict[str, Any]]:
    """Extra synthetic events: a "Dock scheduling" project is created with a worker-owned loop
    to Ben, then merged into Quillon, all revealed by one email on 2027-01-12 (checkpoint cp2)."""
    return [dict(e) for e in _MERGE_EVENTS]


_MERGE_EVENTS = [
    {
        "id": "e-0040", "t": "2027-01-12T12:00:00-08:00", "type": "entity.create",
        "summary": "Dock scheduling project started under Ben", "entity": "pr-dock",
        "kind": "project", "name": "Dock scheduling", "surface_forms": ["Dock", "dock slots"],
        "attrs": {"status": "active", "owner": "p-ben-okoro", "members": ["p-ben-okoro"],
                  "blocker": "Waiting on Pellan yard telemetry export"},
    },
    {
        "id": "e-0041", "t": "2027-01-12T12:05:00-08:00", "type": "commitment.create",
        "summary": "I promised Ben a dock slot forecast by Tuesday", "commitment": "c-006",
        "kind": "task", "what": "Send Ben the dock slot forecast", "debtor": "p-ada-quist",
        "creditor": "p-ben-okoro", "project": "pr-dock", "status": "open", "due": "2027-01-12",
        "accepted": True, "basis": "sent", "keywords": ["slot forecast", "dock slot"],
    },
    {
        "id": "e-0042", "t": "2027-01-12T12:30:00-08:00", "type": "project.merge",
        "summary": "Dock scheduling folded into Quillon", "projects": ["pr-dock"],
        "into": "pr-quillon",
    },
    {
        "id": "e-9020", "t": "2027-01-12T13:00:00-08:00", "type": "artifact.emit",
        "artifact": "em-0010", "channel": "email", "path": "inbox/2027-01-12/em-0010.eml",
        "received_at": "2027-01-12T13:00:00-08:00", "reveals": ["e-0040", "e-0041", "e-0042"],
        "noise": False, "challenges": ["restructuring"], "secrets": [], "title": "Dock scheduling",
        "parent": None,
    },
]  # fmt: skip
