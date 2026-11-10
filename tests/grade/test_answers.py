"""Per-question grading: every question type, abstentions, validation and citations."""

from __future__ import annotations

import json

import pytest

from wcb.grade.answers import (
    QuestionScore,
    ScoreContext,
    answer_text,
    citation_precision,
    collect_cites,
    parse_number,
    priority_gold,
    score_answers,
    score_question,
    store_record_id,
)
from wcb.grade.judge import HeuristicJudge

J = HeuristicJudge()


# ---------------------------------------------------------------- gold builders (formats.md §3.2)
def q_point(
    kind, value, entity=None, accept=(), *, support=("em-0004",), answerable=True, qid="q-p"
):
    gold = (
        {"kind": kind, "value": value, "entity": entity, "accept": list(accept)}
        if answerable
        else {}
    )
    return {
        "id": qid,
        "type": "point",
        "template": "loop_owner",
        "params": {},
        "text": "?",
        "answerable": answerable,
        "challenges": ["transfer"],
        "support": list(support),
        "gold": gold,
    }


def loop_item(loop, what, counterparty, status="open", due=None, keywords=(), support=()):
    return {
        "loop": loop,
        "what": what,
        "counterparty": counterparty,
        "direction": "i_owe",
        "status": status,
        "due": due,
        "keywords": list(keywords),
        "support": list(support),
    }


C001 = loop_item(
    "c-001",
    "Return the Tessellate security questionnaire",
    "p-cora-velez",
    due="2027-01-12",
    keywords=["security questionnaire", "questionnaire"],
    support=["em-0001"],
)
C003 = loop_item(
    "c-003",
    "Review Sam Patel's ingestion design doc",
    "p-sam-patel",
    due="2027-01-13",
    keywords=["ingestion design", "design doc"],
    support=["em-0002", "nt-0002"],
)
C004 = loop_item(
    "c-004",
    "Send Ada Tessellate volume pricing",
    "p-cora-velez",
    keywords=["volume pricing", "pricing"],
    support=["mt-0001", "em-0004"],
)
C002 = loop_item(
    "c-002",
    "Send Ada the January reconciliation report",
    "p-ben-okoro",
    keywords=["reconciliation report", "january"],
    support=["ch-0001"],
)
C005 = loop_item(
    "c-005",
    "Approve Ben's GL sandbox access request",
    "p-ben-okoro",
    status="done",
    keywords=["access request", "sandbox"],
    support=["ch-0001", "ch-0002"],
)


def q_list(items, support=("em-0001", "em-0002", "nt-0002")):
    return {
        "id": "q-l",
        "type": "list",
        "template": "i_owe",
        "answerable": True,
        "challenges": [],
        "support": list(support),
        "gold": {"items": list(items)},
    }


def point(value, cites=("em-0004",)):
    return {"type": "point", "abstain": False, "value": value, "cites": list(cites)}


def listing(*items):
    return {"type": "list", "abstain": False, "items": list(items)}


# ---------------------------------------------------------------- entity resolution
@pytest.mark.parametrize(
    "text, expected",
    [
        ("Cora Velez", {"p-cora-velez"}),
        ("cora", {"p-cora-velez"}),
        ("CORÁ VÉLEZ", {"p-cora-velez"}),
        ("cora.velez@tessellate.example", {"p-cora-velez"}),
        ("Sam", set()),  # shared first name: ambiguous
        ("sam", set()),
        ("Samir", {"p-sam-patel"}),
        ("Sam Patel", {"p-sam-patel"}),
        ("SAM REYES", {"p-sam-reyes"}),
        ("Sam Patel and Sam Reyes", {"p-sam-patel", "p-sam-reyes"}),
        ("Samantha", set()),  # whole words only
        ("@ben", {"p-ben-okoro"}),
        ("B. Okoro", {"p-ben-okoro"}),
        ("Project Quillon", {"pr-quillon"}),
        ("analytics platform selection", {"pr-quillon"}),  # leading 'the' optional
        ("people/cora-velez", {"p-cora-velez"}),
        ("me", {"p-ada-quist"}),
        ("", set()),
        (None, set()),
    ],
)
def test_resolve_entities(ctx, text, expected):
    assert ctx.resolve_entities(text) == expected


