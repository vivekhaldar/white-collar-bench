"""Citation grading (docs/scoring.md, "Citations") and widened gold support (formats.md §3.2).

List and change answers are checked per item: a predicted item's cites must support the gold
item it matched. Other answers are checked against the question as a whole. Gold support is
widened at build time along the world's event threads (`wcb.questions.support`).

The pilot cases are built from `worlds/pilot` sources on the fly (no built gold needed); the
rest use hand-built gold over the mini fixture world.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from wcb.grade.answers import (
    ScoreContext,
    citation_precision,
    cite_groups,
    collect_cites,
    matched_item_support,
    score_question,
)
from wcb.grade.judge import HeuristicJudge
from wcb.questions.build import build_question, load_specs
from wcb.questions.person_evidence import attribute_sources
from wcb.questions.support import ThreadIndex, widen_support
from wcb.questions.templates import TEMPLATES
from wcb.world.model import World
from wcb.world.state import state_at

J = HeuristicJudge()
ROOT = Path(__file__).parents[2]


# ---------------------------------------------------------------- pilot helpers
@pytest.fixture(scope="module")
def pilot() -> World:
    return World.load(ROOT / "worlds" / "pilot")


def pilot_question(world: World, cp: str, qid: str) -> tuple[dict, dict]:
    """(gold question, gold state) for a pilot question, built from the world's sources."""
    date = next(c["date"] for c in world.checkpoints() if c["id"] == cp)
    state = state_at(world, date)
    spec = next(s for s in load_specs(world) if s["id"] == qid and str(s["checkpoint"]) == cp)
    return build_question(spec, world, state), state


@pytest.fixture(scope="module")
def q013(pilot):
    """Pilot cp1 q-013, "What do I owe Sade?": c-055 (weekly update, em-0019) and c-070
    (Council chargeback summary, mt-0008)."""
    q, state = pilot_question(pilot, "cp1", "q-013")
    ctx = ScoreContext.from_state(pilot, state)
    answer = {
        "type": "list",
        "abstain": False,
        "items": [
            {
                "text": g["what"],
                "counterparty": state["entities"][g["counterparty"]]["name"],
                "direction": g["direction"],
                "status": g["status"],
                "due": g["due"],
                "cites": list(g["support"]),
            }
            for g in q["gold"]["items"]
        ],
    }
    return q, answer, ctx


def with_cites(answer: dict, *per_item: list[str]) -> dict:
    out = copy.deepcopy(answer)
    for item, cites in zip(out["items"], per_item, strict=True):
        item["cites"] = list(cites)
    return out


# ---------------------------------------------------------------- pilot: issue #7
def test_pilot_q013_gold_items_have_distinct_support(q013):
    q, _, _ = q013
    assert [(g["loop"], g["support"]) for g in q["gold"]["items"]] == [
        ("c-055", ["em-0019"]),
        ("c-070", ["mt-0008"]),
    ]


def test_pilot_correct_citations_keep_full_credit(q013):
    q, answer, ctx = q013
    s = score_question(q, answer, J, ctx)
    assert (s.base, s.citation, s.score) == (1.0, 1.0, 1.0)
    assert s.details["citations"]["scope"] == "item"


def test_pilot_swapped_citation_scores_lower_with_the_same_base(q013):
    q, answer, ctx = q013
    good = score_question(q, answer, J, ctx)
    swapped = score_question(q, with_cites(answer, ["mt-0008"], ["mt-0008"]), J, ctx)
    assert swapped.base == good.base == 1.0
    assert swapped.citation == pytest.approx(0.5) and swapped.score == pytest.approx(0.875)
    assert swapped.details["citations"]["invalid"] == [
        {"cite": "mt-0008", "why": "wrong_item", "item": 0}
    ]
    # Both items citing both sources: each item has one right and one wrong source.
    both = score_question(
        q, with_cites(answer, ["em-0019", "mt-0008"] * 2, ["mt-0008", "em-0019"]), J, ctx
    )
    assert both.base == 1.0 and both.citation == pytest.approx(0.5)


