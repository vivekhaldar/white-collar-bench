"""Provider request/response shapes, retries and errors (no network: urlopen is mocked)."""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import pytest

from wcb.agents.providers import (
    AnthropicProvider,
    ContextTooLong,
    HTTPConfig,
    Message,
    OpenAIProvider,
    ProviderError,
    ToolCall,
    ToolResult,
    make_provider,
)
from wcb.agents.tools import TOOL_SPECS

CONVERSATION = [
    Message("user", "Today is 2027-03-01. Do the task."),
    Message(
        "assistant",
        "Reading the inbox.",
        [ToolCall("call_1", "list_files", {"path": "inbox"})],
    ),
    Message("tool", results=[ToolResult("call_1", "list_files", "inbox/2027-03-01/", False)]),
    Message("assistant", "", [ToolCall("call_2", "read_file", {"path": "x"})]),
    Message(
        "tool",
        text="Keep going.",
        results=[ToolResult("call_2", "read_file", "error: 'x' does not exist", True)],
    ),
]


class FakeHTTP:
    """Replaces urllib.request.urlopen: records requests, replays scripted responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(
            {
                "url": req.full_url,
                "headers": {k.lower(): v for k, v in req.header_items()},
                "body": json.loads(req.data.decode()),
                "timeout": timeout,
            }
        )
        status, payload, headers = self.responses.pop(0)
        raw = json.dumps(payload).encode() if not isinstance(payload, bytes) else payload
        if status >= 400:
            raise urllib.error.HTTPError(
                req.full_url, status, "err", headers or {}, io.BytesIO(raw)
            )
        return io.BytesIO(raw)


@pytest.fixture
def http(monkeypatch):
    def install(*responses):
        fake = FakeHTTP(responses)
        monkeypatch.setattr(urllib.request, "urlopen", fake)
        return fake

    return install


def no_sleep_cfg(**kw):
    delays = []
    cfg = HTTPConfig(sleep=delays.append, log=lambda m: None, **kw)
    return cfg, delays


ANTHROPIC_REPLY = {
    "id": "msg_1",
    "type": "message",
    "role": "assistant",
    "model": "claude-test-1",
    "content": [
        {"type": "text", "text": "I'll write the log."},
        {
            "type": "tool_use",
            "id": "toolu_9",
            "name": "write_file",
            "input": {"path": "logs/2027-03-01.md", "content": "x"},
        },
    ],
    "stop_reason": "tool_use",
    "usage": {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_input_tokens": 300,
        "cache_creation_input_tokens": 50,
    },
}


# ---------------------------------------------------------------- Anthropic
def test_anthropic_request_shape(http, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-anthropic")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    fake = http((200, ANTHROPIC_REPLY, None))
    cfg, _ = no_sleep_cfg(timeout_s=33)
    p = AnthropicProvider("claude-test", http=cfg, temperature=0.2)
    reply = p.complete("SYSTEM", CONVERSATION, TOOL_SPECS, 1234)

    req = fake.requests[0]
    assert req["url"] == "https://api.anthropic.com/v1/messages"
    assert req["headers"]["x-api-key"] == "sk-test-anthropic"
    assert req["headers"]["anthropic-version"] == "2023-06-01"
    assert req["headers"]["content-type"] == "application/json"
    assert req["timeout"] == 33
    body = req["body"]
    assert body["model"] == "claude-test" and body["max_tokens"] == 1234
    assert body["temperature"] == 0.2
    assert body["system"] == [
        {"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}
    ]
    assert [t["name"] for t in body["tools"]] == [s["name"] for s in TOOL_SPECS]
    assert body["tools"][0]["input_schema"] == TOOL_SPECS[0]["parameters"]
    assert body["tools"][-1]["cache_control"] == {"type": "ephemeral"}
    msgs = body["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant", "user"]
    assert msgs[0]["content"] == [{"type": "text", "text": "Today is 2027-03-01. Do the task."}]
    assert msgs[1]["content"] == [
        {"type": "text", "text": "Reading the inbox."},
        {"type": "tool_use", "id": "call_1", "name": "list_files", "input": {"path": "inbox"}},
    ]
    assert msgs[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "inbox/2027-03-01/"}
    ]
    assert msgs[3]["content"] == [
        {"type": "tool_use", "id": "call_2", "name": "read_file", "input": {"path": "x"}}
    ]
    last = msgs[4]["content"]
    assert last[0]["type"] == "tool_result" and last[0]["is_error"] is True
    assert last[1]["text"] == "Keep going." and last[1]["cache_control"] == {"type": "ephemeral"}
    # The neutral conversation is not mutated by the conversion.
    assert CONVERSATION[1].tool_calls[0].arguments == {"path": "inbox"}

    assert reply.text == "I'll write the log." and reply.stop_reason == "tool_use"
    assert reply.tool_calls == [
        ToolCall("toolu_9", "write_file", {"path": "logs/2027-03-01.md", "content": "x"})
    ]
    assert reply.usage.input_tokens == 450 and reply.usage.output_tokens == 20
    assert reply.usage.cache_read_input_tokens == 300 and reply.model == "claude-test-1"


def test_anthropic_base_url_and_no_cache(http, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://proxy.example:8080/v1/")
    fake = http((200, ANTHROPIC_REPLY, None))
    p = AnthropicProvider("m", http=no_sleep_cfg()[0], prompt_cache=False)
    p.complete("S", [Message("user", "hi")], [], 10)
    assert fake.requests[0]["url"] == "http://proxy.example:8080/v1/messages"
    assert "cache_control" not in json.dumps(fake.requests[0]["body"])
    assert "tools" not in fake.requests[0]["body"]


def test_anthropic_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="ANTHROPIC_API_KEY is not set.*env_passthrough"):
        AnthropicProvider("m")


# ---------------------------------------------------------------- OpenAI
OPENAI_REPLY = {
    "id": "chatcmpl-1",
    "model": "gpt-test-2",
    "choices": [
        {
            "index": 0,
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_a",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"pattern": "Dana"}'},
                    },
                    {
                        "id": "call_b",
                        "type": "function",
                        "function": {"name": "write_file", "arguments": '{"path": "a.md", "con'},
                    },
                ],
            },
        }
    ],
    "usage": {
        "prompt_tokens": 500,
        "completion_tokens": 40,
        "prompt_tokens_details": {"cached_tokens": 128},
    },
}


def test_openai_request_shape(http, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-openai")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    fake = http((200, OPENAI_REPLY, None))
    p = OpenAIProvider("gpt-test", http=no_sleep_cfg()[0])
    reply = p.complete("SYSTEM", CONVERSATION, TOOL_SPECS, 999)

    req = fake.requests[0]
    assert req["url"] == "https://api.openai.com/v1/chat/completions"
    assert req["headers"]["authorization"] == "Bearer sk-test-openai"
    body = req["body"]
    assert body["model"] == "gpt-test"
    assert body["max_completion_tokens"] == 999 and "max_tokens" not in body
    assert "temperature" not in body
    assert body["tools"][0] == {
        "type": "function",
        "function": {
            "name": TOOL_SPECS[0]["name"],
            "description": TOOL_SPECS[0]["description"],
            "parameters": TOOL_SPECS[0]["parameters"],
        },
    }
    msgs = body["messages"]
    assert [m["role"] for m in msgs] == [
        "system", "user", "assistant", "tool", "assistant", "tool", "user",
    ]  # fmt: skip
    assert msgs[0] == {"role": "system", "content": "SYSTEM"}
    assert msgs[2]["content"] == "Reading the inbox."
    assert msgs[2]["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
            "function": {"name": "list_files", "arguments": '{"path": "inbox"}'},
        }
    ]
    assert msgs[3] == {"role": "tool", "tool_call_id": "call_1", "content": "inbox/2027-03-01/"}
    assert msgs[4]["content"] is None
    assert msgs[5]["content"].startswith("ERROR: ")
    assert msgs[6] == {"role": "user", "content": "Keep going."}

    assert reply.stop_reason == "tool_use" and reply.model == "gpt-test-2"
    assert reply.tool_calls[0] == ToolCall("call_a", "search", {"pattern": "Dana"})
    assert (
        reply.tool_calls[1].arguments_error
        and "not valid JSON" in reply.tool_calls[1].arguments_error
    )
    assert reply.usage.input_tokens == 500 and reply.usage.cache_read_input_tokens == 128


def test_openai_compatible_endpoint_without_key(http, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1/")
    reply_payload = {
        "choices": [{"finish_reason": "stop", "message": {"content": "All done."}}],
    }
    fake = http((200, reply_payload, None))
    p = OpenAIProvider("qwen-local", http=no_sleep_cfg()[0], temperature=0)
    reply = p.complete("S", [Message("user", "hi")], [], 50)
    req = fake.requests[0]
    assert req["url"] == "http://localhost:11434/v1/chat/completions"
    assert "authorization" not in req["headers"]
    assert req["body"]["max_tokens"] == 50 and req["body"]["temperature"] == 0
    assert "tools" not in req["body"]
    assert reply.text == "All done." and reply.stop_reason == "end" and reply.tool_calls == []
    assert reply.usage.input_tokens == 0  # servers may omit usage


def test_openai_missing_key_for_openai_endpoint(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    with pytest.raises(ProviderError, match="OPENAI_API_KEY is not set"):
        OpenAIProvider("gpt-test")


def test_openai_switches_max_tokens_parameter(http, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://gateway.example/v1")
    err = {
        "error": {"message": "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens'."}
    }
    ok = {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}
    fake = http((400, err, None), (200, ok, None))
    reply = OpenAIProvider("m", http=no_sleep_cfg()[0]).complete("S", [Message("user", "x")], [], 7)
    assert "max_tokens" in fake.requests[0]["body"]
    assert fake.requests[1]["body"]["max_completion_tokens"] == 7
    assert "max_tokens" not in fake.requests[1]["body"]
    assert reply.stop_reason == "max_tokens"


# ---------------------------------------------------------------- retries and errors
def test_retries_on_429_and_5xx_with_backoff(http, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    fake = http(
        (429, {"error": "rate"}, {"retry-after": "3"}),
        (529, {"error": "overloaded"}, None),
        (200, ANTHROPIC_REPLY, None),
    )
    cfg, delays = no_sleep_cfg(retries=3, backoff_s=1.0)
    reply = AnthropicProvider("m", http=cfg).complete("S", [Message("user", "x")], [], 10)
    assert len(fake.requests) == 3 and len(delays) == 2
    assert delays[0] >= 3  # Retry-After honoured
    assert reply.tool_calls


def test_retries_exhausted(http, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    http(*[(503, {"error": "down"}, None)] * 3)
    cfg, delays = no_sleep_cfg(retries=2)
    with pytest.raises(ProviderError, match="after 3 attempts.*HTTP 503"):
        AnthropicProvider("m", http=cfg).complete("S", [Message("user", "x")], [], 10)
    assert len(delays) == 2


def test_connection_errors_are_retried(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    calls = []

    def flaky(req, timeout=None):
        calls.append(1)
        if len(calls) == 1:
            raise urllib.error.URLError("connection refused")
        return io.BytesIO(json.dumps(OPENAI_REPLY).encode())

    monkeypatch.setattr(urllib.request, "urlopen", flaky)
    reply = OpenAIProvider("m", http=no_sleep_cfg()[0]).complete("S", [Message("user", "x")], [], 5)
    assert len(calls) == 2 and reply.tool_calls


@pytest.mark.parametrize(
    "status,body,match",
    [
        (
            401,
            {"error": {"message": "invalid x-api-key"}},
            "authentication failed.*ANTHROPIC_API_KEY",
        ),
        (
            404,
            {"error": {"message": "model: nope"}},
            "does not exist there or the base URL is wrong",
        ),
        (400, {"error": {"message": "bad request: messages.0"}}, "HTTP 400"),
    ],
)
def test_http_errors_are_explained(http, monkeypatch, status, body, match):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    fake = http((status, body, None))
    with pytest.raises(ProviderError, match=match):
        AnthropicProvider("m", http=no_sleep_cfg()[0]).complete("S", [Message("user", "x")], [], 10)
    assert len(fake.requests) == 1  # not retried


def test_context_too_long_is_detected(http, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    http((400, {"error": {"message": "prompt is too long: 250000 tokens > 200000 maximum"}}, None))
    with pytest.raises(ContextTooLong):
        AnthropicProvider("m", http=no_sleep_cfg()[0]).complete("S", [Message("user", "x")], [], 10)


def test_non_json_response(http, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    http((200, b"<html>login</html>", None))
    with pytest.raises(ProviderError, match="not JSON"):
        AnthropicProvider("m", http=no_sleep_cfg()[0]).complete("S", [Message("user", "x")], [], 10)


def test_make_provider_validation(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert make_provider("anthropic", "m").name == "anthropic"
    with pytest.raises(ProviderError, match="unknown provider"):
        make_provider("gemini", "m")
    with pytest.raises(ProviderError, match="placeholder"):
        make_provider("anthropic", "<model-id>")
