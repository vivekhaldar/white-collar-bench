"""Model providers for the simple harness, using only ``urllib`` from the standard library.

Two wire protocols cover almost every model:

- :class:`AnthropicProvider`: the Anthropic Messages API with native ``tool_use`` blocks.
  ``POST {ANTHROPIC_BASE_URL or https://api.anthropic.com}/v1/messages`` with ``x-api-key:
  $ANTHROPIC_API_KEY`` and ``anthropic-version: 2023-06-01``.
- :class:`OpenAIProvider`: the OpenAI Chat Completions API with function tools, which OpenAI and
  most other servers speak (OpenRouter, vLLM, Ollama, LM Studio, llama.cpp, Together, Groq,
  Gemini's OpenAI endpoint, ...). ``POST {OPENAI_BASE_URL or https://api.openai.com/v1}
  /chat/completions`` with ``Authorization: Bearer $OPENAI_API_KEY``.

The harness talks to both through one provider-neutral conversation model: :class:`Message`,
:class:`ToolCall`, :class:`ToolResult` and :class:`Reply`. Each provider converts it to and from
its wire format, so adding a provider means writing one class with a ``complete`` method.

Transient failures (HTTP 408/409/425/429/5xx/529, connection errors, timeouts) are retried with
exponential backoff and jitter, honouring ``Retry-After``. Other HTTP errors raise
:class:`ProviderError` with a message that says what to check. A request rejected because the
conversation is too long raises :class:`ContextTooLong`, which the harness handles by dropping
old tool output and trying again.
"""

from __future__ import annotations

import http.client
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

ANTHROPIC_DEFAULT_BASE = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"

RETRY_STATUSES = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529})
_CONTEXT_ERROR = re.compile(
    r"context[ _-]?(length|window)|prompt is too long|maximum context|too many tokens"
    r"|input is too long|reduce the length|context_length_exceeded",
    re.I,
)


# ====================================================================== errors
class ProviderError(RuntimeError):
    """A model call failed in a way retrying will not fix. The message says what to check."""


class ContextTooLong(ProviderError):
    """The provider rejected the request because the conversation is too long."""


class HTTPStatusError(ProviderError):
    """A non-retryable HTTP error. ``status`` and ``body`` hold the response."""

    def __init__(self, status: int, body: str, url: str):
        self.status, self.body, self.url = status, body, url
        super().__init__(f"HTTP {status} from {url}: {_snippet(body)}")


# ====================================================================== conversation model
@dataclass
class ToolCall:
    """A tool the model asked to run. ``arguments_error`` is set if the arguments were not JSON."""

    id: str
    name: str
    arguments: dict[str, Any]
    arguments_error: str | None = None


@dataclass
class ToolResult:
    """The outcome of one :class:`ToolCall`, sent back to the model."""

    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """One conversation turn.

    - ``role="user"``: ``text`` from the harness (the task prompt, or a nudge).
    - ``role="assistant"``: the model's ``text`` and ``tool_calls``.
    - ``role="tool"``: ``results`` for the previous assistant turn's tool calls, plus optional
      ``text`` the harness appends after them.
    """

    role: str
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    results: list[ToolResult] = field(default_factory=list)


