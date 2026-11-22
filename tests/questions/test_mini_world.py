"""Gold questions for the mini world (tests/fixtures/mini-world/questions.yaml)."""

from __future__ import annotations

import json

from wcb.questions.build import build_questions, visible_questions
from wcb.util.dates import text_variants


def items(q: dict) -> dict[str, dict]:
    return {i["loop"]: i for i in q["gold"]["items"]}


def rubric_by_aspect(q: dict, aspect: str) -> list[dict]:
    return [r for r in q["gold"]["rubric"] if r["aspect"] == aspect]


# ---------------------------------------------------------------- documents
def test_documents_per_checkpoint(mini_docs):
    assert list(mini_docs) == ["cp1", "cp2"]
    cp1, cp2 = mini_docs["cp1"], mini_docs["cp2"]
    assert (cp1["world"], cp1["checkpoint"], cp1["date"]) == ("mini", "cp1", "2027-01-11")
    assert cp2["date"] == "2027-01-12"
    assert [q["id"] for q in cp1["questions"]] == ["q-001", "q-002", "q-003", "q-004", "q-005"]
    assert [q["id"] for q in cp2["questions"]][0] == "q-006"
    for doc in mini_docs.values():
        for q in doc["questions"]:
            assert set(q) == {
                "id", "type", "template", "params", "text", "answerable", "challenges",
                "support", "gold",
            }  # fmt: skip


def test_build_is_deterministic(mini_world, mini_states, mini_docs):
    again = build_questions(mini_world, mini_states)
    assert json.dumps(again, sort_keys=True) == json.dumps(mini_docs, sort_keys=True)


def test_states_missing_from_mapping_are_computed(mini_world, mini_docs):
    assert build_questions(mini_world, {}) == mini_docs


# ---------------------------------------------------------------- list questions
def test_q001_i_owe_cora(question):
    q = question("q-001")
    assert (q["type"], q["text"], q["answerable"]) == (
        "list",
        "What do I currently owe Cora Velez?",
        True,
    )
    assert list(items(q)) == ["c-001"]
    item = items(q)["c-001"]
    assert item["status"] == "open" and item["due"] == "2027-01-12"
    assert item["direction"] == "i_owe" and item["counterparty"] == "p-cora-velez"
    assert q["support"] == ["em-0001"]


def test_q002_owed_to_me_after_transfer(question):
    q = question("q-002")
    assert list(items(q)) == ["c-004"]
    item = items(q)["c-004"]
    assert item["counterparty"] == "p-cora-velez" and item["direction"] == "owed_to_me"
    assert q["support"] == ["mt-0001", "em-0004"]


def test_q005_alias_text_and_endorsed_loop(question):
    q = question("q-005")
    assert q["text"] == "What do I owe Samir?"
    assert "Samir" in q["text"]
    item = items(q)["c-003"]
    assert item["due"] == "2027-01-13" and item["counterparty"] == "p-sam-patel"
    assert q["challenges"] == ["alias", "endorsement"]


def test_q011_unrevealed_closure_stays_open(question):
    q = question("q-011")
    assert items(q)["c-002"]["status"] == "open"


# ---------------------------------------------------------------- point questions
def test_q003_superseded_target_date(question):
    q = question("q-003")
    assert q["text"] == "What is the current target date for Quillon?"
    assert q["gold"] == {
        "kind": "date",
        "value": "2027-02-05",
        "entity": None,
        "accept": ["2027-02-05"],
    }
    assert q["support"] == ["nt-0002"]


def test_q004_unobservable_budget_is_unanswerable(question):
    q = question("q-004")
    assert q["text"] == "What is the budget for Quillon?"  # spec text overrides the template
    assert q["answerable"] is False and q["gold"] == {} and q["support"] == []
    assert q["type"] == "point"


def test_q012_loop_owner_after_transfer(question):
    q = question("q-012")
    assert q["text"] == 'Who is responsible for "Send Ada Tessellate volume pricing"?'
    assert q["gold"]["kind"] == "entity"
    assert q["gold"]["entity"] == "p-cora-velez" and q["gold"]["value"] == "Cora Velez"
    assert "Cora" in q["gold"]["accept"]
    assert q["support"] == ["em-0004"]


def test_q013_person_attr_with_name_collision(question):
    q = question("q-013")
    assert q["text"] == "What is Sam Reyes's role?"
    assert q["gold"]["kind"] == "text" and q["gold"]["value"] == "Solutions engineer"


# ---------------------------------------------------------------- temporal, priority, change
def test_q009_decision_date(question):
    q = question("q-009")
    assert q["text"] == "When did we decide to run the Quillon pilot at the Reno and Sparks depots?"
    assert q["gold"] == {"date": "2027-01-12", "event": "e-0031"}
    assert q["support"] == ["mn-0001"]


def test_q010_focus_tomorrow(question):
    g = question("q-010")["gold"]
    assert g["tomorrow"] == "2027-01-13" and g["k"] == 10
    assert [i["loop"] for i in g["must_include"]] == ["c-003"]
    assert [i["loop"] for i in g["worker_active"]] == ["c-003"]
    # c-001 and c-005 are done; c-002 and c-004 are owed by others.
    assert [i["loop"] for i in g["distractors"]] == ["c-001", "c-002", "c-004", "c-005"]


