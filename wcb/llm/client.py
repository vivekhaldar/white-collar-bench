"""A minimal, dependency-free LLM client used by the LLM judge (docs/judge.md).

One interface, three back ends, chosen by a *spec* string:

| Spec | Back end |
|---|---|
| `anthropic:<model>` | Anthropic Messages API. Uses the official `anthropic` SDK when it is importable, otherwise a raw HTTPS POST to `$ANTHROPIC_BASE_URL/v1/messages` (default `https://api.anthropic.com`) with `x-api-key: $ANTHROPIC_API_KEY` and `anthropic-version: 2023-06-01`. |
| `openai:<model>` | Any OpenAI-compatible chat endpoint: POST `$OPENAI_BASE_URL/chat/completions` (default `https://api.openai.com/v1`) with `Authorization: Bearer $OPENAI_API_KEY`. Works with OpenRouter, vLLM, llama.cpp servers and similar. |
| `cmd:<shell command>` | Runs the command with `/bin/sh -c`, writes the prompt to stdin and reads the completion from stdout, e.g. `cmd:claude -p`. |

Every client has a `model` attribute (the model name, or the command for `cmd:`), a `spec`
attribute (the full spec string) and one method::

    complete(prompt, *, system=None, temperature=0.0, max_tokens=512) -> str

HTTP calls use `urllib` only and retry with exponential backoff on HTTP 429 and 5xx and on
connection errors, honouring `Retry-After`. Some newer models reject sampling parameters; when
a request fails with HTTP 400 mentioning `temperature`, the client drops the parameter for the
rest of its life and retries once, so a judge pinned to such a model still works (decisions
are then made at the model's default sampling, and the judge cache keeps re-grading stable).

Tests never touch the network: they inject a fake `urlopen` or a fake client.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

ANTHROPIC_DEFAULT_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"

#: HTTP statuses worth retrying: rate limits, timeouts, conflicts and server errors.
RETRY_STATUSES = frozenset({408, 409, 429, 500, 502, 503, 504, 529})


class LLMError(RuntimeError):
    """A model call failed for good (after retries, or with a non-retryable error)."""

    def __init__(self, message: str, *, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


# ---------------------------------------------------------------- HTTP with retries
def post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    *,
    retries: int = 4,
    backoff: float = 1.0,
    timeout: float = 120.0,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """POST `body` as JSON and return the decoded JSON response.

    Retries up to `retries` times on HTTP 429/5xx (see `RETRY_STATUSES`) and on connection
    errors, sleeping `backoff * 2**attempt` seconds plus jitter, or the server's `Retry-After`
    when it is given. Raises `LLMError` (with `.status` and `.body`) otherwise.
    """
    data = json.dumps(body).encode("utf-8")
    hdrs = {"content-type": "application/json", **headers}
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
        try:
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            text = _read_error_body(e)
            if e.code not in RETRY_STATUSES or attempt >= retries:
                raise LLMError(
                    f"HTTP {e.code} from {url}: {text[:500]}", status=e.code, body=text
                ) from e
            delay = _retry_after(e) or backoff * (2**attempt) + random.uniform(0, backoff)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt >= retries:
                raise LLMError(f"cannot reach {url}: {e}") from e
            delay = backoff * (2**attempt) + random.uniform(0, backoff)
        attempt += 1
        sleep(min(delay, 60.0))


def _read_error_body(e: urllib.error.HTTPError) -> str:
    try:
        return e.read().decode("utf-8", "replace")
    except Exception:  # pragma: no cover - best effort
        return ""


def _retry_after(e: urllib.error.HTTPError) -> float | None:
    value = e.headers.get("retry-after") if e.headers else None
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _mentions(err: LLMError, word: str) -> bool:
    return err.status == 400 and word in (err.body or str(err)).lower()


# ---------------------------------------------------------------- clients
class LLMClient:
    """Base class. Subclasses implement `complete`.

    Attributes:
        model: the model name (for `cmd:` clients, the command line).
        spec: the spec string the client was made from, e.g. `anthropic:claude-opus-5-5`.
    """

    model: str = ""
    spec: str = ""

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        """Return the model's text completion of a single-turn `prompt`."""
        raise NotImplementedError


