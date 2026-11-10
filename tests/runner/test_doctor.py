"""`wcb doctor` on the mini world: a passing adapter, a crashing one and a missing command."""

from __future__ import annotations

from pathlib import Path

from wcb.cli import main
from wcb.paths import repo_root
from wcb.runner.doctor import FAIL, doctor, format_result

ROOT = repo_root()


def _quiet(*_a, **_k):
    pass


def test_null_adapter_passes(tmp_path):
    res = doctor(ROOT / "adapters" / "examples" / "null.yaml", out=tmp_path / "run", echo=_quiet)
    assert res.ok, format_result(res)
    texts = [c.text for c in res.checks]
    assert any("cp2: answers file is valid" in t for t in texts)
    assert any(t == "ingestion did not change the store" for t in texts)  # a warning, not a failure
    assert "WCB score" in res.summary


def test_crashing_agent_fails_with_stderr_tail(tmp_path):
    script = tmp_path / "boom.py"
    script.write_text("import sys\nprint('model key missing', file=sys.stderr)\nsys.exit(3)\n")
    adapter = tmp_path / "boom.yaml"
    adapter.write_text(
        f"name: boom\nversion: '1'\nmodel: none\ncmd: [python, {script}]\ntimeout_s: 30\n"
    )
    res = doctor(adapter, out=tmp_path / "run", echo=_quiet)
    assert not res.ok
    failed = [c for c in res.checks if c.level == FAIL]
    assert any("2027-01-11.ingest: failed (exit 3)" in c.text for c in failed)
    assert any("model key missing" in c.hint for c in failed)
    assert "FAIL" in format_result(res)


def test_missing_command_is_reported(tmp_path):
    adapter = tmp_path / "missing.yaml"
    adapter.write_text("name: m\nversion: '1'\nmodel: none\ncmd: [wcb-no-such-agent-xyz]\n")
    res = doctor(adapter, out=tmp_path / "run", echo=_quiet)
    assert any(
        c.level == FAIL and c.text == "ingest command not found: wcb-no-such-agent-xyz"
        for c in res.checks
    )


def test_invalid_adapter_file(tmp_path):
    adapter = tmp_path / "bad.yaml"
    adapter.write_text("name: bad\n")
    res = doctor(adapter, out=tmp_path / "run", echo=_quiet)
    assert not res.ok and res.run_dir is None


def test_cli_exit_codes(tmp_path, capsys):
    assert main(["doctor", "--adapter", str(Path(ROOT, "adapters/examples/null.yaml")),
                 "--out", str(tmp_path / "ok")]) == 0
    assert "wcb doctor: PASS" in capsys.readouterr().out
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: bad\n")
    assert main(["doctor", "--adapter", str(bad), "--out", str(tmp_path / "bad")]) == 1