def test_entity_kind(ctx):
    assert ctx.entity_kind("p-cora-velez") == "person"
    assert ctx.entity_kind("o-tessellate") == "org"
    assert ctx.entity_kind("pr-quillon") == "project"
    assert ctx.entity_kind("pr-unknown") == "project"
    assert ctx.entity_kind("p-unknown") == "person"


# ---------------------------------------------------------------- point
@pytest.mark.parametrize(
    "value, score",
    [
        ("Cora Velez", 1.0),
        ("Cora", 1.0),
        ("cora.velez@tessellate.example", 1.0),
        ("Cora Velez (Tessellate)", 1.0),  # an org next to the person is fine
        ("Cora Velez or Sam Reyes", 0.0),  # hedging between people is not
        ("Sam Reyes", 0.0),  # the previous owner (transfer)
        ("Sam", 0.0),
        ("Tessellate", 0.0),
    ],
)
def test_point_entity(ctx, value, score):
    q = q_point("entity", "Cora Velez", "p-cora-velez")
    assert score_question(q, point(value), J, ctx).base == score


def test_point_entity_name_collision(ctx):
    q = q_point("entity", "Sam Reyes", "p-sam-reyes")
    assert score_question(q, point("Sam"), J, ctx).base == 0.0
    assert score_question(q, point("Sam Reyes"), J, ctx).base == 1.0
    res = score_question(q, point("Sam"), J, ctx)
    assert res.details["resolved"] == []


def test_point_entity_ambiguous_accept_string_does_not_count(ctx):
    # The question builder lists every surface form as an accept string, including a first
    # name shared by two people; the grader must still refuse it.
    q = q_point(
        "entity",
        "Sam Reyes",
        "p-sam-reyes",
        accept=["Sam Reyes", "Sam", "sam.reyes@tessellate.example"],
    )
    assert score_question(q, point("Sam"), J, ctx).base == 0.0
    assert score_question(q, point("sam.reyes@tessellate.example"), J, ctx).base == 1.0


def test_alias_ids(ctx):
    assert ctx.alias_ids("Sam") == {"p-sam-patel", "p-sam-reyes"}
    assert ctx.alias_ids("Cora") == {"p-cora-velez"}
    assert ctx.alias_ids("the Tessellate AE") == set()


def test_point_entity_accept_string(ctx):
    q = q_point("entity", "Cora Velez", "p-cora-velez", accept=["the Tessellate AE"])
    assert score_question(q, point("The Tessellate AE"), J, ctx).base == 1.0


def test_point_entity_worker(ctx):
    q = q_point("entity", "Ada Quist", "p-ada-quist")
    assert score_question(q, point("You"), J, ctx).base == 1.0
    assert score_question(q, point("Ada Quist"), J, ctx).base == 1.0


@pytest.mark.parametrize(
    "value, score",
    [
        ("2027-02-05", 1.0),
        ("5 Feb", 1.0),
        ("February 5th", 1.0),
        ("Fri 5 Feb 2027", 1.0),
        ("Feb. 5", 1.0),
        ("2/5", 1.0),
        ("29 Jan", 0.0),  # the superseded target
        ("2027-01-29", 0.0),
        ("5 Feb 2028", 0.0),
        ("early February", 0.0),
    ],
)
def test_point_date(ctx, value, score):
    q = q_point("date", "2027-02-05")
    assert score_question(q, point(value), J, ctx).base == score


