"""Keyword and rubric helpers."""

from __future__ import annotations

import pytest

from wcb.questions.rubric import (
    distinctive_tokens,
    group,
    normalize_extra_item,
    number_items,
    previous_value,
    rubric_item,
    stale_value_groups,
    status_group,
    text_groups,
    value_groups,
)
from wcb.util.dates import text_variants
from wcb.world.state import state_at


def test_group_normalizes_and_dedups():
    assert group(["Security Questionnaire", "security questionnaire", None, " ", "Café"]) == [
        "security questionnaire",
        "cafe",
    ]


def test_status_synonyms():
    assert status_group("paused") == ["paused", "on hold"]
    assert "folded into" in status_group("merged")
    assert status_group("unusual") == ["unusual"]


def test_distinctive_tokens_skip_generic_and_short_words():
    assert distinctive_tokens("The project update for GL") == []
    assert distinctive_tokens("pilot planning") == ["pilot", "planning"]
    # Longer words win; original order is kept.
    assert distinctive_tokens("Waiting on legal sign-off from Pellan") == ["legal", "pellan"]
    assert distinctive_tokens("Quillon pilot planning", avoid={"quillon"}) == ["pilot", "planning"]


def test_text_groups_turn_embedded_dates_into_variants():
    gs = text_groups("Steering review on 2027-02-03")
    assert gs[0] == group(text_variants("2027-02-03"))
    assert gs[1:] == [["steering"], ["review"]]


def test_value_groups_by_shape(mini_world):
    state = state_at(mini_world, "2027-01-12")
    assert value_groups(mini_world, state, "status", "dormant")[0][0] == "dormant"
    assert value_groups(mini_world, state, "owner", "p-cora-velez") == [
        ["cora velez", "cora", "cora.velez@tessellate.example"]
    ]
    assert value_groups(mini_world, state, "target_date", "2027-02-05") == [
        group(text_variants("2027-02-05"))
    ]
    assert value_groups(mini_world, state, "budget", "1,250") == [["1,250", "1250"]]
    assert value_groups(mini_world, state, "phase", None) == []


def test_stale_text_drops_words_shared_with_current(mini_world):
    state = state_at(mini_world, "2027-01-12")
    stale = stale_value_groups(mini_world, state, "phase", "pilot planning", "pilot rollout")
    assert stale == [["planning"]]
    assert stale_value_groups(mini_world, state, "phase", "same", "same") == []
    assert stale_value_groups(mini_world, state, "status", "active", "paused")[0][0] == "active"


def test_previous_value(mini_world):
    ent = state_at(mini_world, "2027-01-12")["entities"]["pr-quillon"]
    assert previous_value(ent, "target_date") == "2027-01-29"
    assert previous_value(ent, "phase") == "vendor evaluation"
    assert previous_value(ent, "status") is None


def test_rubric_items_and_extra_items():
    a = rubric_item("A", [["X"], []], critical=True, support=["em-0001"], aspect="status")
    assert a["weight"] == 2 and a["keywords"] == [["x"]] and a["stale"] == []
    b = normalize_extra_item(
        {"text": "B", "keywords": ["Reno", ["Sparks", "two depots"]], "weight": 3}
    )
    assert b["keywords"] == [["reno"], ["sparks", "two depots"]] and b["weight"] == 3
    assert b["aspect"] == "extra" and not b["critical"]
    assert [r["id"] for r in number_items([a, b])] == ["r1", "r2"]
    with pytest.raises(ValueError):
        normalize_extra_item({"keywords": ["x"]})
