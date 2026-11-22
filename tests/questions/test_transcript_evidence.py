from pathlib import Path

from wcb.grade.answers import ScoreContext, score_question
from wcb.grade.judge import HeuristicJudge
from wcb.questions.build import build_question, load_specs
from wcb.world.model import World
from wcb.world.state import state_at


def test_wagtail_blocker_conflict_is_scoped_to_project_and_checkpoint():
    world = World.load(Path("worlds/dev/gen-s5-small"))
    specs = {s["id"]: s for s in load_specs(world)}
    before = state_at(world, "2027-03-24")
    assert "uncertain" not in build_question(specs["q-008"], world, before)["gold"]
    state = state_at(world, world.checkpoint("cp1")["date"])
    q = build_question(specs["q-008"], world, state)
    ctx = ScoreContext.from_state(world, state)
    for value, expected in [("Nothing", 1), (q["gold"]["value"], 1), ("bankruptcy", 0)]:
        ans = {"type": "point", "abstain": False, "value": value, "cites": ["mt-0011"]}
        assert score_question(q, ans, HeuristicJudge(), ctx).score == expected
    assert score_question(q, {"type": "point", "abstain": True}, HeuristicJudge(), ctx).score == 1
    qualified = {"type": "point", "abstain": False, "value": "overdue change request",
                 "note": "Isla reported no blockers. Patient data pause status is unresolved.", "cites": ["mt-0011"]}
    assert score_question(q, qualified, HeuristicJudge(), ctx).base == 0.5
    assert score_question(q, {**qualified, "note": "The change request is unresolved."}, HeuristicJudge(), ctx).base == 0
    assert all(r["aspect"] != "blocker" for r in build_question(specs["q-002"], world, state)["gold"]["rubric"])