@pytest.mark.parametrize(
    "value, score",
    [
        ("$180k", 1.0),
        ("180,000 USD", 1.0),
        (180000, 1.0),
        ("USD 180000", 1.0),
        ("0.18m", 1.0),
        ("150k", 0.0),
        ("1.8m", 0.0),
        ("unknown", 0.0),
    ],
)
def test_point_number(ctx, value, score):
    q = q_point("number", "180000 USD")
    assert score_question(q, point(value), J, ctx).base == score


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$180k", 180000.0),
        ("180,000 USD", 180000.0),
        ("1.2m", 1200000.0),
        ("2 million", 2e6),
        ("-3.5", -3.5),
        (42, 42.0),
        ("none", None),
        (None, None),
        (True, None),
    ],
)
def test_parse_number(raw, expected):
    assert parse_number(raw) == expected


@pytest.mark.parametrize(
    "value, score",
    [
        ("Solutions engineer", 1.0),
        ("solutions ENGINEER", 1.0),
        ("Solutions engineer at Tessellate", 1.0),  # all gold tokens present
        ("Engineer", 0.0),
        ("Account executive", 0.0),
        ("SE", 1.0),  # accept alternative
    ],
)
def test_point_text(ctx, value, score):
    q = q_point("text", "Solutions engineer", accept=["SE"])
    assert score_question(q, point(value), J, ctx).base == score


# ---------------------------------------------------------------- abstention and validity
def test_unanswerable_abstain_scores_one(ctx):
    q = q_point("number", None, answerable=False)
    res = score_question(q, {"type": "point", "abstain": True}, J, ctx)
    assert (res.score, res.base, res.citation, res.abstained, res.valid) == (
        1.0,
        1.0,
        None,
        True,
        True,
    )


def test_unanswerable_answered_scores_zero(ctx):
    q = q_point("number", None, answerable=False)
    res = score_question(q, point("180k"), J, ctx)
    assert res.score == 0.0 and res.citation is None and not res.abstained


def test_answerable_abstain_scores_zero(ctx):
    q = q_point("entity", "Cora Velez", "p-cora-velez")
    res = score_question(q, {"type": "point", "abstain": True}, J, ctx)
    assert res.score == 0.0 and res.abstained and res.valid and res.citation is None


def test_missing_answer(ctx):
    res = score_question(q_point("entity", "Cora Velez", "p-cora-velez"), None, J, ctx)
    assert res.score == 0.0 and not res.valid
    assert res.details["problems"] == ["missing answer"]


@pytest.mark.parametrize(
    "answer",
    [
        {"type": "list", "abstain": False, "items": []},  # wrong type
        {"type": "point", "abstain": False},  # value required
        {"type": "point", "value": "Cora"},  # abstain required
        {
            "type": "point",
            "abstain": False,
            "value": "Cora",
            "cites": "em-0004",
        },  # cites not a list
        "Cora Velez",  # not an object
    ],
)
def test_invalid_answer_scores_zero(ctx, answer):
    res = score_question(q_point("entity", "Cora Velez", "p-cora-velez"), answer, J, ctx)
    assert res.score == 0.0 and not res.valid and res.details["problems"]


def test_invalid_list_item_scores_zero(ctx):
    bad = listing({"counterparty": "Cora"})  # item without text
    res = score_question(q_list([C001]), bad, J, ctx)
    assert not res.valid and res.score == 0.0
    bad_status = listing({"text": "Return the questionnaire", "status": "pending"})
    assert not score_question(q_list([C001]), bad_status, J, ctx).valid


def test_unanswerable_with_invalid_answer_scores_zero(ctx):
    q = q_point("number", None, answerable=False)
    assert score_question(q, {"type": "point"}, J, ctx).score == 0.0


# ---------------------------------------------------------------- list
def test_list_exact(ctx):
    ans = listing(
        {
            "text": "Return the Tessellate security questionnaire",
            "counterparty": "Cora Velez",
            "status": "open",
            "due": "2027-01-12",
            "cites": ["em-0001"],
        },
        {
            "text": "Review Samir's ingestion doc",
            "counterparty": "Samir",
            "status": "open",
            "due": "2027-01-13",
            "cites": ["nt-0002"],
        },
    )
    res = score_question(q_list([C001, C003]), ans, J, ctx)
    assert res.base == pytest.approx(1.0)
    assert res.citation == 1.0 and res.score == pytest.approx(1.0)
    assert {m["gold"] for m in res.details["matches"]} == {"c-001", "c-003"}


