"""Adapters: how the runner invokes a competitor's agent (docs/formats.md section 5).

An adapter is a small YAML file::

    name: my-agent
    version: 0.3.1
    model: provider/model-name
    cmd: ["my-agent", "--cwd", "{workspace}", "--prompt-file", "{prompt}"]  # both phases
    ingest:
      timeout_s: 1800
    query:
      cmd: ["my-agent", "--cwd", "{workspace}", "--prompt-file", "{prompt}", "--read-only"]
      timeout_s: 900
    cwd: "{workspace}"
    env: {MY_AGENT_MODE: benchmark}
    env_passthrough: [MY_PROVIDER_API_KEY]

Rules implemented here:

- ``cmd`` is a list (run directly, no shell) or a string (run with ``/bin/sh -c``). A phase's
  ``cmd``, ``cwd`` and ``timeout_s`` override the top-level ones.
- Placeholders (see :data:`PLACEHOLDERS`) are substituted in ``cmd``, ``cwd`` and ``env`` values.
  In a string ``cmd`` each substituted value is shell-quoted with :func:`shlex.quote`, so write
  ``--cwd {workspace}``, not ``--cwd "{workspace}"``. ``${VAR}`` shell syntax is left alone.
- A relative ``cwd`` is resolved against the adapter file's directory. The default is the
  workspace.
- The session environment is minimal: :data:`BASE_ENV` from the runner's environment, the
  variables named in ``env_passthrough``, the literal ``env`` mapping, then the ``WCB_*``
  variables. The directory of the Python interpreter running ``wcb`` is put first on ``PATH`` so
  that ``python`` in a command resolves to the interpreter that has ``wcb`` installed (this is what
  ``adapters/examples/null.yaml`` relies on). Set ``PATH`` in ``env`` to override.
"""

from __future__ import annotations

import hashlib
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PHASES = ("ingest", "query")

PLACEHOLDERS = (
    "workspace",  # absolute path of the directory the agent works in (the store)
    "prompt",  # absolute path of the prompt file (<session_dir>/prompt.md)
    "prompt_text",  # the prompt itself
    "date",  # simulated current date, YYYY-MM-DD
    "phase",  # 'ingest' or 'query'
    "track",  # 'A' or 'B'
    "session_dir",  # absolute path of this session's log directory (outside the workspace)
    "adapter_dir",  # absolute path of the directory holding the adapter file
)
"""Placeholder names recognized in ``cmd``, ``cwd`` and ``env`` values, written ``{name}``."""

BASE_ENV = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "TMPDIR", "SHELL")
"""Variables copied from the runner's environment into every session (when set)."""

WCB_ENV = (
    "WCB_DATE",
    "WCB_PHASE",
    "WCB_TRACK",
    "WCB_WORKSPACE",
    "WCB_PROMPT_FILE",
    "WCB_SESSION_DIR",
)
"""Variables the runner always sets. They cannot be overridden by ``env``."""

DEFAULT_TIMEOUT_S = {"ingest": 1800.0, "query": 900.0}
DEFAULT_CWD = "{workspace}"

TOP_LEVEL_KEYS = frozenset(
    {"name", "version", "model", "description", "cmd", "cwd", "timeout_s", "env", "env_passthrough"}
    | set(PHASES)
)
PHASE_KEYS = frozenset({"cmd", "cwd", "timeout_s"})

_PLACEHOLDER = re.compile(r"(?<!\$)\{([A-Za-z_][A-Za-z0-9_]*)\}")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class AdapterError(ValueError):
    """The adapter file is invalid. The message says what to fix."""


@dataclass
class PhaseSpec:
    """Resolved settings for one phase (top-level values with phase overrides applied)."""

    cmd: list[str] | str
    cwd: str | None
    timeout_s: float


