"""Adapter loading, validation, placeholder substitution and session environment."""

from __future__ import annotations

import hashlib
import os
import shlex
import sys
from pathlib import Path

import pytest
import yaml

from wcb.paths import repo_root
from wcb.runner.adapter import (
    DEFAULT_TIMEOUT_S,
    AdapterError,
    load_adapter,
    python_trusts_cwd,
    with_interpreter_on_path,
)

VARS = {
    "workspace": "/tmp/wcb-ws-abc/my store",
    "prompt": "/runs/x/sessions/2027-03-01.ingest/prompt.md",
    "prompt_text": "Today is 2027-03-01. Do the thing.",
    "date": "2027-03-01",
    "phase": "ingest",
    "track": "A",
    "session_dir": "/runs/x/sessions/2027-03-01.ingest",
}


def write(tmp_path: Path, data, name: str = "adapter.yaml") -> Path:
    p = tmp_path / name
    p.write_text(data if isinstance(data, str) else yaml.safe_dump(data, sort_keys=False))
    return p


def test_minimal_adapter_defaults(tmp_path):
    a = load_adapter(write(tmp_path, {"name": "my-agent", "cmd": ["my-agent", "{prompt}"]}))
    assert a.name == "my-agent" and a.version == "unspecified" and a.model == "unspecified"
    assert any("'model' is not set" in w for w in a.warnings)
    assert any("'version' is not set" in w for w in a.warnings)
    cmd, cwd, timeout = a.command("ingest", VARS)
    assert cmd == ["my-agent", VARS["prompt"]]
    assert cwd == Path(VARS["workspace"]) and timeout == DEFAULT_TIMEOUT_S["ingest"]
    assert a.command("query", {**VARS, "phase": "query"})[2] == DEFAULT_TIMEOUT_S["query"]
    assert a.dir == tmp_path.resolve() and a.path == (tmp_path / "adapter.yaml").resolve()


def test_phase_settings_override_top_level(tmp_path):
    a = load_adapter(
        write(
            tmp_path,
            {
                "name": "x",
                "version": "0.3.1",
                "model": "provider/model",
                "cmd": ["agent", "--cwd", "{workspace}"],
                "timeout_s": 100,
                "ingest": {"timeout_s": 50},
                "query": {"cmd": ["agent", "--read-only"], "cwd": "sub"},
            },
        )
    )
    assert a.warnings == []
    assert a.command("ingest", VARS) == (
        ["agent", "--cwd", VARS["workspace"]],
        Path(VARS["workspace"]),
        50.0,
    )
    cmd, cwd, timeout = a.command("query", VARS)
    assert cmd == ["agent", "--read-only"] and timeout == 100.0
    assert cwd == (tmp_path / "sub").resolve()  # relative cwd: against the adapter's directory


def test_list_command_substitutes_without_quoting(tmp_path):
    a = load_adapter(
        write(
            tmp_path,
            {
                "name": "x",
                "cmd": [
                    "run",
                    "--ws={workspace}",
                    "{prompt_text}",
                    "{date}/{phase}/{track}",
                    "{adapter_dir}/a.sh",
                    "{unknown}",
                ],
                "cwd": None,
            },
        )
    )
    cmd, cwd, _ = a.command("ingest", VARS)
    assert cmd == [
        "run",
        f"--ws={VARS['workspace']}",
        VARS["prompt_text"],
        "2027-03-01/ingest/A",
        f"{tmp_path.resolve()}/a.sh",
        "{unknown}",
    ]
    assert cwd is None
    assert any("'{unknown}' is not a placeholder" in w for w in a.warnings)


def test_string_command_is_shell_quoted(tmp_path):
    a = load_adapter(
        write(
            tmp_path,
            {
                "name": "x",
                "cmd": 'agent --cwd {workspace} -p {prompt_text} --home "${HOME}" | tee log',
            },
        )
    )
    cmd, _, _ = a.command("ingest", VARS)
    assert cmd == (
        f"agent --cwd {shlex.quote(VARS['workspace'])} -p {shlex.quote(VARS['prompt_text'])} "
        '--home "${HOME}" | tee log'
    )
    assert not any("HOME" in w for w in a.warnings)  # ${HOME} is shell syntax, not a placeholder