def test_list_soft_f1_arithmetic(ctx):
    ans = listing(
        # exact: a = 1
        {
            "text": "Send Cora the security questionnaire",
            "counterparty": "Cora",
            "status": "open",
            "due": "2027-01-12",
            "cites": ["em-0001"],
        },
        # status waiting vs open (0.5), wrong due (0), counterparty right (1): a = 0.5
        {
            "text": "Review Sam Patel's ingestion design doc",
            "counterparty": "Sam Patel",
            "status": "waiting",
            "due": "2027-01-20",
            "cites": ["em-0002"],
        },
        # unmatched
        {
            "text": "Book the offsite venue",
            "counterparty": "Ben",
            "status": "open",
            "cites": ["em-0003"],
        },
    )
    res = score_question(q_list([C001, C003]), ans, J, ctx)
    p, r = 1.5 / 3, 1.5 / 2
    assert res.details["precision"] == pytest.approx(p)
    assert res.details["recall"] == pytest.approx(r)
    assert res.base == pytest.approx(2 * p * r / (p + r))  # 0.6
    by_gold = {m["gold"]: m for m in res.details["matches"]}
    assert by_gold["c-003"]["status"] == 0.5 and by_gold["c-003"]["due"] == 0.0
    assert by_gold["c-003"]["counterparty"] == 1.0
    assert res.details["unmatched_pred"] == [2]
    # 2 of 3 cites are in support -> c = 2/3
    assert res.citation == pytest.approx(2 / 3)
    assert res.score == pytest.approx(0.6 * (0.75 + 0.25 * 2 / 3))


def test_list_ambiguous_counterparty_gets_no_credit(ctx):
    ans = listing(
        {
            "text": "Review the ingestion design doc",
            "counterparty": "Sam",
            "status": "open",
            "due": "2027-01-13",
        }
    )
    res = score_question(q_list([C003]), ans, J, ctx)
    m = res.details["matches"][0]
    assert m["counterparty"] == 0.0 and m["credit"] == pytest.approx(2 / 3)


def test_list_status_credit_closed_vs_active(ctx):
    ans = listing(
        {"text": "Approve Ben's GL sandbox access request", "counterparty": "Ben", "status": "open"}
    )
    res = score_question(q_list([C005]), ans, J, ctx)
    m = res.details["matches"][0]
    assert m["status"] == 0.0 and m["due"] == 1.0 and m["counterparty"] == 1.0


def test_list_missing_status_and_null_due(ctx):
    ans = listing({"text": "Tessellate volume pricing", "counterparty": "Cora", "due": None})
    m = score_question(q_list([C004]), ans, J, ctx).details["matches"][0]
    assert (m["status"], m["due"], m["counterparty"]) == (0.0, 1.0, 1.0)


def test_list_gold_without_counterparty_skips_that_credit(ctx):
    gold = {**C004, "counterparty": None}
    ans = listing({"text": "Tessellate volume pricing", "status": "open"})
    m = score_question(q_list([gold]), ans, J, ctx).details["matches"][0]
    assert m["counterparty"] is None and m["credit"] == 1.0


def test_list_duplicate_predictions_count_once(ctx):
    item = {
        "text": "Return the security questionnaire",
        "counterparty": "Cora",
        "status": "open",
        "due": "2027-01-12",
    }
    res = score_question(q_list([C001]), listing(item, dict(item)), J, ctx)
    assert len(res.details["matches"]) == 1
    assert res.base == pytest.approx(2 * 0.5 * 1.0 / 1.5)


@pytest.mark.parametrize(
    "gold, items, expected",
    [
        ([], [], 1.0),
        ([], [{"text": "Anything"}], 0.0),
        ([C001], [], 0.0),
    ],
)
def test_list_empty_cases(ctx, gold, items, expected):
    res = score_question(q_list(gold), listing(*items), J, ctx)
    assert res.base == expected


