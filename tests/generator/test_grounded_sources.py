from wcb.world.planner import make_plan
from wcb.world.simulator import simulate


def test_hedged_offers_are_unaccepted_in_new_worlds():
    plan = make_plan(2)
    sim = simulate(plan, 2)
    events = {e["id"]: e for e in sim.events}
    offers = [events[a.event] for c in sim.comms for a in c.acts
              if a.how == "hedged" and events[a.event]["type"] == "commitment.create"]
    assert offers
    assert all(not e["accepted"] for e in offers)



def test_suggested_summaries_preserve_the_original_endorsement():
    sim = simulate(make_plan(5), 5)
    suggested = [e for e in sim.events if e["type"] == "commitment.create" and not e["accepted"]]
    assert suggested
    assert all(e["summary"] == f"Suggested (not agreed): {e['what']}" for e in suggested)


def test_new_transcripts_use_content_neutral_probes(tmp_path):
    from wcb.render.transcript import NEUTRAL_PROBES, PROBE_PAIRS
    from wcb.world.generate import generate_world

    world = generate_world(seed=5, size="small", out_dir=tmp_path, build=False)
    transcripts = "\n".join(p.read_text() for p in (world / "inbox").rglob("*.vtt"))
    assert any(question in transcripts for question, _ in NEUTRAL_PROBES)
    assert not any(question in transcripts for question, _ in PROBE_PAIRS)


def test_new_contacts_are_documented_at_first_delivery(tmp_path):
    from wcb.world.generate import generate_world
    from wcb.world.model import World

    w = World.load(generate_world(seed=2, out_dir=tmp_path, build=False))
    for eid, event in w.entity_events().items():
        if event.get("kind") != "person":
            continue
        sources = [a for a in w.artifacts.values() if event["id"] in a.reveals]
        if not sources:
            continue
        other = [a for a in sources if a.title != "Contact directory updates"]
        notes = [a for a in sources if a.title == "Contact directory updates"]
        assert len(notes) == 1 and notes[0].date == min(a.date for a in other)
        entry = next(line for line in (w.dir / notes[0].path).read_text().splitlines()
                     if line.startswith(f"- {event['name']}:"))
        assert event["attrs"].get("role", "") in entry, eid
