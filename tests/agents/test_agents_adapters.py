"""Example adapters parse, carry the required keys, and the custom-agent template works."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "adapters" / "examples"
NEW_EXAMPLES = ["claude-code", "codex", "simple-anthropic", "simple-openai", "custom-script"]
KNOWN_KEYS = {
    "name", "version", "model", "description", "cmd", "cwd", "timeout_s", "env",
    "env_passthrough", "ingest", "query",
}  # fmt: skip
PLACEHOLDERS = {"workspace", "prompt", "prompt_text", "date", "phase", "track", "session_dir",
                "adapter_dir"}  # fmt: skip
VARS = {
    "workspace": "/tmp/wcb-ws-test/my store",
    "prompt": "/tmp/session/prompt.md",
    "prompt_text": "Today is 2027-03-01. Do the task.",
    "date": "2027-03-01",
    "phase": "ingest",
    "track": "A",
    "session_dir": "/tmp/session",
}


@pytest.mark.parametrize("name", NEW_EXAMPLES)
def test_example_yaml_has_required_keys(name):
    data = yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text())
    assert isinstance(data, dict)
    assert set(data) <= KNOWN_KEYS, set(data) - KNOWN_KEYS
    assert data["name"] and data["version"] and data["model"]
    assert data.get("cmd"), "every example sets a top-level cmd used by both phases"
    for phase in ("ingest", "query"):
        assert data[phase]["timeout_s"] > 0
        assert set(data[phase]) <= {"cmd", "cwd", "timeout_s"}
    cmd = data["cmd"] if isinstance(data["cmd"], str) else " ".join(data["cmd"])
    used = set(re.findall(r"(?<!\$)\{([A-Za-z_][A-Za-z0-9_]*)\}", cmd))
    assert used <= PLACEHOLDERS
    for k in data.get("env_passthrough", []):
        assert k.isupper()


@pytest.mark.parametrize("name", NEW_EXAMPLES)
def test_example_loads_with_the_runner_without_warnings(name):
    adapter_mod = pytest.importorskip("wcb.runner.adapter")
    a = adapter_mod.load_adapter(EXAMPLES / f"{name}.yaml")
    assert a.warnings == []
    for phase in ("ingest", "query"):
        cmd, cwd, timeout = a.command(phase, {**VARS, "phase": phase})
        text = cmd if isinstance(cmd, str) else " ".join(cmd)
        assert "{" not in text.replace("${", "")  # every placeholder was filled
        assert timeout > 0


def test_cli_adapters_use_the_documented_flags():
    claude = yaml.safe_load((EXAMPLES / "claude-code.yaml").read_text())["cmd"]
    assert claude[:6] == ["python", "-m", "wcb.agents.wrap", "--format", "claude", "--"]
    for flag in ("--print", "--dangerously-skip-permissions", "--no-session-persistence"):
        assert flag in claude
    assert "{prompt_text}" in claude
    codex = yaml.safe_load((EXAMPLES / "codex.yaml").read_text())["cmd"]
    for flag in ("codex exec", "--cd {workspace}", "--sandbox workspace-write",
                 "--skip-git-repo-check", "--json"):  # fmt: skip
        assert flag in codex
    for name, key in (
        ("simple-anthropic", "ANTHROPIC_API_KEY"),
        ("simple-openai", "OPENAI_API_KEY"),
    ):
        data = yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text())
        assert data["cmd"][:3] == ["python", "-m", "wcb.agents.simple"]
        assert key in data["env_passthrough"]


def test_simple_adapter_cli_matches_the_harness_parser():
    from wcb.agents.simple import build_parser

    for name in ("simple-anthropic", "simple-openai"):
        cmd = yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text())["cmd"]
        args = build_parser().parse_args(cmd[3:])
        assert args.provider in ("anthropic", "openai") and args.max_turns == 80


# ---------------------------------------------------------------- the template
def _run_template(ws: Path, phase: str, date: str, tmp_path: Path):
    session = tmp_path / f"session-{phase}"
    session.mkdir(exist_ok=True)
    (session / "prompt.md").write_text(f"Today is {date}.")
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("WCB_")},
        "WCB_PHASE": phase,
        "WCB_DATE": date,
        "WCB_TRACK": "A",
        "WCB_WORKSPACE": str(ws),
        "WCB_PROMPT_FILE": str(session / "prompt.md"),
        "WCB_SESSION_DIR": str(session),
        "PYTHONPATH": str(REPO),
    }
    return subprocess.run(
        [sys.executable, str(EXAMPLES / "custom_agent_template.py")],
        capture_output=True, text=True, env=env, cwd=ws, timeout=60,
    )  # fmt: skip


def test_custom_template_ingest_and_query(tmp_path, mini_world_dir):
    ws = tmp_path / "ws"
    ws.mkdir()
    shutil.copytree(mini_world_dir / "inbox" / "2027-01-11", ws / "inbox" / "2027-01-11")
    r = _run_template(ws, "ingest", "2027-01-11", tmp_path)
    assert r.returncode == 0, r.stderr
    log = (ws / "logs" / "2027-01-11.md").read_text()
    assert log.startswith('---\nid: "logs/2027-01-11"\ntype: "log"\ndate: "2027-01-11"\n---\n')
    for art in ("nt-0002", "em-0004", "ch-0002", "ca-0001"):
        assert f"- {art} (" in log
    usage = json.loads((ws / ".wcb" / "usage.json").read_text())
    assert set(usage) >= {"input_tokens", "output_tokens", "cost_usd", "tool_calls", "model"}
    meta = yaml.safe_load(log.split("---")[1])
    assert meta == {"id": "logs/2027-01-11", "type": "log", "date": "2027-01-11"}

    shutil.rmtree(ws / "inbox")
    (ws / ".wcb" / "questions.json").write_text(
        json.dumps(
            {
                "date": "2027-01-12",
                "questions": [
                    {"id": "q-001", "type": "list", "text": "What do I owe Cora?"},
                    {"id": "q-002", "type": "temporal", "text": "When did we decide X?"},
                ],
            }
        )
    )
    r = _run_template(ws, "query", "2027-01-12", tmp_path)
    assert r.returncode == 0, r.stderr
    answers = json.loads((ws / ".wcb" / "answers.json").read_text())
    assert answers == {
        "q-001": {"type": "list", "abstain": True},
        "q-002": {"type": "temporal", "abstain": True},
    }
    from wcb.agents.simple import check_answers

    schema = REPO / "contract" / "answers" / "answers.schema.json"
    shutil.copy(schema, ws / ".wcb" / "answer-schema.json")
    assert check_answers(ws) is None


def test_custom_template_rejects_unknown_phase(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    r = _run_template(ws, "review", "2027-01-11", tmp_path)
    assert r.returncode == 2 and "WCB_PHASE" in r.stderr
