"""The metering proxy: forwarding, streaming and usage accounting against a fake upstream."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from wcb.meter import MeterProxy, parse_usage, summarize

ANTHROPIC_JSON = {"model": "claude-x", "usage": {"input_tokens": 100, "output_tokens": 20,
                                                 "cache_read_input_tokens": 50}}
ANTHROPIC_SSE = (
    'event: message_start\ndata: {"type":"message_start","message":{"model":"claude-x",'
    '"usage":{"input_tokens":30,"output_tokens":1,"cache_creation_input_tokens":7}}}\n\n'
    'event: content_block_delta\ndata: {"type":"content_block_delta","delta":{"text":"hi"}}\n\n'
    'event: message_delta\ndata: {"type":"message_delta","usage":{"output_tokens":12}}\n\n'
)
OPENAI_CHAT = {"model": "gpt-x", "usage": {"prompt_tokens": 80, "completion_tokens": 9,
                                           "prompt_tokens_details": {"cached_tokens": 30}}}
OPENAI_STREAM = (
    'data: {"model":"gpt-x","choices":[{"delta":{"content":"a"}}]}\n\n'
    'data: {"model":"gpt-x","choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2}}\n\n'
    "data: [DONE]\n\n"
)
RESPONSES_STREAM = (
    'data: {"type":"response.output_text.delta","delta":"x"}\n\n'
    'data: {"type":"response.completed","response":{"model":"gpt-r","usage":{"input_tokens":40,'
    '"output_tokens":4,"input_tokens_details":{"cached_tokens":10}}}}\n\n'
)


class _Upstream(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.seen.append((self.path, dict(self.headers), body))
        if body.get("stream"):
            data, ctype = (ANTHROPIC_SSE if "messages" in self.path else OPENAI_STREAM), \
                "text/event-stream"
            data = data.encode()
        elif self.path.endswith("/fail"):
            data, ctype = b'{"error": "bad"}', "application/json"
            self.send_response(400)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        else:
            payload = ANTHROPIC_JSON if "messages" in self.path else OPENAI_CHAT
            data, ctype = json.dumps(payload).encode(), "application/json"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def upstream():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    srv.seen = []
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()
    srv.server_close()


def _post(url, body, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, r.read()


def test_forwards_and_meters_by_tag(upstream, tmp_path):
    base = f"http://127.0.0.1:{upstream.server_address[1]}"
    log = tmp_path / "meter.jsonl"
    with MeterProxy(log, upstreams={"anthropic": base, "openai": base}) as p:
        env = p.session_env("2027-03-01.ingest")
        status, body = _post(env["ANTHROPIC_BASE_URL"] + "/v1/messages", {"model": "claude-x"},
                             {"x-api-key": "k1"})
        assert status == 200 and json.loads(body) == ANTHROPIC_JSON
        _, body = _post(env["ANTHROPIC_BASE_URL"] + "/v1/messages", {"stream": True})
        assert body.decode() == ANTHROPIC_SSE  # streamed through unchanged
        q = p.session_env("cp1.query")
        _post(q["OPENAI_BASE_URL"] + "/chat/completions", {"model": "gpt-x"})
        _post(q["OPENAI_BASE_URL"] + "/chat/completions", {"stream": True})
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(q["OPENAI_BASE_URL"] + "/fail", {"model": "gpt-x"})
        assert e.value.code == 400
    path, headers, _ = upstream.seen[0]
    assert path == "/v1/messages" and {k.lower(): v for k, v in headers.items()}["x-api-key"] == "k1"
    assert upstream.seen[2][0] == "/v1/chat/completions"
    ingest = summarize(log, "2027-03-01.ingest")
    assert ingest["calls"] == 2 and ingest["models"] == ["claude-x"]
    assert ingest["input_tokens"] == 130 and ingest["output_tokens"] == 32
    assert ingest["cache_read_input_tokens"] == 50 and ingest["cache_creation_input_tokens"] == 7
    query = summarize(log, "cp1.query")
    assert query["calls"] == 3 and query["errors"] == 1 and query["calls_without_usage"] == 1
    assert query["input_tokens"] == 50 + 5 and query["output_tokens"] == 11
    assert query["cache_read_input_tokens"] == 30
    assert summarize(log)["calls"] == 5


def test_bad_route_and_unreachable_upstream(tmp_path):
    log = tmp_path / "m.jsonl"
    with MeterProxy(log, upstreams={"openai": "http://127.0.0.1:9"}) as p:
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(f"http://127.0.0.1:{p.port}/v1/messages", {})
        assert e.value.code == 404
        with pytest.raises(urllib.error.HTTPError) as e:
            _post(p.base_url("s", "openai") + "/chat/completions", {})
        assert e.value.code == 502
    s = summarize(log, "s")
    assert s["calls"] == 1 and s["errors"] == 1


def test_parse_usage_formats():
    u, m = parse_usage(RESPONSES_STREAM.encode(), "text/event-stream")
    assert m == "gpt-r" and u == {"input_tokens": 30, "output_tokens": 4,
                                  "cache_read_input_tokens": 10}
    u, m = parse_usage(b'{"response": {"model": "r", "usage": {"input_tokens": 3, '
                       b'"output_tokens": 1}}}', "application/json")
    assert m == "r" and u == {"input_tokens": 3, "output_tokens": 1}
    assert parse_usage(b"not json", "application/json") == (None, None)
