from pathlib import Path

import pytest

from wcb.grade.judge import HeuristicJudge
from wcb.grade.matching import describes_suggestion, match_items
from wcb.questions.build import build_question, load_specs
from wcb.world.model import World
from wcb.world.state import state_at


@pytest.mark.parametrize("text", [
    "Discussed and agreed: I'll send the plan",
    "Proposed by Catrin; I said yes and will send it Friday",
    "Suggested I send the deck; I agreed to do it",
    "It was possible; I took it on.",
    "Discussed yesterday. I’ll prepare it.",
    "It was proposed, and the team will send it Friday.",
])
def test_endorsed_proposals_are_commitments(text):
    assert not describes_suggestion(text)


@pytest.mark.parametrize("text", [
    "Proposed, not yet agreed: send the plan",
    "Discussed; I didn't agree to send it.",
    "Suggested that I send it. I’ll try, no promises.",
    "Considering it; I might send it.",
    "Reviewing it was suggested, but no owner was agreed.",
])
def test_unendorsed_proposals_remain_suggestions(text):
    assert describes_suggestion(text)


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



def test_published_suggestion_summaries_are_grounded_in_the_creation():
    from wcb.questions.templates import change_item

    count = 0
    for path in sorted(Path("worlds/dev").glob("*/world.yaml")):
        world = World.load(path.parent)
        state = state_at(world, world.checkpoints()[-1]["date"])
        for event in state["events"]:
            raw = world.by_id[event["id"]]
            if event["type"] == "commitment.create" and raw.get("accepted") is False:
                item = change_item(world, state, event, event.get("project") or "")
                assert item["summary"] == f"Suggested (not agreed): {raw['what']}"
                assert item["optional"] and item["suggested"]
                count += 1
    assert count > 0
