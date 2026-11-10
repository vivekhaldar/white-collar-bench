"""LLM client: spec parsing, request shapes, retries and parameter fallbacks. No network."""

from __future__ import annotations

import io
import json
import sys
import types
import urllib.error

import pytest

from wcb.llm.client import (
    ANTHROPIC_VERSION,
    AnthropicClient,
    CommandClient,
    LLMError,
    OpenAIClient,
    make_client,
    post_json,
)


class FakeHTTP:
    """Stands in for urllib.request.urlopen: replays scripted responses, records requests.

    Each script entry is a dict (JSON response body) or a tuple (status, body_text, headers)
    to raise as an HTTPError.
    """

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []

    def __call__(self, req, timeout=None):
        self.requests.append(
            {
                "url": req.full_url,
                "headers": {k.lower(): v for k, v in req.header_items()},
                "body": json.loads(req.data.decode("utf-8")),
                "timeout": timeout,
            }
        )
        item = self.script.pop(0)
        if isinstance(item, tuple):
            status, text, headers = item
            raise urllib.error.HTTPError(
                req.full_url, status, "error", headers, io.BytesIO(text.encode())
            )
        if isinstance(item, Exception):
            raise item
        return _Resp(json.dumps(item).encode())


class _Resp:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def anthropic_reply(text="YES"):
    return {
        "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": text}],
        "stop_reason": "end_turn",
    }


def openai_reply(text="NO"):
    return {"choices": [{"message": {"role": "assistant", "content": text}}]}


# ---------------------------------------------------------------- make_client
def test_make_client_specs():
    a = make_client("anthropic:claude-opus-5-5")
    assert isinstance(a, AnthropicClient) and a.model == "claude-opus-5-5"
    assert a.spec == "anthropic:claude-opus-5-5"
    o = make_client("openai:gpt-test")
    assert isinstance(o, OpenAIClient) and o.model == "gpt-test" and o.spec == "openai:gpt-test"
    c = make_client("cmd:claude -p")
    assert isinstance(c, CommandClient) and c.command == "claude -p" and c.spec == "cmd:claude -p"
    bare = make_client("claude-haiku-5-5")
    assert isinstance(bare, AnthropicClient) and bare.model == "claude-haiku-5-5"


@pytest.mark.parametrize("spec", ["", "anthropic:", "openai:", "cmd:", "cmd:   "])
def test_make_client_rejects_empty(spec):
    with pytest.raises(ValueError):
        make_client(spec)


