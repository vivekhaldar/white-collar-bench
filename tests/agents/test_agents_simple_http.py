"""End-to-end: the simple harness as a subprocess against a scripted model server on 127.0.0.1.

This exercises the real urllib path, the CLI and the WCB_* environment together. The server
binds to the loopback interface only; no external network is used.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


class ScriptedServer:
    """Serves scripted JSON replies in order and records each request (path, headers, body)."""

    def __init__(self, replies: list[dict]):
        self.replies = list(replies)
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("content-length") or 0)
                body = json.loads(self.rfile.read(length))
                outer.requests.append(
                    {"path": self.path, "headers": dict(self.headers), "body": body}
                )
                payload = json.dumps(outer.replies.pop(0)).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


def _env(ws: Path, session: Path, **extra) -> dict:
    drop = ("WCB_", "OPENAI_", "ANTHROPIC_")
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(drop) and "proxy" not in k.lower()
    }
    (session / "prompt.md").write_text(
        "Today is 2027-01-04. New inputs are in `inbox/2027-01-04/`."
    )
    env.update(
        WCB_WORKSPACE=str(ws),
        WCB_PROMPT_FILE=str(session / "prompt.md"),
        WCB_PHASE="ingest",
        WCB_DATE="2027-01-04",
        WCB_TRACK="A",
        WCB_SESSION_DIR=str(session),
        PYTHONPATH=str(REPO),
        NO_PROXY="*",
        **extra,
    )
    return env


def _openai_tool_reply(call_id: str, name: str, args: dict) -> dict:
    return {
        "model": "local-model",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)},
                        }
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 120, "completion_tokens": 15},
    }


@pytest.fixture
def session(tmp_path) -> Path:
    d = tmp_path / "session"
    d.mkdir()
    return d


def test_openai_compatible_endpoint_end_to_end(ws, session):
    replies = [
        _openai_tool_reply("a1", "read_document", {"path": "inbox/2027-01-04/em-0001.eml"}),
        _openai_tool_reply(
            "a2", "write_file", {"path": "logs/2027-01-04.md", "content": "- em-0001 (email): ok\n"}
        ),
        _openai_tool_reply("a3", "finish", {"summary": "done"}),
    ]
    with ScriptedServer(replies) as srv:
        r = subprocess.run(
            [sys.executable, "-m", "wcb.agents.simple", "--provider", "openai",
             "--model", "local-model", "--max-tokens", "500"],
            capture_output=True, text=True, cwd=ws, timeout=120,
            env=_env(ws, session, OPENAI_BASE_URL=srv.url + "/v1"),
        )  # fmt: skip
    assert r.returncode == 0, r.stderr
    assert (ws / "logs" / "2027-01-04.md").read_text() == "- em-0001 (email): ok\n"
    assert [q["path"] for q in srv.requests] == ["/v1/chat/completions"] * 3
    first = srv.requests[0]["body"]
    assert first["model"] == "local-model" and first["max_tokens"] == 500
    assert first["messages"][1]["content"].startswith("Today is 2027-01-04.")
    assert "authorization" not in {k.lower() for k in srv.requests[0]["headers"]}
    tool_msg = srv.requests[1]["body"]["messages"][-1]
    assert tool_msg["role"] == "tool" and "Please return it by Tuesday." in tool_msg["content"]
    usage = json.loads((ws / ".wcb" / "usage.json").read_text())
    assert usage["input_tokens"] == 360 and usage["output_tokens"] == 45
    assert usage["tool_calls"] == 3 and usage["model"] == "local-model"
    assert (session / "simple-transcript.jsonl").is_file()
    assert "read_document(path=" in r.stdout


def test_anthropic_endpoint_end_to_end(ws, session):
    def reply(tool_id, name, args):
        return {
            "type": "message",
            "model": "claude-local",
            "content": [{"type": "tool_use", "id": tool_id, "name": name, "input": args}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 80, "output_tokens": 12},
        }

    replies = [
        reply("t1", "write_file", {"path": "notes/a.md", "content": "hello"}),
        reply("t2", "finish", {"summary": "ok"}),
    ]
    with ScriptedServer(replies) as srv:
        r = subprocess.run(
            [sys.executable, "-m", "wcb.agents.simple", "--provider", "anthropic",
             "--model", "claude-local", "--price-input", "3", "--price-output", "15"],
            capture_output=True, text=True, cwd=ws, timeout=120,
            env=_env(ws, session, ANTHROPIC_BASE_URL=srv.url, ANTHROPIC_API_KEY="test-key"),
        )  # fmt: skip
    assert r.returncode == 0, r.stderr
    assert (ws / "notes" / "a.md").read_text() == "hello"
    req = srv.requests[0]
    assert req["path"] == "/v1/messages"
    headers = {k.lower(): v for k, v in req["headers"].items()}
    assert headers["x-api-key"] == "test-key" and headers["anthropic-version"] == "2023-06-01"
    second = srv.requests[1]["body"]["messages"]
    assert second[-1]["content"][0]["type"] == "tool_result"
    assert second[-1]["content"][0]["tool_use_id"] == "t1"
    usage = json.loads((ws / ".wcb" / "usage.json").read_text())
    assert usage["cost_usd"] == pytest.approx((160 * 3 + 24 * 15) / 1e6)
