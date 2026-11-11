"""End-to-end tests of the episode runner against a fake built world and a fake agent."""

from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
import time
from pathlib import Path

import pytest

from wcb.grade.score import RunPlan
from wcb.runner import episode, prompts
from wcb.runner.episode import RunConfig, run
from wcb.runner.workspace import tree_files
from wcb.util.io import read_json

# The fake world built in conftest.py: two seed dates, two episode days, cp1 on the last day.
SEED_DATES = ["2027-01-04", "2027-01-05"]
SEED_END = SEED_DATES[-1]
D1, D2 = "2027-01-06", "2027-01-07"


@pytest.fixture
def run_world(tmp_path: Path, fake_world: Path):
    """Run the runner on the fake world; workspaces go to tmp_path/ws, results to tmp_path/run."""

    def go(adapter: Path, **kw) -> int:
        cfg = RunConfig(
            adapter=adapter,
            worlds=[str(kw.pop("world", fake_world))],
            split=None,
            track=kw.pop("track", "A"),
            repeats=kw.pop("repeats", 1),
            out=kw.pop("out", tmp_path / "run"),
            workspace_root=kw.pop("workspace_root", tmp_path / "ws"),
            **kw,
        )
        return run(cfg)

    return go


@pytest.fixture
def mini_world_copy(tmp_path: Path, mini_world_dir: Path) -> Path:
    """A copy of the built mini world, which (unlike the fake world) can be rebuilt."""
    import shutil

    return Path(shutil.copytree(mini_world_dir, tmp_path / "worlds" / "mini-world"))


def r1(tmp_path: Path) -> Path:
    return tmp_path / "run" / "fake" / "r1"


def seen(session_dir: Path) -> dict:
    """What the fake agent recorded about its session."""
    return read_json(session_dir / "fake_agent.json")


