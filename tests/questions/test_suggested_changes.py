from pathlib import Path

from wcb.grade.judge import HeuristicJudge
from wcb.grade.matching import match_items
from wcb.questions.build import build_question, load_specs
from wcb.world.model import World
from wcb.world.state import state_at


def test_unowned_vendor_comparison_is_a_suggestion():
    world = World.load(Path("worlds/dev/gen-s10-w2-small"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    spec = next(q for q in load_specs(world) if q["id"] == "q-003")
    items = build_question(spec, world, state)["gold"]["items"]
    proposal = next(i for i in items if i["event"] == "e-0116")
    assert proposal["summary"] == "Suggested (not agreed): Review Catrin's translation help selection vendor comparison"
    for introduction, expected in [("Suggested (not agreed)", True), ("I promised", False)]:
        pred = {"text": introduction + ": Review Catrin's translation help selection vendor comparison"}
        assert bool(match_items([pred], [proposal], HeuristicJudge(), kind="change", ctx=None)) == expected

