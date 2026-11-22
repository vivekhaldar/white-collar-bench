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