# ---------------------------------------------------------------- Track A happy path
def test_track_a_full_run(
    tmp_path, fake_world, make_adapter, run_world, agent_sessions, monkeypatch
):
    monkeypatch.setenv("WCB_TEST_PASSTHROUGH", "passed")
    monkeypatch.setenv("WCB_TEST_SECRET", "must-not-leak")
    adapter = make_adapter()
    assert run_world(adapter) == 0
    rdir = r1(tmp_path)

    # run.json
    meta = read_json(tmp_path / "run" / "run.json")
    assert meta["status"] == "completed" and meta["track"] == "A" and meta["oracle"] is True
    assert meta["adapter"]["name"] == "fake-agent" and meta["adapter"]["model"] == "test/fake-model"
    assert meta["adapter"]["version"] == "1.0.0" and len(meta["adapter"]["sha256"]) == 64
    assert meta["adapter"]["path"] == str(adapter.resolve())
    assert meta["worlds"] == [{"id": "fake", "path": str(fake_world.resolve()), "repeats": 1,
                               "gold": read_json(fake_world / "gold" / "BUILD.json")}]
    assert meta["started_at"] and meta["finished_at"] and meta["command_line"]
    assert meta["wcb_version"]

    # one ingest session per day, one query, one oracle query
    assert agent_sessions() == [f"ingest {D1}", f"ingest {D2}", f"query {D2}", f"query {D2}"]
    sessions = sorted(p.name for p in (rdir / "sessions").iterdir())
    assert sessions == [f"{D1}.ingest", f"{D2}.ingest", "cp1.query", "cp1.query-oracle"]

    # snapshots: seed store plus one per day, without .git/inbox/.wcb
    snaps = rdir / "snapshots"
    assert sorted(p.name for p in snaps.iterdir()) == [SEED_END, D1, D2]
    assert tree_files(snaps / SEED_END, exclude=()) == ["CONTRACT.md", "people/me.md"]
    assert tree_files(snaps / D1, exclude=()) == ["CONTRACT.md", f"notes/{D1}.md", "people/me.md"]
    assert tree_files(snaps / D2, exclude=()) == [
        "CONTRACT.md",
        f"notes/{D1}.md",
        f"notes/{D2}.md",
        "people/me.md",
    ]
    assert (snaps / D1 / "notes" / f"{D1}.md").read_text() == f"inbox: {D1}\n"

    # final workspace copied into the run, without .git; temp workspaces deleted
    assert tree_files(rdir / "workspace", exclude=()) == tree_files(snaps / D2, exclude=())
    assert list((tmp_path / "ws").iterdir()) == []

    # ingest session.json
    s = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["phase"] == "ingest" and s["date"] == D1 and s["checkpoint"] is None
    assert s["store"] == "agent" and s["exit_code"] == 0 and s["timed_out"] is False
    assert s["status"] == "ok" and isinstance(s["wall_s"], float) and s["timeout_s"] == 30.0
    assert s["started_at"] and s["finished_at"]
    assert s["usage"] == {
        "input_tokens": 11,
        "output_tokens": 7,
        "cost_usd": 0.01,
        "tool_calls": 3,
        "model": "fake",
    }
    sd = rdir / "sessions" / f"{D1}.ingest"
    assert (
        (sd / "usage.json").is_file()
        and (sd / "stdout.log").is_file()
        and (sd / "stderr.log").is_file()
    )
    assert (sd / "prompt.md").read_text() == prompts.render(prompts.INGEST_A, date=D1) + "\n"

    # placeholders and environment
    info = seen(sd)
    ws = info["workspace"]
    assert s["cmd"] == [sys.executable, *info["argv"]]
    assert info["argv"][0] == str(adapter.resolve().parent / "agent.py")
    args = info["argv"][1:]
    assert args == [
        "--workspace", ws, "--prompt", str(sd / "prompt.md"), "--date", D1, "--phase", "ingest",
        "--track", "A", "--session-dir", str(sd),
    ]  # fmt: skip
    assert info["cwd"] == ws
    assert info["inbox"] == [D1]
    env = info["env"]
    assert env["WCB_DATE"] == D1 and env["WCB_PHASE"] == "ingest" and env["WCB_TRACK"] == "A"
    assert env["WCB_WORKSPACE"] == ws and env["WCB_SESSION_DIR"] == str(sd)
    assert env["WCB_PROMPT_FILE"] == str(sd / "prompt.md")
    assert env["WCB_TEST_PASSTHROUGH"] == "passed" and "WCB_TEST_SECRET" not in env
    assert env["LITERAL"] == f"day-{D1}" and env["FAKE_MODE"] == "normal"
    assert env["PATH"].split(os.pathsep)[0] == os.path.dirname(sys.executable)
    allowed = {"PATH", "HOME", "USER", "LANG", "LC_ALL", "TERM", "TMPDIR", "SHELL", "WCB_TEST_PASSTHROUGH",
               "FAKE_MODE", "FAKE_LOG", "LITERAL", "WCB_DATE", "WCB_PHASE", "WCB_TRACK", "WCB_WORKSPACE",
               "WCB_PROMPT_FILE", "WCB_SESSION_DIR"}  # fmt: skip
    # Python itself may add a few variables (e.g. LC_CTYPE coercion); nothing else may leak.
    assert set(env) - allowed <= {"LC_CTYPE", "PYTHONCOERCECLOCALE"}

    # the workspace lives outside the run directory and the world, and is gone afterwards
    rundir = (tmp_path / "run").resolve()
    assert not Path(ws).resolve().is_relative_to(rundir)
    assert not Path(ws).resolve().is_relative_to(fake_world.resolve())
    assert Path(ws).resolve().is_relative_to((tmp_path / "ws").resolve())
    assert not Path(ws).exists()
    assert read_json(rdir / "state.json")["status"] == "done"

    # git history: the second day sees the runner's commits
    git_log = seen(rdir / "sessions" / f"{D2}.ingest")["git_log"]
    if git_log is not None:
        assert git_log[:2] == [f"wcb: after {D1} ingest", "wcb: seed store"]

    # query session: read-only copy with visible questions only
    qd = rdir / "sessions" / "cp1.query"
    q = read_json(qd / "session.json")
    assert (
        q["phase"] == "query"
        and q["checkpoint"] == "cp1"
        and q["store"] == "agent"
        and q["date"] == D2
    )
    assert q["answers"] == {"status": "ok", "answered": 2, "questions": 2}
    assert q["usage"]["input_tokens"] == 11
    visible = read_json(qd / "questions.json")
    assert visible == {
        "date": D2,
        "questions": [
            {"id": "cp1-q1", "type": "point", "text": "Who owns Kite?"},
            {"id": "cp1-q2", "type": "list", "text": "What do I currently owe Ola?"},
        ],
    }
    qinfo = seen(qd)
    assert qinfo["wcb_files"] == ["answer-schema.json", "questions.json"]
    assert qinfo["inbox"] == [] and qinfo["workspace"] != ws
    assert not Path(qinfo["workspace"]).exists()
    assert (qd / "prompt.md").read_text() == prompts.render(prompts.QUERY_A, date=D2) + "\n"
    answers = read_json(rdir / "answers" / "cp1.json")
    assert answers == read_json(qd / "answers.json")
    assert set(answers) == {"cp1-q1", "cp1-q2"}
    assert answers["cp1-q1"]["type"] == "point" and answers["cp1-q2"]["type"] == "list"
    assert f"notes/{D2}.md" in answers["cp1-q1"]["store_files"]
    assert "projects/oracle-marker.md" not in answers["cp1-q1"]["store_files"]

    # oracle query: same questions against the oracle store for the checkpoint date
    od = rdir / "sessions" / "cp1.query-oracle"
    o = read_json(od / "session.json")
    assert o["store"] == "oracle" and o["checkpoint"] == "cp1" and o["phase"] == "query"
    oracle_answers = read_json(rdir / "answers" / "cp1.oracle.json")
    assert oracle_answers["cp1-q1"]["store_files"] == [
        "CONTRACT.md",
        "people/me.md",
        "projects/oracle-marker.md",
    ]
    assert seen(od)["env"]["WCB_TRACK"] == "A"


