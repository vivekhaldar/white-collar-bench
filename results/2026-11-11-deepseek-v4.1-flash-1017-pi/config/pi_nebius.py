"""Run an ephemeral, filesystem-isolated Pi session and export WCB usage."""

import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

MODEL = "deepseek-ai/DeepSeek-V4.1-Flash-1017"
PI_ROOT = Path(os.environ.get("WCB_PI_NODE_MODULES", "/tmp/wcb-pi-current/node_modules"))
TOOLS_ROOT = Path(os.environ.get("WCB_TOOLS_VENV", "/tmp/wcb-deepseek-tools"))


def main():
    workspace = Path(os.environ["WCB_WORKSPACE"]).resolve()
    prompt = Path(os.environ["WCB_PROMPT_FILE"]).read_text()
    usage = dict(
        input_tokens=0,
        output_tokens=0,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
        cost_usd=0.0,
        tool_calls=0,
        turns=0,
        model=MODEL,
        provider="nebius",
        harness="pi/1.5.2",
    )
    last_stop = None
    turn_limit_hit = False
    with tempfile.TemporaryDirectory(prefix="wcb-pi-config-") as config_dir:
        config = Path(config_dir)
        models = {
            "providers": {
                "nebius": {
                    "baseUrl": os.environ.get(
                        "OPENAI_BASE_URL", "https://api.tokenfactory.nebius.com/v1"
                    ),
                    "api": "openai-completions",
                    "apiKey": "$TOKEN_FACTORY_API_KEY",
                    "models": [
                        {
                            "id": MODEL,
                            "name": "DeepSeek V4.1 Flash 1017 (Nebius)",
                            "reasoning": True,
                            "input": ["text"],
                            "contextWindow": 1048576,
                            "maxTokens": 1048576,
                            "samplingParams": {"thinking": {"type": "enabled"}},
                            "cost": {
                                "input": 0.30,
                                "output": 1.20,
                                "cacheRead": 0.006,
                                "cacheWrite": 0.30,
                            },
                            "compat": {
                                "supportsDeveloperRole": False,
                                "supportsReasoningEffort": False,
                                "maxTokensField": "max_tokens",
                            },
                        }
                    ],
                }
            }
        }
        (config / "models.json").write_text(json.dumps(models))
        (config / "settings.json").write_text(json.dumps({"quietStartup": True}))
        (config / "runtime.mjs").write_text(Path(__file__).with_name("runtime.mjs").read_text())
        cmd = [
            "bwrap",
            "--die-with-parent",
            "--unshare-all",
            "--share-net",
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/bin",
            "/bin",
            "--symlink",
            "usr/lib",
            "/lib",
            "--symlink",
            "usr/lib64",
            "/lib64",
            "--ro-bind",
            "/etc/ssl",
            "/etc/ssl",
            "--ro-bind",
            "/etc/resolv.conf",
            "/etc/resolv.conf",
            "--ro-bind",
            "/etc/hosts",
            "/etc/hosts",
            "--ro-bind",
            str(PI_ROOT),
            "/opt/pi/node_modules",
            "--ro-bind",
            str(TOOLS_ROOT),
            "/opt/tools",
            "--bind",
            str(config),
            "/pi-config",
            "--bind",
            str(workspace),
            "/work",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/home/user",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--chdir",
            "/work",
            "--",
            "/usr/local/bin/node",
            "/opt/pi/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
            "--provider",
            "nebius",
            "--model",
            MODEL,
            "--print",
            "--mode",
            "json",
            "--no-session",
            "--offline",
            "--no-extensions",
            "--extension",
            "/pi-config/runtime.mjs",
            "--no-mcp",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
            "--no-context-files",
            "--no-approve",
            "--tools",
            "read,bash,edit,write",
            "--append-system-prompt",
            "You are running unattended in a benchmark session. Nobody will answer "
            "questions or approve actions. Work only with files inside /work; "
            "treat the task's date as today. Stop when the task is done.",
            "--",
            prompt,
        ]
        env = {
            "PATH": "/opt/tools/bin:/usr/local/bin:/usr/bin:/bin",
            "HOME": "/home/user",
            "LANG": "C.UTF-8",
            "PI_CODING_AGENT_DIR": "/pi-config",
            "PI_OFFLINE": "1",
            "PI_TELEMETRY": "0",
            "TOKEN_FACTORY_API_KEY": os.environ["TOKEN_FACTORY_API_KEY"],
        }
        proc = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

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
                # Final message events contain complete text, reasoning and usage.
                # Drop only redundant streaming deltas, not completed messages or tools.
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
                if (
                    event.get("type") == "turn_end"
                    and usage["turns"] >= 120
                    and last_stop == "toolUse"
                ):
                    turn_limit_hit = True
                    print(
                        "Pi session exceeded the fixed 120-turn budget", file=sys.stderr, flush=True
                    )
                    proc.terminate()
            code = proc.wait()
        finally:
            for s, handler in old.items():
                signal.signal(s, handler)
            reason = "turn_limit" if turn_limit_hit else last_stop or "no_assistant_message"
            usage["termination"] = {
                "reason": reason,
                "incomplete": reason != "stop",
                "raw_stop_reason": last_stop,
            }
            out = workspace / ".wcb" / "usage.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(usage, indent=2) + "\n")
        if code == 0 and last_stop in ("error", "aborted"):
            return 1
        return code if code >= 0 else 128 - code


if __name__ == "__main__":
    sys.exit(main())