@dataclass
class Adapter:
    """A loaded, validated adapter file. Build one with :func:`load_adapter`."""

    name: str
    version: str
    model: str
    path: Path  # absolute path of the adapter file
    raw: dict[str, Any]  # the parsed YAML, unmodified
    phases: dict[str, PhaseSpec] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    env_passthrough: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def dir(self) -> Path:
        """Directory holding the adapter file (the ``{adapter_dir}`` placeholder)."""
        return self.path.parent

    @property
    def sha256(self) -> str:
        """SHA-256 of the adapter file's bytes, recorded in run.json."""
        return hashlib.sha256(self.path.read_bytes()).hexdigest()

    def describe(self) -> dict[str, str]:
        """The adapter block of run.json."""
        return {
            "name": self.name,
            "version": self.version,
            "model": self.model,
            "path": str(self.path),
            "sha256": self.sha256,
        }

    def timeout(self, phase: str) -> float:
        return self._phase(phase).timeout_s

    def command(
        self, phase: str, vars: dict[str, str]
    ) -> tuple[list[str] | str, Path | None, float]:
        """The command to run for ``phase`` with placeholders filled from ``vars``.

        Returns ``(cmd, cwd, timeout_s)``. ``cmd`` is an argv list (run without a shell) or a
        string for ``/bin/sh -c`` whose substituted values are shell-quoted. ``cwd`` is ``None``
        only if the adapter sets ``cwd: null`` (run in the runner's working directory).
        ``{adapter_dir}`` is filled automatically.
        """
        spec = self._phase(phase)
        values = self._values(vars)
        if isinstance(spec.cmd, str):
            cmd: list[str] | str = _substitute(spec.cmd, values, quote=True, where=f"{phase} cmd")
        else:
            cmd = [_substitute(a, values, quote=False, where=f"{phase} cmd") for a in spec.cmd]
        cwd: Path | None = None
        if spec.cwd is not None:
            cwd = Path(
                _substitute(spec.cwd, values, quote=False, where=f"{phase} cwd")
            ).expanduser()
            if not cwd.is_absolute():
                cwd = (self.dir / cwd).resolve()
        return cmd, cwd, spec.timeout_s

    def environment(self, vars: dict[str, str]) -> dict[str, str]:
        """The complete environment for a session (nothing else is inherited).

        ``vars`` must contain the placeholder values, at least ``date``, ``phase``, ``track``,
        ``workspace``, ``prompt`` and ``session_dir``.
        """
        values = self._values(vars)
        env = {k: os.environ[k] for k in BASE_ENV if k in os.environ}
        env["PATH"] = with_interpreter_on_path(env.get("PATH", os.defpath))
        for k in self.env_passthrough:
            if k in os.environ:
                env[k] = os.environ[k]
        for k, v in self.env.items():
            env[k] = _substitute(v, values, quote=False, where=f"env {k}")
        try:
            env.update(
                WCB_DATE=values["date"],
                WCB_PHASE=values["phase"],
                WCB_TRACK=values["track"],
                WCB_WORKSPACE=values["workspace"],
                WCB_PROMPT_FILE=values["prompt"],
                WCB_SESSION_DIR=values["session_dir"],
            )
        except KeyError as e:  # a runner bug, not a user error
            raise KeyError(f"session variable {e} is required to build the environment") from e
        return env

    def missing_passthrough(self) -> list[str]:
        """Names in ``env_passthrough`` that are not set in the runner's environment."""
        return [k for k in self.env_passthrough if k not in os.environ]

    # ------------------------------------------------------------ internals
    def _phase(self, phase: str) -> PhaseSpec:
        if phase not in self.phases:
            raise ValueError(f"unknown phase {phase!r}; expected one of {', '.join(PHASES)}")
        return self.phases[phase]

    def _values(self, vars: dict[str, str]) -> dict[str, str]:
        return {"adapter_dir": str(self.dir), **{k: str(v) for k, v in vars.items()}}


def with_interpreter_on_path(path: str) -> str:
    """Put the directory of the running Python interpreter first on ``path`` (deduplicated).

    When ``wcb`` runs from a virtual environment (``.venv/bin/wcb``), this makes ``python`` in an
    adapter command resolve to that environment's interpreter, which has ``wcb`` installed.
    """
    exe_dir = os.path.dirname(sys.executable or "")
    if not exe_dir:
        return path
    rest = [p for p in path.split(os.pathsep) if p and p != exe_dir]
    return os.pathsep.join([exe_dir, *rest])