# ---------------------------------------------------------------- failures
def test_crashed_ingest_restores_store(tmp_path, make_adapter, run_world, agent_sessions):
    assert run_world(make_adapter(mode="crash", fail_date=D2)) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")
    assert s["exit_code"] == 3 and s["status"] == "failed" and s["timed_out"] is False
    assert any("restored" in n for n in s["notes"])
    assert tree_files(rdir / "snapshots" / D2) == tree_files(rdir / "snapshots" / D1)
    assert "notes/partial.md" not in tree_files(rdir / "workspace")
    # the checkpoint query still runs, on the restored store
    assert agent_sessions()[-2:] == [f"query {D2}", f"query {D2}"]
    files = read_json(rdir / "answers" / "cp1.json")["cp1-q1"]["store_files"]
    assert "notes/partial.md" not in files and f"notes/{D2}.md" not in files
    s1 = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s1["store_changes"] == {"added": 1, "modified": 0, "removed": 0}
    assert s["store_changes"] == {"added": 0, "modified": 0, "removed": 0}  # restored


# ---------------------------------------------------------------- termination and no-ops
def test_incomplete_termination_is_recorded_without_changing_the_outcome(
    tmp_path, make_adapter, run_world, capsys
):
    """Issue #11: a truncated final response exits 0; it must be visible, not hidden."""
    term = {"reason": "max_tokens", "incomplete": True, "stop_reason": "max_tokens"}
    adapter = make_adapter(env_extra={"FAKE_TERMINATION": json.dumps(term)})
    assert run_world(adapter, oracle=False) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["termination"] == term and s["incomplete"] is True
    assert s["status"] == "ok" and s["usage"]["termination"] == term
    assert any("did not finish normally" in n and "max_tokens" in n for n in s["notes"])
    # The store is kept, not restored.
    assert f"notes/{D1}.md" in tree_files(rdir / "snapshots" / D1)
    q = read_json(rdir / "sessions" / "cp1.query" / "session.json")
    assert q["incomplete"] is True and q["status"] == "ok" and q["answers"]["status"] == "ok"
    assert "incomplete (max_tokens)" in capsys.readouterr().out


