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
