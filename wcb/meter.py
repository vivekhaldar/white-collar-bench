"""A local metering proxy for model APIs, so token use is measured rather than self-reported.

Agents send their model calls to the proxy instead of the provider. The proxy forwards each
request unchanged, streams the response back, and records the token usage it finds in the
response (JSON or server-sent events) in a JSONL log. URLs carry a *tag* that attributes calls to
a session, and the upstream provider:

    http://127.0.0.1:<port>/t/<tag>/anthropic/v1/messages      -> https://api.anthropic.com/v1/messages
    http://127.0.0.1:<port>/t/<tag>/openai/v1/chat/completions -> https://api.openai.com/v1/chat/completions

So an agent is pointed at the proxy with, for example,
``ANTHROPIC_BASE_URL=http://127.0.0.1:8787/t/2027-03-01.ingest/anthropic`` and
``OPENAI_BASE_URL=http://127.0.0.1:8787/t/2027-03-01.ingest/openai/v1``.

Usage formats understood: Anthropic Messages (``usage`` in JSON; ``message_start`` and
``message_delta`` events when streaming) and OpenAI Chat Completions and Responses (``usage`` in
JSON; the final chunk when ``stream_options.include_usage`` is set; ``response.completed``).
Requests whose usage cannot be read are still logged, with ``usage_found: false``.

Only the standard library is used. The proxy listens on 127.0.0.1 by default and should never
be exposed to other machines: it forwards the caller's credentials as they are.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

DEFAULT_UPSTREAMS = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
}


def default_upstreams() -> dict[str, str]:
    """Provider endpoints, honouring ANTHROPIC_BASE_URL and OPENAI_BASE_URL (e.g. a gateway).

    A trailing ``/v1`` on the OpenAI URL is dropped because clients send it in the path.
    """
    import os

    ups = dict(DEFAULT_UPSTREAMS)
    if os.environ.get("ANTHROPIC_BASE_URL"):
        ups["anthropic"] = os.environ["ANTHROPIC_BASE_URL"].rstrip("/")
    if os.environ.get("OPENAI_BASE_URL"):
        ups["openai"] = os.environ["OPENAI_BASE_URL"].rstrip("/").removesuffix("/v1")
    return ups


_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
    "transfer-encoding", "upgrade", "host", "content-length", "accept-encoding",
}
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens",
              "cache_creation_input_tokens")


# ---------------------------------------------------------------- usage parsing
def _usage_from_obj(obj: dict[str, Any]) -> dict[str, int] | None:
    """Normalize one provider ``usage`` object to Anthropic-style keys."""
    if not isinstance(obj, dict):
        return None
    out: dict[str, int] = {}

    def num(v: Any) -> int | None:
        return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    if any(k in obj for k in ("input_tokens", "output_tokens")):  # Anthropic, OpenAI Responses
        for k in USAGE_KEYS:
            if num(obj.get(k)) is not None:
                out[k] = num(obj[k])
        details = obj.get("input_tokens_details") or {}
        if num(details.get("cached_tokens")):
            out["cache_read_input_tokens"] = num(details["cached_tokens"])
            out["input_tokens"] = out.get("input_tokens", 0) - out["cache_read_input_tokens"]
    elif any(k in obj for k in ("prompt_tokens", "completion_tokens")):  # OpenAI Chat
        cached = num((obj.get("prompt_tokens_details") or {}).get("cached_tokens")) or 0
        out["input_tokens"] = (num(obj.get("prompt_tokens")) or 0) - cached
        out["output_tokens"] = num(obj.get("completion_tokens")) or 0
        if cached:
            out["cache_read_input_tokens"] = cached
    return out or None


def parse_usage(body: bytes, content_type: str) -> tuple[dict[str, int] | None, str | None]:
    """Token usage and model name from a complete response body (JSON or SSE)."""
    text = body.decode("utf-8", errors="replace")
    if "text/event-stream" in content_type or text.lstrip().startswith(("event:", "data:")):
        return _parse_sse(text)
    try:
        data = json.loads(text)
    except ValueError:
        return None, None
    if not isinstance(data, dict):
        return None, None
    model = data.get("model") if isinstance(data.get("model"), str) else None
    usage = _usage_from_obj(data.get("usage"))
    if usage is None and isinstance(data.get("response"), dict):
        usage = _usage_from_obj(data["response"].get("usage"))
        model = model or data["response"].get("model")
    return usage, model


def _parse_sse(text: str) -> tuple[dict[str, int] | None, str | None]:
    usage: dict[str, int] = {}
    model = None
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            ev = json.loads(payload)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        kind = ev.get("type")
        if kind == "message_start" and isinstance(ev.get("message"), dict):  # Anthropic
            msg = ev["message"]
            model = msg.get("model") or model
            usage.update(_usage_from_obj(msg.get("usage")) or {})
        elif kind == "message_delta":  # Anthropic: cumulative output tokens
            u = _usage_from_obj(ev.get("usage")) or {}
            usage.update({k: v for k, v in u.items() if k == "output_tokens" or v})
        elif kind == "response.completed" and isinstance(ev.get("response"), dict):  # Responses
            model = ev["response"].get("model") or model
            usage.update(_usage_from_obj(ev["response"].get("usage")) or {})
        elif isinstance(ev.get("usage"), dict):  # Chat Completions final chunk
            model = ev.get("model") or model
            usage.update(_usage_from_obj(ev["usage"]) or {})
        elif isinstance(ev.get("model"), str):
            model = model or ev["model"]
    return (usage or None), model


# ---------------------------------------------------------------- proxy
@dataclass
class MeterProxy:
    """A metering proxy running in a background thread. Use as a context manager."""

    log_path: Path
    host: str = "127.0.0.1"
    port: int = 0  # 0 picks a free port
    upstreams: dict[str, str] = field(default_factory=default_upstreams)
    timeout_s: float = 600.0

    def __post_init__(self) -> None:
        self.log_path = Path(self.log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    # ---- lifecycle
    def start(self) -> MeterProxy:
        handler = _make_handler(self)
        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def __enter__(self) -> MeterProxy:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # ---- URLs and environment
    def base_url(self, tag: str, provider: str, host: str | None = None) -> str:
        """Base URL an agent should use for `provider`, attributing calls to `tag`."""
        h = host or self.host
        quoted = urllib.parse.quote(tag, safe="")
        suffix = "/v1" if provider == "openai" else ""
        return f"http://{h}:{self.port}/t/{quoted}/{provider}{suffix}"

    def session_env(self, tag: str, host: str | None = None) -> dict[str, str]:
        """Environment variables that point common SDKs at the proxy for one session."""
        return {
            "WCB_LLM_BASE_URL": f"http://{host or self.host}:{self.port}/t/"
                                f"{urllib.parse.quote(tag, safe='')}",
            "ANTHROPIC_BASE_URL": self.base_url(tag, "anthropic", host),
            "OPENAI_BASE_URL": self.base_url(tag, "openai", host),
        }

    # ---- records
    def record(self, rec: dict[str, Any]) -> None:
        line = json.dumps(rec, sort_keys=True)
        with self._lock, self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def summarize(log_path: Path, tag: str | None = None) -> dict[str, Any]:
    """Totals over the log, optionally for one tag: calls, tokens per kind and models seen."""
    tot: dict[str, Any] = {"calls": 0, "calls_without_usage": 0, "errors": 0,
                           **{k: 0 for k in USAGE_KEYS}, "models": []}
    models: set[str] = set()
    p = Path(log_path)
    if not p.is_file():
        return tot
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if tag is not None and r.get("tag") != tag:
            continue
        tot["calls"] += 1
        if not r.get("usage_found"):
            tot["calls_without_usage"] += 1
        if not (200 <= int(r.get("status") or 0) < 300):
            tot["errors"] += 1
        for k in USAGE_KEYS:
            tot[k] += int((r.get("usage") or {}).get(k) or 0)
        if r.get("model"):
            models.add(r["model"])
    tot["models"] = sorted(models)
    return tot


def _make_handler(proxy: MeterProxy):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args) -> None:  # silence the default stderr access log
            pass

        def _route(self) -> tuple[str, str, str] | None:
            parts = self.path.split("/", 4)  # '', 't', tag, provider, rest
            if len(parts) < 4 or parts[1] != "t":
                return None
            tag = urllib.parse.unquote(parts[2])
            provider = parts[3]
            rest = "/" + parts[4] if len(parts) > 4 else "/"
            if provider not in proxy.upstreams:
                return None
            return tag, provider, rest

        def _handle(self) -> None:
            route = self._route()
            if route is None:
                body = json.dumps({"error": "wcb meter: use /t/<tag>/<provider>/<path>; "
                                            f"providers: {sorted(proxy.upstreams)}"}).encode()
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            tag, provider, rest = route
            length = int(self.headers.get("Content-Length") or 0)
            req_body = self.rfile.read(length) if length else None
            up = urllib.parse.urlsplit(proxy.upstreams[provider])
            conn_cls = (http.client.HTTPSConnection if up.scheme == "https"
                        else http.client.HTTPConnection)
            t0 = time.monotonic()
            rec: dict[str, Any] = {
                "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tag": tag,
                "provider": provider, "method": self.command, "path": rest.split("?")[0],
            }
            headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP}
            headers["Accept-Encoding"] = "identity"  # so usage can be read from the body
            try:
                conn = conn_cls(up.netloc, timeout=proxy.timeout_s)
                conn.request(self.command, up.path.rstrip("/") + rest, body=req_body,
                             headers=headers)
                resp = conn.getresponse()
            except OSError as e:
                rec.update(status=502, error=str(e), usage_found=False,
                           wall_s=round(time.monotonic() - t0, 3))
                proxy.record(rec)
                body = json.dumps({"error": f"wcb meter: upstream unreachable: {e}"}).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() not in _HOP:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.send_header("Connection", "close")
            self.end_headers()
            buf = bytearray()
            try:
                while True:
                    chunk = resp.read1(65536)
                    if not chunk:
                        break
                    buf += chunk
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except OSError:
                rec["client_disconnected"] = True
            finally:
                conn.close()
                self.close_connection = True
            usage, model = parse_usage(bytes(buf), resp.getheader("Content-Type") or "")
            if model is None and req_body:
                try:
                    model = json.loads(req_body).get("model")
                except (ValueError, AttributeError):
                    model = None
            rec.update(status=resp.status, model=model, usage=usage or {},
                       usage_found=usage is not None, wall_s=round(time.monotonic() - t0, 3))
            proxy.record(rec)

        do_POST = _handle
        do_GET = _handle
        do_PUT = _handle
        do_DELETE = _handle

    return Handler
