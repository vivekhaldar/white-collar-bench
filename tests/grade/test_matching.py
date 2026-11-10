"""Candidate generation and one-to-one matching of predicted items to gold items."""

from __future__ import annotations

from wcb.grade.judge import HeuristicJudge
from wcb.grade.matching import (
    CANDIDATE_SIMILARITY,
    assign,
    candidate_pairs,
    match_items,
    similarity,
)

GOLD = [
    {
        "loop": "c-001",
        "what": "Return the Tessellate security questionnaire",
        "counterparty": "p-cora-velez",
        "keywords": ["security questionnaire", "questionnaire"],
        "support": ["em-0001"],
    },
    {
        "loop": "c-002",
        "what": "Send Ada the January reconciliation report",
        "counterparty": "p-ben-okoro",
        "keywords": ["reconciliation report", "january"],
        "support": ["ch-0001"],
    },
    {
        "loop": "c-003",
        "what": "Review Sam Patel's ingestion design doc",
        "counterparty": "p-sam-patel",
        "keywords": ["ingestion design", "design doc"],
        "support": ["em-0002", "nt-0002"],
    },
]


class Always:
    """Judge that confirms (or rejects) every pair it is asked about."""

    def __init__(self, answer=True):
        self.answer = answer
        self.name = "always"
        self.calls = []

    def same_item(self, pred, gold, *, kind):
        self.calls.append((pred.get("text"), gold.get("loop"), kind))
        return self.answer

    def rubric(self, *_):  # pragma: no cover - unused
        return "missing"


def test_candidate_by_shared_citation(ctx):
    pred = [{"text": "Something entirely different", "cites": ["nt-0002"]}]
    assert candidate_pairs(pred, GOLD, ctx) == [(0, 2)]


def test_candidate_by_counterparty(ctx):
    pred = [{"text": "Unrelated words here", "counterparty": "Ben"}]
    assert candidate_pairs(pred, GOLD, ctx) == [(0, 1)]
    # An ambiguous name is not a counterparty hit.
    sam = {"text": "Unrelated words about something else entirely", "counterparty": "Sam"}
    assert candidate_pairs([sam], GOLD, ctx) == []
    # Without a context the counterparty route is off.
    assert candidate_pairs(pred, GOLD, None) == []


def test_candidate_by_similarity(ctx):
    pred = [{"text": "Security questionnaire for Tessellate"}]
    assert candidate_pairs(pred, GOLD, ctx) == [(0, 0)]
    assert similarity(pred[0], GOLD[0]) >= CANDIDATE_SIMILARITY


def test_unrelated_items_are_not_candidates(ctx):
    pred = [{"text": "Book the team offsite", "counterparty": "Nobody Known", "cites": ["em-0003"]}]
    assert candidate_pairs(pred, GOLD, ctx) == []


def test_similarity_bounds():
    assert similarity({"text": ""}, GOLD[0]) == 0.0
    assert similarity({"text": "Return the Tessellate security questionnaire"}, GOLD[0]) > 0.9


def test_match_items_with_heuristic_judge(ctx):
    pred = [
        {"text": "Review Samir's ingestion doc", "counterparty": "Samir"},
        {"text": "Send Cora the completed security questionnaire", "counterparty": "Cora"},
        {"text": "Plan the offsite"},
    ]
    assert match_items(pred, GOLD, HeuristicJudge(), kind="loop", ctx=ctx) == [(0, 2), (1, 0)]


def test_match_items_is_one_to_one(ctx):
    pred = [
        {"text": "Return the security questionnaire"},
        {"text": "Return the security questionnaire"},
    ]
    pairs = match_items(pred, GOLD, HeuristicJudge(), kind="loop", ctx=ctx)
    assert len(pairs) == 1 and pairs[0][1] == 0


def test_match_items_only_confirmed_pairs(ctx):
    pred = [{"text": "Return the security questionnaire", "cites": ["em-0001"]}]
    assert match_items(pred, GOLD, Always(False), kind="loop", ctx=ctx) == []


def test_match_items_asks_each_pair_once_and_passes_kind(ctx):
    judge = Always(True)
    item = {"text": "Security questionnaire", "cites": ["em-0001"]}
    match_items([item, dict(item)], GOLD, judge, kind="change", ctx=ctx)
    assert judge.calls == [("Security questionnaire", "c-001", "change")]


def test_match_items_shows_counterparty_name_to_judge(ctx):
    seen = []

    class Recorder(Always):
        def same_item(self, pred, gold, *, kind):
            seen.append(gold)
            return True

    match_items([{"text": "x", "counterparty": "Cora"}], GOLD, Recorder(), kind="loop", ctx=ctx)
    assert seen[0]["counterparty_name"] == "Cora Velez"
    assert "counterparty_name" not in GOLD[0]  # gold is not mutated


def test_assign_greedy_then_augmenting_paths():
    # Greedy alone would take (0, 0) and leave pred 1 unmatched; the augmenting path moves
    # pred 0 to gold 1 so both predictions match.
    edges = [(0.9, 0, 0), (0.8, 0, 1), (0.7, 1, 0)]
    assert assign(edges) == [(0, 1), (1, 0)]


def test_assign_prefers_higher_similarity_when_cardinality_ties():
    edges = [(0.4, 0, 0), (0.9, 1, 0)]
    assert assign(edges) == [(1, 0)]


def test_assign_empty():
    assert assign([]) == []


def test_assign_is_maximum_on_a_chain():
    # p0-g0, p1-g0, p1-g1, p2-g1, p2-g2: the maximum matching has 3 pairs.
    edges = [(0.9, 1, 0), (0.9, 2, 1), (0.5, 0, 0), (0.5, 1, 1), (0.1, 2, 2)]
    pairs = assign(edges)
    assert len(pairs) == 3
    assert len({j for _, j in pairs}) == 3
