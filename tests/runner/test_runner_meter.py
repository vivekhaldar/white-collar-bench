"""`wcb run --meter`: sessions' model calls go through the proxy and land in session.json."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wcb.cli import main
from wcb.paths import repo_root
from wcb.util.io import read_json

ROOT = repo_root()
AGENT = """
import json, os, runpy, sys, urllib.request
req = urllib.request.Request(os.environ["ANTHROPIC_BASE_URL"] + "/v1/messages",
    data=json.dumps({"model": "fake-model"}).encode(), method="POST",
    headers={"Content-Type": "application/json"})
urllib.request.urlopen(req, timeout=10).read()
sys.argv = ["null"]
runpy.run_module("wcb.baselines.null", run_name="__main__")
"""


class _Upstream(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        data = json.dumps({"model": "fake-model",
                           "usage": {"input_tokens": 11, "output_tokens": 3}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def test_run_with_meter_records_usage(tmp_path, monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _Upstream)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{srv.server_address[1]}")
        agent = tmp_path / "agent.py"
        agent.write_text(AGENT)
        adapter = tmp_path / "a.yaml"
        adapter.write_text(f"name: metered\nversion: '1'\nmodel: fake\ncmd: [python, {agent}]\n")
        out = tmp_path / "run"
        assert main(["run", "--adapter", str(adapter), "--world",
                     str(ROOT / "tests/fixtures/mini-world"), "--out", str(out), "--no-oracle",
                     "--meter"]) == 0
    finally:
        srv.shutdown()
        srv.server_close()
    assert read_json(out / "run.json")["options"]["meter"] is True
    sessions = sorted((out / "mini" / "r1" / "sessions").glob("*/session.json"))
    assert len(sessions) == 4
    for f in sessions:
        s = read_json(f)
        assert s["status"] == "ok", s
        m = s["metered_usage"]
        assert m["calls"] == 1 and m["input_tokens"] == 11 and m["output_tokens"] == 3
        assert m["models"] == ["fake-model"]
    lines = (out / "meter.jsonl").read_text().splitlines()
    assert len(lines) == 4 and all(json.loads(x)["tag"].startswith("mini/r1/") for x in lines)


def test_report_prefers_metered_tokens(tmp_path, monkeypatch):
    test_run_with_meter_records_usage(tmp_path, monkeypatch)
    out = tmp_path / "run"
    assert main(["score", str(out)]) == 0
    eff = read_json(out / "scores" / "report.json")["efficiency"]["summary"]["ingest"]
    assert eff["usage_metered"] == 2 and eff["input_tokens"]["total"] == 22
    assert "| Metered |" in (out / "scores" / "report.md").read_text()
