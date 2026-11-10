"""The null baseline, alone and end to end through the runner with adapters/examples/null.yaml."""

from __future__ import annotations

import json
from pathlib import Path

from wcb.baselines import null
from wcb.contract.answers import check_answers
from wcb.paths import repo_root
from wcb.runner.episode import RunConfig, run
from wcb.runner.workspace import tree_files
from wcb.util.io import read_json


def test_null_query_abstains_on_everything(tmp_path, monkeypatch):
    (tmp_path / ".wcb").mkdir()
    qs = {"date": "2027-03-02", "questions": [{"id": "q-1", "type": "point", "text": "?"},
                                              {"id": "q-2", "type": "status", "text": "?"}]}  # fmt: skip
    (tmp_path / ".wcb" / "questions.json").write_text(json.dumps(qs))
    monkeypatch.setenv("WCB_PHASE", "query")
    monkeypatch.setenv("WCB_WORKSPACE", str(tmp_path))
    assert null.main() == 0
    answers = read_json(tmp_path / ".wcb" / "answers.json")
    assert answers == {
        "q-1": {"type": "point", "abstain": True},
        "q-2": {"type": "status", "abstain": True},
    }
    assert all(not p for p in check_answers(answers, qs["questions"]).values())
    assert read_json(tmp_path / ".wcb" / "usage.json") == null.ZERO_USAGE


def test_null_ingest_changes_nothing_in_the_store(tmp_path, monkeypatch):
    (tmp_path / "people").mkdir()
    (tmp_path / "people" / "me.md").write_text("x\n")
    monkeypatch.setenv("WCB_PHASE", "ingest")
    monkeypatch.setenv("WCB_WORKSPACE", str(tmp_path))
    assert null.main() == 0
    assert tree_files(tmp_path) == ["people/me.md"]


def test_null_rejects_unknown_phase(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("WCB_PHASE", raising=False)
    monkeypatch.setenv("WCB_WORKSPACE", str(tmp_path))
    assert null.main() == 2
    assert "WCB_PHASE" in capsys.readouterr().err


def test_null_baseline_end_to_end(tmp_path: Path, fake_world: Path):
    root = repo_root()
    assert root is not None
    cfg = RunConfig(
        adapter=root / "adapters" / "examples" / "null.yaml",
        worlds=[str(fake_world)],
        split=None,
        track="A",
        repeats=1,
        out=tmp_path / "run",
        workspace_root=tmp_path / "ws",
    )
    assert run(cfg) == 0
    rdir = tmp_path / "run" / "fake" / "r1"
    expected = {
        "cp1-q1": {"type": "point", "abstain": True},
        "cp1-q2": {"type": "list", "abstain": True},
    }
    assert read_json(rdir / "answers" / "cp1.json") == expected
    assert read_json(rdir / "answers" / "cp1.oracle.json") == expected
    for name in ("2027-01-06.ingest", "2027-01-07.ingest", "cp1.query", "cp1.query-oracle"):
        s = read_json(rdir / "sessions" / name / "session.json")
        assert s["status"] == "ok", (
            name,
            s["notes"],
            (rdir / "sessions" / name / "stderr.log").read_text(),
        )
        assert s["usage"] == null.ZERO_USAGE
    # The store never changes: every snapshot equals the seed store.
    seed = tree_files(rdir / "snapshots" / "2027-01-05")
    assert seed == ["CONTRACT.md", "people/me.md"]
    assert tree_files(rdir / "snapshots" / "2027-01-07") == seed == tree_files(rdir / "workspace")
    assert read_json(tmp_path / "run" / "run.json")["adapter"]["name"] == "null-baseline"


def test_agent_files_cannot_shadow_the_baseline_modules(tmp_path: Path, fake_world: Path):
    """The example adapters run `python -I -m ...` in the workspace: modules an agent leaves at
    the store root (json.py, a wcb/ package) must not replace the real ones in later sessions."""
    seed = fake_world / "gold" / "oracle-store" / "2027-01-05"
    for name in ("json.py", "typing.py", "signal.py"):
        (seed / name).write_text('raise SystemExit("shadowed: agent file imported")\n')
    (seed / "wcb").mkdir()
    (seed / "wcb" / "__init__.py").write_text('raise SystemExit("shadowed: agent wcb imported")\n')
    root = repo_root()
    assert root is not None
    cfg = RunConfig(
        adapter=root / "adapters" / "examples" / "null.yaml",
        worlds=[str(fake_world)],
        split=None,
        track="A",
        repeats=1,
        out=tmp_path / "run",
        workspace_root=tmp_path / "ws",
        build=False,
    )
    assert run(cfg) == 0
    rdir = tmp_path / "run" / "fake" / "r1"
    for name in ("2027-01-06.ingest", "2027-01-07.ingest", "cp1.query"):
        s = read_json(rdir / "sessions" / name / "session.json")
        assert s["status"] == "ok", (rdir / "sessions" / name / "stderr.log").read_text()
    assert "json.py" in tree_files(rdir / "snapshots" / "2027-01-07")
