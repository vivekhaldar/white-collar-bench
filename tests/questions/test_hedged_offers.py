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

