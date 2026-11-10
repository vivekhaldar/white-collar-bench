"""Template edge cases: unanswerable targets, name forms, merges, extra rubric items."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wcb.questions.build import build_question, build_questions
from wcb.questions.templates import (
    QTYPES,
    TEMPLATES,
    lower_first,
    since_text,
)
from wcb.world.state import state_at

DOCS = Path(__file__).parents[2] / "docs"


def build_one(world, date: str, template: str, params: dict, **spec) -> dict:
    """Build a single question against the gold state at `date`."""
    s = {"id": "q-x", "checkpoint": "cp2", "template": template, "params": params, **spec}
    return build_question(s, world, state_at(world, date))


# ---------------------------------------------------------------- registry and docs
def test_registry_matches_formats_table():
    text = (DOCS / "formats.md").read_text(encoding="utf-8")
    section = text.split("### 3.1", 1)[1].split("### 3.2", 1)[0]
    rows = re.findall(r"^\| `(\w+)` \| (\w+) \|", section, flags=re.M)
    assert rows, "template table not found in docs/formats.md §3.1"
    assert {name: qtype for name, qtype in rows} == {n: t.qtype for n, t in TEMPLATES.items()}
    assert {t.qtype for t in TEMPLATES.values()} == set(QTYPES)


def test_every_template_is_documented():
    text = (DOCS / "questions.md").read_text(encoding="utf-8")
    for name in TEMPLATES:
        assert f"`{name}`" in text, name


def test_template_api(mini_world):
    state = state_at(mini_world, "2027-01-12")
    t = TEMPLATES["loop_due"]
    assert (t.name, t.qtype) == ("loop_due", "point")
    params = {"commitment": "c-003"}
    assert (
        t.text(params, mini_world, state)
        == 'When is "Review Sam Patel\'s ingestion design doc" due?'
    )
    answerable, gold, support = t.gold(params, mini_world, state)
    assert answerable and gold["kind"] == "date" and gold["value"] == "2027-01-13"
    assert support == ["nt-0002"]  # the update that set the due date


# ---------------------------------------------------------------- unanswerable
def test_unknowable_person_is_unanswerable(mini_world):
    # Ben is first revealed on 2027-01-05.
    q = build_one(mini_world, "2027-01-04", "i_owe", {"person": "p-ben-okoro"})
    assert q["answerable"] is False and q["gold"] == {} and q["support"] == []
    assert q["text"] == "What do I currently owe Ben Okoro?"  # names come from the world


def test_loop_without_due_date_is_unanswerable(mini_world):
    q = build_one(mini_world, "2027-01-12", "loop_due", {"commitment": "c-004"})
    assert q["answerable"] is False


def test_unknowable_loop_and_decision(mini_world):
    q = build_one(mini_world, "2027-01-04", "loop_owner", {"commitment": "c-004"})
    assert q["answerable"] is False
    assert q["text"] == 'Who is responsible for "Send Ada Tessellate volume pricing"?'
    q = build_one(mini_world, "2027-01-11", "decision_date", {"decision": "d-002"})
    assert q["answerable"] is False
    q = build_one(mini_world, "2027-01-12", "event_date", {"event": "e-0033"}, text="When?")
    assert q["answerable"] is False  # never revealed


def test_hidden_and_missing_attributes(mini_world):
    q = build_one(
        mini_world, "2027-01-12", "person_attr", {"person": "p-nina-hart", "attribute": "_minor"}
    )
    assert q["answerable"] is False
    q = build_one(
        mini_world, "2027-01-12", "project_attr", {"project": "pr-quillon", "attribute": "blocker"}
    )
    assert q["answerable"] is False and q["text"] == "What is currently blocking Quillon?"


def test_empty_list_is_answerable(mini_world):
    # c-003 is only a suggestion until it is accepted on 2027-01-11.
    q = build_one(mini_world, "2027-01-08", "i_owe", {"person": "p-sam-patel"})
    assert q["answerable"] is True and q["gold"] == {"items": []} and q["support"] == []


# ---------------------------------------------------------------- point variants
def test_entity_valued_attributes(mini_world):
    q = build_one(
        mini_world, "2027-01-12", "project_attr", {"project": "pr-ledger", "attribute": "owner"}
    )
    assert q["text"] == "Who owns Ledger cleanup?"
    assert q["gold"]["kind"] == "entity" and q["gold"]["entity"] == "p-ben-okoro"
    assert q["gold"]["accept"][:3] == ["Ben Okoro", "Ben", "B. Okoro"]
    assert q["support"] == ["ch-0001"]
    q = build_one(
        mini_world, "2027-01-12", "person_attr", {"person": "p-sam-reyes", "attribute": "org"}
    )
    assert q["text"] == "Which organization is Sam Reyes with?"
    assert q["gold"]["entity"] == "o-tessellate" and q["gold"]["value"] == "Tessellate Analytics"


def test_worker_owned_loop_accepts_me(mini_world):
    q = build_one(mini_world, "2027-01-11", "loop_owner", {"commitment": "c-001"})
    assert q["gold"]["entity"] == "p-ada-quist" and "me" in q["gold"]["accept"]


def test_other_point_texts(mini_world):
    state = state_at(mini_world, "2027-01-12")
    t = TEMPLATES["person_attr"]
    assert t.text({"person": "p-ben-okoro", "attribute": "email"}, mini_world, state) == (
        "What is Ben Okoro's email address?"
    )
    assert t.text({"person": "p-ben-okoro", "attribute": "relationship"}, mini_world, state) == (
        "What is my working relationship with Ben Okoro?"
    )
    t = TEMPLATES["project_attr"]
    assert t.text({"project": "pr-quillon", "attribute": "status"}, mini_world, state) == (
        "What is the current status of Quillon: active, paused, dormant, done or cancelled?"
    )
    assert t.text({"project": "pr-quillon", "attribute": "risk_level"}, mini_world, state) == (
        "What is the risk level of Quillon?"
    )


# ---------------------------------------------------------------- texts
def test_name_form_selects_surface_form(mini_world):
    q = build_one(
        mini_world, "2027-01-11", "i_owe", {"person": "p-sam-patel", "name_form": "Samir"}
    )
    assert q["text"] == "What do I currently owe Samir?"
    assert q["params"]["name_form"] == "Samir"
    q = build_one(
        mini_world,
        "2027-01-12",
        "project_status",
        {"project": "pr-quillon", "name_form": "Project Quillon"},
    )
    assert q["text"] == "What is the status of Project Quillon?"


def test_helpers():
    assert since_text("2027-03-01") == "Monday 1 March"
    assert since_text("2027-01-08") == "Friday 8 January"
    assert lower_first("Limit the pilot") == "limit the pilot"
    assert lower_first("GL sandbox first") == "GL sandbox first"


def test_event_date(mini_world):
    q = build_one(
        mini_world,
        "2027-01-12",
        "event_date",
        {"event": "e-0023"},
        text="When did Ben confirm his sandbox access?",
    )
    assert q["type"] == "temporal" and q["text"] == "When did Ben confirm his sandbox access?"
    assert q["gold"] == {"date": "2027-01-11", "event": "e-0023"} and q["support"] == ["ch-0002"]


def test_project_loops(mini_world):
    q = build_one(mini_world, "2027-01-11", "project_loops", {"project": "pr-quillon"})
    assert q["text"] == "What loops are open on Quillon?"
    assert [i["loop"] for i in q["gold"]["items"]] == ["c-001", "c-004"]
    assert {i["loop"]: i["direction"] for i in q["gold"]["items"]} == {
        "c-001": "i_owe",
        "c-004": "owed_to_me",
    }


# ---------------------------------------------------------------- restructuring
def test_merge(world_copy, merge_events):
    world_copy.add_events(merge_events)
    w = world_copy.load()
    date = "2027-01-12"

    status = build_one(w, date, "project_status", {"project": "pr-dock"})
    r1 = status["gold"]["rubric"][0]
    assert r1["aspect"] == "status" and r1["text"] == "Dock scheduling has been merged into Quillon"
    assert r1["keywords"][0] == ["merged", "folded into"] and "quillon" in r1["keywords"][1]
    assert "active" in r1["stale"][0]
    assert r1["support"] == ["em-0010"]
    (blocker,) = [r for r in status["gold"]["rubric"] if r["aspect"] == "blocker"]
    assert blocker["critical"] and blocker["keywords"] == [["pellan"], ["telemetry"]]
    (latest,) = [r for r in status["gold"]["rubric"] if r["aspect"] == "latest_change"]
    assert latest["text"] == "Dock scheduling folded into Quillon"
    assert "quillon" in latest["keywords"][0] and "merged" in latest["keywords"][1]

    # The merge moved c-006 to Quillon.
    loops = build_one(w, date, "project_loops", {"project": "pr-quillon"})
    assert "c-006" in [i["loop"] for i in loops["gold"]["items"]]

    changes = build_one(w, date, "project_changes", {"project": "pr-dock", "since": "2027-01-11"})
    assert [i["event"] for i in changes["gold"]["items"]] == ["e-0040", "e-0041", "e-0042"]
    merge_kw = changes["gold"]["items"][2]["keywords"]
    assert "quillon" in merge_kw and "dock scheduling" not in merge_kw

    # Ben's merged project no longer counts, but the loop I owe him puts Quillon in common.
    brief = build_one(w, date, "person_brief", {"person": "p-ben-okoro"})
    shared = [r["text"] for r in brief["gold"]["rubric"] if r["aspect"] == "shared_project"]
    assert shared == [
        "Shared project: Quillon (Ben Okoro is a party to open loops)",
        "Shared project: Ledger cleanup (Ben Okoro is owner)",
    ]
    owe = [r for r in brief["gold"]["rubric"] if r["aspect"] == "i_owe"]
    assert owe[0]["text"] == "I owe Ben Okoro: Send Ben the dock slot forecast (due 2027-01-12)"

    focus = build_one(w, date, "focus_tomorrow", {})
    assert [i["loop"] for i in focus["gold"]["must_include"]] == ["c-006", "c-003"]


def test_person_brief_with_nothing_shared(mini_world):
    q = build_one(mini_world, "2027-01-12", "person_brief", {"person": "p-nina-hart"})
    (item,) = q["gold"]["rubric"]
    assert item["aspect"] == "nothing_shared" and item["id"] == "r1"


# ---------------------------------------------------------------- build options and errors
def test_extra_rubric_and_spec_text(world_copy):
    world_copy.set_questions(
        [
            {
                "id": "q-100",
                "checkpoint": "cp2",
                "template": "project_status",
                "params": {"project": "pr-quillon"},
                "text": "Where are we on Quillon?",
                "extra_rubric": [
                    {
                        "text": "Pilot covers Reno and Sparks",
                        "keywords": ["Sparks"],
                        "critical": True,
                    },
                    "Mentions the steering meeting",
                ],
            }
        ]
    )
    docs = world_copy.build()
    assert docs["cp1"]["questions"] == []  # every checkpoint gets a document
    (q,) = docs["cp2"]["questions"]
    assert q["text"] == "Where are we on Quillon?"
    rubric = q["gold"]["rubric"]
    assert [r["id"] for r in rubric] == [f"r{i}" for i in range(1, 8)]
    assert rubric[-2]["keywords"] == [["sparks"]] and rubric[-2]["weight"] == 2
    assert rubric[-1]["keywords"] == [] and rubric[-1]["weight"] == 1


def test_since_given_as_yaml_date(world_copy):
    (world_copy.root / "questions.yaml").write_text(
        "- {id: q-1, checkpoint: cp2, template: project_changes, params: {project: pr-ledger, since: 2027-01-08}}\n"
    )
    (q,) = world_copy.build()["cp2"]["questions"]
    assert q["params"]["since"] == "2027-01-08"
    assert [i["event"] for i in q["gold"]["items"]] == ["e-0023"]


def test_bad_specs_raise(world_copy):
    world_copy.set_questions([{"id": "q-1", "checkpoint": "cp1", "template": "nope", "params": {}}])
    with pytest.raises(ValueError, match="unknown template"):
        world_copy.build()
    world_copy.set_questions(
        [{"id": "q-1", "checkpoint": "cp1", "template": "i_owe", "params": {}}]
    )
    with pytest.raises(ValueError, match="needs params"):
        world_copy.build()


def test_missing_questions_file(world_copy):
    (world_copy.root / "questions.yaml").unlink()
    w = world_copy.load()
    docs = build_questions(w, {})
    assert {cp: d["questions"] for cp, d in docs.items()} == {"cp1": [], "cp2": []}