def test_pilot_swapped_citations_on_both_items(q013):
    q, answer, ctx = q013
    s = score_question(q, with_cites(answer, ["mt-0008"], ["em-0019"]), J, ctx)
    assert s.base == 1.0 and s.citation == 0.0 and s.score == pytest.approx(0.75)
    assert {i["why"] for i in s.details["citations"]["invalid"]} == {"wrong_item"}


@pytest.mark.parametrize(
    "cite, why",
    [
        ("zz-doesnotexist", "not_delivered"),  # no such artifact
        ("em-0033", "not_delivered"),  # a real artifact, delivered after cp1
        ("em-0001", "not_in_support"),  # delivered, about something else
    ],
)
def test_pilot_invalid_sources_fail(q013, cite, why):
    q, answer, ctx = q013
    s = score_question(q, with_cites(answer, [cite], ["mt-0008"]), J, ctx)
    assert s.base == 1.0 and s.citation == pytest.approx(0.5)
    assert s.details["citations"]["invalid"] == [{"cite": cite, "why": why, "item": 0}]


def test_pilot_change_items_are_checked_per_item(pilot):
    q, state = pilot_question(pilot, "cp1", "q-014")
    ctx = ScoreContext.from_state(pilot, state)
    items = q["gold"]["items"]
    answer = {
        "type": "change",
        "abstain": False,
        "items": [
            {
                "text": " ".join([g["summary"], *g["keywords"]]),
                "date": g["date"],
                "cites": g["support"],
            }
            for g in items
        ],
    }
    good = score_question(q, answer, J, ctx)
    assert good.base == 1.0 and good.citation == 1.0
    # Item 0 cites only a source that supports some other change, not its own.
    own = set(items[0]["support"])
    other = next(a for g in items[1:] for a in g["support"] if a not in own)
    bad = copy.deepcopy(answer)
    bad["items"][0]["cites"] = [other]
    s = score_question(q, bad, J, ctx)
    assert s.base == good.base and s.citation < 1.0
    assert {"cite": other, "why": "wrong_item", "item": 0} in s.details["citations"]["invalid"]


# ---------------------------------------------------------------- pilot: widened support
def test_change_item_support_covers_later_updates_only(pilot):
    q, state = pilot_question(pilot, "cp1", "q-014")
    idx = ThreadIndex(pilot, state)
    events = {ev["id"]: ev for ev in state["events"]}
    widened = 0
    for item in q["gold"]["items"]:
        ev = events[item["event"]]
        assert set(ev["artifacts"]) <= set(item["support"])
        thread = idx.primary[ev["id"]]
        later = {
            a
            for e in state["events"]
            if idx.pos[e["id"]] >= idx.pos[ev["id"]] and idx.primary[e["id"]] == thread
            for a in e["artifacts"]
        }
        assert set(item["support"]) == later
        widened += len(item["support"]) > len(ev["artifacts"])
    assert widened  # some change in q-014 has a later update on the same commitment
    assert set(q["support"]) == {a for it in q["gold"]["items"] for a in it["support"]}