# ---------------------------------------------------------------- Anthropic over HTTP
def test_anthropic_http_request_shape(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    monkeypatch.delenv("WCB_LLM_EFFORT", raising=False)
    http = FakeHTTP(anthropic_reply("YES"))
    c = AnthropicClient("claude-test", use_sdk=False, urlopen=http, sleep=lambda s: None)
    out = c.complete("Same?", system="Be strict.", temperature=0.0, max_tokens=64)
    assert out == "YES"  # thinking blocks are skipped
    req = http.requests[0]
    assert req["url"] == "https://api.anthropic.com/v1/messages"
    assert req["headers"]["x-api-key"] == "test-key"
    assert req["headers"]["anthropic-version"] == ANTHROPIC_VERSION == "2023-06-01"
    assert req["headers"]["content-type"] == "application/json"
    assert req["body"] == {
        "model": "claude-test",
        "max_tokens": 64,
        "system": "Be strict.",
        "temperature": 0.0,
        "messages": [{"role": "user", "content": "Same?"}],
    }


def test_anthropic_base_url_and_effort(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://proxy.example:8080/")
    monkeypatch.setenv("WCB_LLM_EFFORT", "low")
    http = FakeHTTP(anthropic_reply())
    AnthropicClient("m", use_sdk=False, urlopen=http).complete("p")
    assert http.requests[0]["url"] == "http://proxy.example:8080/v1/messages"
    assert http.requests[0]["body"]["output_config"] == {"effort": "low"}
    assert "system" not in http.requests[0]["body"]


def test_anthropic_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        AnthropicClient("m", use_sdk=False, urlopen=FakeHTTP()).complete("p")


def test_anthropic_retries_on_429_and_5xx(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    sleeps = []
    http = FakeHTTP(
        (429, "rate limited", {"retry-after": "3"}),
        (529, "overloaded", {}),
        urllib.error.URLError("reset"),
        anthropic_reply("NO"),
    )
    c = AnthropicClient("m", use_sdk=False, urlopen=http, sleep=sleeps.append, retries=4)
    assert c.complete("p") == "NO"
    assert len(http.requests) == 4
    assert sleeps[0] == 3.0 and len(sleeps) == 3


def test_anthropic_gives_up_after_retries(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    http = FakeHTTP(*[(500, "boom", {})] * 3)
    c = AnthropicClient("m", use_sdk=False, urlopen=http, sleep=lambda s: None, retries=2)
    with pytest.raises(LLMError) as e:
        c.complete("p")
    assert e.value.status == 500 and len(http.requests) == 3


def test_anthropic_does_not_retry_client_errors(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    http = FakeHTTP((401, '{"error": "invalid x-api-key"}', {}))
    with pytest.raises(LLMError) as e:
        AnthropicClient("m", use_sdk=False, urlopen=http, sleep=lambda s: None).complete("p")
    assert e.value.status == 401 and len(http.requests) == 1


def test_anthropic_drops_rejected_temperature(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    err = '{"type":"error","error":{"type":"invalid_request_error","message":"temperature is not supported"}}'
    http = FakeHTTP((400, err, {}), anthropic_reply("YES"), anthropic_reply("NO"))
    c = AnthropicClient("m", use_sdk=False, urlopen=http, sleep=lambda s: None)
    assert c.complete("p", temperature=1.0) == "YES"
    assert (
        "temperature" in http.requests[0]["body"] and "temperature" not in http.requests[1]["body"]
    )
    assert c.complete("p") == "NO"  # remembered: no second failing request
    assert len(http.requests) == 3 and "temperature" not in http.requests[2]["body"]


def test_post_json_timeout_is_passed():
    http = FakeHTTP({"ok": True})
    assert post_json("http://x.example/y", {"a": 1}, {}, timeout=7, urlopen=http) == {"ok": True}
    assert http.requests[0]["timeout"] == 7


# ---------------------------------------------------------------- Anthropic via the SDK
def _fake_sdk(record, *, fail_temperature=False):
    mod = types.ModuleType("anthropic")

    class APIError(Exception):
        pass

    class APIStatusError(APIError):
        def __init__(self, message, status_code):
            super().__init__(message)
            self.status_code = status_code

    class Messages:
        def create(self, **kwargs):
            record.append(kwargs)
            if fail_temperature and "temperature" in kwargs:
                raise APIStatusError("temperature: not supported for this model", 400)
            block = types.SimpleNamespace(type="text", text="COVERED")
            return types.SimpleNamespace(
                content=[types.SimpleNamespace(type="thinking"), block], stop_reason="end_turn"
            )

    class Anthropic:
        def __init__(self, **kwargs):
            record.append({"init": kwargs})
            self.messages = Messages()

    mod.Anthropic, mod.APIError, mod.APIStatusError = Anthropic, APIError, APIStatusError
    return mod


def test_anthropic_sdk_path(monkeypatch):
    record = []
    monkeypatch.setitem(sys.modules, "anthropic", _fake_sdk(record))
    monkeypatch.delenv("WCB_LLM_EFFORT", raising=False)
    c = AnthropicClient("claude-test")
    assert c.use_sdk is True
    assert c.complete("p", system="s", max_tokens=99) == "COVERED"
    assert record[0]["init"]["max_retries"] == c.retries
    assert record[1] == {
        "model": "claude-test",
        "max_tokens": 99,
        "system": "s",
        "temperature": 0.0,
        "messages": [{"role": "user", "content": "p"}],
    }


def test_anthropic_sdk_drops_rejected_temperature(monkeypatch):
    record = []
    monkeypatch.setitem(sys.modules, "anthropic", _fake_sdk(record, fail_temperature=True))
    c = AnthropicClient("m")
    assert c.complete("p") == "COVERED"
    assert "temperature" not in record[-1] and c.send_temperature is False


# ---------------------------------------------------------------- OpenAI-compatible
def test_openai_request_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.example/api/v1/")
    http = FakeHTTP(openai_reply("NO"))
    c = OpenAIClient("vendor/model", urlopen=http)
    assert c.complete("Same?", system="Be strict.", temperature=1.0, max_tokens=32) == "NO"
    req = http.requests[0]
    assert req["url"] == "https://openrouter.example/api/v1/chat/completions"
    assert req["headers"]["authorization"] == "Bearer sk-test"
    assert req["body"] == {
        "model": "vendor/model",
        "max_tokens": 32,
        "temperature": 1.0,
        "messages": [
            {"role": "system", "content": "Be strict."},
            {"role": "user", "content": "Same?"},
        ],
    }


def test_openai_without_key_for_local_servers(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    http = FakeHTTP(openai_reply("YES"))
    assert OpenAIClient("m", urlopen=http).complete("p") == "YES"
    assert "authorization" not in http.requests[0]["headers"]
    assert http.requests[0]["url"] == "https://api.openai.com/v1/chat/completions"


def test_openai_parameter_fallbacks(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    http = FakeHTTP(
        (400, "Unsupported parameter: 'max_tokens'", {}),
        (400, "Unsupported value: 'temperature' does not support 0", {}),
        openai_reply("YES"),
    )
    c = OpenAIClient("m", urlopen=http, sleep=lambda s: None)
    assert c.complete("p") == "YES"
    last = http.requests[-1]["body"]
    assert (
        "max_completion_tokens" in last and "max_tokens" not in last and "temperature" not in last
    )


def test_openai_content_parts_and_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    parts = {
        "choices": [
            {
                "message": {
                    "content": [{"type": "text", "text": "YE"}, {"type": "text", "text": "S"}]
                }
            }
        ]
    }
    http = FakeHTTP(parts, {"choices": []})
    c = OpenAIClient("m", urlopen=http)
    assert c.complete("p") == "YES"
    assert c.complete("p") == ""


def test_openai_retries_5xx(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    http = FakeHTTP((503, "unavailable", {}), openai_reply("NO"))
    assert OpenAIClient("m", urlopen=http, sleep=lambda s: None).complete("p") == "NO"
    assert len(http.requests) == 2


# ---------------------------------------------------------------- command
def test_command_client_stdin_stdout():
    c = make_client("cmd:cat")
    assert c.complete("hello") == "hello"
    assert c.complete("hello", system="sys") == "sys\n\nhello"
    assert c.model == "cat"


def test_command_client_env():
    c = CommandClient('echo "$WCB_LLM_TEMPERATURE $WCB_LLM_MAX_TOKENS"')
    assert c.complete("x", temperature=1.0, max_tokens=7).strip() == "1.0 7"


def test_command_client_failure():
    c = CommandClient("echo nope >&2; exit 3", retries=1)
    with pytest.raises(LLMError, match="exit 3: nope"):
        c.complete("x")


def test_command_client_timeout():
    c = CommandClient("sleep 5", retries=0, timeout=0.2)
    with pytest.raises(LLMError, match="timed out"):
        c.complete("x")