@dataclass
class Usage:
    """Token counts for one or more model calls. ``input_tokens`` includes cached tokens."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def add(self, other: Usage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_input_tokens += other.cache_read_input_tokens
        self.cache_creation_input_tokens += other.cache_creation_input_tokens


@dataclass
class Reply:
    """A model response. ``stop_reason`` is ``tool_use``, ``end``, ``max_tokens`` or ``other``."""

    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    stop_reason: str
    model: str | None = None


# ====================================================================== HTTP
@dataclass
class HTTPConfig:
    """Network settings shared by both providers."""

    timeout_s: float = 600.0
    retries: int = 6
    backoff_s: float = 2.0
    max_backoff_s: float = 60.0
    sleep: Callable[[float], None] = time.sleep
    log: Callable[[str], None] = lambda msg: print(msg, file=sys.stderr, flush=True)


def post_json(url: str, headers: dict[str, str], body: dict, cfg: HTTPConfig) -> dict:
    """POST ``body`` as JSON and return the decoded JSON response, retrying transient failures.

    Raises :class:`HTTPStatusError` for other HTTP errors and :class:`ProviderError` when retries
    are exhausted or the response is not JSON.
    """
    data = json.dumps(body).encode("utf-8")
    last = ""
    for attempt in range(cfg.retries + 1):
        req = urllib.request.Request(
            url, data=data, method="POST", headers={"content-type": "application/json", **headers}
        )
        retry_after: float | None = None
        try:
            with urllib.request.urlopen(req, timeout=cfg.timeout_s) as resp:
                raw = resp.read()
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as e:
                raise ProviderError(
                    f"{url} returned a response that is not JSON ({e}): {_snippet(raw)}; check "
                    "the base URL points at the API, not a web page"
                ) from e
        except urllib.error.HTTPError as e:
            text = _read_error_body(e)
            if e.code not in RETRY_STATUSES:
                raise HTTPStatusError(e.code, text, url) from None
            last = f"HTTP {e.code}: {_snippet(text)}"
            retry_after = _retry_after(e.headers.get("retry-after") if e.headers else None)
        except (
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            ConnectionError,
        ) as e:
            reason = getattr(e, "reason", e)
            last = f"connection error: {reason}"
        if attempt == cfg.retries:
            break
        delay = min(cfg.max_backoff_s, cfg.backoff_s * 2**attempt) * (0.5 + random.random() / 2)
        if retry_after is not None:
            delay = min(max(delay, retry_after), cfg.max_backoff_s * 5)
        cfg.log(f"[provider] {last}; retry {attempt + 1}/{cfg.retries} in {delay:.1f}s")
        cfg.sleep(delay)
    raise ProviderError(f"giving up on {url} after {cfg.retries + 1} attempts; last error: {last}")


def _read_error_body(e: urllib.error.HTTPError) -> str:
    try:
        return e.read().decode("utf-8", errors="replace")
    except Exception:  # the body is best-effort context only
        return ""


def _retry_after(value: str | None) -> float | None:
    try:
        return max(0.0, float(value)) if value else None
    except ValueError:
        return None


def _snippet(body: str | bytes, n: int = 500) -> str:
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")
    body = " ".join(body.split())
    return body if len(body) <= n else body[:n] + " [...]"


def _explain(e: HTTPStatusError, key_env: str, base_env: str, model: str) -> ProviderError:
    """Turn an HTTP error into an actionable message (or :class:`ContextTooLong`)."""
    if e.status in (400, 413, 422) and _CONTEXT_ERROR.search(e.body):
        return ContextTooLong(f"the conversation is too long for the model: {_snippet(e.body)}")
    if e.status in (401, 403):
        return ProviderError(
            f"authentication failed (HTTP {e.status}) at {e.url}: check that {key_env} is valid "
            f"for this endpoint and listed under env_passthrough in your adapter. "
            f"Response: {_snippet(e.body)}"
        )
    if e.status == 404:
        return ProviderError(
            f"HTTP 404 from {e.url}: the model {model!r} does not exist there or the base URL is "
            f"wrong (check {base_env} and --model). Response: {_snippet(e.body)}"
        )
    return ProviderError(f"HTTP {e.status} from {e.url}: {_snippet(e.body)}")


def _api_key(env: str, *, required: bool, example: str) -> str | None:
    key = os.environ.get(env, "").strip()
    if not key and required:
        raise ProviderError(
            f"{env} is not set. Export it before running wcb (export {env}=...) and add it to "
            f"env_passthrough in your adapter, as in {example}"
        )
    return key or None


# ====================================================================== Anthropic
class AnthropicProvider:
    """The Anthropic Messages API (``/v1/messages``) with native tool use.

    Prompt caching is on by default: the system prompt, the tool list and the newest message
    carry ``cache_control`` breakpoints, so each turn re-reads the previous turns from cache.
    """

    name = "anthropic"

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key_env: str = "ANTHROPIC_API_KEY",
        http: HTTPConfig | None = None,
        temperature: float | None = None,
        prompt_cache: bool = True,
    ):
        self.model = model
        self.api_key = _api_key(
            api_key_env, required=True, example="adapters/examples/simple-anthropic.yaml"
        )
        self.api_key_env = api_key_env
        base = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or ANTHROPIC_DEFAULT_BASE).rstrip(
            "/"
        )
        self.url = base + ("/messages" if base.endswith("/v1") else "/v1/messages")
        self.http = http or HTTPConfig()
        self.temperature = temperature
        self.prompt_cache = prompt_cache

    def build_request(
        self, system: str, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> dict:
        """The JSON body for ``/v1/messages`` (exposed for tests and debugging)."""
        wire = anthropic_messages(messages)
        tool_defs = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]
        system_blocks: list[dict] = [{"type": "text", "text": system}]
        if self.prompt_cache:
            system_blocks[-1]["cache_control"] = {"type": "ephemeral"}
            if tool_defs:
                tool_defs[-1]["cache_control"] = {"type": "ephemeral"}
            if wire and wire[-1]["content"]:
                wire[-1]["content"][-1]["cache_control"] = {"type": "ephemeral"}
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": wire,
        }
        if tool_defs:
            body["tools"] = tool_defs
        if self.temperature is not None:
            body["temperature"] = self.temperature
        return body

    def complete(
        self, system: str, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> Reply:
        body = self.build_request(system, messages, tools, max_tokens)
        headers = {"x-api-key": self.api_key or "", "anthropic-version": ANTHROPIC_VERSION}
        try:
            data = post_json(self.url, headers, body, self.http)
        except HTTPStatusError as e:
            raise _explain(e, self.api_key_env, "ANTHROPIC_BASE_URL", self.model) from None
        return parse_anthropic_response(data)


def anthropic_messages(messages: list[Message]) -> list[dict]:
    """Convert neutral messages to Anthropic's alternating user/assistant content blocks."""
    out: list[dict] = []

    def push(role: str, blocks: list[dict]) -> None:
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for m in messages:
        if m.role == "assistant":
            blocks: list[dict] = []
            if m.text:
                blocks.append({"type": "text", "text": m.text})
            for c in m.tool_calls:
                blocks.append(
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                )
            push("assistant", blocks or [{"type": "text", "text": "(no output)"}])
        else:
            blocks = [
                {
                    "type": "tool_result",
                    "tool_use_id": r.call_id,
                    "content": r.content or "(empty)",
                    **({"is_error": True} if r.is_error else {}),
                }
                for r in m.results
            ]
            if m.text:
                blocks.append({"type": "text", "text": m.text})
            push("user", blocks or [{"type": "text", "text": "(empty)"}])
    return out


