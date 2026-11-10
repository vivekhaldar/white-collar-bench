"""The simple harness loop with a scripted fake provider, its CLI and usage reporting."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wcb.agents import simple
from wcb.agents.providers import ContextTooLong, Message, ProviderError, Reply, ToolCall, Usage
from wcb.agents.simple import LoopConfig, check_answers, run_session, truncate, usage_record

REPO = Path(__file__).resolve().parents[2]


class FakeProvider:
    """Replays scripted replies and records every request it receives."""

    name = "fake"

    def __init__(self, script, model="fake-model-1"):
        self.script = list(script)
        self.model = model
        self.requests: list[dict] = []

    def complete(self, system, messages, tools, max_tokens):
        self.requests.append(
            {
                "system": system,
                "messages": [_snapshot(m) for m in messages],
                "tools": [t["name"] for t in tools],
                "max_tokens": max_tokens,
            }
        )
        if not self.script:
            raise AssertionError("the fake provider ran out of scripted replies")
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def _snapshot(m: Message) -> dict:
    return {
        "role": m.role,
        "text": m.text,
        "calls": [(c.name, dict(c.arguments)) for c in m.tool_calls],
        "results": [(r.name, r.content, r.is_error) for r in m.results],
    }


def call(name, **args):
    call.n = getattr(call, "n", 0) + 1
    return ToolCall(f"c{call.n}", name, args)


def tools(*calls, text="", inp=100, out=10):
    return Reply(text, list(calls), Usage(inp, out), "tool_use", "fake-model-1")


def say(text, stop="end", inp=50, out=5):
    return Reply(text, [], Usage(inp, out), stop, "fake-model-1")


QUESTIONS = {
    "date": "2027-03-02",
    "questions": [
        {"id": "q-001", "type": "point", "text": "Who owns Thistledown?"},
        {"id": "q-002", "type": "list", "text": "What do I owe Dana?"},
    ],
}


@pytest.fixture
def query_ws(ws):
    wcb = ws / ".wcb"
    wcb.mkdir()
    (wcb / "questions.json").write_text(json.dumps(QUESTIONS))
    schema = REPO / "contract" / "answers" / "answers.schema.json"
    (wcb / "answer-schema.json").write_text(schema.read_text())
    return ws


# ---------------------------------------------------------------- loop
def test_write_then_finish(ws, tmp_path):
    p = FakeProvider(
        [
            tools(call("list_files", path="inbox/2027-01-04"), text="Looking at the inbox."),
            tools(
                call("write_file", path="logs/2027-01-04.md", content="- em-0001 (email): noted\n")
            ),
            tools(call("finish", summary="Logged one input.")),
        ]
    )
    transcript = tmp_path / "session" / "t.jsonl"
    logs: list[str] = []
    stats = run_session(p, ws, "Today is 2027-01-04.", transcript=transcript, log=logs.append)

    assert (ws / "logs" / "2027-01-04.md").read_text() == "- em-0001 (email): noted\n"
    assert stats.stop == "finish" and stats.summary == "Logged one input."
    assert stats.turns == 3 and stats.tool_calls == 3
    assert stats.usage.input_tokens == 300 and stats.usage.output_tokens == 30
    assert stats.tool_counts == {"list_files": 1, "write_file": 1}
    # The model saw the generic system prompt, the task prompt and every tool.
    first = p.requests[0]
    assert first["system"] == simple.SYSTEM_PROMPT
    assert first["messages"] == [
        {"role": "user", "text": "Today is 2027-01-04.", "calls": [], "results": []}
    ]
    assert "finish" in first["tools"] and len(first["tools"]) == 9
    second = p.requests[1]["messages"]
    assert second[-1]["results"][0][1].splitlines()[0].startswith("inbox/2027-01-04/em-0001.eml")
    assert any("write_file(path=" in line for line in logs)
    events = [json.loads(line) for line in transcript.read_text().splitlines()]
    assert [e["event"] for e in events] == ["start", "turn", "turn", "turn", "end"]
    assert events[0]["prompt"] == "Today is 2027-01-04." and events[-1]["stop"] == "finish"


def test_tool_errors_are_returned_to_the_model(ws):
    bad = ToolCall("x1", "write_file", {}, arguments_error="arguments are not valid JSON")
    p = FakeProvider(
        [
            tools(call("read_file", path="../escape")),
            tools(bad),
            tools(call("finish", summary="ok")),
        ]
    )
    run_session(p, ws, "go", log=lambda m: None)
    escape = p.requests[1]["messages"][-1]["results"][0]
    assert escape[2] is True and "'..'" in escape[1]
    parse = p.requests[2]["messages"][-1]["results"][0]
    assert parse[2] is True and "smaller parts" in parse[1]


def test_text_reply_nudges_once_then_ends(ws):
    p = FakeProvider([say("I have updated everything."), say("Done.")])
    stats = run_session(p, ws, "go", log=lambda m: None)
    assert stats.stop == "end_turn" and stats.turns == 2 and stats.summary == "Done."
    nudge = p.requests[1]["messages"][-1]
    assert nudge["role"] == "user" and "call finish" in nudge["text"]


def test_max_tokens_reply_is_nudged(ws):
    p = FakeProvider([say("partial", stop="max_tokens"), tools(call("finish", summary="s"))])
    stats = run_session(p, ws, "go", log=lambda m: None)
    assert "output token limit" in p.requests[1]["messages"][-1]["text"]
    assert stats.stop == "finish"


def test_no_progress_stops(ws):
    script = [say("thinking", stop="max_tokens") for _ in range(5)]
    stats = run_session(FakeProvider(script), ws, "go", config=LoopConfig(max_nudges=2), log=print)
    assert stats.stop == "no_progress" and stats.turns == 3


def test_max_turns(ws):
    script = [tools(call("list_files")) for _ in range(5)]
    stats = run_session(FakeProvider(script), ws, "go", config=LoopConfig(max_turns=3), log=print)
    assert stats.stop == "max_turns" and stats.turns == 3 and stats.tool_calls == 3


def test_query_session_is_read_only_and_checks_answers(query_ws):
    good = {"q-001": {"type": "point", "abstain": True}, "q-002": {"type": "list", "abstain": True}}
    p = FakeProvider(
        [
            tools(call("write_file", path="people/me.md", content="changed")),
            tools(call("finish", summary="nothing written")),
            tools(
                call(
                    "write_file",
                    path=".wcb/answers.json",
                    content=json.dumps({"q-001": {"type": "point", "abstain": False}}),
                ),
                call("finish", summary="answered"),
            ),
            tools(call("write_file", path=".wcb/answers.json", content=json.dumps(good))),
            tools(call("finish", summary="answered all")),
        ]
    )
    stats = run_session(p, query_ws, "answer", phase="query", log=lambda m: None)
    assert (query_ws / "people" / "me.md").read_text().endswith("Ada Quist\n")
    store_write = p.requests[1]["messages"][-1]["results"][0]
    assert store_write[2] is True and "read-only" in store_write[1]
    first_finish = p.requests[2]["messages"][-1]["results"][0]
    assert first_finish[2] and "has not been written" in first_finish[1]
    second_finish = p.requests[3]["messages"][-1]["results"][1]
    assert second_finish[0] == "finish" and second_finish[2]
    assert "q-002" in second_finish[1] and "'value' is a required property" in second_finish[1]
    assert stats.stop == "finish" and stats.summary == "answered all"


def test_query_finish_accepted_after_two_rejections(query_ws):
    p = FakeProvider([tools(call("finish", summary="x")) for _ in range(3)])
    stats = run_session(p, query_ws, "answer", phase="query", log=lambda m: None)
    assert stats.stop == "finish" and stats.turns == 3


def test_query_text_reply_with_good_answers_ends(query_ws):
    (query_ws / ".wcb" / "answers.json").write_text(
        json.dumps(
            {
                "q-001": {"type": "point", "abstain": True},
                "q-002": {"type": "list", "abstain": True},
            }
        )
    )
    stats = run_session(
        FakeProvider([say("All answered.")]), query_ws, "a", phase="query", log=print
    )
    assert stats.stop == "end_turn" and stats.turns == 1


def test_check_answers(query_ws):
    f = query_ws / ".wcb" / "answers.json"
    assert "not been written" in check_answers(query_ws)
    f.write_text("{oops")
    assert "not valid JSON" in check_answers(query_ws)
    f.write_text("[]")
    assert "JSON object" in check_answers(query_ws)
    f.write_text(json.dumps({"q-001": {"type": "list", "abstain": True}}))
    problem = check_answers(query_ws)
    assert "no answer for 1 question(s): q-002" in problem and "must have type 'point'" in problem
    f.write_text(
        json.dumps(
            {
                "q-001": {"type": "point", "abstain": False, "value": "Imogen Tran"},
                "q-002": {
                    "type": "list",
                    "abstain": False,
                    "items": [{"text": "x", "due": "soon"}],
                },
            }
        )
    )
    assert "q-002/items/0/due" in check_answers(query_ws)
    f.write_text(
        json.dumps(
            {
                "q-001": {"type": "point", "abstain": False, "value": "Imogen Tran", "cites": []},
                "q-002": {"type": "list", "abstain": False, "items": [{"text": "x"}]},
            }
        )
    )
    assert check_answers(query_ws) is None


def test_context_pruning_drops_old_tool_output(ws):
    (ws / "big.md").write_text(("word " * 20 + "\n") * 400)
    script = [tools(call("read_file", path="big.md")) for _ in range(6)]
    script.append(tools(call("finish", summary="s")))
    p = FakeProvider(script)
    logs: list[str] = []
    cfg = LoopConfig(context_budget=12_000, max_tool_output=30_000, keep_recent=2)
    run_session(p, ws, "go", config=cfg, log=logs.append)
    last = p.requests[-1]["messages"]
    assert last[0]["text"] == "go"  # the task prompt is never dropped
    contents = [r[1] for m in last for r in m["results"]]
    assert any(c.startswith("[earlier output of read_file removed") for c in contents)
    assert contents[-1].startswith("[big.md: lines 1-400 of 400]")  # the newest output is kept
    assert simple.estimate_tokens("", [Message("user", "")]) < 12_000
    assert any("dropped" in line for line in logs)


def test_long_tool_output_is_truncated(ws):
    (ws / "big.md").write_text(("x" * 99 + "\n") * 500)
    p = FakeProvider([tools(call("read_file", path="big.md")), tools(call("finish", summary="s"))])
    run_session(p, ws, "go", config=LoopConfig(max_tool_output=5000), log=lambda m: None)
    content = p.requests[1]["messages"][-1]["results"][0][1]
    assert len(content) < 5300 and "characters truncated" in content
    assert truncate("short", 10) == "short"


def test_context_too_long_recovers_by_pruning(ws):
    (ws / "big.md").write_text(("word " * 20 + "\n") * 400)
    p = FakeProvider(
        [
            tools(call("read_file", path="big.md")),
            tools(call("read_file", path="big.md")),
            tools(call("read_file", path="big.md")),
            ContextTooLong("too long"),
            tools(call("finish", summary="s")),
        ]
    )
    stats = run_session(p, ws, "go", config=LoopConfig(keep_recent=2), log=lambda m: None)
    assert stats.stop == "finish"
    retried = p.requests[-1]["messages"]
    assert retried[2]["results"][0][1].startswith("[earlier output")


def test_provider_error_propagates_with_partial_stats(ws):
    stats = simple.SessionStats()
    p = FakeProvider([tools(call("list_files")), ProviderError("HTTP 500")])
    with pytest.raises(ProviderError):
        run_session(p, ws, "go", stats=stats, log=lambda m: None)
    assert stats.stop == "error" and stats.turns == 1 and stats.usage.input_tokens == 100


# ---------------------------------------------------------------- usage and CLI
def test_usage_record_cost():
    stats = simple.SessionStats(usage=Usage(1_000_000, 100_000, 400_000, 100_000), turns=4)
    stats.tool_calls = 9
    rec = usage_record(stats, provider="anthropic", model="m", price_input=3, price_output=15,
                       price_cache_read=0.3)  # fmt: skip
    # 500k uncached * 3 + 100k writes * 3.75 + 400k reads * 0.3 + 100k out * 15, per million
    assert rec["cost_usd"] == pytest.approx(1.5 + 0.375 + 0.12 + 1.5)
    assert rec["tool_calls"] == 9 and rec["turns"] == 4 and rec["model"] == "m"
    assert {"input_tokens", "output_tokens", "cost_usd", "tool_calls", "model", "provider"} <= set(
        rec
    )
    assert usage_record(stats, provider="openai", model="m")["cost_usd"] is None


def test_main_runs_a_session_and_writes_usage(ws, tmp_path, monkeypatch, capsys):
    script = [
        tools(call("write_file", path="notes/today.md", content="hello")),
        tools(call("finish", summary="done")),
    ]
    fake = FakeProvider(script)
    monkeypatch.setattr(simple, "make_provider", lambda name, model, **kw: fake)
    session = tmp_path / "session"
    session.mkdir()
    prompt = session / "prompt.md"
    prompt.write_text("Today is 2027-01-04. New inputs are in `inbox/2027-01-04/`.")
    monkeypatch.setenv("WCB_WORKSPACE", str(ws))
    monkeypatch.setenv("WCB_PROMPT_FILE", str(prompt))
    monkeypatch.setenv("WCB_PHASE", "ingest")
    monkeypatch.setenv("WCB_SESSION_DIR", str(session))
    code = simple.main(["--provider", "anthropic", "--model", "fake-model", "--max-turns", "5"])
    assert code == 0
    assert (ws / "notes" / "today.md").read_text() == "hello"
    usage = json.loads((ws / ".wcb" / "usage.json").read_text())
    assert usage["input_tokens"] == 200 and usage["output_tokens"] == 20
    assert usage["tool_calls"] == 2 and usage["turns"] == 2
    assert usage["model"] == "fake-model-1" and usage["provider"] == "anthropic"
    assert usage["stop"] == "finish" and usage["cost_usd"] is None
    assert (session / simple.TRANSCRIPT_NAME).is_file()
    assert fake.requests[0]["messages"][0]["text"].startswith("Today is 2027-01-04.")
    assert "stop=finish" in capsys.readouterr().out


def test_main_writes_usage_on_provider_error(ws, monkeypatch):
    fake = FakeProvider([tools(call("list_files")), ProviderError("HTTP 500 from x")])
    monkeypatch.setattr(simple, "make_provider", lambda name, model, **kw: fake)
    code = simple.main(
        ["--provider", "openai", "--model", "m", "--workspace", str(ws), "--prompt", "go",
         "--transcript", ""]
    )  # fmt: skip
    assert code == 1
    usage = json.loads((ws / ".wcb" / "usage.json").read_text())
    assert usage["stop"] == "error" and usage["turns"] == 1


def test_cli_config_errors(ws, tmp_path, monkeypatch):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("WCB_", "ANTHROPIC_"))}
    env["PYTHONPATH"] = str(REPO)

    def run(*args, **extra):
        return subprocess.run(
            [sys.executable, "-m", "wcb.agents.simple", *args],
            capture_output=True, text=True, env={**env, **extra}, cwd=ws, timeout=60,
        )  # fmt: skip

    r = run("--provider", "anthropic", "--model", "m")
    assert r.returncode == 2 and "no prompt" in r.stderr
    r = run("--provider", "anthropic", "--model", "m", "--prompt", "go")
    assert r.returncode == 2 and "ANTHROPIC_API_KEY is not set" in r.stderr
    r = run("--provider", "anthropic", "--model", "<model-id>", "--prompt", "go",
            ANTHROPIC_API_KEY="k")  # fmt: skip
    assert r.returncode == 2 and "placeholder" in r.stderr
    r = run("--provider", "openai", "--model", "m", "--prompt-file", str(tmp_path / "missing.md"))
    assert r.returncode == 2 and "cannot read the prompt file" in r.stderr
    r = run("--provider", "openai", "--model", "m", "--prompt", "x", WCB_PHASE="review")
    assert r.returncode == 2 and "WCB_PHASE" in r.stderr