@pytest.mark.parametrize("cp, qid", [("cp2", "q-029"), ("cp3", "q-044"), ("cp1", "q-001")])
def test_status_and_brief_support_covers_facts(pilot, cp, qid):
    # An artifact that reveals a recent event, loop or decision in the judge's facts is valid
    # evidence, even when no rubric item names it (issue #7: the Kian consultation plan).
    q, state = pilot_question(pilot, cp, qid)
    template = TEMPLATES[q["template"]]
    _, _, before = template.gold(q["params"], pilot, state)
    assert set(before) <= set(q["support"])
    events = {ev["id"]: ev for ev in state["events"]}
    facts = q["gold"]["facts"]
    for ev in facts.get("recent_events") or []:
        assert set(events[ev["event"]]["artifacts"]) <= set(q["support"]), ev
    for section in ("active_loops", "i_owe", "owed_to_me"):
        for lp in facts.get(section) or []:
            assert set(state["loops"][lp["loop"]]["evidence"]) <= set(q["support"]), lp
    # Each required role must cite evidence tying its value to the named person.
    original = template.gold(q["params"], pilot, state)[1]["rubric"]
    assert [r["support"] for r in q["gold"]["rubric"] if r["aspect"] != "role"] == [
        r["support"] for r in original if r["aspect"] != "role"
    ]
    for role in (r for r in q["gold"]["rubric"] if r["aspect"] == "role"):
        assert role["support"] and set(role["support"]) <= set(
            attribute_sources(pilot, state, q["params"]["person"], "role")
        )
    # Still only delivered artifacts, in delivery order.
    order = {a: i for i, a in enumerate(state["delivered"])}
    assert all(a in order for a in q["support"])
    assert [order[a] for a in q["support"]] == sorted(order[a] for a in q["support"])


def test_brief_widening_reaches_a_closed_loop_in_recent_events(pilot):
    q, state = pilot_question(pilot, "cp2", "q-029")
    template = TEMPLATES[q["template"]]
    _, _, before = template.gold(q["params"], pilot, state)
    added = set(q["support"]) - set(before)
    assert added  # the pilot analogue of the q-038 Kian case
    ctx = ScoreContext.from_state(pilot, state)
    for a in sorted(added):
        c, d = citation_precision({"claims": [{"text": "x", "cites": [a]}]}, q["support"], ctx)
        assert c == 1.0 and d["scope"] == "question"
    c, _ = citation_precision({"cites": ["em-0001"]}, q["support"], ctx)
    assert c == 0.0  # an irrelevant delivered artifact still fails


def test_point_and_temporal_support_unchanged(pilot):
    n = 0
    for spec in load_specs(pilot):
        template = TEMPLATES[spec["template"]]
        if template.qtype not in ("point", "temporal", "list", "priority"):
            continue
        date = next(c["date"] for c in pilot.checkpoints() if c["id"] == str(spec["checkpoint"]))
        state = state_at(pilot, date)
        q = build_question(spec, pilot, state)
        ok, gold, support = template.gold(q["params"], pilot, state)
        if ok and q["template"] == "person_attr" and q["params"]["attribute"] in {"role", "org", "relationship"}:
            evidence = attribute_sources(pilot, state, q["params"]["person"], q["params"]["attribute"])
            assert set(q["support"]) <= set(evidence)
            assert bool(evidence) != bool(q["gold"].get("uncertain"))
        elif ok:
            assert q["support"] == list(support), q["id"]  # loops already carry their thread
            assert q["gold"] == gold
            n += 1
    assert n > 10


def test_widen_support_does_not_mutate_and_is_idempotent(pilot):
    q, state = pilot_question(pilot, "cp1", "q-014")
    template = TEMPLATES[q["template"]]
    _, gold, support = template.gold(q["params"], pilot, state)
    snapshot = copy.deepcopy((gold, support))
    once = widen_support("change", gold, support, pilot, state)
    assert (gold, support) == snapshot
    assert widen_support("change", *once, pilot, state) == once
    assert widen_support("change", {}, [], pilot, state) == ({}, [])


# ---------------------------------------------------------------- hand-built gold (mini world)
def loop_item(loop, what, counterparty, support, due=None, keywords=()):
    return {
        "loop": loop,
        "what": what,
        "counterparty": counterparty,
        "direction": "i_owe",
        "status": "open",
        "due": due,
        "keywords": list(keywords),
        "support": list(support),
    }


QUESTIONNAIRE = loop_item(
    "c-001",
    "Return the Tessellate security questionnaire",
    "p-cora-velez",
    ["em-0001"],
    due="2027-01-12",
    keywords=["security questionnaire", "questionnaire"],
)
DESIGN_DOC = loop_item(
    "c-003",
    "Review Sam Patel's ingestion design doc",
    "p-sam-patel",
    ["em-0002", "nt-0002"],
    due="2027-01-13",
    keywords=["ingestion design", "design doc"],
)


