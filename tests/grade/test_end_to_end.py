"""End to end: fabricate a run directory, score it with `score_run`, and check the report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from wcb.baselines.gold_answers import perfect_answers
from wcb.baselines.null import abstain_all
from wcb.cli import main as wcb_main
from wcb.grade.score import Report, score_run
from wcb.paths import contract_dir
from wcb.questions.build import visible_questions
from wcb.store.oracle import record_ids
from wcb.util.io import write_json
from wcb.world.build import build_world
from wcb.world.model import World

ADAPTER = {"name": "fixture-agent", "version": "0.0.1", "model": "none"}
USAGE = {"input_tokens": 1000, "output_tokens": 100, "cost_usd": 0.01, "tool_calls": 4}


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


def fabricate_run(
    run_dir: Path,
    world: World,
    episodes: list[str],
    *,
    track: str = "A",
    oracle: bool = True,
    options: dict | None = None,
) -> Path:
    """Write a run directory like `wcb run` would (docs/formats.md §6).

    `episodes[k-1]` says what repeat k's agent did: 'perfect' (gold answers, oracle stores as
    snapshots), 'null' (abstains everywhere), or 'missing' (no answers, no snapshots).
    Oracle answers are perfect for every repeat when `oracle` is True.
    """
    meta = {
        "wcb_version": "0.1.0",
        "adapter": ADAPTER,
        "track": track,
        "oracle": oracle,
        "worlds": [{"id": world.id, "path": str(world.dir), "repeats": len(episodes)}],
        "status": "completed",
        "options": options or {},
    }
    write_json(run_dir / "run.json", meta)
    ids = record_ids(world)
    for k, kind in enumerate(episodes, 1):
        ep = run_dir / world.id / f"r{k}"
        ep.mkdir(parents=True)
        if kind == "missing":
            continue
        for d in [world.seed_end, *world.episode_days()]:
            snap = ep / "snapshots" / d
            shutil.copytree(world.dir / "gold" / "oracle-store" / d, snap)
            shutil.copyfile(contract_dir() / "CONTRACT.md", snap / "CONTRACT.md")
        for d in world.episode_days():
            session(ep, f"{d}.ingest", phase="ingest", date=d, store="agent", wall_s=30.0)
        for cp in world.checkpoints():
            doc = gold_doc(world, cp["id"])
            answers = (
                perfect_answers(doc, ids)
                if kind == "perfect"
                else abstain_all(visible_questions(doc))
            )
            write_json(ep / "answers" / f"{cp['id']}.json", answers)
            session(
                ep, f"{cp['id']}.query", phase="query", date=cp["date"], store="agent", wall_s=10.0
            )
            if oracle:
                write_json(ep / "answers" / f"{cp['id']}.oracle.json", perfect_answers(doc, ids))
                session(
                    ep,
                    f"{cp['id']}.query-oracle",
                    phase="query",
                    date=cp["date"],
                    store="oracle",
                    wall_s=8.0,
                )
    return run_dir


def session(ep: Path, name: str, *, phase: str, date: str, store: str, wall_s: float) -> None:
    write_json(
        ep / "sessions" / name / "session.json",
        {
            "phase": phase,
            "date": date,
            "checkpoint": name.split(".")[0] if phase == "query" else None,
            "store": store,
            "exit_code": 0,
            "timed_out": False,
            "wall_s": wall_s,
            "usage": USAGE,
            "status": "ok",
        },
    )


# ---------------------------------------------------------------- the main scenario
@pytest.fixture(scope="module")
def scored(built_world, tmp_path_factory):
    """Repeat 1 is perfect; repeat 2 abstains everywhere and drops a loop on the last day."""
    run = fabricate_run(tmp_path_factory.mktemp("run") / "run", built_world, ["perfect", "null"])
    last = run / built_world.id / "r2" / "snapshots" / built_world.episode_days()[-1]
    (last / "loops" / "review-sam-patel-s-ingestion-design-doc.md").unlink()
    report = score_run(run)
    return run, report


def test_report_files_are_written(scored):
    run, report = scored
    assert isinstance(report, Report)
    data = json.loads((run / "scores" / "report.json").read_text("utf-8"))
    assert data["headline"] == report.data["headline"]
    md = (run / "scores" / "report.md").read_text("utf-8")
    for heading in (
        "## Headline",
        "## By question type",
        "## By planted challenge",
        "## By checkpoint",
        "## Store integrity per day",
        "## Efficiency",
        "## Failure samples",
    ):
        assert heading in md


def test_headline_numbers(scored):
    _, report = scored
    h = report.data["headline"]
    perfect, null = report.data["worlds"][0]["repeats"]
    assert perfect["score"] >= 95
    # Null answers: cp1 earns only its unanswerable bucket (1 of 3 buckets), cp2 earns nothing.
    assert null["score"] == pytest.approx(100 / 6)
    assert h["wcb"] == pytest.approx((perfect["score"] + null["score"]) / 2)
    assert h["wcb_ci95"] == [h["wcb"], h["wcb"]]  # one world: degenerate interval
    assert h["synthesis"] >= 95
    assert h["ingestion_cost"] == pytest.approx(h["synthesis"] - h["wcb"])
    assert (h["n_worlds"], h["n_episodes"], h["n_questions"]) == (1, 2, 26)
    assert perfect["sis"]["mean"] == pytest.approx(100.0)
    assert null["sis"]["final"] < 100.0 and null["sis"]["final_date"] == "2027-01-12"
    assert h["sis_final"] < h["sis"] < 100.0


def test_breakdowns(scored):
    _, report = scored
    b = report.data["breakdowns"]
    assert list(b["by_type"])[-1] == "unanswerable"
    assert b["by_type"]["unanswerable"]["wcb"] == pytest.approx(100.0)
    assert b["by_type"]["list"]["wcb"] == pytest.approx(50.0, abs=2.5)
    assert b["by_type"]["list"]["n"] == 8
    assert "transfer" in b["by_challenge"]
    cps = {c["checkpoint"]: c for c in b["by_checkpoint"]}
    assert cps["cp1"]["day_index"] == 1 and cps["cp2"]["day_index"] == 2
    days = report.data["sis_by_day"]
    assert [d["date"] for d in days] == ["2027-01-11", "2027-01-12"]
    assert days[0]["sis"] == pytest.approx(100.0) and days[1]["loop_f1"] < 1.0


def test_failure_samples_and_question_rows(scored):
    _, report = scored
    fails = report.data["failures"]
    assert 0 < len(fails) <= 10
    assert all(f["repeat"] == 2 and f["score"] < 1 for f in fails)
    assert all("gold" in f and "predicted" in f for f in fails)
    assert fails[0]["predicted"]["abstain"] is True
    rows = report.data["questions"]
    assert {r["store"] for r in rows} == {"agent", "oracle"}
    assert len(rows) == 2 * 2 * 13


def test_efficiency(scored):
    _, report = scored
    eff = report.data["efficiency"]
    assert eff["summary"]["ingest"]["sessions"] == 4
    assert eff["summary"]["ingest"]["wall_s"]["total"] == pytest.approx(120.0)
    assert eff["summary"]["query"]["input_tokens"]["total"] == pytest.approx(4000)
    assert eff["summary"]["query_oracle"]["sessions"] == 4
    assert eff["per_episode"]["cost_usd"] == pytest.approx(0.04)
    assert len(eff["per_ingest_day"]) == 2


def test_summary_text(scored):
    _, report = scored
    text = report.summary_text()
    assert text.startswith("WCB score (Track A): ")
    assert f"{report.data['headline']['wcb']:.1f}" in text
    assert "Synthesis" in text and "SIS" in text and "report.json" in text


def test_rescoring_is_stable(scored, tmp_path):
    run, report = scored
    again = score_run(run, out_dir=tmp_path / "again")
    assert again.data["headline"] == report.data["headline"]
    assert (tmp_path / "again" / "report.md").is_file()


# ---------------------------------------------------------------- robustness
def test_missing_answers_and_snapshots_score_zero_with_notes(built_world, tmp_path):
    run = fabricate_run(tmp_path / "run", built_world, ["perfect", "missing"])
    (run / built_world.id / "r1" / "answers" / "cp2.json").unlink()
    report = score_run(run)
    perfect, missing = report.data["worlds"][0]["repeats"]
    assert missing["score"] == 0.0 and missing["sis"] is None
    assert perfect["checkpoints"][1]["score"] == 0.0
    notes = "\n".join(report.data["notes"])
    assert "r1: answers/cp2.json is missing" in notes
    assert "r2: no snapshots" in notes
    assert report.data["headline"]["sis"] == pytest.approx(100.0)


def test_impossible_temporal_date_scores_zero_without_stopping_the_run(built_world, tmp_path):
    # The schema only checks the YYYY-MM-DD pattern, so 2027-02-30 is a valid answer; it used
    # to raise from the business-day arithmetic and abort `wcb score` for the whole run.
    run = fabricate_run(tmp_path / "run", built_world, ["perfect"])
    path = run / built_world.id / "r1" / "answers" / "cp2.json"
    answers = json.loads(path.read_text("utf-8"))
    qid = next(q["id"] for q in gold_doc(built_world, "cp2")["questions"] if q["type"] == "temporal")
    answers[qid] = {"type": "temporal", "abstain": False, "date": "2027-02-30", "cites": []}
    write_json(path, answers)
    report = score_run(run)
    row = next(
        r for r in report.data["questions"] if r["id"] == qid and r["store"] == "agent"
    )
    assert row["valid"] and row["score"] == 0.0
    assert report.data["headline"]["wcb"] > 80


def test_grader_errors_score_zero_with_a_note(built_world, tmp_path, monkeypatch):
    import wcb.grade.answers as answers_mod

    def broken(q, answer, judge, ctx):
        raise ValueError("cannot read this answer")

    monkeypatch.setitem(answers_mod.GRADERS, "temporal", broken)
    run = fabricate_run(tmp_path / "run", built_world, ["perfect"])
    report = score_run(run)
    rows = [r for r in report.data["questions"] if r["type"] == "temporal"]
    assert rows and all(r["score"] == 0.0 for r in rows)
    notes = "\n".join(report.data["notes"])
    assert "could not be graded (ValueError: cannot read this answer)" in notes


def test_track_b_has_no_sis_or_synthesis(built_world, tmp_path):
    run = fabricate_run(tmp_path / "run", built_world, ["perfect"], track="B", oracle=False)
    report = score_run(run)
    h = report.data["headline"]
    assert h["wcb"] >= 95 and h["synthesis"] is None and h["sis"] is None
    assert "SIS" not in report.summary_text()


def test_skip_ingest_reports_synthesis_only(built_world, tmp_path):
    run = fabricate_run(tmp_path / "run", built_world, ["missing"], options={"skip_ingest": True})
    ep = run / built_world.id / "r1"
    for cp in built_world.checkpoints():
        doc = gold_doc(built_world, cp["id"])
        write_json(ep / "answers" / f"{cp['id']}.oracle.json", perfect_answers(doc))
    h = score_run(run).data["headline"]
    assert h["wcb"] is None and h["sis"] is None and h["synthesis"] >= 95


def test_gold_questions_are_built_when_missing(built_world, tmp_path):
    world_copy = tmp_path / "mini-world"
    shutil.copytree(built_world.dir, world_copy)
    run = fabricate_run(tmp_path / "run", World.load(world_copy), ["perfect"])
    shutil.rmtree(world_copy / "gold" / "questions")
    shutil.rmtree(world_copy / "gold" / "state")
    report = score_run(run)
    assert report.data["headline"]["wcb"] >= 95
    assert any("gold/questions/cp1.json missing" in n for n in report.data["notes"])


def test_missing_run_json_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        score_run(tmp_path)


def test_cli_score(built_world, tmp_path, capsys):
    run = fabricate_run(tmp_path / "run", built_world, ["perfect"])
    assert wcb_main(["score", str(run), "--out", str(tmp_path / "out")]) == 0
    assert "WCB score (Track A)" in capsys.readouterr().out
    assert (tmp_path / "out" / "report.json").is_file()
    assert (tmp_path / "out" / "report.md").is_file()
