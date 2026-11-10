"""`wcb bundle` archives and the maintainer test-split script."""

from __future__ import annotations

import importlib.util
import json
import tarfile

import pytest

from wcb.cli import main
from wcb.paths import repo_root, resolve_split

ROOT = repo_root()
MINI = ROOT / "tests" / "fixtures" / "mini-world"


@pytest.fixture(scope="module")
def scored_run(tmp_path_factory):
    run = tmp_path_factory.mktemp("bundle") / "run"
    assert main(["run", "--adapter", str(ROOT / "adapters/examples/null.yaml"), "--world",
                 str(MINI), "--out", str(run), "--no-oracle"]) == 0
    return run


def test_bundle_requires_scores(scored_run, tmp_path, capsys):
    assert main(["bundle", str(scored_run), "--out", str(tmp_path / "x.tar.gz")]) == 2
    assert "wcb score" in capsys.readouterr().err


def test_bundle_contents_and_manifest(scored_run, tmp_path):
    assert main(["score", str(scored_run)]) == 0
    out = tmp_path / "results.tar.gz"
    assert main(["bundle", str(scored_run), "--out", str(out)]) == 0
    with tarfile.open(out) as tar:
        names = tar.getnames()
        manifest = json.load(tar.extractfile("results/MANIFEST.json"))
    assert "results/run.json" in names and "results/scores/report.json" in names
    assert "results/adapter/null.yaml" in names
    assert "results/mini/r1/answers/cp2.json" in names
    assert not any(n.endswith(".log") or "/snapshots/" in n for n in names)
    assert set(manifest["files"]) == {n.removeprefix("results/") for n in names} - {"MANIFEST.json"}
    assert manifest["headline"]["wcb"] == pytest.approx(16.67, abs=0.01)
    out2 = tmp_path / "full.tar.gz"
    assert main(["bundle", str(scored_run), "--out", str(out2), "--logs", "--snapshots"]) == 0
    with tarfile.open(out2) as tar:
        names = tar.getnames()
    assert any(n.endswith("stderr.log") for n in names)
    assert any("/snapshots/2027-01-12/projects/" in n for n in names)


def _split_script():
    spec = importlib.util.spec_from_file_location("make_test_split", ROOT / "scripts/make_test_split.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_make_test_split_and_verify(tmp_path, capsys):
    mod = _split_script()
    out = tmp_path / "split"
    assert mod.main(["--release", "9.9", "--out", str(out), "--mix", "small:1"]) == 0
    seeds = json.loads((out / "SEEDS.private.json").read_text())
    commits = json.loads((out / "commitments.json").read_text())
    (w,) = commits["worlds"]
    assert w["id"] == "test-9-9-01" and "seed" not in w
    assert w["seed_sha256"] == mod.seed_commitment(seeds["worlds"][0]["seed"], seeds["worlds"][0]["salt"])
    assert resolve_split(str(out)) == [(out / "test-9-9-01").resolve()]
    assert mod.main(["--verify", str(out)]) == 0
    (out / "commitments.json").write_text(
        json.dumps({**commits, "worlds": [{**w, "world_jsonl_sha256": "0" * 64}]})
    )
    assert mod.main(["--verify", str(out)]) == 1
    assert "MISMATCH" in capsys.readouterr().out