def q_list(*items):
    return {
        "id": "q-l",
        "type": "list",
        "template": "i_owe",
        "answerable": True,
        "challenges": [],
        "support": sorted({a for it in items for a in it["support"]}),
        "gold": {"items": list(items)},
    }


def answer(*cites_per_item, top=()):
    preds = [
        {
            "text": "Return the Tessellate security questionnaire",
            "counterparty": "Cora Velez",
            "status": "open",
            "due": "2027-01-12",
        },
        {
            "text": "Review Samir's ingestion design doc",
            "counterparty": "Sam Patel",
            "status": "open",
            "due": "2027-01-13",
        },
    ]
    for p, cites in zip(preds, cites_per_item, strict=True):
        p["cites"] = list(cites)
    out = {"type": "list", "abstain": False, "items": preds}
    if top:
        out["cites"] = list(top)
    return out


def test_one_source_genuinely_supporting_two_items(ctx):
    # nt-0002 carries evidence for both loops: citing it on both is fully valid.
    q = q_list(
        {**QUESTIONNAIRE, "support": ["em-0001", "nt-0002"]},
        DESIGN_DOC,
    )
    s = score_question(q, answer(["nt-0002"], ["nt-0002"]), J, ctx)
    assert s.base == 1.0 and s.citation == 1.0
    assert s.details["citations"]["total"] == 2  # counted once per item


def test_one_source_supporting_one_item_repeated_on_both(ctx):
    # em-0002 supports only the design-doc loop. Global deduplication used to count it once
    # (c = 1); per item it is right once and wrong once.
    q = q_list(QUESTIONNAIRE, DESIGN_DOC)
    s = score_question(q, answer(["em-0002"], ["em-0002"]), J, ctx)
    assert s.base == 1.0 and s.citation == pytest.approx(0.5)
    assert s.details["citations"]["invalid"] == [
        {"cite": "em-0002", "why": "wrong_item", "item": 0}
    ]
    # Repeating it within one item still counts once.
    s2 = score_question(q, answer(["em-0001"], ["em-0002", "em-0002", "nt-0002"]), J, ctx)
    assert s2.citation == 1.0 and s2.details["citations"]["total"] == 3


def test_unmatched_items_and_top_level_cites_use_question_support(ctx):
    q = q_list(QUESTIONNAIRE, DESIGN_DOC)
    ans = answer(["em-0001"], ["nt-0002"], top=["em-0002", "mt-0001"])
    ans["items"].append(
        {"text": "Book the offsite venue", "counterparty": "Ben", "cites": ["em-0002", "ch-0001"]}
    )
    s = score_question(q, ans, J, ctx)
    assert s.details["unmatched_pred"] == [2]
    inv = s.details["citations"]["invalid"]
    assert {"cite": "mt-0001", "why": "not_in_support"} in inv  # top level
    assert {"cite": "ch-0001", "why": "not_in_support", "item": 2} in inv
    # Valid: em-0001 (item 0), nt-0002 (item 1), em-0002 (top), em-0002 (unmatched item 2).
    assert s.details["citations"]["valid"] == 4 and s.details["citations"]["total"] == 6


def test_matched_item_support_mapping():
    q = q_list(QUESTIONNAIRE, DESIGN_DOC)
    details = {"matches": [{"pred": 1, "gold": "c-001"}, {"pred": 0, "gold": "c-003"}]}
    assert matched_item_support(q, details) == {1: ["em-0001"], 0: ["em-0002", "nt-0002"]}
    no_support = q_list({**QUESTIONNAIRE, "support": []})
    assert matched_item_support(no_support, {"matches": [{"pred": 0, "gold": "c-001"}]}) == {}
    assert matched_item_support({"type": "point"}, {}) is None
    assert matched_item_support({"type": "priority", "gold": {}}, {"matches": []}) is None


