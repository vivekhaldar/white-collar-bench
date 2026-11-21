"""Run an ephemeral, filesystem-isolated Pi session against a LiteLLM proxy; export WCB usage.

Derived from the DeepSeek run's `pi_nebius.py`, with one security change its report asked for:
the provider key never enters the Pi sandbox. This wrapper (outside the sandbox) starts a local
forwarder that adds the LiteLLM key to each request and sends it on to `ANTHROPIC_BASE_URL` (the
runner's metering proxy under `wcb run --meter`, else the LiteLLM host). Pi gets a placeholder
key and the forwarder's loopback URL, so neither its environment nor its tools can read the key.

Environment: WCB_CLAUDE_MODEL (LiteLLM model name, e.g. claude-haiku-5.5), LITELLM_API_KEY,
ANTHROPIC_BASE_URL, WCB_PI_NODE_MODULES, WCB_TOOLS_VENV.
"""

import http.client
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL = os.environ["WCB_CLAUDE_MODEL"]
PI_ROOT = Path(os.environ.get("WCB_PI_NODE_MODULES", "/tmp/wcb-pi-current/node_modules"))
TOOLS_ROOT = Path(os.environ.get("WCB_TOOLS_VENV", "/tmp/wcb-claude-tools"))
TURN_BUDGET = 120

# LiteLLM's /model/info prices for these deployments, USD per million tokens.
PRICES = {
    "claude-haiku-5.5": {"input": 0.10, "output": 0.50, "cacheRead": 0.01, "cacheWrite": 0.125},
    "claude-sonnet-5.5": {"input": 2.0, "output": 10.0, "cacheRead": 0.10, "cacheWrite": 2.5},
    "claude-opus-5.5": {"input": 4.0, "output": 20.0, "cacheRead": 0.20, "cacheWrite": 5.0},
}
_HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
        "trailers", "transfer-encoding", "upgrade", "host", "content-length",
        "x-api-key", "authorization"}  # fmt: skip


