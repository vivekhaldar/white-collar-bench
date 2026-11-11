"""The judge calibration set: labelled rubric and same-item decisions (docs/judge.md).

`tests/fixtures/judge-calibration/cases.jsonl` holds self-contained decisions (the rubric
item, the question's facts and the answer text, or the predicted and gold items) labelled by
hand under `calibration` after reading the sources and the checkpoint's gold. They come from
real agent prose (the Qwen3.8-27B run in results/2026-11-11-qwen3.8-27b-pi), honest
paraphrases, and adversarial controls: keyword stuffing, lists of every status, role, date or
loop, superseded values asserted as current, wrong owners after a transfer, conflated projects
or people, and merged versus separate events. Cases marked `heldout` were written after the
design was fixed and were not used to tune it. The file is in the `wcb judge` sample format,
so `wcb judge agreement` compares the labellers in it (`calibration`, the judge before this
calibration `heuristic-ed8e033`, and an LLM judge on 100 of the decisions).

These tests check the current heuristic judge against the hand labels in both directions:
every decision agrees except the documented disagreements below, which are limits of a lexical
judge (the LLM judge handles most of them). When a change fixes one, remove it from the list;
when a change breaks one, either fix it or document it here and in docs/judge.md.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from wcb.grade.agreement import agreement, decision_id, read_sample
from wcb.grade.judge import HeuristicJudge

CASES = Path(__file__).parents[1] / "fixtures" / "judge-calibration" / "cases.jsonl"
HUMAN = CASES.with_name("human-sample.jsonl")
J = HeuristicJudge()

#: Decisions where the heuristic judge and the hand label differ, and why.
KNOWN = {
    # Rubric: a contradiction the heuristic cannot see without a stale value in the item.
    "pilot-q044-other-person-r11": "another role for the person; roles have no stale group",
    "held-pilot-q015-stale-r3": "outage told as ongoing; a cleared-blocker item has no stale group",
    "held-pilot-q001-onhold-r1": "'on hold' for an active project with no previous status",
    "pilot-q032-r4-cleared": "blocker told as cleared; the blocker item has no stale group",
    "held-gen-s8-q107-r3-reversed": "hand-off in the wrong direction; names are not ordered",
    "held-gen-s8-q107-r3-still-adwoa": "hand-off denied; only values are checked for negation",
    "pilot-q036-r11-wrong-leader": "one value misattributed, the other fine: missing, not contradicted",
    # Rubric: lexical limits.
    "pilot-q036-chatty-r11": "long sentence of true detail the facts do not hold: passage unfocused",
    "held-pilot-q008-honest-r1": "'the writing-feedback bake-off' is not one of the project's names",
    "held-pilot-q008-honest-r9": "role item without keywords: under 60% of its words",
    "real-gen-s8-w4-cp8-q-107-r5": "'cutover plan' names two loops of the project",
    # Rubric: a dump of every date includes the superseded one (deliberately counted).
    "pilot-q032-padded-r5": "appended date dump includes the old target",
    "stuff-q-032-r5-generic": "date dump includes the old target",
    # same_item: paraphrases with extra framing words, verbose items, sibling items.
    "pilot-q037-sep-reverse": "paraphrase; leftover words look like a different object",
    "pilot-q037-options-sent": "paraphrase; leftover words look like a different object",
    "mini-q008-phase-moved": "paraphrase; leftover words look like a different object",
    "mini-q008-target-moved": "paraphrase; leftover words look like a different object",
    "held-pilot-q014-arb": "paraphrase; leftover words look like a different object",
    "held-pilot-q014-context-api": "paraphrase; leftover words look like a different object",
    "held-pilot-q014-option2": "paraphrase; leftover words look like a different object",
    "pilot-list-draft-the-rfq-requiremen-0": "terse paraphrase sharing too few words",
    "real-gen-s2-w1-cp2-q-018-p5-g5": "verbose prediction: under 40% of its words are the item's",
    "pilot-list-send-scrivelo's-lms-inte-1": "sibling loop sharing 'LMS integration'",
    "pilot-q050-speaker-asked-vs-sent": "the ask and its delivery read alike",
    # same_item: one item describing two gold events matches the less similar one only.
    "held-pilot-q025-dsa-sent-vs-waiting": "one happening, two gold events",
    "mini-q008-merged-make": "merged reversal and replacement",
    "pilot-q037-merged-make": "merged reversal and replacement",
    "pilot-q050-merged-delivered": "merged phase and status change",
    "real-gen-s8-w4-cp8-q-108-p0-g1": "merged phase and status change",
}


def load() -> list[dict]:
    return read_sample(CASES)


def verdict(case: dict):
    i = case["inputs"]
    if case["kind"] == "rubric":
        return J.rubric(i["answer_text"], i["item"], i["facts"])
    return J.same_item(i["pred"], i["gold"], kind=i["kind"])


def test_cases_are_well_formed():
    cases = load()
    assert len(cases) >= 200
    assert len({c["id"] for c in cases}) == len(cases)
    assert len({c["case"] for c in cases}) == len(cases)
    for c in cases:
        assert c["id"] == decision_id(c["kind"], c["inputs"]), c["case"]
        assert c["source"] and c["group"], c["case"]
        label = c["labels"]["calibration"]
        if c["kind"] == "rubric":
            assert label in ("covered", "missing", "contradicted"), c["case"]
        else:
            assert isinstance(label, bool), c["case"]
    kinds = Counter(c["kind"] for c in cases)
    assert kinds["rubric"] >= 150 and kinds["same_item"] >= 60
    assert sum(c["group"] == "real-agent" for c in cases) >= 60
    assert set(KNOWN) <= {c["case"] for c in cases}


@pytest.mark.parametrize("case", load(), ids=lambda c: c["case"])
def test_heuristic_agrees_with_the_hand_labels(case):
    got, want = verdict(case), case["labels"]["calibration"]
    if case["case"] in KNOWN:
        assert got != want, f"{case['case']} now agrees: remove it from KNOWN"
    else:
        assert got == want, (case["case"], case.get("why"))


def test_no_false_positives_on_adversarial_controls():
    # Stuffing, padding, conflated projects and swapped values never earn coverage they lack.
    n = 0
    for c in load():
        if c["kind"] != "rubric" or c["labels"]["calibration"] == "covered":
            continue
        if c["group"] in ("stuffing", "padding", "conflated-project", "history-framing"):
            n += 1
            assert verdict(c) != "covered", c["case"]
    assert n >= 40


def test_agreement_with_the_hand_labels():
    cases = load()
    for c in cases:
        c["labels"]["heuristic"] = verdict(c)
    rows = {(r["kind"], r["a"], r["b"]): r for r in agreement(cases)}
    rubric = rows[("rubric", "calibration", "heuristic")]
    before = rows[("rubric", "calibration", "heuristic-ed8e033")]
    assert rubric["kappa"] >= 0.8 and rubric["kappa"] > before["kappa"] + 0.1
    # Matching was reviewed but not changed (docs/judge.md): no worse than before.
    same = rows[("same_item", "calibration", "heuristic")]
    assert same["kappa"] >= rows[("same_item", "calibration", "heuristic-ed8e033")]["kappa"]


def test_human_sample_is_ready_to_label():
    sample = read_sample(HUMAN)
    assert len(sample) == 100
    ids = {c["id"] for c in load()}
    for r in sample:
        assert r["id"] in ids
        assert r["id"] == decision_id(r["kind"], r["inputs"])
        assert set(r["labels"]) == {"calibration", *[k for k in r["labels"] if k.startswith("llm:")]}