def test_optional_suggestion_keeps_its_item_evidence(ctx):
    q = q_list(QUESTIONNAIRE)
    q["gold"]["suggested"] = [DESIGN_DOC]
    result = score_question(q, answer(["em-0001"], ["em-0002"]), J, ctx)
    assert result.base == result.citation == 1
    assert result.details["unmatched_pred"] == []


def test_cite_groups_keep_positions():
    ans = {"cites": ["em-1"], "items": [{"cites": ["em-2"]}, "junk", {"text": "x"}]}
    assert cite_groups(ans) == [("cites", ["em-1"]), ("items[0]", ["em-2"]), ("items[2]", [])]
    assert collect_cites(ans) == ["em-1", "em-2"]


# ---------------------------------------------------------------- store paths, per item
def store_ctx(ctx, store):
    return ScoreContext(
        alias_table=ctx.alias_table,
        entities=ctx.entities,
        worker=ctx.worker,
        date=ctx.date,
        delivered=ctx.delivered,
        store_root=store,
    )


def test_store_record_must_carry_the_items_evidence(ctx, store):
    # people/cora-velez cites em-0001 (the questionnaire's evidence) and nothing else.
    sctx = store_ctx(ctx, store)
    q = q_list(QUESTIONNAIRE, DESIGN_DOC)
    right = score_question(q, answer(["[[people/cora-velez]]"], ["nt-0002"]), J, sctx)
    assert right.citation == 1.0
    # Attached to the design-doc item, the record mentions a valid artifact of the question,
    # but not one that supports this item: no laundering.
    wrong = score_question(q, answer(["em-0001"], ["./people/cora-velez.md"]), J, sctx)
    assert wrong.base == 1.0 and wrong.citation == pytest.approx(0.5)
    assert wrong.details["citations"]["invalid"] == [
        {"cite": "./people/cora-velez.md", "why": "wrong_item", "item": 1}
    ]


def test_store_record_mentioning_an_unrelated_artifact_fails(ctx, store):
    # loops/send-volume-pricing cites em-0004: delivered and real, but not about this question.
    sctx = store_ctx(ctx, store)
    q = q_list(QUESTIONNAIRE, DESIGN_DOC)
    s = score_question(q, answer(["loops/send-volume-pricing"], ["nt-0002"]), J, sctx)
    assert s.citation == pytest.approx(0.5)
    assert s.details["citations"]["invalid"] == [
        {"cite": "loops/send-volume-pricing", "why": "record_unsupported", "item": 0}
    ]


def test_store_paths_normalize_per_item_and_shortcuts_fail(ctx, store):
    sctx = store_ctx(ctx, store)
    q = q_list(QUESTIONNAIRE, DESIGN_DOC)
    cites0 = ["people/cora-velez", "./people/cora-velez.md", "people/cora-velez#Log", "people/me"]
    s = score_question(q, answer(cites0, ["loops/missing", "nt-0002"]), J, sctx)
    d = s.details["citations"]
    assert d["total"] == 4 and d["valid"] == 2  # the three cora forms are one record
    assert {(i["cite"], i["why"], i["item"]) for i in d["invalid"]} == {
        ("people/me", "worker_record", 0),
        ("loops/missing", "no_such_record", 1),
    }


def test_question_scoped_types_still_pool_and_deduplicate(ctx):
    # A brief: claims are not item-structured, so a repeated source counts once.
    q = {
        "id": "q-b",
        "type": "brief",
        "template": "person_brief",
        "answerable": True,
        "support": ["em-0001"],
        "gold": {"rubric": [], "facts": {}},
    }
    ans = {
        "type": "brief",
        "abstain": False,
        "summary": "x",
        "claims": [
            {"text": "a", "cites": ["em-0001"]},
            {"text": "b", "cites": ["em-0001", "em-0002"]},
        ],
    }
    s = score_question(q, ans, J, ctx)
    assert s.details["citations"]["scope"] == "question"
    assert s.citation == pytest.approx(0.5)
    assert s.details["citations"]["invalid"] == [{"cite": "em-0002", "why": "not_in_support"}]
