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
    for note in ["commitments.md H25", "commitments.md #24", "commitments.md B#17", "commitments.md 2027-11-05"]:
        assert score([note, "ch-0001"]) == 1
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



def test_source_index_requires_a_real_file_pointing_to_the_delivered_source(tmp_path):
    ctx = ScoreContext({}, {}, "", "", {"mn-0015"}, store_root=tmp_path, track="A")
    root = tmp_path / "sources"
    root.mkdir()
    path = root / "mn-0015.md"
    path.write_text("Source: mn-0015")
    assert citation_precision({"cites": ["sources/mn-0015.md", "mn-0015 (auto)"]}, ["mn-0015"], ctx)[1]["total"] == 1
    assert citation_precision({"cites": ["sources/mn-0015.md"]}, ["mn-0015"], ctx)[0] == 1
    path.unlink()
    assert citation_precision({"cites": ["sources/mn-0015.md"]}, ["mn-0015"], ctx)[0] == 0


def test_split_citation_gets_a_second_read_of_the_source(make_fake_client):
    from wcb.grade.citation_evidence import evidence_vote
    from wcb.grade.judge import LLMJudge, PanelJudge

    world = World.load(Path("worlds/dev/gen-s9-large"))
    ctx = ScoreContext.from_state(world, state_at(world, world.checkpoint("cp1")["date"]))
    q = {"type": "priority", "text": "What should I focus on tomorrow?"}
    answer = {"items": [{"text": "A pricing comparison for Anh is still an unsent draft", "cites": ["em-0118"]}]}
    for second, expected in [("YES", True), ("NO", False)]:
        first = make_fake_client(["NO", second])
        other = make_fake_client(["YES", "YES"])
        panel = PanelJudge([LLMJudge(first), LLMJudge(other)])
        assert evidence_vote(q, answer, "em-0118", 0, ctx, panel, None) == expected
        assert len(first.calls) == len(other.calls) == 2