def start_forwarder(upstream: str, key: str) -> ThreadingHTTPServer:
    up = urllib.parse.urlsplit(upstream)
    conn_cls = http.client.HTTPSConnection if up.scheme == "https" else http.client.HTTPConnection

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in _HOP}
            headers["x-api-key"] = key
            conn = conn_cls(up.netloc, timeout=900)
            try:
                conn.request(self.command, up.path.rstrip("/") + self.path, body=body,
                             headers=headers)  # fmt: skip
                resp = conn.getresponse()
                self.send_response(resp.status, resp.reason)
                for k, v in resp.getheaders():
                    if k.lower() not in _HOP:
                        self.send_header(k, v)
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Connection", "close")
                self.end_headers()
                while chunk := resp.read1(65536):
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except OSError as e:
                msg = json.dumps({"error": f"forwarder: {e}"}).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
            finally:
                conn.close()
                self.close_connection = True

        do_GET = do_POST

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    workspace = Path(os.environ["WCB_WORKSPACE"]).resolve()
    prompt = Path(os.environ["WCB_PROMPT_FILE"]).read_text()
    upstream = os.environ.get("ANTHROPIC_BASE_URL", "https://brk-litellm.centralus.cloudapp.azure.com")
    forwarder = start_forwarder(upstream, os.environ["LITELLM_API_KEY"])
    price = PRICES[MODEL]
    usage = dict(
        input_tokens=0, output_tokens=0, cache_read_input_tokens=0,
        cache_creation_input_tokens=0, cost_usd=0.0, tool_calls=0, turns=0,
        model=MODEL, provider="litellm", harness="pi/1.5.2",
    )  # fmt: skip
    last_stop = None
    turn_limit_hit = False
    with tempfile.TemporaryDirectory(prefix="wcb-pi-config-") as config_dir:
        config = Path(config_dir)
        models = {
            "providers": {
                "litellm": {
                    "baseUrl": f"http://127.0.0.1:{forwarder.server_address[1]}",
                    "api": "anthropic-messages",
                    "apiKey": "placeholder-key-injected-outside-sandbox",
                    "models": [
                        {
                            "id": MODEL,
                            "name": MODEL,
                            "reasoning": True,
                            "input": ["text"],
                            "contextWindow": 1000000,
                            "maxTokens": 128000,
                            "cost": price,
                            "thinkingLevelMap": {"off": None, "minimal": None, "low": "low",
                                                 "medium": "medium", "high": "high"},
                            "compat": {
                                "forceAdaptiveThinking": True,
                                "supportsTemperature": False,
                                "supportsStrictTools": True,
                            },
                        }
                    ],
                }
            }
        }
        (config / "models.json").write_text(json.dumps(models))
        (config / "settings.json").write_text(
            json.dumps({"quietStartup": True, "defaultThinkingLevel": "medium"})
        )
        (config / "runtime.mjs").write_text(Path(__file__).with_name("runtime.mjs").read_text())
        cmd = [
            "bwrap", "--die-with-parent", "--unshare-all", "--share-net",
            "--ro-bind", "/usr", "/usr", "--symlink", "usr/bin", "/bin",
            "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
            "--ro-bind", "/etc/ssl", "/etc/ssl", "--ro-bind", "/etc/resolv.conf", "/etc/resolv.conf",
            "--ro-bind", "/etc/hosts", "/etc/hosts",
            "--ro-bind", str(PI_ROOT), "/opt/pi/node_modules",
            "--ro-bind", str(TOOLS_ROOT), "/opt/tools",
            "--bind", str(config), "/pi-config", "--bind", str(workspace), "/work",
            "--tmpfs", "/tmp", "--dir", "/home/user", "--proc", "/proc", "--dev", "/dev",
            "--chdir", "/work", "--",
            "/usr/local/bin/node", "/opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
            "--provider", "litellm", "--model", MODEL, "--thinking", "medium",
            "--print", "--mode", "json", "--no-session", "--offline", "--no-extensions",
            "--extension", "/pi-config/runtime.mjs", "--no-mcp", "--no-skills",
            "--no-prompt-templates", "--no-themes", "--no-context-files", "--no-approve",
            "--tools", "read,bash,edit,write",
            "--append-system-prompt",
            "You are running unattended in a benchmark session. Nobody will answer "
            "questions or approve actions. Work only with files inside /work; "
            "treat the task's date as today. Stop when the task is done.",
            "--", prompt,
        ]  # fmt: skip
        env = {
            "PATH": "/opt/tools/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": "/home/user",
            "LANG": "C.UTF-8",
            "PI_CODING_AGENT_DIR": "/pi-config",
            "PI_OFFLINE": "1",
            "PI_TELEMETRY": "0",
        }
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", bufsize=1)  # fmt: skip

        def forward(signum, _frame):
            if proc.poll() is None:
                proc.send_signal(signum)

        old = {s: signal.signal(s, forward) for s in (signal.SIGTERM, signal.SIGINT)}
        try:
            for line in proc.stdout:
                try:
                    event = json.loads(line)
                except ValueError:
                    print(line, end="", flush=True)
                    continue
                if event.get("type") != "message_update":
                    print(line, end="", flush=True)
                if event.get("type") == "tool_execution_start":
                    usage["tool_calls"] += 1
                if event.get("type") == "message_end":
                    message = event.get("message", {})
                    if message.get("role") == "assistant":
                        last_stop = message.get("stopReason")
                        u = message.get("usage", {})
                        usage["turns"] += 1
                        usage["input_tokens"] += sum(
                            u.get(k, 0) for k in ("input", "cacheRead", "cacheWrite")
                        )
                        usage["output_tokens"] += u.get("output", 0)
                        usage["cache_read_input_tokens"] += u.get("cacheRead", 0)
                        usage["cache_creation_input_tokens"] += u.get("cacheWrite", 0)
                        usage["cost_usd"] += u.get("cost", {}).get("total", 0)
                if (event.get("type") == "turn_end" and usage["turns"] >= TURN_BUDGET
                        and last_stop == "toolUse"):  # fmt: skip
                    turn_limit_hit = True
                    print(f"Pi session exceeded the fixed {TURN_BUDGET}-turn budget",
                          file=sys.stderr, flush=True)  # fmt: skip
                    proc.terminate()
            code = proc.wait()
        finally:
            for s, handler in old.items():
                signal.signal(s, handler)
            forwarder.shutdown()
            reason = "turn_limit" if turn_limit_hit else last_stop or "no_assistant_message"
            usage["termination"] = {"reason": reason, "incomplete": reason != "stop",
                                    "raw_stop_reason": last_stop}  # fmt: skip
            out = workspace / ".wcb" / "usage.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(usage, indent=2) + "\n")
        if code == 0 and last_stop in ("error", "aborted"):
            return 1
        return code if code >= 0 else 128 - code


if __name__ == "__main__":
    sys.exit(main())