def test_list_wrong_items_score_zero(ctx):
    ans = listing({"text": "Plan the team offsite", "counterparty": "Ben", "status": "open"})
    assert score_question(q_list([C001, C003]), ans, J, ctx).base == 0.0


# ---------------------------------------------------------------- status / brief
RUBRIC = [
    {
        "id": "r1",
        "text": "Decision target is 5 February",
        "weight": 2,
        "critical": True,
        "keywords": [["2027-02-05"]],
        "stale": [["2027-01-29"]],
        "support": ["nt-0002"],
    },
    {
        "id": "r2",
        "text": "Pilot scope is Reno and Sparks depots",
        "weight": 2,
        "critical": True,
        "keywords": [["sparks"], ["reno"]],
        "stale": [["reno only", "only reno", "reno depot only"]],
        "support": ["mn-0001"],
    },
    {
        "id": "r3",
        "text": "Waiting on volume pricing from Cora",
        "weight": 1,
        "critical": False,
        "keywords": [["volume pricing", "pricing"], ["cora"]],
        "stale": [],
        "support": ["em-0004"],
    },
]


def q_status(rubric=RUBRIC, qtype="status"):
    return {
        "id": "q-s",
        "type": qtype,
        "template": "project_status",
        "answerable": True,
        "challenges": ["supersession"],
        "support": ["nt-0002", "mn-0001", "em-0004"],
        "gold": {"rubric": rubric, "facts": {"target_date": "2027-02-05"}},
    }


def status(summary, *claims):
    return {
        "type": "status",
        "abstain": False,
        "summary": summary,
        "claims": [{"text": t, "cites": c} for t, c in claims],
    }


def test_status_all_covered(ctx):
    ans = status(
        "Quillon decision moved to Feb 5; pilot widened to Reno and Sparks.",
        ("Still waiting on volume pricing from Cora", ["em-0004"]),
    )
    res = score_question(q_status(), ans, J, ctx)
    assert res.base == 1.0
    assert [v["verdict"] for v in res.details["verdicts"]] == ["covered"] * 3
    assert res.citation == 1.0


def test_status_partial_weights(ctx):
    ans = status("Pilot now at Reno and Sparks depots.")  # r2 covered (2), r1 and r3 missing
    res = score_question(q_status(), ans, J, ctx)
    assert res.base == pytest.approx(2 / 5)
    assert res.citation == 0.0 and res.score == pytest.approx(0.4 * 0.75)


def test_status_contradiction_stale_date(ctx):
    # Stale target (29 Jan) presented as current, new date absent -> r1 contradicted.
    ans = status(
        "Quillon decision targeted for 29 January. Pilot at Reno and Sparks.",
        ("Cora owes us volume pricing", ["em-0004"]),
    )
    res = score_question(q_status(), ans, J, ctx)
    verdicts = {v["item"]: v["verdict"] for v in res.details["verdicts"]}
    assert verdicts == {"r1": "contradicted", "r2": "covered", "r3": "covered"}
    assert res.base == pytest.approx((2 + 1 - 2) / 5)


def test_status_new_and_stale_date_counts_as_covered(ctx):
    ans = status("Target moved from 29 Jan to 5 Feb.")
    verdicts = {
        v["item"]: v["verdict"] for v in score_question(q_status(), ans, J, ctx).details["verdicts"]
    }
    assert verdicts["r1"] == "covered"


def test_status_floor_at_zero(ctx):
    ans = status("Decision due 2027-01-29; pilot is Reno only.")
    res = score_question(q_status(), ans, J, ctx)
    assert res.base == 0.0


def test_brief_uses_same_rubric_rules(ctx):
    ans = {"type": "brief", "abstain": False, "summary": "Cora: volume pricing outstanding."}
    res = score_question(q_status(qtype="brief"), ans, J, ctx)
    assert res.base == pytest.approx(1 / 5)


def test_status_empty_rubric(ctx):
    assert score_question(q_status(rubric=[]), status("Anything"), J, ctx).base == 1.0


