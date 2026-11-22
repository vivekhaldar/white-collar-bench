from wcb.grade.answers import relationship_matches, status_credit
from wcb.questions.templates import list_item


def test_relationship_description_controls():
    assert relationship_matches("Colleague in my own org (SLIO)", "peer")
    assert relationship_matches("Cross-department collaborator: the Selfell lead", "stakeholder")
    assert relationship_matches("Client counterpart: Customer Service Manager at Selfell Public Works", "stakeholder")
    assert relationship_matches("External collaborator: the Revenue Cycle Analyst", "stakeholder")
    assert not relationship_matches("my manager", "peer")
    assert not relationship_matches("vendor", "peer")
    assert not relationship_matches("Colleague in my own org: vendor", "peer")
    assert not relationship_matches("not a colleague in my own org", "peer")


def test_status_alias_requires_an_unqualified_incoming_obligation():
    from pathlib import Path

    from wcb.world.model import World
    from wcb.world.state import state_at

    world = World.load(Path("worlds/dev/gen-s5-small"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    assert list_item(world, state, "c-045")["accept_status"] == ["open", "waiting"]
    state["loops"]["c-045"]["history"].append({"changes": {"status": "waiting"}})
    assert "accept_status" not in list_item(world, state, "c-045")
    assert status_credit("done", "waiting") == 0