def test_q008_changes_since_friday(question):
    q = question("q-008")
    # `since` is exclusive, and the default text says so.
    assert q["text"] == "What changed on Quillon since the end of Friday 8 January?"
    events = [i["event"] for i in q["gold"]["items"]]
    assert events == ["e-0020", "e-0022", "e-0030", "e-0031", "e-0035", "e-0032"]
    assert all(i["date"] > "2027-01-08" for i in q["gold"]["items"])
    by_id = {i["event"]: i for i in q["gold"]["items"]}
    assert by_id["e-0030"]["type"] == "decision.reverse"
    assert by_id["e-0031"]["keywords"] == ["sparks", "reno", "pilot"]
    assert "target date" in by_id["e-0020"]["keywords"] and "feb 5" in by_id["e-0020"]["keywords"]
    # The summary fact.set is not a state change; the c-003 update is not on Quillon.
    assert "e-0034" not in events and "e-0021" not in events
    assert q["support"] == ["nt-0002", "em-0004", "mn-0001", "em-0005"]


# ---------------------------------------------------------------- status and brief
def test_q006_status_rubric(question):
    q = question("q-006")
    rubric = q["gold"]["rubric"]
    assert [r["id"] for r in rubric] == [f"r{i}" for i in range(1, len(rubric) + 1)]
    assert [r["aspect"] for r in rubric] == [
        "status", "phase", "latest_change", "target_date", "loop",
    ]  # fmt: skip

    (status,) = rubric_by_aspect(q, "status")
    assert status["critical"] and status["weight"] == 2
    assert "in progress" in status["keywords"][0] and status["stale"] == []

    (phase,) = rubric_by_aspect(q, "phase")
    assert phase["keywords"] == [["pilot"], ["planning"]]
    assert phase["stale"] == [["vendor"], ["evaluation"]]
    assert not phase["critical"] and phase["weight"] == 1

    # The latest project-level change; loop events (the questionnaire sent later that day)
    # are left to the loop items. Giving the old phase contradicts it, as it does r2.
    (latest,) = rubric_by_aspect(q, "latest_change")
    assert latest["text"] == "Quillon phase is now pilot planning"
    assert latest["keywords"] == [["pilot"], ["planning"]]
    assert latest["stale"] == [["vendor"], ["evaluation"]] and latest["support"] == ["mn-0001"]

    (target,) = rubric_by_aspect(q, "target_date")
    assert target["critical"] and target["keywords"] == [sorted(text_variants("2027-02-05"))]
    assert target["stale"] == [sorted(text_variants("2027-01-29"))]

    (loop,) = rubric_by_aspect(q, "loop")
    assert loop["text"] == "Send Ada Tessellate volume pricing (owner: Cora Velez)"
    assert loop["keywords"] == [["volume pricing", "pricing"]]

    facts = q["gold"]["facts"]
    assert (
        facts["attrs"]["owner"] == "Ada Quist"
        and facts["superseded"]["target_date"] == "2027-01-29"
    )
    assert {d["decision"]: d["status"] for d in facts["decisions"]} == {
        "d-001": "reversed",
        "d-002": "made",
    }


def test_q007_person_brief(question):
    q = question("q-007")
    assert q["text"] == "What am I working on with Ben Okoro?"
    aspects = [r["aspect"] for r in q["gold"]["rubric"]]
    assert aspects == ["shared_project", "owed_to_me"]  # No delivered source states Ben’s title.
    shared, owed = q["gold"]["rubric"]
    assert "ledger cleanup" in shared["keywords"][0] and "gl cleanup" in shared["keywords"][0]
    assert owed["critical"] and owed["keywords"] == [["reconciliation report", "january"]]
    assert [f["loop"] for f in q["gold"]["facts"]["owed_to_me"]] == ["c-002"]


def test_keywords_are_lowercase(mini_docs):
    def walk(x):
        if isinstance(x, str):
            yield x
        elif isinstance(x, list):
            for y in x:
                yield from walk(y)

    for doc in mini_docs.values():
        for q in doc["questions"]:
            g = q["gold"]
            groups = [*(r["keywords"] + r["stale"] for r in g.get("rubric", []))]
            groups += [i["keywords"] for i in g.get("items", [])]
            for kw in (k for grp in groups for k in walk(grp)):
                assert kw == kw.lower() and kw.strip(), (q["id"], kw)


def test_support_is_delivered_and_in_delivery_order(mini_docs, mini_states):
    for doc in mini_docs.values():
        delivered = mini_states[doc["date"]]["delivered"]
        for q in doc["questions"]:
            idx = [delivered.index(a) for a in q["support"]]
            assert idx == sorted(idx) and len(set(idx)) == len(idx), q["id"]


# ---------------------------------------------------------------- visible questions
def test_visible_questions_strip_gold(mini_docs):
    vis = visible_questions(mini_docs["cp1"])
    assert vis["date"] == "2027-01-11"
    assert vis["questions"][3] == {
        "id": "q-004",
        "type": "point",
        "text": "What is the budget for Quillon?",
    }
    for q in vis["questions"]:
        assert set(q) == {"id", "type", "text"}
    assert "gold" not in json.dumps(vis) and "answerable" not in json.dumps(vis)