def test_answer_text_joins_summary_and_claims():
    ans = status("S.", ("A", []), ("B", []))
    assert answer_text(ans) == "S.\nA\nB"


def test_rubric_invalid_verdict_counts_as_missing(ctx):
    class Odd:
        name = "odd"

        def rubric(self, *_):
            return "maybe"

    res = score_question(q_status(), status("x"), Odd(), ctx)
    assert {v["verdict"] for v in res.details["verdicts"]} == {"missing"}


# ---------------------------------------------------------------- change
CHANGES = [
    {
        "event": "e-0020",
        "summary": "Quillon decision target moved to 5 February",
        "date": "2027-01-11",
        "type": "fact.set",
        "keywords": ["5 february", "target"],
        "support": ["nt-0002"],
    },
    {
        "event": "e-0030",
        "summary": "Reno-only pilot reversed at steering",
        "date": "2027-01-12",
        "type": "decision.reverse",
        "keywords": ["reversed", "reno"],
        "support": ["mn-0001"],
    },
    {
        "event": "e-0032",
        "summary": "I sent Cora the completed security questionnaire",
        "date": "2027-01-12",
        "type": "commitment.resolve",
        "keywords": ["security questionnaire"],
        "support": ["em-0005"],
    },
]


def q_change(items=CHANGES):
    return {
        "id": "q-c",
        "type": "change",
        "template": "project_changes",
        "answerable": True,
        "challenges": [],
        "support": ["nt-0002", "mn-0001", "em-0005"],
        "gold": {"items": items},
    }


def change(*texts):
    return {
        "type": "change",
        "abstain": False,
        "items": [{"text": t, "cites": ["mn-0001"]} for t in texts],
    }


def test_change_f1(ctx):
    ans = change(
        "Decision target moved to 5 Feb", "Reno-only pilot was reversed", "Budget approved"
    )
    res = score_question(q_change(), ans, J, ctx)
    assert res.base == pytest.approx(2 / 3)
    assert {m["gold"] for m in res.details["matches"]} == {"e-0020", "e-0030"}
    assert res.details["unmatched_gold"] == ["e-0032"]


def test_change_perfect_and_empty(ctx):
    ans = change(
        "Target moved to 5 Feb", "Reno-only pilot reversed", "Sent Cora the security questionnaire"
    )
    assert score_question(q_change(), ans, J, ctx).base == pytest.approx(1.0)
    assert score_question(q_change([]), change(), J, ctx).base == 1.0
    assert score_question(q_change([]), change("Something"), J, ctx).base == 0.0
    assert score_question(q_change(), change(), J, ctx).base == 0.0


# ---------------------------------------------------------------- temporal
def q_temporal(date="2027-01-12"):  # a Tuesday
    return {
        "id": "q-t",
        "type": "temporal",
        "template": "decision_date",
        "answerable": True,
        "challenges": [],
        "support": ["mn-0001"],
        "gold": {"date": date, "event": "e-0031"},
    }


@pytest.mark.parametrize(
    "gold, got, expected",
    [
        ("2027-01-12", "2027-01-12", 1.0),
        ("2027-01-12", "2027-01-13", 0.5),
        ("2027-01-12", "2027-01-11", 0.5),
        ("2027-01-12", "2027-01-14", 0.0),
        ("2027-01-08", "2027-01-11", 0.5),  # Friday -> Monday is one business day
        ("2027-01-08", "2027-01-09", 0.5),  # Friday -> Saturday
        ("2027-01-08", "2027-01-12", 0.0),
    ],
)
def test_temporal(ctx, gold, got, expected):
    ans = {"type": "temporal", "abstain": False, "date": got, "cites": ["mn-0001"]}
    res = score_question(q_temporal(gold), ans, J, ctx)
    assert res.base == expected
    assert res.score == expected  # cite is in support


def test_temporal_bad_date_format_is_invalid(ctx):
    ans = {"type": "temporal", "abstain": False, "date": "12 Jan"}
    assert not score_question(q_temporal(), ans, J, ctx).valid


