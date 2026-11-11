"""Run a CLI agent and turn its machine-readable output into ``.wcb/usage.json``.

CLI agents such as Claude Code and Codex report token use in their JSON output, not in the
``.wcb/usage.json`` file the runner reads (docs/formats.md section 5). This wrapper runs the
agent, copies its stdout through unchanged (so ``stdout.log`` keeps the full trace), parses the
usage from it, and writes ``.wcb/usage.json`` in the workspace when the agent exits::

    python -m wcb.agents.wrap --format claude -- claude -p "..." --output-format stream-json --verbose
    python -m wcb.agents.wrap --format codex  -- codex exec --json ...

Formats:

- ``claude``: Claude Code ``--output-format stream-json`` (with ``--verbose``) or ``json``. Usage
  comes from the final ``result`` event (``modelUsage`` when present, else ``usage``), with
  ``total_cost_usd``, ``num_turns`` and the number of ``tool_use`` blocks.
- ``codex``: Codex ``exec --json`` events. Usage is the sum of ``turn.completed`` usage; tool
  calls count completed command, file-change, MCP and web-search items.

The wrapper exits with the agent's exit status (127 if the agent is not installed). Usage is
written even if the agent fails or the session is stopped by SIGTERM; fields it cannot find are
0 or ``null``. ``input_tokens`` includes cached input tokens.

The record also says why the agent stopped, in ``termination``: ``{"reason": ..., "incomplete":
true|false}`` plus the raw fields it was derived from. ``incomplete`` is true when the agent's own
output shows it did not finish normally, even if it exited 0:

- ``claude``: the last assistant message's ``stop_reason`` is ``max_tokens`` (reason
  ``max_tokens``: the final response was truncated); the ``result`` event has ``is_error`` or a
  ``subtype`` other than ``success`` (reason: the subtype, e.g. ``error_max_turns``); or there is
  no ``result`` event (reason ``no_result``, e.g. the agent was killed). Otherwise the reason is
  the subtype (``success``).
- ``codex``: the last outcome is a ``turn.failed`` (reason ``turn_failed``) or an ``error`` event
  not followed by a ``turn.completed`` (reason ``error``), or no turn completed at all (reason
  ``no_turn_completed``). Otherwise the reason is ``completed``. Error messages are kept in
  ``errors``.

The exit status is never changed; the runner records ``termination`` in ``session.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

FORMATS = ("claude", "codex")
CODEX_TOOL_ITEMS = frozenset({"command_execution", "file_change", "mcp_tool_call", "web_search"})


class UsageParser:
    """Accumulates usage from an agent's JSON output, one line at a time."""

    def __init__(self, fmt: str, model: str | None = None):
        if fmt not in FORMATS:
            raise ValueError(f"unknown format {fmt!r}; choose one of: {', '.join(FORMATS)}")
        self.fmt = fmt
        self.model = model
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 0
        self.cost_usd: float | None = None
        self.tool_calls = 0
        self.turns: int | None = None
        self._claude_messages: dict[str, dict] = {}  # message id -> usage, for runs without result
        self._have_result = False
        self._codex_cumulative: dict[str, int] | None = None
        # termination
        self._result_subtype: str | None = None
        self._result_is_error: bool | None = None
        self._stop_reason: str | None = None
        self._last_message_id: str | None = None
        self._codex_outcome: str | None = None  # "completed" | "turn_failed" | "error"
        self._errors: list[str] = []

    # ---------------------------------------------------------------- input
    def feed_line(self, line: str) -> None:
        """Parse one line of output. Lines that are not JSON are ignored."""
        line = line.strip()
        if not line or line[0] not in "[{":
            return
        try:
            obj = json.loads(line)
        except ValueError:
            return
        for event in obj if isinstance(obj, list) else [obj]:
            if isinstance(event, dict):
                (self._claude if self.fmt == "claude" else self._codex)(event)

    def feed_text(self, text: str) -> None:
        """Parse a whole output (a single JSON document or JSON lines)."""
        stripped = text.strip()
        try:
            whole = json.loads(stripped)
        except ValueError:
            for line in text.splitlines():
                self.feed_line(line)
            return
        for event in whole if isinstance(whole, list) else [whole]:
            if isinstance(event, dict):
                (self._claude if self.fmt == "claude" else self._codex)(event)

    # ---------------------------------------------------------------- claude
    def _claude(self, e: dict) -> None:
        kind = e.get("type")
        if kind == "assistant":
            msg = e.get("message") or {}
            if not str(msg.get("model") or "<").startswith("<"):  # skip "<synthetic>" messages
                self.model = self.model or msg.get("model")
            # stream-json repeats a message per content block, possibly with stop_reason null
            # until the last one: keep the latest non-null stop_reason of the latest message.
            mid = msg.get("id")
            if mid is None or mid != self._last_message_id:
                self._last_message_id = mid
                self._stop_reason = msg.get("stop_reason")
            elif msg.get("stop_reason") is not None:
                self._stop_reason = msg.get("stop_reason")
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    self.tool_calls += 1
            if not self._have_result and isinstance(msg.get("usage"), dict):
                # stream-json repeats a message per content block; keep the last usage per id
                self._claude_messages[msg.get("id") or str(len(self._claude_messages))] = msg[
                    "usage"
                ]
                self._claude_totals_from_messages()
        elif kind == "result":
            self._have_result = True
            if e.get("subtype") is not None:
                self._result_subtype = str(e["subtype"])
            if e.get("is_error") is not None:
                self._result_is_error = bool(e["is_error"])
            if e.get("total_cost_usd") is not None:
                self.cost_usd = float(e["total_cost_usd"])
            if e.get("num_turns") is not None:
                self.turns = int(e["num_turns"])
            per_model = e.get("modelUsage")
            if isinstance(per_model, dict) and per_model:
                self.model = self.model or ",".join(sorted(per_model))
                fields = {
                    "inputTokens": 0,
                    "outputTokens": 0,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 0,
                }
                for mu in per_model.values():
                    for k in fields:
                        fields[k] += int((mu or {}).get(k) or 0)
                self._set_claude(
                    fields["inputTokens"],
                    fields["outputTokens"],
                    fields["cacheReadInputTokens"],
                    fields["cacheCreationInputTokens"],
                )
            elif isinstance(e.get("usage"), dict):
                u = e["usage"]
                self._set_claude(
                    int(u.get("input_tokens") or 0),
                    int(u.get("output_tokens") or 0),
                    int(u.get("cache_read_input_tokens") or 0),
                    int(u.get("cache_creation_input_tokens") or 0),
                )

    def _claude_totals_from_messages(self) -> None:
        sums = [0, 0, 0, 0]
        for u in self._claude_messages.values():
            sums[0] += int(u.get("input_tokens") or 0)
            sums[1] += int(u.get("output_tokens") or 0)
            sums[2] += int(u.get("cache_read_input_tokens") or 0)
            sums[3] += int(u.get("cache_creation_input_tokens") or 0)
        self._set_claude(*sums)

    def _set_claude(self, fresh: int, out: int, cache_read: int, cache_write: int) -> None:
        self.input_tokens = fresh + cache_read + cache_write
        self.output_tokens = out
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_write

    # ---------------------------------------------------------------- codex
    def _codex(self, e: dict) -> None:
        kind = e.get("type")
        if kind == "turn.completed" and isinstance(e.get("usage"), dict):
            u = e["usage"]
            self.input_tokens += int(u.get("input_tokens") or 0)
            self.output_tokens += int(u.get("output_tokens") or 0)
            self.cache_read_input_tokens += int(u.get("cached_input_tokens") or 0)
            self.turns = (self.turns or 0) + 1
        if kind == "turn.completed":
            self._codex_outcome = "completed"
        elif kind == "turn.failed":
            self._codex_outcome = "turn_failed"
            self._error(e.get("error"))
        elif kind == "error":
            self._codex_outcome = "error"
            self._error(e)
        elif kind == "item.completed":
            item = e.get("item") or {}
            if item.get("type") in CODEX_TOOL_ITEMS:
                self.tool_calls += 1
        elif isinstance(e.get("msg"), dict):  # older Codex event format
            msg = e["msg"]
            if msg.get("type") == "task_complete":
                self._codex_outcome = "completed"
            elif msg.get("type") == "error":
                self._codex_outcome = "error"
                self._error(msg)
            elif msg.get("type") == "token_count":
                total = (msg.get("info") or {}).get("total_token_usage") or msg
                self.input_tokens = int(total.get("input_tokens") or 0)
                self.output_tokens = int(total.get("output_tokens") or 0)
                self.cache_read_input_tokens = int(total.get("cached_input_tokens") or 0)
            elif msg.get("type") in (
                "exec_command_begin",
                "patch_apply_begin",
                "mcp_tool_call_begin",
            ):
                self.tool_calls += 1

    def _error(self, err: Any) -> None:
        message = err.get("message") if isinstance(err, dict) else err
        if message and len(self._errors) < 10:
            self._errors.append(str(message)[:500])

    # ---------------------------------------------------------------- output
    def termination(self) -> dict[str, Any]:
        """Why the agent stopped: ``{"reason", "incomplete", ...raw fields}``."""
        if self.fmt == "claude":
            raw = {
                "result_subtype": self._result_subtype,
                "is_error": self._result_is_error,
                "stop_reason": self._stop_reason,
            }
            if self._stop_reason == "max_tokens":
                reason, incomplete = "max_tokens", True
            elif not self._have_result:
                reason, incomplete = "no_result", True
            elif self._result_is_error or (self._result_subtype or "success") != "success":
                reason, incomplete = self._result_subtype or "error", True
            else:
                reason, incomplete = self._result_subtype or "success", False
            return {"reason": reason, "incomplete": incomplete, **raw}
        outcome = self._codex_outcome or "no_turn_completed"
        return {"reason": outcome, "incomplete": outcome != "completed", "errors": self._errors}

    def record(self, provider: str) -> dict[str, Any]:
        """The ``.wcb/usage.json`` content."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cost_usd": self.cost_usd,
            "tool_calls": self.tool_calls,
            "turns": self.turns,
            "model": self.model,
            "provider": provider,
            "harness": f"wcb.agents.wrap:{self.fmt}",
            "termination": self.termination(),
        }


def write_usage(workspace: Path, record: dict[str, Any]) -> Path:
    out = Path(workspace) / ".wcb" / "usage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m wcb.agents.wrap",
        description="Run a CLI agent, pass its output through, and write .wcb/usage.json.",
        usage="python -m wcb.agents.wrap --format {claude,codex} [--model M] -- COMMAND [ARGS...]",
    )
    p.add_argument("--format", required=True, choices=FORMATS, help="the agent's output format")
    p.add_argument("--model", help="model name to report if the output does not say")
    p.add_argument("--provider", help="provider name to report (default: the format)")
    p.add_argument(
        "--workspace", help="where .wcb/usage.json goes (default: $WCB_WORKSPACE or cwd)"
    )
    p.add_argument("command", nargs=argparse.REMAINDER, help="the agent command, after --")
    a = p.parse_args(argv)
    cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not cmd:
        p.error("give the agent command after --, e.g. -- claude -p 'prompt' --output-format json")
    workspace = Path(a.workspace or os.environ.get("WCB_WORKSPACE") or ".")
    parser = UsageParser(a.format, a.model)
    provider = a.provider or {"claude": "claude-code", "codex": "codex"}[a.format]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, errors="replace", bufsize=1)
    except FileNotFoundError:
        print(
            f"wcb.agents.wrap: {cmd[0]!r} was not found on PATH. Install it, or set PATH in the "
            "adapter's env (the session PATH is your PATH with the wcb interpreter's directory "
            "first).",
            file=sys.stderr,
        )
        record = parser.record(provider)
        record["termination"] = {"reason": "not_started", "incomplete": True}
        write_usage(workspace, record)
        return 127

    def forward(signum, _frame):
        if proc.poll() is None:
            proc.send_signal(signum)

    old = {s: signal.signal(s, forward) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            parser.feed_line(line)
        code = proc.wait()
    finally:
        for s, h in old.items():
            signal.signal(s, h)
        try:
            write_usage(workspace, parser.record(provider))
        except OSError as e:
            print(f"wcb.agents.wrap: could not write .wcb/usage.json: {e}", file=sys.stderr)
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    sys.exit(main())
