from pathlib import Path

from wcb.grade.answers import grade_change
from wcb.grade.judge import HeuristicJudge
from wcb.questions.build import build_question, load_specs
from wcb.world.model import World
from wcb.world.state import state_at


def test_handoff_and_decision_bundles():
    world = World.load(Path("worlds/dev/gen-s1-w1"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    spec = next(q for q in load_specs(world) if q["id"] == "q-003")
    items = {g["event"]: g for g in build_question(spec, world, state)["gold"]["items"]}
    for first, last, text in [
        ("e-0218", "e-0232", "Marten RACI chart confirmed with Yasmin (done)"),
        ("e-0196", "e-0197", "Decided approach C; rollout checklist dropped"),
    ]:
        assert items[last]["paired_event"] == first
        question = {"gold": {"items": [items[first], items[last]]}}
        answer = {"items": [{"text": text, "cites": items[last]["support"]}]}
        score, details = grade_change(question, answer, HeuristicJudge(), None)
        assert score == details["precision"] == details["recall"] == 1
        unrelated = {**items[last], "paired_event": "unrelated"}
        score, _ = grade_change({"gold": {"items": [items[first], unrelated]}}, answer, HeuristicJudge(), None)
        assert score < 1

        wrong_day = {"items": [{**answer["items"][0], "date": "1999-01-01"}]}
        assert grade_change(question, wrong_day, HeuristicJudge(), None)[0] < 1