class AnthropicClient(LLMClient):
    """Anthropic Messages API client (official SDK when importable, raw HTTPS otherwise).

    `use_sdk=None` picks the SDK if `import anthropic` works. Pass `use_sdk=False` to force
    the raw HTTP path. Environment: `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`,
    `WCB_LLM_MAX_RETRIES` (default 4), `WCB_LLM_TIMEOUT` (seconds, default 120) and
    `WCB_LLM_EFFORT` (optional `output_config.effort`, e.g. `low`, for models that support it).
    """

    def __init__(
        self,
        model: str,
        *,
        use_sdk: bool | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        retries: int | None = None,
        timeout: float | None = None,
        effort: str | None = None,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = model
        self.spec = f"anthropic:{model}"
        self.api_key = api_key
        self.base_url = (
            base_url or os.environ.get("ANTHROPIC_BASE_URL") or ANTHROPIC_DEFAULT_BASE_URL
        ).rstrip("/")
        self.retries = _env_int("WCB_LLM_MAX_RETRIES", 4) if retries is None else retries
        self.timeout = _env_float("WCB_LLM_TIMEOUT", 120.0) if timeout is None else timeout
        self.effort = effort if effort is not None else (os.environ.get("WCB_LLM_EFFORT") or None)
        if use_sdk is None:
            try:
                import anthropic  # noqa: F401

                use_sdk = True
            except ImportError:
                use_sdk = False
        self.use_sdk = use_sdk
        self.send_temperature = True
        self._urlopen = urlopen
        self._sleep = sleep
        self._sdk: Any = None

    def _body(
        self, prompt: str, system: str | None, temperature: float, max_tokens: int
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        if self.send_temperature:
            body["temperature"] = temperature
        if self.effort:
            body["output_config"] = {"effort": self.effort}
        return body

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        for _ in range(2):  # second pass only after dropping a rejected temperature
            body = self._body(prompt, system, temperature, max_tokens)
            try:
                resp = self._call_sdk(body) if self.use_sdk else self._call_http(body)
            except LLMError as e:
                if self.send_temperature and _mentions(e, "temperature"):
                    self.send_temperature = False
                    continue
                raise
            return _anthropic_text(resp)
        raise LLMError("unreachable")  # pragma: no cover

    def _call_http(self, body: dict[str, Any]) -> dict[str, Any]:
        key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("ANTHROPIC_API_KEY is not set (needed for anthropic:<model> judges)")
        headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
        return post_json(
            f"{self.base_url}/v1/messages",
            body,
            headers,
            retries=self.retries,
            timeout=self.timeout,
            urlopen=self._urlopen,
            sleep=self._sleep,
        )

    def _call_sdk(self, body: dict[str, Any]) -> dict[str, Any]:
        import anthropic

        if self._sdk is None:
            kwargs: dict[str, Any] = {"max_retries": self.retries, "timeout": self.timeout}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._sdk = anthropic.Anthropic(**kwargs)
        extra = {}
        if "output_config" in body:  # pass through even if the installed SDK predates it
            extra["extra_body"] = {"output_config": body.pop("output_config")}
        try:
            msg = self._sdk.messages.create(**body, **extra)
        except anthropic.APIStatusError as e:
            raise LLMError(str(e), status=getattr(e, "status_code", None), body=str(e)) from e
        except anthropic.APIError as e:  # connection errors after the SDK's own retries
            raise LLMError(str(e)) from e
        content = [
            {"type": getattr(b, "type", ""), "text": getattr(b, "text", "")}
            for b in (msg.content or [])
        ]
        return {"content": content, "stop_reason": getattr(msg, "stop_reason", None)}


def _anthropic_text(resp: dict[str, Any]) -> str:
    """Concatenate the `text` blocks of a Messages API response (thinking blocks are skipped)."""
    blocks = resp.get("content") or []
    return "".join(
        b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
    )


class OpenAIClient(LLMClient):
    """OpenAI-compatible `/chat/completions` client (OpenAI, OpenRouter, vLLM, ...).

    Environment: `OPENAI_BASE_URL` (default `https://api.openai.com/v1`), `OPENAI_API_KEY`
    (omitted from the request when unset, for local servers), `WCB_LLM_MAX_RETRIES`,
    `WCB_LLM_TIMEOUT`. If the server rejects `max_tokens` the client switches to
    `max_completion_tokens`; if it rejects `temperature` the client stops sending it.
    """

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        retries: int | None = None,
        timeout: float | None = None,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.model = model
        self.spec = f"openai:{model}"
        self.api_key = api_key
        self.base_url = (
            base_url or os.environ.get("OPENAI_BASE_URL") or OPENAI_DEFAULT_BASE_URL
        ).rstrip("/")
        self.retries = _env_int("WCB_LLM_MAX_RETRIES", 4) if retries is None else retries
        self.timeout = _env_float("WCB_LLM_TIMEOUT", 120.0) if timeout is None else timeout
        self.send_temperature = True
        self.max_tokens_field = "max_tokens"
        self._urlopen = urlopen
        self._sleep = sleep

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        key = self.api_key or os.environ.get("OPENAI_API_KEY")
        headers = {"authorization": f"Bearer {key}"} if key else {}
        messages = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": prompt}
        ]
        for _ in range(3):  # at most two parameter fix-ups
            body: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                self.max_tokens_field: max_tokens,
            }
            if self.send_temperature:
                body["temperature"] = temperature
            try:
                resp = post_json(
                    f"{self.base_url}/chat/completions",
                    body,
                    headers,
                    retries=self.retries,
                    timeout=self.timeout,
                    urlopen=self._urlopen,
                    sleep=self._sleep,
                )
            except LLMError as e:
                if self.max_tokens_field == "max_tokens" and _mentions(e, "max_tokens"):
                    self.max_tokens_field = "max_completion_tokens"
                    continue
                if self.send_temperature and _mentions(e, "temperature"):
                    self.send_temperature = False
                    continue
                raise
            return _openai_text(resp)
        raise LLMError(f"request to {self.base_url} kept failing on parameter errors")