# ---------------------------------------------------------------- priority
C003_DUE = {**C003}
C006 = loop_item(
    "c-006",
    "Draft the Q1 freight analytics roadmap",
    "p-ben-okoro",
    keywords=["analytics roadmap", "q1 roadmap"],
)


def q_priority(
    must=(C001, C003_DUE), active=(C001, C003_DUE, C006), distractors=(C004, C005), k=10
):
    return {
        "id": "q-f",
        "type": "priority",
        "template": "focus_tomorrow",
        "answerable": True,
        "challenges": [],
        "support": ["em-0001", "nt-0002"],
        "gold": {
            "must_include": list(must),
            "worker_active": list(active),
            "distractors": list(distractors),
            "k": k,
        },
    }


def prio(*texts):
    return {
        "type": "priority",
        "abstain": False,
        "items": [{"text": t, "why": "due soon", "cites": ["nt-0002"]} for t in texts],
    }


def test_priority_gold_dedupes_roles():
    items, roles = priority_gold(q_priority()["gold"])
    assert [i["loop"] for i in items] == ["c-001", "c-003", "c-006", "c-004", "c-005"]
    assert roles == ["must", "must", "active", "distractor", "distractor"]


def test_priority_perfect(ctx):
    res = score_question(
        q_priority(),
        prio("Return the security questionnaire", "Review Samir's ingestion design doc"),
        J,
        ctx,
    )
    assert res.base == 1.0 and res.details["recall"] == 1.0 and res.details["penalty"] == 0.0


def test_priority_other_active_loops_are_not_penalized(ctx):
    res = score_question(
        q_priority(),
        prio(
            "Return the security questionnaire",
            "Review the ingestion design doc",
            "Draft the Q1 analytics roadmap",
        ),
        J,
        ctx,
    )
    assert res.base == 1.0


def test_priority_penalty_for_distractors(ctx):
    # One must-include item (recall 1/2) and one distractor (penalty 1/2) -> 0.25.
    res = score_question(
        q_priority(),
        prio("Return the Tessellate security questionnaire", "Chase Tessellate volume pricing"),
        J,
        ctx,
    )
    assert res.details["recall"] == 0.5 and res.details["penalty"] == 0.5
    assert res.base == pytest.approx(0.25)
    assert res.details["missed_must"] == ["c-003"]


def test_priority_closed_loop_is_a_distractor(ctx):
    res = score_question(
        q_priority(),
        prio(
            "Approve Ben's GL sandbox access request",
            "Return the security questionnaire",
            "Review the ingestion design doc",
        ),
        J,
        ctx,
    )
    assert res.base == pytest.approx(1.0 * (1 - 1 / 3))


def test_priority_only_top_k_counts(ctx):
    ans = prio(
        "Draft the Q1 analytics roadmap",
        "Return the security questionnaire",
        "Review the ingestion design doc",
    )
    res = score_question(q_priority(k=2), ans, J, ctx)
    assert res.details["n_top"] == 2 and res.details["recall"] == 0.5


def test_priority_empty_answer(ctx):
    assert score_question(q_priority(), prio(), J, ctx).base == 0.0
    assert score_question(q_priority(must=(), active=(C006,)), prio(), J, ctx).base == 1.0


def test_priority_empty_must_with_distractor(ctx):
    res = score_question(
        q_priority(must=(), active=(C006,)), prio("Chase Tessellate volume pricing"), J, ctx
    )
    assert res.base == 0.0  # recall 1 x (1 - 1)


# ---------------------------------------------------------------- citations
def test_collect_cites_everywhere():
    ans = {
        "cites": ["em-1"],
        "items": [{"text": "a", "cites": ["em-2"]}, {"text": "b"}],
        "claims": [{"text": "c", "cites": ["em-3", "em-3"]}],
    }
    assert collect_cites(ans) == ["em-1", "em-2", "em-3", "em-3"]