def load_adapter(path: Path) -> Adapter:
    """Load and validate an adapter file.

    Raises :class:`FileNotFoundError` if the file does not exist and :class:`AdapterError` (a
    ``ValueError``) for invalid content. Non-fatal problems, such as unknown keys, are returned in
    ``Adapter.warnings``.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"adapter file not found: {path} (see adapters/examples/null.yaml for an example)"
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise AdapterError(f"{path}: invalid YAML: {e}") from e
    if not isinstance(raw, dict):
        raise AdapterError(
            f"{path}: an adapter file must be a YAML mapping with at least 'name' and 'cmd'"
        )

    errors: list[str] = []
    warnings: list[str] = []

    for k in sorted(set(raw) - TOP_LEVEL_KEYS, key=str):
        warnings.append(
            f"unknown key {k!r} ignored (known keys: {', '.join(sorted(TOP_LEVEL_KEYS))})"
        )

    name = _scalar(raw.get("name"))
    if not name:
        errors.append(
            "'name' is required: a short identifier for your agent, e.g. 'name: my-agent'"
        )
    version = _scalar(raw.get("version"))
    if not version:
        warnings.append("'version' is not set; it is recorded in run.json and reports")
    model = _scalar(raw.get("model"))
    if not model:
        warnings.append(
            "'model' is not set; it is reported on the leaderboard (e.g. provider/model-name)"
        )

    top_cmd = _check_cmd(raw.get("cmd"), "cmd", errors)
    top_cwd = _check_cwd(raw, "cwd", errors, default=DEFAULT_CWD)
    top_timeout = _check_timeout(raw.get("timeout_s"), "timeout_s", errors)

    env: dict[str, str] = {}
    raw_env = raw.get("env")
    if raw_env is not None:
        if not isinstance(raw_env, dict):
            errors.append(
                "'env' must be a mapping of variable names to values, e.g. {MODE: benchmark}"
            )
        else:
            for k, v in raw_env.items():
                if not isinstance(k, str) or not _ENV_NAME.match(k):
                    errors.append(f"env: {k!r} is not a valid environment variable name")
                elif v is None or isinstance(v, (dict, list)):
                    errors.append(f"env: {k} must be a string or number, got {type(v).__name__}")
                elif k in WCB_ENV:
                    warnings.append(f"env: {k} is set by the runner and cannot be overridden")
                else:
                    env[k] = str(v).lower() if isinstance(v, bool) else str(v)

    passthrough: list[str] = []
    raw_pass = raw.get("env_passthrough")
    if raw_pass is not None:
        if isinstance(raw_pass, str):
            raw_pass = [raw_pass]
        if not isinstance(raw_pass, list):
            errors.append("'env_passthrough' must be a list of variable names, e.g. [MY_API_KEY]")
        else:
            for k in raw_pass:
                if not isinstance(k, str) or not _ENV_NAME.match(k):
                    errors.append(
                        f"env_passthrough: {k!r} is not a valid environment variable name"
                    )
                elif k in WCB_ENV:
                    warnings.append(
                        f"env_passthrough: {k} is set by the runner and cannot be passed through"
                    )
                else:
                    passthrough.append(k)

    phases: dict[str, PhaseSpec] = {}
    for phase in PHASES:
        block = raw.get(phase)
        if block is None:
            block = {}
        if not isinstance(block, dict):
            errors.append(
                f"'{phase}' must be a mapping with any of: {', '.join(sorted(PHASE_KEYS))}"
            )
            continue
        for k in sorted(set(block) - PHASE_KEYS, key=str):
            warnings.append(
                f"unknown key {phase}.{k} ignored (phase blocks accept: {', '.join(sorted(PHASE_KEYS))})"
            )
        if "cmd" in block:
            cmd = _check_cmd(block["cmd"], f"{phase}.cmd", errors)
            given = block["cmd"] is not None
        else:
            cmd, given = top_cmd, raw.get("cmd") is not None
        if not given:  # (an invalid command was already reported by _check_cmd)
            errors.append(
                f"no command for the {phase} phase: set top-level 'cmd' (used by both phases) "
                f"or '{phase}.cmd'"
            )
        cwd = (
            _check_cwd(block, f"{phase}.cwd", errors, default=top_cwd)
            if "cwd" in block
            else top_cwd
        )
        timeout = _check_timeout(block.get("timeout_s"), f"{phase}.timeout_s", errors)
        timeout = timeout or top_timeout or DEFAULT_TIMEOUT_S[phase]
        if cmd is not None:
            phases[phase] = PhaseSpec(cmd=cmd, cwd=cwd, timeout_s=timeout)

    if errors:
        raise AdapterError(f"{path}: invalid adapter:\n" + "\n".join(f"  - {e}" for e in errors))

    # Unknown placeholders are probably typos ({workdir} instead of {workspace}).
    templates: list[tuple[str, str]] = []
    for phase, spec in phases.items():
        parts = [spec.cmd] if isinstance(spec.cmd, str) else spec.cmd
        templates += [(f"{phase} cmd", p) for p in parts]
        if spec.cwd is not None:
            templates.append((f"{phase} cwd", spec.cwd))
    templates += [(f"env {k}", v) for k, v in env.items()]
    seen: set[tuple[str, str]] = set()
    for where, text in templates:
        for m in _PLACEHOLDER.finditer(text):
            key = (where, m.group(1))
            if m.group(1) not in PLACEHOLDERS and key not in seen:
                seen.add(key)
                warnings.append(
                    f"{where}: '{{{m.group(1)}}}' is not a placeholder and is passed through "
                    f"literally (placeholders: {', '.join('{' + p + '}' for p in PLACEHOLDERS)})"
                )

    return Adapter(
        name=name or "",
        version=version or "unspecified",
        model=model or "unspecified",
        path=path,
        raw=raw,
        phases=phases,
        env=env,
        env_passthrough=passthrough,
        warnings=[f"{path.name}: {w}" for w in warnings],
    )


# ---------------------------------------------------------------- helpers
def _scalar(v: Any) -> str | None:
    if v is None or isinstance(v, (dict, list)):
        return None
    s = str(v).strip()
    return s or None


def _check_cmd(v: Any, where: str, errors: list[str]) -> list[str] | str | None:
    if v is None:
        return None
    if isinstance(v, str):
        if not v.strip():
            errors.append(f"'{where}' is an empty string")
            return None
        return v
    if isinstance(v, list):
        if not v:
            errors.append(f"'{where}' is an empty list; give the program and its arguments")
            return None
        out = []
        for i, a in enumerate(v):
            if a is None or isinstance(a, (dict, list)):
                errors.append(
                    f"'{where}[{i}]' must be a string, got {type(a).__name__} "
                    '(quote YAML values such as {workspace}: "{workspace}")'
                )
            else:
                out.append(str(a).lower() if isinstance(a, bool) else str(a))
        return out
    errors.append(
        f"'{where}' must be a list of arguments or a shell command string, got {type(v).__name__}"
    )
    return None


def _check_cwd(block: dict, where: str, errors: list[str], default: str | None) -> str | None:
    key = where.rsplit(".", 1)[-1]
    if key not in block:
        return default
    v = block[key]
    if v is None:
        return None
    if isinstance(v, (dict, list)) or not str(v).strip():
        errors.append(f"'{where}' must be a directory path such as \"{{workspace}}\"")
        return default
    return str(v)


def _check_timeout(v: Any, where: str, errors: list[str]) -> float | None:
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
        errors.append(f"'{where}' must be a positive number of seconds, got {v!r}")
        return None
    return float(v)


def _substitute(text: str, values: dict[str, str], *, quote: bool, where: str) -> str:
    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name not in PLACEHOLDERS:
            return m.group(0)
        if name not in values:
            raise AdapterError(f"{where}: placeholder {{{name}}} has no value in this session")
        return shlex.quote(values[name]) if quote else values[name]

    return _PLACEHOLDER.sub(repl, text)
