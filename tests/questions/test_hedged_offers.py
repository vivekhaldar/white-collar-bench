from pathlib import Path

from wcb.questions.templates import TEMPLATES, hedged_offer
from wcb.world.model import World
from wcb.world.state import state_at


def test_yael_offer_is_optional_until_endorsed():
    world = World.load(Path("worlds/dev/gen-s2-w1"))
    state = state_at(world, world.checkpoint("cp1")["date"])
    _, gold, _ = TEMPLATES["i_owe"].gold({"person": "p-yael-ellery"}, world, state)
    offer = next(i for i in gold["items"] if i["loop"] == "c-064")
    assert offer["optional"]
    loop = state["loops"]["c-064"]
    endorsed = {**loop, "history": [*loop["history"], {"changes": {"accepted": True}}]}
    assert not hedged_offer(world, endorsed)



def test_published_hedged_templates_never_require_an_unendorsed_offer():
    from wcb.questions.build import build_questions
    from wcb.util.io import read_yaml
    from wcb.world.simulator import simulate

    seen = 0
    for path in sorted(Path("worlds/dev").glob("*/plan.yaml")):
        plan = read_yaml(path)
        sim = simulate(plan, plan["generator"]["seed"])
        events = {e["id"]: e for e in sim.events}
        offers = {events[a.event]["commitment"] for c in sim.comms for a in c.acts
                  if a.how == "hedged" and events[a.event]["type"] == "commitment.create"}
        seen += len(offers)
        world = World.load(path.parent)
        for doc in build_questions(world, {}).values():
            state = state_at(world, doc["date"])
            for cid in offers & state["loops"].keys():
                loop = state["loops"][cid]
                if any(h.get("changes", {}).get("accepted") or "debtor" in h.get("changes", {})
                       for h in loop.get("history", [])[1:]):
                    continue
                for q in doc["questions"]:
                    gold = q["gold"]
                    assert all(i.get("loop") != cid for i in gold.get("must_include", []))
                    for item in gold.get("items", []):
                        if item.get("loop") == cid or item.get("event") == loop["history"][0]["event"]:
                            assert item.get("optional"), (world.id, q["id"], item)
                    for item in gold.get("rubric", []):
                        if item["aspect"] in {"loop", "i_owe", "owed_to_me"} and loop["what"] in item["text"]:
                            assert item.get("optional"), (world.id, q["id"], item)
    assert seen > 0