@pytest.mark.parametrize(
    "cite, rid",
    [
        ("loops/x", "loops/x"),
        ("loops/x.md", "loops/x"),
        ("./loops/x.md", "loops/x"),
        ("[[loops/x]]", "loops/x"),
        ("loops/x#Log", "loops/x"),
        ("/people/me.md", "people/me"),
        ("sources/em-0004.md", None),
        ("loops/../people/x", None),
        ("loops", None),
        ("em-0004", None),
    ],
)
def test_store_record_id(cite, rid):
    assert store_record_id(cite) == rid


def test_citation_factor_no_cites(ctx):
    q = q_point("entity", "Cora Velez", "p-cora-velez")
    res = score_question(q, point("Cora Velez", cites=()), J, ctx)
    assert res.citation == 0.0 and res.score == pytest.approx(0.75)


def test_citation_factor_half_valid(ctx):
    q = q_point("entity", "Cora Velez", "p-cora-velez", support=("em-0004",))
    res = score_question(q, point("Cora Velez", cites=("em-0004", "em-0001")), J, ctx)
    assert res.citation == 0.5 and res.score == pytest.approx(0.875)
    assert res.details["citations"]["invalid"] == [{"cite": "em-0001", "why": "not_in_support"}]


def test_citation_reasons(ctx):
    c, d = citation_precision({"cites": ["em-9999", "loops/x", "nonsense"]}, ["em-0004"], ctx)
    assert c == 0.0
    assert [i["why"] for i in d["invalid"]] == ["not_delivered", "unrecognized", "unrecognized"]


def test_store_path_citations(ctx, store):
    sctx = ScoreContext(
        alias_table=ctx.alias_table,
        entities=ctx.entities,
        worker=ctx.worker,
        date=ctx.date,
        delivered=ctx.delivered,
        store_root=store,
    )
    cites = [
        "loops/send-volume-pricing",
        "loops/send-volume-pricing.md",
        "./loops/send-volume-pricing.md",
        "[[people/cora-velez]]",
        "loops/missing",
        "sources/em-0004.md",
    ]
    c, d = citation_precision({"cites": cites}, [], sctx)
    assert d["valid"] == 4 and c == pytest.approx(4 / 6)
    assert {i["why"] for i in d["invalid"]} == {"no_such_record", "unrecognized"}
    # Without a store root, store paths are not checkable and do not count as valid.
    c2, _ = citation_precision({"cites": cites[:1]}, [], ctx)
    assert c2 == 0.0


def test_wrong_answer_scores_zero_even_with_citations(ctx):
    q = q_point("entity", "Cora Velez", "p-cora-velez")
    assert score_question(q, point("Ben Okoro"), J, ctx).score == 0.0


# ---------------------------------------------------------------- whole documents
def test_score_answers_document(ctx):
    doc = {
        "world": "mini",
        "checkpoint": "cp2",
        "date": "2027-01-12",
        "questions": [
            q_point("entity", "Cora Velez", "p-cora-velez", qid="q-1"),
            q_point("number", None, answerable=False, qid="q-2"),
            {**q_temporal(), "id": "q-3"},
        ],
    }
    answers = {"q-1": point("Cora"), "q-2": {"type": "point", "abstain": True}}
    res = score_answers(doc, answers, J, ctx)
    assert [r.id for r in res] == ["q-1", "q-2", "q-3"]
    assert [r.score for r in res] == [1.0, 1.0, 0.0]
    assert all(isinstance(r, QuestionScore) for r in res)
    json.dumps([r.to_dict() for r in res])  # report-ready
    assert [r.score for r in score_answers(doc, None, J, ctx)] == [0.0, 0.0, 0.0]


def test_question_score_metadata(ctx):
    q = q_point("entity", "Cora Velez", "p-cora-velez")
    res = score_question(q, point("Cora"), J, ctx)
    assert (res.id, res.type, res.template, res.answerable, res.challenges) == (
        "q-p",
        "point",
        "loop_owner",
        True,
        ["transfer"],
    )