def test_complete_and_malformed_termination(tmp_path, make_adapter, run_world):
    term = {"reason": "success", "incomplete": False}
    assert run_world(make_adapter(env_extra={"FAKE_TERMINATION": json.dumps(term)}),
                     oracle=False, max_days=1) == 0  # fmt: skip
    s = read_json(r1(tmp_path) / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["termination"] == term and "incomplete" not in s
    assert not any("did not finish" in n for n in s["notes"])

    out = tmp_path / "run2"
    adapter = make_adapter(env_extra={"FAKE_TERMINATION": '"truncated"'})
    assert run_world(adapter, oracle=False, max_days=1, out=out) == 0
    s = read_json(out / "fake" / "r1" / "sessions" / f"{D1}.ingest" / "session.json")
    assert "termination" not in s and "incomplete" not in s
    assert any("termination is not" in n for n in s["notes"])


def test_ingest_that_changes_nothing_is_visible_but_not_retried(
    tmp_path, make_adapter, run_world, agent_sessions, capsys
):
    assert run_world(make_adapter(mode="noop", fail_date=D1), oracle=False) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["status"] == "ok" and s["store_changes"] == {"added": 0, "modified": 0, "removed": 0}
    assert "incomplete" not in s
    s2 = read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")
    assert s2["store_changes"] == {"added": 1, "modified": 0, "removed": 0}
    assert agent_sessions() == [f"ingest {D1}", f"ingest {D2}", f"query {D2}"]  # no retry
    out = capsys.readouterr().out
    assert f"{D1} ingest" in out and "the session changed nothing in the store" in out
    assert out.count("changed nothing") == 1


def test_store_changes_count_added_modified_and_removed(tmp_path):
    from wcb.runner.workspace import tree_changes

    old, new = tmp_path / "old", tmp_path / "new"
    for d in (old, new):
        (d / "notes").mkdir(parents=True)
        (d / ".git").mkdir()
        (d / "notes" / "same.md").write_text("same\n")
    (old / "notes" / "edit.md").write_text("one\n")
    (new / "notes" / "edit.md").write_text("two\n")
    (old / "notes" / "gone.md").write_text("x\n")
    (new / "notes" / "new.md").write_text("x\n")
    (new / "notes" / "sub").mkdir()  # directories are not counted
    (new / ".git" / "HEAD").write_text("ref\n")  # nor is .git
    assert tree_changes(old, new) == {"added": 1, "modified": 1, "removed": 1}
    assert tree_changes(old, old) == {"added": 0, "modified": 0, "removed": 0}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:  # a zombie waiting to be reaped is not running
        return Path(f"/proc/{pid}/stat").read_text().split(") ")[1][0] != "Z"
    except (OSError, IndexError):
        return True


def test_timeout_kills_process_group_and_restores(tmp_path, make_adapter, run_world, monkeypatch):
    monkeypatch.setattr(episode, "KILL_GRACE_S", 1.0)
    t0 = time.monotonic()
    assert run_world(make_adapter(mode="sleep", fail_date=D1, ingest_timeout=4)) == 0
    assert time.monotonic() - t0 < 30
    rdir = r1(tmp_path)
    sd = rdir / "sessions" / f"{D1}.ingest"
    s = read_json(sd / "session.json")
    assert s["timed_out"] is True and s["status"] == "timeout" and s["wall_s"] < 15
    assert "notes/partial.md" not in tree_files(rdir / "snapshots" / D1)
    assert tree_files(rdir / "snapshots" / D1) == tree_files(rdir / "snapshots" / SEED_END)
    child = int((sd / "child.pid").read_text())
    deadline = time.monotonic() + 5
    while _alive(child) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(child), "the agent's child process survived the timeout"
    # the next day runs normally
    assert read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")["status"] == "ok"


LINUX = pytest.mark.skipif(
    not sys.platform.startswith("linux"), reason="needs /proc and PR_SET_CHILD_SUBREAPER"
)


@LINUX
@pytest.mark.parametrize("hang", [False, True], ids=["agent-exits", "agent-times-out"])
def test_processes_that_leave_the_session_are_killed(
    tmp_path, make_adapter, run_world, monkeypatch, hang
):
    """A daemon started with setsid() must not outlive its session or edit the store later."""
    monkeypatch.setattr(episode, "KILL_GRACE_S", 1.0)
    env = {"FAKE_HANG": "1", "FAKE_LATE_S": "4"} if hang else {"FAKE_LATE_S": "1.5"}
    adapter = make_adapter(mode="escape", fail_date=D1, ingest_timeout=2, env_extra=env)
    assert run_world(adapter, oracle=False) == 0
    rdir = r1(tmp_path)
    sd = rdir / "sessions" / f"{D1}.ingest"
    assert read_json(sd / "session.json")["status"] == ("timeout" if hang else "ok")
    daemon = int((sd / "escaped.pid").read_text())
    assert not _alive(daemon), "a process that left the session's process group survived it"
    for snap in (D1, D2):
        assert "notes/late.md" not in tree_files(rdir / "snapshots" / snap)
    assert "notes/late.md" not in tree_files(rdir / "workspace")


def test_store_changes_between_sessions_are_reverted(
    tmp_path, make_adapter, run_world, agent_sessions, monkeypatch
):
    """Whatever edits the workspace after a snapshot (a stray process, a person) is undone and
    noted before the next session, so it is never credited to the next day."""
    real = episode.snapshot

    def snapshot_then_tamper(ws, dest):
        real(ws, dest)
        if Path(dest).name == D1:
            (Path(ws) / "notes" / "stray.md").write_text("written between sessions\n")
            (Path(ws) / "people" / "me.md").write_text("tampered\n")

    monkeypatch.setattr(episode, "snapshot", snapshot_then_tamper)
    assert run_world(make_adapter(), oracle=False) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")
    assert s["status"] == "ok"
    assert any("changed after snapshots/" + D1 in n and "notes/stray.md" in n for n in s["notes"])
    assert "notes/stray.md" not in seen(rdir / "sessions" / f"{D2}.ingest")["files"]
    assert "notes/stray.md" not in tree_files(rdir / "snapshots" / D2)
    assert "tampered" not in (rdir / "snapshots" / D2 / "people" / "me.md").read_text()
    # a session that starts from an unchanged workspace gets no such note
    q = read_json(rdir / "sessions" / "cp1.query" / "session.json")
    assert not any("changed after" in n for n in q["notes"])


def test_sighup_interrupts_the_run_like_ctrl_c(tmp_path, fake_world, make_adapter):
    """Closing the terminal (SIGHUP) stops the agent and leaves a resumable, 'interrupted' run."""
    import signal
    import subprocess

    adapter = make_adapter(mode="sleep", fail_date=D1, ingest_timeout=60)
    out, ws_root = tmp_path / "run", tmp_path / "ws"
    code = "import sys; from wcb.cli import main; sys.exit(main())"
    runner = subprocess.Popen(
        [sys.executable, "-c", code, "run", "--adapter", str(adapter), "--world", str(fake_world),
         "--out", str(out), "--workspace-root", str(ws_root), "--no-oracle"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )  # fmt: skip
    sd = out / "fake" / "r1" / "sessions" / f"{D1}.ingest"
    deadline = time.monotonic() + 30
    while not (sd / "child.pid").is_file() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert (sd / "child.pid").is_file(), "the agent never started"
    runner.send_signal(signal.SIGHUP)
    assert runner.wait(timeout=30) != 0
    assert read_json(out / "run.json")["status"] == "interrupted"
    state = read_json(out / "fake" / "r1" / "state.json")
    assert state["status"] == "interrupted" and Path(state["workspace"]).is_dir()
    for pid in (seen(sd)["pid"], int((sd / "child.pid").read_text())):
        deadline = time.monotonic() + 5
        while _alive(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not _alive(pid), "the agent survived the runner's SIGHUP"


@pytest.mark.parametrize("sig", ["SIGTERM", "SIGHUP", "SIGQUIT"])
def test_termination_signals_raise_keyboard_interrupt(sig):
    import signal

    signum = getattr(signal, sig)
    unhandled: list[int] = []

    def fallback(n, frame):  # stands in for the default action, which would end pytest
        unhandled.append(n)

    previous = signal.signal(signum, fallback)
    try:
        with pytest.raises(KeyboardInterrupt), episode._sigterm_as_interrupt():
            os.kill(os.getpid(), signum)
            time.sleep(5)
        assert not unhandled
        assert signal.getsignal(signum) is fallback  # the previous handler is put back
    finally:
        signal.signal(signum, previous)


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
@pytest.mark.parametrize("what", ["file", "dir", "usage", "wcbdir"])
def test_permissions_an_agent_removes_do_not_stop_the_run(tmp_path, make_adapter, run_world, what):
    adapter = make_adapter(mode="vandal", fail_date=D1, env_extra={"FAKE_VANDAL": what})
    assert run_world(adapter, oracle=False) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["status"] == "ok", s["notes"]
    assert s["usage"]["input_tokens"] == 11  # .wcb/usage.json was readable again
    snap = tree_files(rdir / "snapshots" / D1)
    assert "people/me.md" in snap and f"notes/{D1}.md" in snap
    if what == "dir":
        assert "notes/private/secret.md" in snap
    assert read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")["status"] == "ok"
    assert read_json(tmp_path / "run" / "run.json")["status"] == "completed"
    assert not list((rdir / "snapshots").glob(".*.partial"))


def test_special_files_an_agent_leaves_are_deleted(tmp_path, make_adapter, run_world):
    adapter = make_adapter(mode="vandal", fail_date=D1, env_extra={"FAKE_VANDAL": "fifo"})
    assert run_world(adapter, oracle=False) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["status"] == "ok"
    assert any("special files" in n and "inbox" in n and "notes/pipe" in n for n in s["notes"])
    assert tree_files(rdir / "snapshots" / D1) == ["CONTRACT.md", f"notes/{D1}.md", "people/me.md"]
    assert read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")["status"] == "ok"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_unreadable_answers_do_not_stop_the_run(tmp_path, make_adapter, run_world):
    adapter = make_adapter(mode="vandal", env_extra={"FAKE_VANDAL": "answers"})
    assert run_world(adapter) == 0
    rdir = r1(tmp_path)
    q = read_json(rdir / "sessions" / "cp1.query" / "session.json")
    assert q["answers"] == {"status": "ok", "answered": 2, "questions": 2}


def test_unreadable_store_fails_the_session_and_restores(
    tmp_path, make_adapter, run_world, monkeypatch
):
    """A store the runner cannot copy even after fixing permissions (e.g. files owned by another
    user) fails the session like a crash. If the workspace cannot be cleaned either, the episode
    continues in a fresh workspace rebuilt from the last snapshot."""
    import shutil

    real_snapshot, real_restore = episode.snapshot, episode.restore
    calls = {"snapshot": 0, "restore": 0}

    def flaky_snapshot(ws, dest):
        if Path(dest).name == D1 and calls["snapshot"] == 0:
            calls["snapshot"] += 1
            raise shutil.Error([(str(ws), str(dest), "[Errno 13] Permission denied")])
        real_snapshot(ws, dest)

    def flaky_restore(ws, snap):
        calls["restore"] += 1
        if calls["restore"] == 1:
            raise PermissionError(13, "Permission denied", str(ws))
        real_restore(ws, snap)

    monkeypatch.setattr(episode, "snapshot", flaky_snapshot)
    monkeypatch.setattr(episode, "restore", flaky_restore)
    assert run_world(make_adapter(), oracle=False) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["status"] == "failed" and s["exit_code"] == 0
    assert any("could not clean up or snapshot" in n for n in s["notes"])
    assert any("could not be cleaned" in n for n in s["notes"])
    assert tree_files(rdir / "snapshots" / D1) == tree_files(rdir / "snapshots" / SEED_END)
    # the next day runs in a new workspace holding the restored store
    old_ws = seen(rdir / "sessions" / f"{D1}.ingest")["workspace"]
    d2 = seen(rdir / "sessions" / f"{D2}.ingest")
    assert d2["workspace"] != old_ws and f"notes/{D1}.md" not in d2["files"]
    assert read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")["status"] == "ok"
    assert not episode._ingest_completed(rdir / "sessions" / f"{D1}.ingest")
    shutil.rmtree(old_ws, ignore_errors=True)


def test_query_session_cannot_change_the_store(tmp_path, make_adapter, run_world):
    assert run_world(make_adapter(mode="modify_query"), oracle=False) == 0
    rdir = r1(tmp_path)
    info = seen(rdir / "sessions" / "cp1.query")
    if os.geteuid() != 0:  # root ignores file permissions
        assert info["attempts"]["edit"] == "PermissionError"
    assert info["attempts"]["created"] is True
    final = tree_files(rdir / "workspace")
    assert "notes/hack.md" not in final and "CONTRACT.md" in final
    assert "tampered" not in (rdir / "workspace" / "people" / "me.md").read_text()
    assert read_json(rdir / "answers" / "cp1.json")  # answers are still collected
    assert not (rdir / "answers" / "cp1.oracle.json").exists()


@pytest.mark.parametrize(
    ("mode", "status"),
    [("bad_answers", "invalid_json"), ("no_answers", "missing"), ("symlink_answers", "invalid")],
)
def test_unusable_answers_become_empty(tmp_path, make_adapter, run_world, mode, status):
    assert run_world(make_adapter(mode=mode), oracle=False) == 0
    rdir = r1(tmp_path)
    assert read_json(rdir / "answers" / "cp1.json") == {}
    s = read_json(rdir / "sessions" / "cp1.query" / "session.json")
    assert (
        s["status"] == "ok" and s["answers"]["status"] == status and s["answers"]["answered"] == 0
    )
    assert any("answers" in n for n in s["notes"])
    if mode == "bad_answers":
        assert (rdir / "sessions" / "cp1.query" / "answers.raw.json").read_text() == "{not json"


def test_missing_command_is_a_failed_session_not_a_crash(tmp_path, make_adapter, run_world):
    adapter = make_adapter(cmd=["wcb-no-such-agent-command", "{workspace}"])
    assert run_world(adapter) == 0
    rdir = r1(tmp_path)
    s = read_json(rdir / "sessions" / f"{D1}.ingest" / "session.json")
    assert s["status"] == "error" and s["exit_code"] == 127
    assert "not found" in (rdir / "sessions" / f"{D1}.ingest" / "stderr.log").read_text()
    assert read_json(rdir / "answers" / "cp1.json") == {}


def test_shell_string_command_quotes_placeholders(tmp_path, make_adapter, run_world):
    adapter_dir = tmp_path / "adapter dir"
    cmd = (
        f"{shlex.quote(sys.executable)} {{adapter_dir}}/agent.py --workspace {{workspace}} "
        "--prompt {prompt} --date {date} --text {prompt_text} && echo done-$WCB_PHASE"
    )
    adapter = make_adapter(cmd=cmd, directory=adapter_dir)
    assert run_world(adapter, workspace_root=tmp_path / "ws root", oracle=False) == 0
    sd = r1(tmp_path) / "sessions" / f"{D1}.ingest"
    info = seen(sd)
    assert info["argv"][0] == str(adapter_dir / "agent.py")
    assert info["argv"][1:] == [
        "--workspace", info["workspace"], "--prompt", str(sd / "prompt.md"), "--date", D1,
        "--text", prompts.ingest_prompt("A", D1),
    ]  # fmt: skip
    assert " " in info["workspace"]
    s = read_json(sd / "session.json")
    assert isinstance(s["cmd"], str) and shlex.quote(info["workspace"]) in s["cmd"]
    assert (sd / "stdout.log").read_text().strip() == "done-ingest"


# ---------------------------------------------------------------- Track B
def test_track_b_seed_session_gets_all_seed_inboxes(
    tmp_path, make_adapter, run_world, agent_sessions
):
    assert run_world(make_adapter(), track="B", oracle=True) == 0
    rdir = r1(tmp_path)
    meta = read_json(tmp_path / "run" / "run.json")
    assert meta["track"] == "B" and meta["oracle"] is False
    assert agent_sessions() == [f"ingest {SEED_END}", f"ingest {D1}", f"ingest {D2}", f"query {D2}"]

    sd = rdir / "sessions" / "seed.ingest"
    info = seen(sd)
    assert info["inbox"] == SEED_DATES
    assert info["files"] == ["GOALS.md"]
    assert info["env"]["WCB_DATE"] == SEED_END and info["env"]["WCB_TRACK"] == "B"
    prompt = (sd / "prompt.md").read_text()
    assert prompt == prompts.seed_prompt(SEED_END, SEED_DATES) + "\n"
    assert all(f"`inbox/{d}/`" in prompt for d in SEED_DATES) and f"Today is {SEED_END}." in prompt
    s = read_json(sd / "session.json")
    assert s["seed_dates"] == SEED_DATES and s["phase"] == "ingest" and s["date"] == SEED_END
    # Compared with the GOALS.md-only store, though the seed snapshot replaces it in place.
    assert s["store_changes"] == {"added": 1, "modified": 0, "removed": 0}

    assert (
        (rdir / "sessions" / f"{D1}.ingest" / "prompt.md")
        .read_text()
        .startswith(prompts.render(prompts.INGEST_B, date=D1))
    )
    assert (rdir / "sessions" / "cp1.query" / "prompt.md").read_text() == prompts.render(
        prompts.QUERY_B, date=D2
    ) + "\n"
    assert tree_files(rdir / "snapshots" / SEED_END) == ["GOALS.md", f"notes/{SEED_END}.md"]
    final = tree_files(rdir / "workspace")
    assert "GOALS.md" in final and "CONTRACT.md" not in final
    assert not (rdir / "sessions" / "cp1.query-oracle").exists()
    assert not (rdir / "answers" / "cp1.oracle.json").exists()


# ---------------------------------------------------------------- resume
def test_resume_skips_completed_sessions(tmp_path, make_adapter, run_world, agent_sessions):
    adapter = make_adapter()
    assert run_world(adapter, max_days=1) == 0
    assert agent_sessions() == [f"ingest {D1}"]  # cp1 is on day 2, outside --max-days 1
    rdir = r1(tmp_path)
    assert not (rdir / "answers").exists()

    with pytest.raises(ValueError, match="--resume"):
        run_world(adapter)

    assert run_world(adapter, resume=True) == 0
    assert agent_sessions() == [f"ingest {D1}", f"ingest {D2}", f"query {D2}", f"query {D2}"]
    # the second day was ingested on the store rebuilt from the first day's snapshot
    assert tree_files(rdir / "snapshots" / D2) == [
        "CONTRACT.md",
        f"notes/{D1}.md",
        f"notes/{D2}.md",
        "people/me.md",
    ]
    meta = read_json(tmp_path / "run" / "run.json")
    assert meta["status"] == "completed" and len(meta["resumed_at"]) == 1
    # The run now covers every day, and the scorer must see that (not the first --max-days 1).
    assert meta["options"]["max_days"] is None
    assert [r["options"]["max_days"] for r in meta["resumed_with"]] == [None]
    assert RunPlan.from_meta(tmp_path / "run", meta).max_days is None

    assert run_world(adapter, resume=True) == 0
    assert len(agent_sessions()) == 4  # nothing left to run
    assert list((tmp_path / "ws").iterdir()) == []


def test_resume_without_skip_ingest_adds_the_agent_episode(
    tmp_path, make_adapter, run_world, agent_sessions
):
    adapter = make_adapter()
    assert run_world(adapter, skip_ingest=True) == 0
    assert agent_sessions() == [f"query {D2}"]
    assert run_world(adapter, resume=True) == 0
    assert agent_sessions()[1:] == [f"ingest {D1}", f"ingest {D2}", f"query {D2}"]
    meta = read_json(tmp_path / "run" / "run.json")
    assert meta["options"]["skip_ingest"] is False
    assert RunPlan.from_meta(tmp_path / "run", meta).agent is True


@pytest.mark.parametrize(
    ("old", "new", "max_days", "skip_ingest"),
    [
        ({"max_days": 1, "skip_ingest": False}, {"max_days": None, "skip_ingest": False}, None, False),
        ({"max_days": 2, "skip_ingest": False}, {"max_days": 1, "skip_ingest": False}, 2, False),
        ({"max_days": 1, "skip_ingest": False}, {"max_days": 3, "skip_ingest": False}, 3, False),
        ({"max_days": None, "skip_ingest": False}, {"max_days": 1, "skip_ingest": False}, None, False),
        ({"max_days": 1, "skip_ingest": True}, {"max_days": 1, "skip_ingest": True}, 1, True),
        ({"max_days": 1, "skip_ingest": True}, {"max_days": 1, "skip_ingest": False}, 1, False),
        ({"max_days": 1, "skip_ingest": False}, {"max_days": 1, "skip_ingest": True}, 1, False),
        ({}, {"max_days": 2, "skip_ingest": False}, None, False),
    ],
)
def test_resume_merges_options_over_invocations(old, new, max_days, skip_ingest):
    merged = episode._merge_options(old, {"workspace_root": None, "meter": False, **new})
    assert merged["max_days"] == max_days and merged["skip_ingest"] is skip_ingest


def test_resume_reruns_failed_ingest_and_later_sessions(
    tmp_path, make_adapter, run_world, agent_sessions
):
    assert run_world(make_adapter(mode="crash", fail_date=D2)) == 0
    assert len(agent_sessions()) == 4
    assert run_world(make_adapter(), resume=True) == 0
    # day 1 and the oracle query are kept; the failed day and its checkpoint query run again
    assert agent_sessions()[4:] == [f"ingest {D2}", f"query {D2}"]
    rdir = r1(tmp_path)
    assert read_json(rdir / "sessions" / f"{D2}.ingest" / "session.json")["status"] == "ok"
    assert f"notes/{D2}.md" in read_json(rdir / "answers" / "cp1.json")["cp1-q1"]["store_files"]


def test_resume_after_interrupt_reuses_workspace(
    tmp_path, make_adapter, run_world, agent_sessions, monkeypatch
):
    adapter = make_adapter()
    real = episode.run_process

    def interrupt_on_day_two(cmd, cwd, env, *args, **kw):
        if env["WCB_DATE"] == D2 and env["WCB_PHASE"] == "ingest":
            raise KeyboardInterrupt
        return real(cmd, cwd, env, *args, **kw)

    monkeypatch.setattr(episode, "run_process", interrupt_on_day_two)
    with pytest.raises(KeyboardInterrupt):
        run_world(adapter)
    rdir = r1(tmp_path)
    assert read_json(tmp_path / "run" / "run.json")["status"] == "interrupted"
    state = read_json(rdir / "state.json")
    assert state["status"] == "interrupted" and Path(state["workspace"]).is_dir()

    monkeypatch.setattr(episode, "run_process", real)
    assert run_world(adapter, resume=True) == 0
    assert agent_sessions() == [f"ingest {D1}", f"ingest {D2}", f"query {D2}", f"query {D2}"]
    assert seen(rdir / "sessions" / f"{D2}.ingest")["workspace"] == state["workspace"]
    assert seen(rdir / "sessions" / f"{D2}.ingest")["inbox"] == [D2]
    assert not Path(state["workspace"]).exists()
    assert read_json(tmp_path / "run" / "run.json")["status"] == "completed"


# ---------------------------------------------------------------- oracle-only and options
def test_skip_ingest_runs_only_oracle_queries(tmp_path, make_adapter, run_world, agent_sessions):
    assert run_world(make_adapter(), skip_ingest=True) == 0
    rdir = r1(tmp_path)
    assert agent_sessions() == [f"query {D2}"]
    assert sorted(p.name for p in (rdir / "sessions").iterdir()) == ["cp1.query-oracle"]
    assert sorted(p.name for p in (rdir / "answers").iterdir()) == ["cp1.oracle.json"]
    assert not (rdir / "snapshots").exists() and not (rdir / "workspace").exists()


def test_repeats_get_separate_directories(tmp_path, make_adapter, run_world):
    assert run_world(make_adapter(), repeats=2, oracle=False) == 0
    for k in (1, 2):
        assert (tmp_path / "run" / "fake" / f"r{k}" / "answers" / "cp1.json").is_file()
    assert read_json(tmp_path / "run" / "run.json")["worlds"][0]["repeats"] == 2


def test_default_workspace_is_in_system_temp(tmp_path, make_adapter, run_world):
    assert run_world(make_adapter(), workspace_root=None, max_days=1) == 0
    ws = Path(seen(r1(tmp_path) / "sessions" / f"{D1}.ingest")["workspace"])
    assert (
        ws.name.startswith("wcb-ws-")
        and ws.parent.resolve() == Path(tempfile.gettempdir()).resolve()
    )
    assert not ws.resolve().is_relative_to((tmp_path / "run").resolve()) and not ws.exists()


def test_unbuilt_world_is_rejected_with_a_fix(tmp_path, fake_world, make_adapter, run_world):
    import shutil

    shutil.rmtree(fake_world / "gold")
    with pytest.raises(FileNotFoundError, match="wcb world build") as e:
        run_world(make_adapter(), build=False)
    assert "gold/oracle-store/2027-01-05/" in str(e.value)
    assert not (tmp_path / "run").exists()


def test_unbuildable_world_fails_before_any_session(tmp_path, fake_world, make_adapter, run_world):
    import shutil

    shutil.rmtree(fake_world / "gold")  # and the fake world has no world.jsonl to build from
    with pytest.raises(ValueError, match="failed to build"):
        run_world(make_adapter())
    assert not (tmp_path / "run").exists()


def test_stale_world_is_rebuilt_before_running(tmp_path, make_adapter, run_world, mini_world_copy):
    from wcb.world.build import gold_status

    (mini_world_copy / "gold" / "BUILD.json").unlink()
    assert run_world(make_adapter(), world=mini_world_copy, max_days=1) == 0
    assert gold_status(mini_world_copy) is None


def test_missing_manifest_is_rejected(tmp_path, fake_world, make_adapter, run_world):
    (fake_world / "inbox" / D1 / "manifest.json").unlink()
    with pytest.raises(FileNotFoundError, match=f"inbox/{D1}/manifest.json"):
        run_world(make_adapter())


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"track": "B", "skip_ingest": True}, "Track A"),
        ({"skip_ingest": True, "oracle": False}, "nothing to run"),
        ({"repeats": 0}, "--repeats"),
        ({"max_days": 0}, "--max-days"),
    ],
)
def test_invalid_options(make_adapter, run_world, kw, message):
    with pytest.raises(ValueError, match=message):
        run_world(make_adapter(), **kw)


def test_workspace_root_inside_run_dir_is_rejected(tmp_path, make_adapter, run_world):
    with pytest.raises(ValueError, match="inside the run directory"):
        run_world(make_adapter(), workspace_root=tmp_path / "run" / "ws")


def test_world_must_be_given(tmp_path, make_adapter):
    cfg = RunConfig(
        adapter=make_adapter(), worlds=[], split=None, track="A", repeats=1, out=tmp_path / "o"
    )
    with pytest.raises(ValueError, match="--world"):
        run(cfg)