def test_environment_is_minimal(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", "/home/tester")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("MY_PROVIDER_API_KEY", "sk-test")
    monkeypatch.setenv("UNRELATED_SECRET", "nope")
    monkeypatch.delenv("MISSING_KEY", raising=False)
    a = load_adapter(
        write(
            tmp_path,
            {
                "name": "x",
                "cmd": ["agent"],
                "env": {
                    "MODE": "benchmark",
                    "LOG_DIR": "{session_dir}/logs",
                    "FLAG": True,
                    "WCB_DATE": "1999-01-01",
                },
                "env_passthrough": ["MY_PROVIDER_API_KEY", "MISSING_KEY"],
            },
        )
    )
    assert any("WCB_DATE is set by the runner" in w for w in a.warnings)
    assert a.missing_passthrough() == ["MISSING_KEY"]
    env = a.environment(VARS)
    assert env["HOME"] == "/home/tester"
    assert (
        env["MY_PROVIDER_API_KEY"] == "sk-test"
        and "UNRELATED_SECRET" not in env
        and "MISSING_KEY" not in env
    )
    assert (
        env["MODE"] == "benchmark"
        and env["LOG_DIR"] == f"{VARS['session_dir']}/logs"
        and env["FLAG"] == "true"
    )
    assert (
        env["WCB_DATE"] == "2027-03-01" and env["WCB_PHASE"] == "ingest" and env["WCB_TRACK"] == "A"
    )
    assert env["WCB_WORKSPACE"] == VARS["workspace"] and env["WCB_PROMPT_FILE"] == VARS["prompt"]
    assert env["WCB_SESSION_DIR"] == VARS["session_dir"]
    assert env["PATH"].split(os.pathsep) == [os.path.dirname(sys.executable), "/usr/bin", "/bin"]


def test_env_can_override_path(tmp_path, monkeypatch):
    a = load_adapter(
        write(tmp_path, {"name": "x", "cmd": ["agent"], "env": {"PATH": "/opt/agent/bin"}})
    )
    assert a.environment(VARS)["PATH"] == "/opt/agent/bin"


def test_interpreter_dir_is_deduplicated():
    d = os.path.dirname(sys.executable)
    assert with_interpreter_on_path(os.pathsep.join(["/a", d, "/b"])) == os.pathsep.join(
        [d, "/a", "/b"]
    )


def test_missing_command_is_an_error(tmp_path):
    p = write(tmp_path, {"name": "x", "query": {"cmd": ["agent"]}})
    with pytest.raises(AdapterError, match="no command for the ingest phase"):
        load_adapter(p)


def test_all_errors_reported_together(tmp_path):
    p = write(
        tmp_path,
        {
            "cmd": {"bad": 1},
            "timeout_s": -5,
            "env": ["A=1"],
            "env_passthrough": [3],
            "query": {"cmd": [], "timeout_s": "soon"},
        },
    )
    with pytest.raises(AdapterError) as e:
        load_adapter(p)
    msg = str(e.value)
    for needle in ("'name' is required", "'cmd' must be a list", "'timeout_s' must be a positive",
                   "'env' must be a mapping", "env_passthrough: 3", "'query.cmd' is an empty list",
                   "'query.timeout_s' must be a positive"):  # fmt: skip
        assert needle in msg, needle


def test_unknown_keys_are_warnings(tmp_path):
    a = load_adapter(
        write(tmp_path, {"name": "x", "cmd": ["a"], "comand": ["typo"], "ingest": {"timeout": 5}})
    )
    assert any("unknown key 'comand'" in w for w in a.warnings)
    assert any("unknown key ingest.timeout" in w for w in a.warnings)


def test_file_errors(tmp_path):
    with pytest.raises(FileNotFoundError, match="adapter file not found"):
        load_adapter(tmp_path / "nope.yaml")
    with pytest.raises(AdapterError, match="invalid YAML"):
        load_adapter(write(tmp_path, "name: [unclosed"))
    with pytest.raises(AdapterError, match="must be a YAML mapping"):
        load_adapter(write(tmp_path, "- just\n- a list\n"))


def test_unknown_phase(tmp_path):
    a = load_adapter(write(tmp_path, {"name": "x", "cmd": ["a"]}))
    with pytest.raises(ValueError, match="unknown phase"):
        a.command("grade", VARS)


def test_describe_has_sha256(tmp_path):
    p = write(tmp_path, {"name": "x", "version": 2, "model": "m", "cmd": "a"})
    d = load_adapter(p).describe()
    assert d == {
        "name": "x",
        "version": "2",
        "model": "m",
        "path": str(p.resolve()),
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    }


def test_example_null_adapter_is_clean():
    root = repo_root()
    assert root is not None
    a = load_adapter(root / "adapters" / "examples" / "null.yaml")
    assert a.warnings == []
    assert a.command("query", VARS)[0] == ["python", "-I", "-m", "wcb.baselines.null"]


@pytest.mark.parametrize(
    ("cmd", "trusts"),
    [
        (["python", "-m", "my_agent"], True),
        (["python3.12", "-c", "import my_agent"], True),
        (["/usr/bin/python3", "-B", "-m", "my_agent"], True),
        (["python", "-Bm", "my_agent"], True),
        (["uv", "run", "python", "-m", "my_agent"], True),
        (["python", "-W", "error", "-m", "my_agent"], True),
        ("python -m wcb.agents.wrap --format codex -- codex exec {prompt_text}", True),
        (["python", "-I", "-m", "my_agent"], False),
        (["python", "-Im", "my_agent"], False),
        (["python3", "-P", "-m", "my_agent"], False),
        (["python", "{adapter_dir}/agent.py", "-m"], False),  # a script: its own dir is on sys.path
        (["my-agent", "--python", "-m"], False),
        ("python -I -m wcb.agents.wrap --format codex -- codex exec {prompt_text}", False),
        ('docker run img sh -c "$WCB_AGENT_CMD"', False),
    ],
)
def test_python_trusts_cwd(cmd, trusts):
    assert python_trusts_cwd(cmd) is trusts


def test_python_m_in_the_workspace_is_a_warning(tmp_path):
    base = {"name": "x", "version": "1", "model": "m"}
    a = load_adapter(write(tmp_path, {**base, "cmd": ["python", "-m", "my_agent"]}))
    assert [w for w in a.warnings if "sys.path" in w] == [
        "adapter.yaml: ingest and query cmd: Python run with -m or -c puts its working directory, "
        "the workspace, first on sys.path, so a file the agent leaves in the store (json.py, a "
        "wcb/ directory) replaces the real module; add -I (python -I -m ...), or -P on Python 3.11+"
    ]
    for data in (
        {**base, "cmd": ["python", "-I", "-m", "my_agent"]},
        {**base, "cmd": ["python", "-m", "my_agent"], "cwd": "{adapter_dir}"},
        {**base, "cmd": ["python", "{adapter_dir}/agent.py"]},
    ):
        assert load_adapter(write(tmp_path, data)).warnings == [], data
    mixed = {**base, "cmd": ["python", "-I", "-m", "a"], "query": {"cmd": ["python", "-m", "b"]}}
    assert any(w.startswith("adapter.yaml: query cmd:") for w in load_adapter(write(tmp_path, mixed)).warnings)