def _openai_text(resp: dict[str, Any]) -> str:
    choices = resp.get("choices") or []
    if not choices:
        return ""
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, list):  # some servers return content parts
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


class CommandClient(LLMClient):
    """Run a shell command per call: prompt on stdin, completion on stdout.

    The system prompt, if any, is prepended to the prompt, separated by a blank line. The
    command also sees `WCB_LLM_TEMPERATURE` and `WCB_LLM_MAX_TOKENS` in its environment.
    A non-zero exit is retried `retries` times (env `WCB_LLM_MAX_RETRIES`, default 2), then
    raises `LLMError`. `WCB_LLM_TIMEOUT` (seconds, default 300) bounds each run.
    """

    def __init__(self, command: str, *, retries: int | None = None, timeout: float | None = None):
        self.model = command
        self.spec = f"cmd:{command}"
        self.command = command
        self.retries = _env_int("WCB_LLM_MAX_RETRIES", 2) if retries is None else retries
        self.timeout = _env_float("WCB_LLM_TIMEOUT", 300.0) if timeout is None else timeout

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
    ) -> str:
        text = f"{system}\n\n{prompt}" if system else prompt
        env = {
            **os.environ,
            "WCB_LLM_TEMPERATURE": str(temperature),
            "WCB_LLM_MAX_TOKENS": str(max_tokens),
        }
        last = ""
        for _ in range(self.retries + 1):
            try:
                proc = subprocess.run(
                    self.command,
                    shell=True,
                    input=text,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    env=env,
                )
            except subprocess.TimeoutExpired:
                last = f"timed out after {self.timeout}s"
                continue
            if proc.returncode == 0:
                return proc.stdout
            last = f"exit {proc.returncode}: {proc.stderr.strip()[:500]}"
        raise LLMError(f"judge command {self.command!r} failed: {last}")


def make_client(spec: str) -> LLMClient:
    """Build a client from a spec: `anthropic:<model>`, `openai:<model>` or `cmd:<command>`.

    A spec without a known provider prefix is treated as an Anthropic model name.
    """
    spec = spec.strip()
    provider, sep, rest = spec.partition(":")
    if sep and provider == "anthropic" and rest:
        return AnthropicClient(rest)
    if sep and provider == "openai" and rest:
        return OpenAIClient(rest)
    if sep and provider == "cmd" and rest.strip():
        return CommandClient(rest.strip())
    if sep and provider in ("anthropic", "openai", "cmd"):
        raise ValueError(f"LLM spec {spec!r} names no model or command")
    if not spec:
        raise ValueError("empty LLM spec")
    return AnthropicClient(spec)
