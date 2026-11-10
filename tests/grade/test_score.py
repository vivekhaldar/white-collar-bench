"""Run scoring building blocks: perfect and null answers, aggregation and confidence intervals."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from wcb.baselines.gold_answers import perfect_answers
from wcb.baselines.null import abstain_all
from wcb.contract.answers import check_answers
from wcb.grade.answers import QuestionScore, ScoreContext, score_answers
from wcb.grade.judge import HeuristicJudge
from wcb.grade.score import (
    UNANSWERABLE,
    bootstrap_ci,
    checkpoint_score,
    diff,
    mean,
    question_bucket,
    read_answers,
)
from wcb.questions.build import visible_questions
from wcb.store.oracle import record_ids
from wcb.world.build import build_world
from wcb.world.model import World
from wcb.world.state import state_at

J = HeuristicJudge()


@pytest.fixture(scope="module")
def built_world(tmp_path_factory, request) -> World:
    """A copy of the mini world with everything under gold/ freshly built."""
    src = Path(request.config.rootpath) / "tests" / "fixtures" / "mini-world"
    dst = tmp_path_factory.mktemp("built") / "mini-world"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("gold", "manifest.json"))
    result = build_world(dst)
    assert result.ok, result.format()
    return World.load(dst)


def gold_doc(world: World, cp_id: str) -> dict:
    return json.loads((world.dir / "gold" / "questions" / f"{cp_id}.json").read_text("utf-8"))


def contexts(world: World):
    """(checkpoint, gold doc, context over the oracle store) for every checkpoint."""
    for cp in world.checkpoints():
        state = state_at(world, cp["date"])
        store = world.dir / "gold" / "oracle-store" / cp["date"]
        yield cp, gold_doc(world, cp["id"]), ScoreContext.from_state(world, state, store_root=store)


# ---------------------------------------------------------------- perfect and null answers
@pytest.mark.parametrize("with_store_ids", [False, True])
def test_perfect_answers_score_full_marks(built_world, with_store_ids):
    ids = record_ids(built_world) if with_store_ids else None
    n = 0
    for cp, doc, ctx in contexts(built_world):
        answers = perfect_answers(doc, ids)
        assert not any(check_answers(answers, doc["questions"]).values())
        for s in score_answers(doc, answers, J, ctx):
            assert s.score >= 0.95, (cp["id"], s.id, s.details)
            n += 1
    assert n == 13


def test_perfect_answers_cite_store_records(built_world):
    doc = gold_doc(built_world, "cp1")
    answers = perfect_answers(doc, record_ids(built_world))
    cites = [c for it in answers["q-001"]["items"] for c in it["cites"]]
    assert "loops/return-the-tessellate-security-questionnaire" in cites
    assert answers["q-004"] == {"type": "point", "abstain": True}


def test_perfect_answers_names(built_world):
    doc = gold_doc(built_world, "cp1")
    plain = perfect_answers(doc)
    assert plain["q-001"]["items"][0]["counterparty"] == "cora velez"
    named = perfect_answers(doc, entity_names={"p-cora-velez": "Cora"})
    assert named["q-001"]["items"][0]["counterparty"] == "Cora"
    via_store = perfect_answers(doc, record_ids(built_world))
    assert via_store["q-002"]["items"][0]["counterparty"] == "cora velez"


def test_null_answers_score_only_on_unanswerable(built_world):
    seen_unanswerable = 0
    for _, doc, ctx in contexts(built_world):
        answers = abstain_all(visible_questions(doc))
        for s in score_answers(doc, answers, J, ctx):
            if s.answerable:
                assert s.score == 0.0, s.id
            else:
                assert s.score == 1.0, s.id
                seen_unanswerable += 1
    assert seen_unanswerable == 1


# ---------------------------------------------------------------- aggregation
def qs(qid: str, qtype: str, score: float, answerable: bool = True) -> QuestionScore:
    return QuestionScore(
        id=qid,
        type=qtype,
        template="t",
        answerable=answerable,
        challenges=[],
        valid=True,
        abstained=False,
        base=score,
        citation=1.0,
        score=score,
        details={},
    )


def test_checkpoint_score_is_a_macro_average_over_buckets():
    scores = [
        qs("a", "list", 1.0),
        qs("b", "list", 1.0),
        qs("c", "list", 1.0),
        qs("d", "point", 0.0),
        qs("e", "point", 1.0, answerable=False),
    ]
    value, buckets = checkpoint_score(scores)
    assert buckets == {"point": 0.0, "list": 1.0, UNANSWERABLE: 1.0}
    assert value == pytest.approx(2 / 3)
    assert question_bucket(scores[-1]) == UNANSWERABLE
    assert checkpoint_score([]) == (None, {})


def test_bootstrap_ci():
    assert bootstrap_ci([]) is None
    assert bootstrap_ci([42.0]) == [42.0, 42.0]
    values = [10.0, 50.0, 60.0, 90.0]
    lo, hi = bootstrap_ci(values)
    assert min(values) <= lo <= mean(values) <= hi <= max(values)
    assert bootstrap_ci(values) == [lo, hi]  # deterministic seed


def test_numeric_helpers():
    assert mean([None, 1.0, 3.0]) == 2.0 and mean([None]) is None
    assert diff(90.0, 70.0) == 20.0 and diff(None, 1.0) is None


def test_read_answers(tmp_path):
    assert read_answers(tmp_path / "none.json") == ({}, "is missing")
    (tmp_path / "bad.json").write_text("{", encoding="utf-8")
    assert read_answers(tmp_path / "bad.json") == ({}, "is not valid JSON")
    (tmp_path / "list.json").write_text("[]", encoding="utf-8")
    assert read_answers(tmp_path / "list.json") == ({}, "is not a JSON object")
    (tmp_path / "ok.json").write_text('{"q-1": {"type": "point", "abstain": true}}', "utf-8")
    assert read_answers(tmp_path / "ok.json")[1] is None
