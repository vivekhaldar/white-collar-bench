"""Gold-derived perfect answers score exactly 1 on every public world (issue #9).

`wcb.baselines.gold_answers.perfect_answers` restates each question's gold. If such an answer
loses anything, the grader, not the answer, is wrong: the pilot's cp3 q-036 once scored 0.733
because "the 78/74 in the 4 March email were v1 totals" was read as asserting the old totals.
Gold is computed in memory (`state_at`, `build_questions`), so the test never reads `gold/`,
which `wcb world build` may be rewriting, and follows the dev worlds when they are regenerated.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wcb.baselines.gold_answers import perfect_answers
from wcb.grade.answers import ScoreContext, score_answers
from wcb.grade.judge import HeuristicJudge
from wcb.questions.build import build_questions
from wcb.world.model import World
from wcb.world.state import state_at

ROOT = Path(__file__).parents[2]
WORLDS = [ROOT / "worlds" / "pilot"] + sorted(
    p for p in (ROOT / "worlds" / "dev").glob("*") if (p / "world.yaml").exists()
)


@pytest.mark.parametrize("root", WORLDS, ids=lambda p: p.name)
def test_perfect_answers_score_exactly_one(root):
    world = World.load(root)
    states = {cp["date"]: state_at(world, cp["date"]) for cp in world.checkpoints()}
    judge = HeuristicJudge()
    n, below = 0, []
    for cp, doc in build_questions(world, states).items():
        ctx = ScoreContext.from_state(world, states[doc["date"]])
        for s in score_answers(doc, perfect_answers(doc), judge, ctx):
            n += 1
            if s.base != 1.0:
                below.append((cp, s.id, s.type, s.base, s.details.get("verdicts")))
    assert n > 0
    assert not below, below


def test_every_public_world_is_checked():
    assert {p.name for p in WORLDS} >= {"pilot"}
    assert len(WORLDS) >= 2, "dev worlds missing"
