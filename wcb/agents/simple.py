"""A simple, provider-agnostic model harness: one model, a fixed minimal tool loop.

Use it to benchmark a raw model without writing an agent::

    python -m wcb.agents.simple --provider anthropic --model <model-id>
    python -m wcb.agents.simple --provider openai --model <model-id> [--max-turns 80] [--max-tokens 8000]

Inside ``wcb run`` it reads the session from the runner's environment: ``WCB_WORKSPACE`` (the
working directory), ``WCB_PROMPT_FILE`` (the fixed benchmark prompt), ``WCB_PHASE`` and
``WCB_SESSION_DIR``. See ``adapters/examples/simple-anthropic.yaml`` and
``adapters/examples/simple-openai.yaml``, and docs/adapters.md for every option.

What the harness does, and nothing more:

1. Sends a short, generic system prompt (:data:`SYSTEM_PROMPT`, no knowledge of any world) and
   the session prompt to the model, with the file tools from :mod:`wcb.agents.tools`, all
   confined to the workspace. In query sessions only ``.wcb/`` is writable.
2. Runs the tools the model calls and returns their output (each result capped at
   ``--max-tool-output`` characters) until the model calls ``finish``, stops calling tools, or
   reaches ``--max-turns``.
3. Keeps the conversation under ``--context-budget`` estimated tokens by replacing the oldest
   tool output (and long arguments of old ``write_file`` calls) with short placeholders.
4. In query sessions, checks ``.wcb/answers.json`` when the model calls ``finish``: if it is
   missing, not JSON, fails ``.wcb/answer-schema.json`` or misses questions, the model is told
   what is wrong and gets another chance (twice at most).
5. Writes ``.wcb/usage.json`` (tokens, tool calls, turns, model, provider, optional cost) even
   when the session fails or is stopped by the runner's timeout (SIGTERM), and a JSONL
   transcript to ``$WCB_SESSION_DIR/simple-transcript.jsonl`` for debugging.

Exit status: 0 when the loop ends normally (including at ``--max-turns``), 1 when the model API
fails after retries, 2 for configuration errors (missing API key, prompt or workspace), 130/143
when interrupted. A non-zero exit makes the runner discard the session's store changes.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wcb.agents.providers import (
    ContextTooLong,
    HTTPConfig,
    Message,
    ProviderError,
    Reply,
    ToolCall,
    ToolResult,
    Usage,
    make_provider,
)
from wcb.agents.tools import FINISH, TOOL_SPECS, Toolbox, Workspace

SYSTEM_PROMPT = (
    "You are an assistant maintaining a knowledge store in your working directory. "
    "Follow the task. Use tools. Be precise and cite artifact IDs.\n\n"
    "All paths are relative to the working directory. Nobody will answer questions during this "
    "session, so work autonomously, and call finish with a short summary when the task is done."
)
"""The default system prompt. It is generic on purpose: adapters must not add world knowledge."""

TRANSCRIPT_NAME = "simple-transcript.jsonl"
PRUNED_RESULT = "[earlier output of {name} removed to save context; call the tool again if needed]"
PRUNED_ARG = "[{n} characters omitted to save context]"
CHARS_PER_TOKEN = 4


class SessionInterrupted(Exception):
    """Raised inside the loop when the process receives SIGTERM or SIGINT."""

    def __init__(self, signum: int):
        self.signum = signum
        super().__init__(f"interrupted by signal {signum}")


@dataclass
class LoopConfig:
    """Limits for one session. The defaults suit models with a 128k-token context or more."""

    max_turns: int = 80
    """Model calls before the loop stops."""
    max_tokens: int = 8000
    """Output tokens per model call."""
    context_budget: int = 100_000
    """Estimated conversation tokens above which old tool output is dropped."""
    max_tool_output: int = 20_000
    """Characters per tool result; longer output is truncated with a note."""
    keep_recent: int = 6
    """Most recent messages that are never pruned."""
    max_nudges: int = 3
    """Consecutive replies without tool calls before the loop gives up."""
    finish_checks: int = 2
    """Times ``finish`` may be rejected because ``.wcb/answers.json`` has problems (queries)."""


@dataclass
class SessionStats:
    """What happened in a session; also the content of ``.wcb/usage.json``."""

    usage: Usage = field(default_factory=Usage)
    turns: int = 0
    tool_calls: int = 0
    stop: str = "running"  # finish | end_turn | max_turns | no_progress | error | interrupted
    summary: str = ""
    model: str | None = None
    tool_counts: dict[str, int] = field(default_factory=dict)


# ====================================================================== the loop
def run_session(
    provider: Any,
    workspace: Path,
    prompt: str,
    *,
    phase: str = "ingest",
    config: LoopConfig | None = None,
    system: str = SYSTEM_PROMPT,
    transcript: Path | None = None,
    log: Callable[[str], None] = print,
    stats: SessionStats | None = None,
) -> SessionStats:
    """Run the tool loop until the model finishes. Returns the session's statistics.

    ``provider`` needs a ``complete(system, messages, tools, max_tokens) -> Reply`` method (see
    :mod:`wcb.agents.providers`); tests pass a scripted fake. Pass ``stats`` to observe progress
    even if the loop raises (the CLI uses this to write usage on errors).
    """
    cfg = config or LoopConfig()
    stats = stats if stats is not None else SessionStats()
    ws = Workspace(workspace, read_only=(phase == "query"))
    toolbox = Toolbox(ws)
    tape = _Transcript(transcript)
    tape.write(
        event="start",
        provider=getattr(provider, "name", "?"),
        model=getattr(provider, "model", None),
        phase=phase,
        workspace=str(ws.root),
        system=system,
        prompt=prompt,
    )
    messages: list[Message] = [Message("user", prompt)]
    budget = cfg.context_budget
    nudges = 0
    rejections = 0
    try:
        while stats.turns < cfg.max_turns:
            _prune(system, messages, budget, cfg.keep_recent, log)
            reply, budget = _complete(provider, system, messages, cfg, budget, log)
            stats.turns += 1
            stats.usage.add(reply.usage)
            stats.model = reply.model or stats.model
            messages.append(Message("assistant", reply.text, list(reply.tool_calls)))
            if reply.text.strip():
                log(f"[turn {stats.turns}] model: {_short(reply.text, 400)}")

            if not reply.tool_calls:
                problem = _finish_problem(ws.root, phase)
                if reply.stop_reason == "max_tokens":
                    note = (
                        "Your reply was cut off at the output token limit. Continue with tool "
                        "calls, and write large files in smaller parts."
                    )
                elif problem:
                    note = f"The task is not complete: {problem}. Continue using the tools."
                elif nudges == 0 and phase != "query":
                    note = (
                        "If the task is complete, call finish with a short summary. Otherwise "
                        "continue working with the tools."
                    )
                else:
                    stats.stop, stats.summary = "end_turn", reply.text
                    tape.write(event="turn", turn=stats.turns, reply=_reply_dict(reply))
                    break
                nudges += 1
                tape.write(event="turn", turn=stats.turns, reply=_reply_dict(reply), nudge=note)
                if nudges > cfg.max_nudges:
                    stats.stop = "no_progress"
                    log(f"[simple] the model made no tool calls in {nudges} replies; stopping")
                    break
                messages.append(Message("user", note))
                continue

            nudges = 0
            results: list[ToolResult] = []
            finished = False
            calls = sorted(reply.tool_calls, key=lambda c: c.name == FINISH)  # finish runs last
            for call in calls:
                stats.tool_calls += 1
                if call.name == FINISH and not call.arguments_error:
                    problem = _finish_problem(ws.root, phase)
                    if problem and rejections < cfg.finish_checks:
                        rejections += 1
                        result = ToolResult(
                            call.id,
                            call.name,
                            f"finish was not accepted: {problem}. Fix this, then call finish again.",
                            True,
                        )
                    else:
                        finished = True
                        stats.summary = str(call.arguments.get("summary") or reply.text)
                        result = ToolResult(call.id, call.name, "Session finished.")
                else:
                    result = _run_tool(toolbox, call, cfg.max_tool_output)
                log(
                    f"[turn {stats.turns}] {call.name}{_fmt_args(call.arguments)} -> "
                    f"{'ERROR ' if result.is_error else ''}{_short(result.content, 160)}"
                )
                results.append(result)
            messages.append(Message("tool", results=results))
            tape.write(
                event="turn",
                turn=stats.turns,
                reply=_reply_dict(reply),
                results=[_result_dict(r) for r in results],
            )
            if finished:
                stats.stop = "finish"
                break
        else:
            stats.stop = "max_turns"
            log(f"[simple] reached --max-turns {cfg.max_turns} before the model called finish")
    except SessionInterrupted:
        stats.stop = "interrupted"
        raise
    except ProviderError:
        stats.stop = "error"
        raise
    finally:
        stats.tool_counts = dict(toolbox.counts)
        tape.write(
            event="end",
            stop=stats.stop,
            turns=stats.turns,
            tool_calls=stats.tool_calls,
            usage=vars(stats.usage),
            summary=stats.summary,
        )
        tape.close()
    return stats


def _complete(
    provider: Any,
    system: str,
    messages: list[Message],
    cfg: LoopConfig,
    budget: int,
    log: Callable[[str], None],
) -> tuple[Reply, int]:
    """Call the model; on a context-length error, drop old output harder and retry (3 tries).

    Returns the reply and the (possibly lowered) context budget for the rest of the session.
    """
    for attempt in range(3):
        try:
            return provider.complete(system, messages, TOOL_SPECS, cfg.max_tokens), budget
        except ContextTooLong:
            if attempt == 2:
                raise
            budget = max(4000, int(min(budget, estimate_tokens(system, messages)) * 0.6))
            dropped = _prune(system, messages, budget, keep_recent=2, log=log)
            log(f"[simple] context too long for the model; context budget lowered to ~{budget}")
            if not dropped:
                raise ProviderError(
                    "the conversation is too long for the model and no old tool output is left "
                    "to drop; lower --max-tool-output or --max-tokens (output tokens count "
                    "against the context too), or use a model with a larger context"
                ) from None
    raise AssertionError("unreachable")


def _run_tool(toolbox: Toolbox, call: ToolCall, max_chars: int) -> ToolResult:
    if call.arguments_error:
        toolbox.counts[call.name] += 1
        return ToolResult(
            call.id,
            call.name,
            f"error: could not read the arguments for {call.name}: {call.arguments_error}. "
            "If your reply was cut off by the output limit, write the file in smaller parts.",
            True,
        )
    r = toolbox.call(call.name, call.arguments)
    return ToolResult(call.id, call.name, truncate(r.content, max_chars), r.is_error)


# ====================================================================== query checks
def _finish_problem(root: Path, phase: str) -> str | None:
    return check_answers(root) if phase == "query" else None


def check_answers(root: Path) -> str | None:
    """Problems with ``<root>/.wcb/answers.json`` as one sentence, or ``None`` if it looks fine.

    Checks that the file exists, is a JSON object, answers every question in
    ``.wcb/questions.json`` with the right ``type``, and validates against
    ``.wcb/answer-schema.json`` when present.
    """
    wcb = Path(root) / ".wcb"
    f = wcb / "answers.json"
    if not f.is_file():
        return ".wcb/answers.json has not been written yet"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return f".wcb/answers.json is not valid JSON ({e})"
    if not isinstance(data, dict):
        return ".wcb/answers.json must be a JSON object mapping question IDs to answers"
    problems: list[str] = []
    try:
        questions = json.loads((wcb / "questions.json").read_text(encoding="utf-8"))
        qs = {q["id"]: q.get("type") for q in questions.get("questions", [])}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        qs = {}
    missing = [q for q in qs if q not in data]
    if missing:
        problems.append(f"no answer for {len(missing)} question(s): {', '.join(missing[:10])}")
    for qid, ans in data.items():
        if qid in qs and isinstance(ans, dict) and qs[qid] and ans.get("type") != qs[qid]:
            problems.append(f"{qid} must have type {qs[qid]!r}, not {ans.get('type')!r}")
    problems += _schema_problems(wcb / "answer-schema.json", data)
    if not problems:
        return None
    shown = problems[:8]
    more = f" (and {len(problems) - 8} more)" if len(problems) > 8 else ""
    return "problems in .wcb/answers.json: " + "; ".join(shown) + more


def _schema_problems(schema_file: Path, data: dict) -> list[str]:
    try:
        schema = json.loads(schema_file.read_text(encoding="utf-8"))
        import jsonschema
    except (OSError, ValueError, ImportError):
        return []
    defs = schema.get("$defs") or {}
    cls = jsonschema.validators.validator_for(schema)
    out = []
    for qid, ans in data.items():
        if not isinstance(ans, dict) or ans.get("type") not in defs:
            out.append(f"{qid}: 'type' must be one of {', '.join(sorted(defs))}")
            continue
        validator = cls({"$defs": defs, "$ref": f"#/$defs/{ans['type']}"})
        for err in sorted(validator.iter_errors(ans), key=lambda e: list(e.path))[:3]:
            where = "/".join(str(p) for p in err.path)
            out.append(f"{qid}{'/' + where if where else ''}: {err.message}")
    return out


# ====================================================================== context management
def truncate(text: str, max_chars: int) -> str:
    """Cap ``text`` at about ``max_chars``, keeping the start and the last few lines."""
    if len(text) <= max_chars:
        return text
    tail = min(1000, max_chars // 5)
    head = max_chars - tail
    cut = len(text) - head - tail
    return (
        f"{text[:head]}\n[... {cut} characters truncated; read a smaller range with offset/limit "
        f"or narrow the search ...]\n{text[-tail:]}"
    )


def estimate_tokens(system: str, messages: list[Message]) -> int:
    """A rough token estimate for the conversation (characters / 4, plus the tool schemas)."""
    tools = len(json.dumps(TOOL_SPECS))
    return (len(system) + tools + sum(_msg_chars(m) for m in messages)) // CHARS_PER_TOKEN


def _msg_chars(m: Message) -> int:
    n = len(m.text)
    for c in m.tool_calls:
        n += len(c.name) + sum(len(str(v)) for v in c.arguments.values()) + 20
    for r in m.results:
        n += len(r.content) + 20
    return n


def _prune(
    system: str, messages: list[Message], budget: int, keep_recent: int, log: Callable[[str], None]
) -> int:
    """If the conversation is over ``budget``, drop old tool output until it is under 60% of it.

    The first message (the task prompt) and the last ``keep_recent`` messages are kept. Returns
    the number of items replaced with placeholders.
    """
    total = estimate_tokens(system, messages) * CHARS_PER_TOKEN
    if total <= budget * CHARS_PER_TOKEN:
        return 0
    target = int(budget * 0.6) * CHARS_PER_TOKEN
    dropped = 0
    for m in messages[1 : max(1, len(messages) - keep_recent)]:
        if total <= target:
            break
        for r in m.results:
            if len(r.content) > 200 and not r.content.startswith("[earlier output"):
                new = PRUNED_RESULT.format(name=r.name)
                total -= len(r.content) - len(new)
                r.content = new
                dropped += 1
        for c in m.tool_calls:
            for k, v in list(c.arguments.items()):
                if isinstance(v, str) and len(v) > 400:
                    new = PRUNED_ARG.format(n=len(v))
                    total -= len(v) - len(new)
                    c.arguments = {**c.arguments, k: new}
                    dropped += 1
    if dropped:
        log(f"[simple] context over ~{budget} tokens: dropped {dropped} old tool output(s)")
    return dropped


# ====================================================================== usage and transcript
def usage_record(
    stats: SessionStats,
    *,
    provider: str,
    model: str,
    price_input: float | None = None,
    price_output: float | None = None,
    price_cache_read: float | None = None,
) -> dict[str, Any]:
    """The ``.wcb/usage.json`` content (docs/formats.md section 5, plus harness extras).

    Prices are USD per million tokens. Without them ``cost_usd`` is ``null``. Cache reads are
    charged at ``price_cache_read`` (default: the input price); Anthropic cache writes at 1.25x.
    """
    u = stats.usage
    cost = None
    if price_input is not None and price_output is not None:
        read_price = price_input if price_cache_read is None else price_cache_read
        write_mult = 1.25 if provider == "anthropic" else 1.0
        uncached = u.input_tokens - u.cache_read_input_tokens - u.cache_creation_input_tokens
        cost = round(
            (
                uncached * price_input
                + u.cache_creation_input_tokens * price_input * write_mult
                + u.cache_read_input_tokens * read_price
                + u.output_tokens * price_output
            )
            / 1e6,
            6,
        )
    return {
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
        "cache_read_input_tokens": u.cache_read_input_tokens,
        "cache_creation_input_tokens": u.cache_creation_input_tokens,
        "cost_usd": cost,
        "tool_calls": stats.tool_calls,
        "turns": stats.turns,
        "model": stats.model or model,
        "provider": provider,
        "harness": "wcb.agents.simple",
        "stop": stats.stop,
        "tool_counts": stats.tool_counts,
    }


def write_usage(workspace: Path, record: dict[str, Any]) -> Path:
    """Write ``record`` to ``<workspace>/.wcb/usage.json`` and return the path."""
    out = Path(workspace) / ".wcb" / "usage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return out


class _Transcript:
    """Append-only JSONL log of the session (outside the workspace). Failures are ignored."""

    MAX_FIELD = 4000

    def __init__(self, path: Path | None):
        self.fh = None
        if path is not None:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                self.fh = open(path, "a", encoding="utf-8")
            except OSError:
                self.fh = None

    def write(self, **event: Any) -> None:
        if self.fh is not None:
            self.fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            self.fh.flush()

    def close(self) -> None:
        if self.fh is not None:
            self.fh.close()
            self.fh = None


def _reply_dict(reply: Reply) -> dict[str, Any]:
    return {
        "text": reply.text,
        "stop_reason": reply.stop_reason,
        "usage": vars(reply.usage),
        "tool_calls": [
            {"id": c.id, "name": c.name, "arguments": c.arguments, "error": c.arguments_error}
            for c in reply.tool_calls
        ],
    }


def _result_dict(r: ToolResult) -> dict[str, Any]:
    return {
        "id": r.call_id,
        "name": r.name,
        "is_error": r.is_error,
        "content": _short(r.content, _Transcript.MAX_FIELD, flat=False),
    }


def _short(text: str, n: int, *, flat: bool = True) -> str:
    if flat:
        text = " ".join(text.split())
    return text if len(text) <= n else text[:n] + f" [...{len(text) - n} more chars]"


def _fmt_args(args: dict[str, Any]) -> str:
    parts = []
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 80:
            parts.append(f"{k}=<{len(v)} chars>")
        else:
            parts.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
    return "(" + ", ".join(parts) + ")"


# ====================================================================== CLI
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m wcb.agents.simple",
        description=(
            "Run one benchmark session with a raw model behind a fixed file-tool loop. "
            "Session settings default to the WCB_* variables set by 'wcb run'."
        ),
    )
    p.add_argument(
        "--provider",
        required=True,
        choices=["anthropic", "openai"],
        help="wire protocol: 'anthropic' (Messages API) or 'openai' (Chat Completions, "
        "any OpenAI-compatible server)",
    )
    p.add_argument("--model", required=True, help="model ID as the endpoint expects it")
    p.add_argument("--max-turns", type=int, default=80, help="model calls per session (80)")
    p.add_argument("--max-tokens", type=int, default=8000, help="output tokens per call (8000)")
    p.add_argument(
        "--context-budget",
        type=int,
        default=100_000,
        help="estimated conversation tokens before old tool output is dropped (100000)",
    )
    p.add_argument(
        "--max-tool-output",
        type=int,
        default=20_000,
        help="characters per tool result before truncation (20000)",
    )
    p.add_argument("--temperature", type=float, help="sampling temperature (default: provider's)")
    p.add_argument(
        "--base-url",
        help="API base URL (default: $ANTHROPIC_BASE_URL or "
        "$OPENAI_BASE_URL, else the provider's public API)",
    )
    p.add_argument(
        "--api-key-env",
        help="environment variable holding the API key "
        "(default: ANTHROPIC_API_KEY or OPENAI_API_KEY)",
    )
    p.add_argument(
        "--no-prompt-cache",
        action="store_true",
        help="anthropic: do not send cache_control breakpoints",
    )
    p.add_argument(
        "--request-timeout", type=float, default=600.0, help="seconds per API call (600)"
    )
    p.add_argument("--retries", type=int, default=6, help="retries for 429/5xx/network errors (6)")
    p.add_argument("--workspace", help="working directory (default: $WCB_WORKSPACE, else cwd)")
    p.add_argument("--prompt-file", help="prompt file (default: $WCB_PROMPT_FILE)")
    p.add_argument("--prompt", help="prompt text (overrides --prompt-file)")
    p.add_argument(
        "--phase",
        choices=["ingest", "query"],
        help="session phase (default: $WCB_PHASE, else ingest); query is read-only except .wcb/",
    )
    p.add_argument("--system-prompt-file", help="replace the default generic system prompt")
    p.add_argument(
        "--transcript",
        help=f"JSONL transcript path (default: $WCB_SESSION_DIR/{TRANSCRIPT_NAME}; '' to disable)",
    )
    p.add_argument("--price-input", type=float, help="USD per million input tokens, for cost_usd")
    p.add_argument("--price-output", type=float, help="USD per million output tokens")
    p.add_argument(
        "--price-cache-read",
        type=float,
        help="USD per million cached input tokens (default: --price-input)",
    )
    p.add_argument("--quiet", action="store_true", help="only print the final summary line")
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    say = (lambda _m: None) if a.quiet else (lambda m: print(m, flush=True))

    def fail(msg: str, code: int = 2) -> int:
        print(f"wcb.agents.simple: error: {msg}", file=sys.stderr, flush=True)
        return code

    workspace = Path(a.workspace or os.environ.get("WCB_WORKSPACE") or ".").resolve()
    if not workspace.is_dir():
        return fail(f"workspace {workspace} is not a directory (set --workspace or WCB_WORKSPACE)")
    if a.prompt is not None:
        prompt = a.prompt
    else:
        pf = a.prompt_file or os.environ.get("WCB_PROMPT_FILE")
        if not pf:
            return fail(
                "no prompt: pass --prompt-file or --prompt, or run under 'wcb run', "
                "which sets WCB_PROMPT_FILE"
            )
        try:
            prompt = Path(pf).read_text(encoding="utf-8")
        except OSError as e:
            return fail(f"cannot read the prompt file {pf}: {e.strerror or e}")
    phase = a.phase or os.environ.get("WCB_PHASE") or "ingest"
    if phase not in ("ingest", "query"):
        return fail(f"WCB_PHASE must be 'ingest' or 'query', got {phase!r}")
    system = SYSTEM_PROMPT
    if a.system_prompt_file:
        try:
            system = Path(a.system_prompt_file).read_text(encoding="utf-8")
        except OSError as e:
            return fail(f"cannot read --system-prompt-file: {e.strerror or e}")
    if a.transcript is not None:
        transcript = Path(a.transcript) if a.transcript else None
    elif os.environ.get("WCB_SESSION_DIR"):
        transcript = Path(os.environ["WCB_SESSION_DIR"]) / TRANSCRIPT_NAME
    else:
        transcript = None

    http = HTTPConfig(timeout_s=a.request_timeout, retries=max(0, a.retries))
    kwargs: dict[str, Any] = {"base_url": a.base_url, "http": http, "temperature": a.temperature}
    if a.api_key_env:
        kwargs["api_key_env"] = a.api_key_env
    if a.provider == "anthropic":
        kwargs["prompt_cache"] = not a.no_prompt_cache
    try:
        provider = make_provider(a.provider, a.model, **kwargs)
    except ProviderError as e:
        return fail(str(e))

    cfg = LoopConfig(
        max_turns=max(1, a.max_turns),
        max_tokens=max(1, a.max_tokens),
        context_budget=max(4000, a.context_budget),
        max_tool_output=max(1000, a.max_tool_output),
    )
    stats = SessionStats()

    def on_signal(signum, _frame):
        raise SessionInterrupted(signum)

    old = {s: signal.signal(s, on_signal) for s in (signal.SIGTERM, signal.SIGINT)}
    say(f"[simple] {a.provider}:{a.model} phase={phase} workspace={workspace}")
    code = 0
    try:
        run_session(
            provider,
            workspace,
            prompt,
            phase=phase,
            config=cfg,
            system=system,
            transcript=transcript,
            log=say,
            stats=stats,
        )
    except SessionInterrupted as e:
        code = 128 + e.signum
        print(f"wcb.agents.simple: stopped by signal {e.signum}", file=sys.stderr, flush=True)
    except ProviderError as e:
        code = fail(str(e), 1)
    finally:
        for s, h in old.items():
            signal.signal(s, h)
        record = usage_record(
            stats,
            provider=a.provider,
            model=a.model,
            price_input=a.price_input,
            price_output=a.price_output,
            price_cache_read=a.price_cache_read,
        )
        try:
            write_usage(workspace, record)
        except OSError as e:
            print(f"wcb.agents.simple: could not write .wcb/usage.json: {e}", file=sys.stderr)
    print(
        f"[simple] stop={stats.stop} turns={stats.turns} tool_calls={stats.tool_calls} "
        f"input_tokens={stats.usage.input_tokens} output_tokens={stats.usage.output_tokens}",
        flush=True,
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