_ANTHROPIC_STOP = {
    "tool_use": "tool_use",
    "end_turn": "end",
    "stop_sequence": "end",
    "max_tokens": "max_tokens",
}


def parse_anthropic_response(data: dict) -> Reply:
    """Convert a ``/v1/messages`` response into a :class:`Reply`."""
    if data.get("type") == "error":
        raise ProviderError(f"Anthropic API error: {data.get('error')}")
    texts, calls = [], []
    for block in data.get("content") or []:
        if block.get("type") == "text":
            texts.append(block.get("text", ""))
        elif block.get("type") == "tool_use":
            args = block.get("input")
            calls.append(
                ToolCall(
                    id=block.get("id") or f"call_{len(calls)}",
                    name=block.get("name", ""),
                    arguments=args if isinstance(args, dict) else {},
                    arguments_error=None if isinstance(args, dict) else "input was not an object",
                )
            )
    u = data.get("usage") or {}
    cache_read = int(u.get("cache_read_input_tokens") or 0)
    cache_write = int(u.get("cache_creation_input_tokens") or 0)
    usage = Usage(
        input_tokens=int(u.get("input_tokens") or 0) + cache_read + cache_write,
        output_tokens=int(u.get("output_tokens") or 0),
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_write,
    )
    stop = _ANTHROPIC_STOP.get(data.get("stop_reason") or "", "other")
    return Reply("\n".join(t for t in texts if t), calls, usage, stop, data.get("model"))


# ====================================================================== OpenAI-compatible
class OpenAIProvider:
    """The OpenAI Chat Completions API (``/chat/completions``) with function tools.

    Works with any OpenAI-compatible server. The API key is required only for the default
    ``api.openai.com`` endpoint; local servers (vLLM, Ollama) usually need none.

    OpenAI's newer models take ``max_completion_tokens`` while many compatible servers only know
    ``max_tokens``: the provider starts with ``max_completion_tokens`` on api.openai.com and
    ``max_tokens`` elsewhere, and switches automatically if the server rejects the parameter.
    """

    name = "openai"

    def __init__(
        self,
        model: str,
        *,
        base_url: str | None = None,
        api_key_env: str = "OPENAI_API_KEY",
        http: HTTPConfig | None = None,
        temperature: float | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        self.model = model
        base = (base_url or os.environ.get("OPENAI_BASE_URL") or OPENAI_DEFAULT_BASE).rstrip("/")
        self.url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        is_openai = urllib.parse.urlparse(self.url).hostname == "api.openai.com"
        self.api_key = _api_key(
            api_key_env, required=is_openai, example="adapters/examples/simple-openai.yaml"
        )
        self.api_key_env = api_key_env
        self.http = http or HTTPConfig()
        self.temperature = temperature
        self.max_tokens_param = "max_completion_tokens" if is_openai else "max_tokens"
        self.extra_headers = extra_headers or {}

    def build_request(
        self, system: str, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> dict:
        """The JSON body for ``/chat/completions`` (exposed for tests and debugging)."""
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *openai_messages(messages)],
            self.max_tokens_param: max_tokens,
        }
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["parameters"],
                    },
                }
                for t in tools
            ]
        if self.temperature is not None:
            body["temperature"] = self.temperature
        return body

    def complete(
        self, system: str, messages: list[Message], tools: list[dict], max_tokens: int
    ) -> Reply:
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        for attempt in range(2):
            body = self.build_request(system, messages, tools, max_tokens)
            try:
                data = post_json(self.url, headers, body, self.http)
                break
            except HTTPStatusError as e:
                other = (
                    "max_tokens"
                    if self.max_tokens_param == "max_completion_tokens"
                    else "max_completion_tokens"
                )
                if attempt == 0 and e.status == 400 and self.max_tokens_param in e.body:
                    self.http.log(
                        f"[provider] server rejected {self.max_tokens_param}; using {other}"
                    )
                    self.max_tokens_param = other
                    continue
                raise _explain(e, self.api_key_env, "OPENAI_BASE_URL", self.model) from None
        return parse_openai_response(data)


