"""Judge agreement tooling (wcb/grade/agreement.py): kappa, sampling, labelling, collection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_end_to_end import built_world, fabricate_run  # noqa: F401  (fixture re-export)

from wcb.grade import agreement as A
from wcb.grade.judge import HeuristicJudge


def _rec(kind: str, i: int, **labels) -> dict:
    inputs = ({"pred": {"text": f"item {i}"}, "gold": {"what": f"gold {i}"}, "kind": "loop"}
              if kind == "same_item" else {"answer_text": f"answer {i}", "item": {"text": f"x{i}"},
                                           "facts": {}})
    return {"id": f"{kind}-{i}", "kind": kind, "inputs": inputs, "labels": dict(labels)}


def test_cohen_kappa_known_values():
    assert A.cohen_kappa([True, True, False, False], [True, False, False, False]) == pytest.approx(0.5)
    assert A.cohen_kappa(["covered", "missing"], ["covered", "missing"]) == pytest.approx(1.0)
    assert A.cohen_kappa([True, False], [False, True]) == pytest.approx(-1.0)
    assert A.cohen_kappa([True, True], [True, True]) is None  # chance agreement is 1
    assert A.cohen_kappa([], []) is None


def test_recording_judge_records_each_distinct_decision_once():
    rec = A.RecordingJudge(HeuristicJudge())
    pred, gold = {"text": "Send Ola the budget"}, {"what": "Send Ola the budget", "keywords": ["budget"]}
    first = rec.same_item(pred, gold, kind="loop")
    assert rec.same_item(pred, gold, kind="loop") == first
    rec.rubric("The budget went to Ola.", {"text": "budget sent", "keywords": [["budget"]]}, {})
    kinds = sorted(r["kind"] for r in rec.records.values())
    assert kinds == ["rubric", "same_item"]
    r = next(r for r in rec.records.values() if r["kind"] == "same_item")
    assert r["labels"] == {"heuristic": first}
    assert r["id"] == A.decision_id("same_item", r["inputs"])


def test_sampling_is_stratified_and_seeded():
    pool = ([_rec("same_item", i, heuristic=i % 10 == 0) for i in range(100)]
            + [_rec("rubric", i, heuristic="contradicted" if i < 3 else "covered") for i in range(50)])
    s = A.sample_decisions(pool, 20, seed=1)
    assert len(s) == 20 and s == A.sample_decisions(pool, 20, seed=1)
    kinds = [r["kind"] for r in s]
    assert kinds.count("same_item") == 10 and kinds.count("rubric") == 10
    assert sum(r["labels"]["heuristic"] is True for r in s if r["kind"] == "same_item") == 5
    assert sum(r["labels"]["heuristic"] == "contradicted" for r in s) == 3  # all the rare ones
    assert len(A.sample_decisions(pool[:4], 20)) == 4


def test_agreement_rows_and_labelling(tmp_path: Path):
    recs = [_rec("same_item", i, heuristic=i < 2, alice=i < 3) for i in range(4)]
    recs.append(_rec("rubric", 9, heuristic="covered"))
    rows = A.agreement(recs)
    assert len(rows) == 1
    row = rows[0]
    assert (row["kind"], row["a"], row["b"], row["n"]) == ("same_item", "alice", "heuristic", 4)
    assert row["agreement"] == pytest.approx(0.75)
    assert row["confusion"] == {"no / no": 1, "yes / no": 1, "yes / yes": 2}
    assert "alice vs heuristic" in A.format_agreement(rows)

    path = tmp_path / "s.jsonl"
    A.write_sample(path, recs)
    back = A.read_sample(path)
    assert back == recs
    done = A.label_with_judge(back, HeuristicJudge(), "heuristic-again")
    assert done == len(back)
    assert all(isinstance(r["labels"]["heuristic-again"], bool) for r in back[:4])
    assert back[4]["labels"]["heuristic-again"] in A.RUBRIC_VERDICTS
    assert A.label_with_judge(back, HeuristicJudge(), "heuristic-again") == 0  # nothing left

    assert A.parse_human_label("same_item", " Y ") is True
    assert A.parse_human_label("rubric", "x") == "contradicted"
    assert A.parse_human_label("rubric", "maybe") is None


def test_prompt_matches_what_the_llm_judge_sees():
    from wcb.grade.judge import rubric_prompt, same_item_prompt

    s = _rec("same_item", 1)
    assert A.prompt_for(s) == same_item_prompt(s["inputs"]["pred"], s["inputs"]["gold"], "loop")
    r = _rec("rubric", 1)
    assert A.prompt_for(r) == rubric_prompt("answer 1", {"text": "x1"}, {})


def test_collect_decisions_from_a_scored_run(built_world, tmp_path):  # noqa: F811
    run = fabricate_run(tmp_path / "run", built_world, ["perfect", "null"])
    decisions = A.collect_decisions([run])
    kinds = {d["kind"] for d in decisions}
    assert kinds == {"same_item", "rubric"}
    assert len({d["id"] for d in decisions}) == len(decisions)
    assert all(d["labels"]["heuristic"] is not None for d in decisions)
    json.dumps(decisions)  # serializable as a sample file


def test_cli_sample_run_and_agreement(built_world, tmp_path, capsys):  # noqa: F811
    from wcb.cli import main

    run = fabricate_run(tmp_path / "run", built_world, ["perfect"])
    out = tmp_path / "sample.jsonl"
    assert main(["judge", "sample", str(run), "--n", "10", "--out", str(out)]) == 0
    assert main(["judge", "sample", str(run), "--out", str(out)]) == 1  # will not overwrite
    assert main(["judge", "run", str(out), "--judge", "heuristic", "--name", "again"]) == 0
    capsys.readouterr()
    assert main(["judge", "agreement", str(out), "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert rows and all(r["agreement"] == 1.0 for r in rows)
