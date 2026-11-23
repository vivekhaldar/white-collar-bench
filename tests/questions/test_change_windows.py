import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from wcb.questions.build import build_question, build_questions, load_specs
from wcb.world.model import World
from wcb.world.state import state_at

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
LAST_WEEKDAY = re.compile(r"\bsince last (" + "|".join(WEEKDAYS) + r")\b", re.I)


@pytest.mark.parametrize("path", sorted(Path("worlds").rglob("world.yaml")), ids=str)
def test_since_last_weekday_matches_most_recent_prior_date(path):
    for doc in build_questions(World.load(path.parent), {}).values():
        checkpoint = date.fromisoformat(doc["date"])
        for question in doc["questions"]:
            match = LAST_WEEKDAY.search(question["text"])
            if match:
                weekday = WEEKDAYS.index(match[1].lower())
                days_back = (checkpoint.weekday() - weekday) % 7 or 7
                assert question["params"]["since"] == (checkpoint - timedelta(days=days_back)).isoformat(), (
                    path, doc["checkpoint"], question["id"]
                )


def test_pilot_friday_events_are_baseline_and_later_changes_count():
    world = World.load(Path("worlds/pilot"))
    spec = next(q for q in load_specs(world) if q["id"] == "q-014")
    state = state_at(world, world.checkpoint(spec["checkpoint"])["date"])
    items = build_question(spec, world, state)["gold"]["items"]
    events = {item["event"] for item in items}
    assert events.isdisjoint({"e-0169", "e-0170", "e-0171", "e-0175", "e-0185"})
    assert {"e-0197", "e-0198"} <= events
    assert all(item["date"] > "2027-02-26" for item in items)