def openai_messages(messages: list[Message]) -> list[dict]:
    """Convert neutral messages to Chat Completions messages (``tool`` role for results)."""
    out: list[dict] = []
    for m in messages:
        if m.role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.text or None}
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
                    }
                    for c in m.tool_calls
                ]
            elif not m.text:
                msg["content"] = "(no output)"
            out.append(msg)
        else:
            for r in m.results:
                content = r.content or "(empty)"
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": r.call_id,
                        "content": f"ERROR: {content}" if r.is_error else content,
                    }
                )
            if m.text or not m.results:
                out.append({"role": "user", "content": m.text or "(empty)"})
    return out


def parse_openai_response(data: dict) -> Reply:
    """Convert a ``/chat/completions`` response into a :class:`Reply`."""
    if "error" in data and not data.get("choices"):
        raise ProviderError(f"API error: {data['error']}")
    choices = data.get("choices") or []
    if not choices:
        raise ProviderError(f"response has no choices: {_snippet(json.dumps(data))}")
    choice = choices[0]
    msg = choice.get("message") or {}
    content = msg.get("content")
    if isinstance(content, list):  # some servers return content parts
        content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
    calls = []
    for i, tc in enumerate(msg.get("tool_calls") or []):
        fn = tc.get("function") or {}
        raw = fn.get("arguments")
        args: dict[str, Any] = {}
        err = None
        if isinstance(raw, dict):
            args = raw
        elif raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    args = parsed
                else:
                    err = "arguments must be a JSON object"
            except ValueError as e:
                err = f"arguments are not valid JSON ({e})"
        calls.append(
            ToolCall(
                id=tc.get("id") or f"call_{i}",
                name=fn.get("name", ""),
                arguments=args,
                arguments_error=err,
            )
        )
    u = data.get("usage") or {}
    details = u.get("prompt_tokens_details") or {}
    usage = Usage(
        input_tokens=int(u.get("prompt_tokens") or 0),
        output_tokens=int(u.get("completion_tokens") or 0),
        cache_read_input_tokens=int(details.get("cached_tokens") or 0),
    )
    finish = choice.get("finish_reason") or ""
    stop = (
        "tool_use"
        if calls or finish in ("tool_calls", "function_call")
        else {"stop": "end", "length": "max_tokens"}.get(finish, "other" if finish else "end")
    )
    return Reply(content or "", calls, usage, stop, data.get("model"))


# ====================================================================== factory
PROVIDERS = {"anthropic": AnthropicProvider, "openai": OpenAIProvider}


def make_provider(name: str, model: str, **kwargs: Any) -> AnthropicProvider | OpenAIProvider:
    """Build a provider by name (``anthropic`` or ``openai``); ``kwargs`` go to its constructor."""
    if name not in PROVIDERS:
        raise ProviderError(f"unknown provider {name!r}; choose one of: {', '.join(PROVIDERS)}")
    if not model:
        raise ProviderError("--model is required, e.g. --model <model-id>")
    if model.startswith("<") and model.endswith(">"):
        raise ProviderError(
            f"--model is still the placeholder {model}: edit your adapter file and replace it "
            "(and the adapter's `model:` value) with a real model ID for this endpoint"
        )
    return PROVIDERS[name](model, **kwargs)
