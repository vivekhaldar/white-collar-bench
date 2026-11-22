from pathlib import Path

from wcb.grade.answers import ScoreContext, citation_precision
from wcb.grade.citation_evidence import additional_sources
from wcb.world.model import World
from wcb.world.state import state_at


def test_cirrus_calendar_and_unsent_draft():
    world = World.load(Path("worlds/dev/gen-s9-large"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    ctx = ScoreContext.from_state(world, state)
    q = {"type": "priority", "gold": {}}
    items = [
        {"text": "Walkthrough: Cirrus budget justification with Mathieu", "cites": ["ca-0008"]},
        {"text": "Finish the unsent bed management selection pricing comparison draft", "cites": ["em-0118"]},
        {"text": "Completed the Cirrus budget justification walkthrough", "cites": ["ca-0008"]},
        {"text": "Sent the bed management selection pricing comparison", "cites": ["em-0118"]},
    ]
    assert additional_sources(q, {"items": items}, {}, ctx) == {0: {"ca-0008"}, 1: {"em-0118"}}


def test_track_b_workspace_note_has_no_vote(tmp_path):
    ctx = ScoreContext({}, {}, "", "", {"ch-0001"}, store_root=tmp_path, track="B")
    (tmp_path / "commitments.md").write_text("my notes")
    def score(cites):
        return citation_precision({"cites": cites}, ["ch-0001"], ctx)[0]
    assert score(["commitments.md#A20", "ch-0001"]) == 1
    assert score(["commitments.md H25", "ch-0001"]) == 1
    assert score(["commitments.md#A20"]) == 0
    assert score(["missing.md", "ch-0001"]) == 0.5


def test_panel_checks_only_the_cited_claim_and_delivered_source():
    from wcb.grade.citation_evidence import evidence_vote

    world = World.load(Path("worlds/dev/gen-s9-large"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    ctx = ScoreContext.from_state(world, state)
    q = {"type": "priority", "text": "What is on my calendar?"}
    answer = {"items": [{"text": "Walk Mathieu through the Cirrus budget justification", "cites": ["ca-0008"]},
                        {"text": "Unrelated item", "cites": []}]}
    class CheckPacket:
        def citation(self, question, claim, source):
            assert question == q["text"] and "Unrelated" not in claim
            return "Mathieu" in claim and "Cirrus budget justification" in source
    assert evidence_vote(q, answer, "ca-0008", 0, ctx, CheckPacket(), None)
    assert not evidence_vote(q, answer, "ca-9999", 0, ctx, CheckPacket(), None)

