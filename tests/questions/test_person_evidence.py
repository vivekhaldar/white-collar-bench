from pathlib import Path

from wcb.questions.build import build_question, load_specs
from wcb.questions.person_evidence import attribute_sources
from wcb.world.model import World
from wcb.world.state import state_at


def test_role_requires_evidence_about_that_person():
    world = World.load(Path("worlds/dev/gen-s2-w1"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    brief = next(s for s in load_specs(world) if s["id"] == "q-011")
    items = build_question(brief, world, state)["gold"]["rubric"]
    assert not any(item["aspect"] == "role" for item in items)
    assert "nt-0001" in attribute_sources(world, state, "p-tendai-santos", "role")
    assert not attribute_sources(world, {**state, "delivered": []}, "p-tendai-santos", "role")


def test_unstated_org_allows_abstention():
    world = World.load(Path("worlds/dev/gen-s9-large"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    spec = next(s for s in load_specs(world) if s["id"] == "q-009")
    assert build_question(spec, world, state)["gold"]["uncertain"]
