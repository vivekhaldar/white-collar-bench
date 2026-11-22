"""Template edge cases: unanswerable targets, name forms, merges, extra rubric items."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wcb.grade.judge import heuristic_rubric
from wcb.questions.build import build_question, build_questions
from wcb.questions.templates import (
    QTYPES,
    TEMPLATES,
    event_groups,
    lower_first,
    since_text,
    status_change_events,
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
    assert q["answerable"] is True and q["gold"]["items"] == [] and q["support"] == []
    # The suggestion is listed as optional: an answer may include it without losing precision.
    assert [i["loop"] for i in q["gold"]["suggested"]] == ["c-003"]


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


# ---------------------------------------------------------------- gold edge cases
def _emit(aid: str, t: str, reveals: list[str], channel: str = "email") -> dict:
    ext = {"email": "eml", "note": "md"}[channel]
    return {
        "id": f"e-9{aid[-3:]}", "t": t, "type": "artifact.emit", "artifact": aid,
        "channel": channel, "path": f"inbox/{t[:10]}/{aid}.{ext}", "received_at": t,
        "reveals": reveals, "noise": False, "challenges": [], "secrets": [], "title": aid,
        "parent": None,
    }  # fmt: skip


def test_since_is_exclusive_and_the_default_text_says_so(mini_world):
    q = build_one(
        mini_world,
        "2027-01-12",
        "project_changes",
        {"project": "pr-quillon", "since": "2027-01-11"},
    )
    assert q["text"] == "What changed on Quillon since the end of Monday 11 January?"
    # e-0020 and e-0022 happened on Monday 11 January itself, so they are not listed.
    assert [i["event"] for i in q["gold"]["items"]] == ["e-0030", "e-0031", "e-0035", "e-0032"]


def test_suggested_loops_do_not_drive_status_golds(world_copy):
    # A suggestion on Quillon after the last real change; accepted only on the next day.
    world_copy.add_events(
        [
            {
                "id": "e-0060", "t": "2027-01-12T16:30:00-08:00", "type": "commitment.create",
                "summary": "Cora suggested I brief the CFO on Quillon pricing (not agreed)",
                "commitment": "c-010", "kind": "ask", "what": "Brief the CFO on Quillon pricing",
                "debtor": "p-ada-quist", "creditor": "p-cora-velez", "project": "pr-quillon",
                "status": "open", "due": None, "accepted": False, "basis": "received",
                "keywords": ["cfo", "pricing brief"],
            },
            _emit("em-0060", "2027-01-12T16:35:00-08:00", ["e-0060"]),
        ]
    )  # fmt: skip
    w = world_copy.load()
    status = build_one(w, "2027-01-12", "project_status", {"project": "pr-quillon"})
    (latest,) = [r for r in status["gold"]["rubric"] if r["aspect"] == "latest_change"]
    assert latest["text"] == "Quillon phase is now pilot planning"  # project-level only
    recent = [e["event"] for e in status["gold"]["facts"]["recent_events"]]
    assert "e-0060" not in recent and recent[-1] == "e-0032"
    # A change question still lists the suggestion: it is a knowable event on the project.
    changes = build_one(
        w, "2027-01-12", "project_changes", {"project": "pr-quillon", "since": "2027-01-11"}
    )
    assert changes["gold"]["items"][-1]["event"] == "e-0060"


def test_accepting_a_suggestion_is_a_status_change(world_copy):
    world_copy.add_events(
        [
            {
                "id": "e-0060", "t": "2027-01-12T16:30:00-08:00", "type": "commitment.create",
                "summary": "Cora suggested I brief the CFO on Quillon pricing (not agreed)",
                "commitment": "c-010", "kind": "ask", "what": "Brief the CFO on Quillon pricing",
                "debtor": "p-ada-quist", "creditor": "p-cora-velez", "project": "pr-quillon",
                "status": "open", "due": None, "accepted": False, "basis": "received",
                "keywords": ["cfo", "pricing brief"],
            },
            {
                "id": "e-0061", "t": "2027-01-12T16:40:00-08:00", "type": "commitment.update",
                "summary": "I agreed to brief the CFO on Quillon pricing", "commitment": "c-010",
                "changes": {"accepted": True},
            },
            _emit("em-0060", "2027-01-12T16:45:00-08:00", ["e-0060", "e-0061"]),
        ]
    )  # fmt: skip
    status = build_one(world_copy.load(), "2027-01-12", "project_status", {"project": "pr-quillon"})
    # The acceptance is a knowable status change (the judge's facts list it), but the
    # latest-change rubric item is project-level only, so it does not drive that item.
    recent = [e["event"] for e in status["gold"]["facts"]["recent_events"]]
    assert recent[-1] == "e-0061"
    (latest,) = [r for r in status["gold"]["rubric"] if r["aspect"] == "latest_change"]
    assert latest["text"] == "Quillon phase is now pilot planning"


def test_split_and_merge_moves_are_loop_evidence(world_copy):
    # c-004 is split out of Quillon and Ledger cleanup is merged into Quillon; em-0051 and
    # em-0052 reveal only the restructuring, which is the evidence of the loops' new project.
    world_copy.add_events(
        [
            {
                "id": "e-0050", "t": "2027-01-12T09:00:00-08:00", "type": "entity.create",
                "summary": "Quillon pricing workstream started", "entity": "pr-qpricing",
                "kind": "project", "name": "Quillon pricing", "surface_forms": [],
                "attrs": {"status": "active", "owner": "p-ada-quist"},
            },
            _emit("em-0050", "2027-01-12T09:05:00-08:00", ["e-0050"]),
            {
                "id": "e-0051", "t": "2027-01-12T09:10:00-08:00", "type": "project.split",
                "summary": "Volume pricing split out of Quillon", "project": "pr-quillon",
                "into": ["pr-qpricing"], "moves": {"c-004": "pr-qpricing"},
            },
            _emit("em-0051", "2027-01-12T09:15:00-08:00", ["e-0051"]),
            {
                "id": "e-0052", "t": "2027-01-12T09:20:00-08:00", "type": "project.merge",
                "summary": "Ledger cleanup folded into Quillon", "projects": ["pr-ledger"],
                "into": "pr-quillon",
            },
            _emit("em-0052", "2027-01-12T09:25:00-08:00", ["e-0052"]),
        ]
    )  # fmt: skip
    w = world_copy.load()
    state = state_at(w, "2027-01-12")
    assert state["loops"]["c-004"]["evidence"] == ["mt-0001", "em-0004", "em-0051"]
    assert state["loops"]["c-002"]["evidence"] == ["ch-0001", "em-0052"]
    assert state["entities"]["pr-qpricing"]["evidence"] == ["em-0050", "em-0051"]
    split = build_one(w, "2027-01-12", "project_loops", {"project": "pr-qpricing"})
    assert split["gold"]["items"][0]["support"] == ["mt-0001", "em-0004", "em-0051"]
    assert split["support"] == ["mt-0001", "em-0004", "em-0051"]
    merged = build_one(w, "2027-01-12", "project_loops", {"project": "pr-quillon"})
    (c002,) = [i for i in merged["gold"]["items"] if i["loop"] == "c-002"]
    assert c002["support"] == ["ch-0001", "em-0052"]


def test_worker_taking_over_accepts_second_person_words(world_copy):
    world_copy.add_events(
        [
            {
                "id": "e-0060", "t": "2027-01-12T16:30:00-08:00", "type": "commitment.update",
                "summary": "Cora handed the volume pricing to me", "commitment": "c-004",
                "changes": {"debtor": "p-ada-quist"},
            },
            {
                "id": "e-0061", "t": "2027-01-12T16:30:00-08:00", "type": "fact.set",
                "summary": "I took over Ledger cleanup from Ben", "subject": "pr-ledger",
                "attribute": "owner", "value": "p-ada-quist",
            },
            _emit("em-0060", "2027-01-12T16:35:00-08:00", ["e-0060", "e-0061"]),
        ]
    )  # fmt: skip
    w = world_copy.load()
    state = state_at(w, "2027-01-12")
    status = build_one(w, "2027-01-12", "project_status", {"project": "pr-quillon"})
    (ev,) = [e for e in status_change_events(w, state, "pr-quillon") if e["id"] == "e-0060"]
    groups = event_groups(w, state, ev, project="pr-quillon")
    assert groups[0] == ["volume pricing", "pricing"]
    assert {"ada quist", "ada", "you", "yours", "me"} <= set(groups[1])
    item = {"text": ev["summary"], "keywords": groups, "stale": []}
    answer = "Cora handed the Tessellate volume pricing over to you, so it's yours now."
    assert heuristic_rubric(answer, item, status["gold"]["facts"]) == "covered"

    ledger = build_one(w, "2027-01-12", "project_status", {"project": "pr-ledger"})
    (latest,) = [r for r in ledger["gold"]["rubric"] if r["aspect"] == "latest_change"]
    assert {"ada", "you", "me"} <= set(latest["keywords"][0])
    # Flat change keywords match predicted items to gold: no pronouns there.
    changes = build_one(
        w, "2027-01-12", "project_changes", {"project": "pr-ledger", "since": "2027-01-11"}
    )
    assert "you" not in changes["gold"]["items"][-1]["keywords"]
    assert "ada" in changes["gold"]["items"][-1]["keywords"]


def test_cleared_value_names_what_was_cleared(world_copy):
    world_copy.add_events(
        [
            {
                "id": "e-0060", "t": "2027-01-11T16:00:00-08:00", "type": "fact.set",
                "summary": "Ledger cleanup blocked by the GL vendor outage", "subject": "pr-ledger",
                "attribute": "blocker", "value": "GL vendor outage",
            },
            _emit("em-0060", "2027-01-11T16:05:00-08:00", ["e-0060"]),
            {
                "id": "e-0061", "t": "2027-01-12T16:00:00-08:00", "type": "fact.set",
                "summary": "GL vendor outage resolved", "subject": "pr-ledger",
                "attribute": "blocker", "value": None,
            },
            _emit("em-0061", "2027-01-12T16:05:00-08:00", ["e-0061"]),
        ]
    )  # fmt: skip
    status = build_one(world_copy.load(), "2027-01-12", "project_status", {"project": "pr-ledger"})
    (latest,) = [r for r in status["gold"]["rubric"] if r["aspect"] == "latest_change"]
    assert latest["critical"] and latest["keywords"][1] == ["vendor", "outage"]
    assert "none" not in latest["keywords"][0]
    facts = status["gold"]["facts"]
    stale = "Ledger cleanup is active and still blocked by the GL vendor outage. Overdue: none."
    assert heuristic_rubric(stale, latest, facts) != "covered"
    assert heuristic_rubric("The GL vendor outage is fixed.", latest, facts) == "covered"
