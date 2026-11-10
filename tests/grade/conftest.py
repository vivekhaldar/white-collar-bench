"""Fixtures for grading tests: a ScoreContext built from the mini fixture world."""

from __future__ import annotations

from pathlib import Path

import pytest

from wcb.grade.answers import ScoreContext
from wcb.world.model import World
from wcb.world.state import state_at


@pytest.fixture(scope="session")
def mini_world() -> World:
    return World.load(Path(__file__).parents[1] / "fixtures" / "mini-world")


@pytest.fixture
def ctx(mini_world: World) -> ScoreContext:
    """Context at the mini world's second checkpoint (2027-01-12), without a store."""
    return ScoreContext.from_state(mini_world, state_at(mini_world, "2027-01-12"))


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """A tiny store with two records, for store-path citations."""
    for rid in ("loops/send-volume-pricing", "people/cora-velez"):
        p = tmp_path / "store" / f"{rid}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\nid: {rid}\n---\n", encoding="utf-8")
    (tmp_path / "store" / "sources").mkdir()
    (tmp_path / "store" / "sources" / "em-0004.md").write_text("archived\n", encoding="utf-8")
    return tmp_path / "store"


class CountingJudge:
    """Wraps a judge and records every same_item / rubric call."""

    def __init__(self, inner):
        self.inner = inner
        self.name = f"counting:{inner.name}"
        self.same_calls: list[tuple[dict, dict, str]] = []
        self.rubric_calls: list[tuple[str, dict]] = []

    def same_item(self, pred, gold, *, kind):
        self.same_calls.append((pred, gold, kind))
        return self.inner.same_item(pred, gold, kind=kind)

    def rubric(self, answer_text, item, facts):
        self.rubric_calls.append((answer_text, item))
        return self.inner.rubric(answer_text, item, facts)


class FakeClient:
    """Scripted LLM client: returns `outputs` in order (cycling) and records prompts."""

    def __init__(self, outputs, model="fake-model", spec="fake:fake-model"):
        self.outputs = list(outputs)
        self.model = model
        self.spec = spec
        self.calls: list[dict] = []

    def complete(self, prompt, *, system=None, temperature=0.0, max_tokens=512):
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.outputs[(len(self.calls) - 1) % len(self.outputs)]


@pytest.fixture
def make_fake_client():
    """Factory: make_fake_client(outputs, model=..., spec=...) -> FakeClient."""
    return FakeClient


@pytest.fixture
def make_counting_judge():
    """Factory: make_counting_judge(inner_judge) -> CountingJudge."""
    return CountingJudge
