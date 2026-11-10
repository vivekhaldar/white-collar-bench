"""The CLI-agent usage wrapper (wcb.agents.wrap)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from wcb.agents.wrap import UsageParser

REPO = Path(__file__).resolve().parents[2]

CLAUDE_STREAM = [
    {"type": "system", "subtype": "init", "model": "claude-x", "tools": ["Bash", "Edit", "Read"]},
    {
        "type": "assistant",
        "message": {
            "id": "m1",
            "model": "claude-x-20270101",
            "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100},
        },
    },
    {
        "type": "assistant",
        "message": {
            "id": "m1",
            "model": "claude-x-20270101",
            "content": [{"type": "tool_use", "id": "t2", "name": "Edit", "input": {}}],
            "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100},
        },
    },
    {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]}},
    {
        "type": "result",
        "subtype": "success",
        "num_turns": 3,
        "total_cost_usd": 0.0421,
        "usage": {
            "input_tokens": 30,
            "output_tokens": 50,
            "cache_read_input_tokens": 400,
            "cache_creation_input_tokens": 70,
        },
        "modelUsage": {
            "claude-x-20270101": {
                "inputTokens": 30,
                "outputTokens": 50,
                "cacheReadInputTokens": 400,
                "cacheCreationInputTokens": 70,
            },
            "claude-small": {"inputTokens": 5, "outputTokens": 1},
        },
    },
]


def test_claude_stream_json():
    p = UsageParser("claude")
    p.feed_line("not json at all")
    for e in CLAUDE_STREAM:
        p.feed_line(json.dumps(e))
    rec = p.record("claude-code")
    assert rec["input_tokens"] == 30 + 5 + 400 + 70
    assert rec["output_tokens"] == 51
    assert rec["cache_read_input_tokens"] == 400 and rec["cache_creation_input_tokens"] == 70
    assert rec["cost_usd"] == 0.0421 and rec["turns"] == 3 and rec["tool_calls"] == 2
    assert rec["model"] == "claude-x-20270101" and rec["provider"] == "claude-code"


def test_claude_json_without_model_usage_and_without_result():
    p = UsageParser("claude")
    p.feed_text(json.dumps({"type": "result", "usage": {"input_tokens": 7, "output_tokens": 2}}))
    assert (p.input_tokens, p.output_tokens) == (7, 2)
    # A run killed before its result event: per-message usage, de-duplicated by message ID.
    q = UsageParser("claude")
    for e in CLAUDE_STREAM[:3]:
        q.feed_line(json.dumps(e))
    assert q.input_tokens == 110 and q.output_tokens == 5 and q.cost_usd is None


def test_codex_jsonl():
    events = [
        {"type": "thread.started", "thread_id": "th"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "command_execution", "command": "ls"}},
        {"type": "item.completed", "item": {"type": "file_change"}},
        {"type": "item.completed", "item": {"type": "agent_message", "text": "done"}},
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 1000, "cached_input_tokens": 600, "output_tokens": 90},
        },
    ]
    p = UsageParser("codex", model="gpt-x")
    for e in events:
        p.feed_line(json.dumps(e))
    rec = p.record("codex")
    assert rec["input_tokens"] == 1000 and rec["output_tokens"] == 90
    assert rec["cache_read_input_tokens"] == 600 and rec["tool_calls"] == 2
    assert rec["turns"] == 1 and rec["model"] == "gpt-x"


def _run_wrap(tmp_path, fmt, script, *extra):
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    env = {**os.environ, "WCB_WORKSPACE": str(ws), "PYTHONPATH": str(REPO)}
    cmd = [sys.executable, "-m", "wcb.agents.wrap", "--format", fmt, *extra, "--",
           sys.executable, "-c", script]  # fmt: skip
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=ws, timeout=60)
    return r, ws


def test_wrapper_passes_output_and_exit_code_through(tmp_path):
    script = (
        "import json, sys\n"
        f"for e in {CLAUDE_STREAM!r}: print(json.dumps(e))\n"
        "print('plain text line')\n"
        "sys.exit(3)\n"
    )
    r, ws = _run_wrap(tmp_path, "claude", script)
    assert r.returncode == 3
    assert "plain text line" in r.stdout and '"type": "result"' in r.stdout
    usage = json.loads((ws / ".wcb" / "usage.json").read_text())
    assert usage["cost_usd"] == 0.0421 and usage["tool_calls"] == 2
    assert usage["harness"] == "wcb.agents.wrap:claude"


def test_wrapper_reports_missing_command(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    env = {**os.environ, "WCB_WORKSPACE": str(ws), "PYTHONPATH": str(REPO)}
    r = subprocess.run(
        [sys.executable, "-m", "wcb.agents.wrap", "--format", "codex", "--", "no-such-agent-xyz"],
        capture_output=True, text=True, env=env, cwd=ws, timeout=60,
    )  # fmt: skip
    assert r.returncode == 127 and "not found on PATH" in r.stderr
    assert json.loads((ws / ".wcb" / "usage.json").read_text())["input_tokens"] == 0
