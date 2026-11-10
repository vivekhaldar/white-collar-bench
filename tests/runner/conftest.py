"""Fixtures for runner tests: a tiny built world and a scriptable fake agent.

The fake world has two seed dates, two episode days and one checkpoint on the last day::

    seed 2027-01-04, 2027-01-05 | episode 2027-01-06, 2027-01-07 | cp1 on 2027-01-07

The fake agent (``agent.py`` next to the adapter file) records what it saw in
``<session_dir>/fake_agent.json`` and appends ``<phase> <date>`` to a log file outside the
workspace, so tests can count sessions. ``FAKE_MODE`` selects a behaviour:

- ``normal``: ingest writes ``notes/<date>.md``; query answers every question.
- ``crash``: on ``FAKE_FAIL_DATE``, ingest writes ``notes/partial.md`` then exits 3.
- ``sleep``: on ``FAKE_FAIL_DATE``, ingest writes ``notes/partial.md``, starts a child process and
  sleeps past the timeout.
- ``modify_query``: query sessions try to edit, create and delete store files.
- ``bad_answers`` / ``no_answers``: query writes invalid JSON / nothing.
- ``symlink_answers``: query makes ``.wcb/answers.json`` a link to a file outside the workspace.
- ``escape``: on ``FAKE_FAIL_DATE``, ingest starts a daemon (double fork and ``setsid``) that
  records its PID in ``escaped.pid``, writes ``notes/late.md`` after ``FAKE_LATE_S`` seconds
  (default 1.5) and then sleeps. With ``FAKE_HANG`` set the agent then sleeps past its timeout;
  otherwise it exits 0 at once.
- ``vandal``: on ``FAKE_FAIL_DATE``, ingest does what ``FAKE_VANDAL`` says and exits 0: ``file``
  (``chmod 000 people/me.md``), ``dir`` (an unreadable ``notes/private/``), ``usage`` (an
  unreadable ``.wcb/usage.json``), ``wcbdir`` (an unreadable ``.wcb/``) or ``fifo`` (``inbox``
  and ``notes/pipe`` become FIFOs). ``answers`` makes ``.wcb/answers.json`` unreadable in queries.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from wcb.world.build import BUILD_STAMP, build_stamp

SEED_DATES = ["2027-01-04", "2027-01-05"]
DAYS = ["2027-01-06", "2027-01-07"]
SEED_END = SEED_DATES[-1]

FAKE_AGENT = r"""
import json, os, subprocess, sys, time
from pathlib import Path

ws = Path(os.environ["WCB_WORKSPACE"])
phase, date = os.environ["WCB_PHASE"], os.environ["WCB_DATE"]
mode = os.environ.get("FAKE_MODE", "normal")
failing = date == os.environ.get("FAKE_FAIL_DATE")
sd = Path(os.environ["WCB_SESSION_DIR"])
if os.environ.get("FAKE_LOG"):
    with open(os.environ["FAKE_LOG"], "a") as f:
        f.write(f"{phase} {date}\n")

def store_files():
    skip = {".git", ".wcb", "inbox"}
    return sorted(p.relative_to(ws).as_posix() for p in ws.rglob("*")
                  if p.is_file() and p.relative_to(ws).parts[0] not in skip)

info = {"argv": sys.argv, "cwd": os.getcwd(), "env": dict(os.environ), "workspace": str(ws),
        "pid": os.getpid(),
        "inbox": sorted(p.name for p in (ws / "inbox").iterdir()) if (ws / "inbox").is_dir() else [],
        "wcb_files": sorted(p.name for p in (ws / ".wcb").iterdir()) if (ws / ".wcb").is_dir() else [],
        "files": store_files()}
try:
    info["git_log"] = subprocess.run(["git", "log", "--format=%s"], cwd=ws, capture_output=True,
                                     text=True).stdout.splitlines()
except OSError:
    info["git_log"] = None

def save():
    (sd / "fake_agent.json").write_text(json.dumps(info, indent=1))

save()
(ws / ".wcb").mkdir(exist_ok=True)
(ws / ".wcb" / "usage.json").write_text(json.dumps(
    {"input_tokens": 11, "output_tokens": 7, "cost_usd": 0.01, "tool_calls": 3, "model": "fake"}))

if phase == "ingest":
    (ws / "notes").mkdir(exist_ok=True)
    (ws / "notes" / f"{date}.md").write_text("inbox: " + ", ".join(info["inbox"]) + "\n")
    if mode == "crash" and failing:
        (ws / "notes" / "partial.md").write_text("half done\n")
        sys.exit(3)
    if mode == "sleep" and failing:
        (ws / "notes" / "partial.md").write_text("half done\n")
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        (sd / "child.pid").write_text(str(child.pid))
        time.sleep(120)
    if mode == "escape" and failing:
        pid_file = sd / "escaped.pid"
        if os.fork() == 0:
            os.setsid()
            if os.fork() == 0:  # the daemon: in its own session, re-parented once its parent exits
                (sd / "escaped.tmp").write_text(str(os.getpid()))
                os.rename(sd / "escaped.tmp", pid_file)
                time.sleep(float(os.environ.get("FAKE_LATE_S", "1.5")))
                (ws / "notes" / "late.md").write_text("written after the session\n")
                time.sleep(60)
            os._exit(0)
        os.wait()
        while not pid_file.exists():
            time.sleep(0.01)
        if os.environ.get("FAKE_HANG"):
            time.sleep(120)
    if mode == "vandal" and failing:
        what = os.environ["FAKE_VANDAL"]
        if what == "file":
            os.chmod(ws / "people" / "me.md", 0)
        elif what == "dir":
            (ws / "notes" / "private").mkdir()
            (ws / "notes" / "private" / "secret.md").write_text("hidden\n")
            os.chmod(ws / "notes" / "private", 0)
        elif what == "usage":
            os.chmod(ws / ".wcb" / "usage.json", 0)
        elif what == "wcbdir":
            os.chmod(ws / ".wcb", 0)
        elif what == "fifo":
            import shutil
            shutil.rmtree(ws / "inbox")
            os.mkfifo(ws / "inbox")
            os.mkfifo(ws / "notes" / "pipe")
    sys.exit(0)

questions = json.loads((ws / ".wcb" / "questions.json").read_text())
if mode == "modify_query":
    attempts = {}
    try:
        with open(ws / "people" / "me.md", "a") as f:
            f.write("tampered\n")
        attempts["edit"] = "ok"
    except PermissionError:
        attempts["edit"] = "PermissionError"
    (ws / "notes").mkdir(exist_ok=True)
    (ws / "notes" / "hack.md").write_text("should be discarded\n")
    if (ws / "CONTRACT.md").exists():
        (ws / "CONTRACT.md").unlink()
    attempts["created"] = (ws / "notes" / "hack.md").exists()
    info["attempts"] = attempts
    save()
if mode == "no_answers":
    sys.exit(0)
if mode == "symlink_answers":
    outside = sd / "outside.json"
    outside.write_text(json.dumps({q["id"]: {"type": q["type"], "abstain": True}
                                   for q in questions["questions"]}))
    os.symlink(outside, ws / ".wcb" / "answers.json")
    sys.exit(0)
if mode == "bad_answers":
    (ws / ".wcb" / "answers.json").write_text("{not json")
    sys.exit(0)
answers = {q["id"]: {"type": q["type"], "abstain": True, "store_files": info["files"]}
           for q in questions["questions"]}
(ws / ".wcb" / "answers.json").write_text(json.dumps(answers))
if mode == "vandal" and os.environ.get("FAKE_VANDAL") == "answers":
    os.chmod(ws / ".wcb" / "answers.json", 0)
"""


def build_world(d: Path, checkpoints: list[dict] | None = None) -> Path:
    """Write a small but complete *built* world (manifests, oracle stores, gold questions)."""
    checkpoints = checkpoints or [{"id": "cp1", "date": DAYS[-1], "label": "end of episode"}]
    d.mkdir(parents=True)
    meta = {
        "id": "fake",
        "title": "Fake runner-test world",
        "version": 1,
        "split": "fixture",
        "worker": "p-ivy-lund",
        "timezone": "-08:00",
        "seed": {"start": SEED_DATES[0], "end": SEED_END},
        "episode": {"days": DAYS},
        "checkpoints": checkpoints,
        "generator": {"kind": "hand-authored"},
    }
    (d / "world.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    for i, date in enumerate(SEED_DATES + DAYS, 1):
        inbox = d / "inbox" / date
        inbox.mkdir(parents=True)
        aid = f"nt-{i:04d}"
        (inbox / f"{aid}.md").write_text(f"# Note for {date}\n\nCall ivy.lund@kestrel.example.\n")
        manifest = {
            "date": date,
            "artifacts": [
                {
                    "id": aid,
                    "channel": "note",
                    "received_at": f"{date}T09:00:00-08:00",
                    "path": f"{aid}.md",
                    "title": f"Note {i}",
                }
            ],
        }
        (inbox / "manifest.json").write_text(json.dumps(manifest))
    me = "---\nid: people/me\ntype: person\nname: Ivy Lund\naliases: [Ivy]\nupdated: {d}\n---\n"
    for date in [SEED_END, *DAYS]:
        store = d / "gold" / "oracle-store" / date
        (store / "people").mkdir(parents=True)
        (store / "people" / "me.md").write_text(me.format(d=date))
    marker = d / "gold" / "oracle-store" / DAYS[-1] / "projects" / "oracle-marker.md"
    marker.parent.mkdir(parents=True)
    marker.write_text("only in the oracle store\n")
    for cp in checkpoints:
        questions = {
            "world": "fake",
            "checkpoint": cp["id"],
            "date": cp["date"],
            "questions": [
                {
                    "id": f"{cp['id']}-q1",
                    "type": "point",
                    "template": "project_attr",
                    "params": {"project": "pr-kite", "attribute": "owner"},
                    "text": "Who owns Kite?",
                    "answerable": True,
                    "challenges": ["alias"],
                    "support": ["nt-0001"],
                    "gold": {
                        "kind": "entity",
                        "value": "Ivy Lund",
                        "entity": "p-ivy-lund",
                        "accept": [],
                    },
                },
                {
                    "id": f"{cp['id']}-q2",
                    "type": "list",
                    "template": "i_owe",
                    "params": {"person": "p-ola-berg"},
                    "text": "What do I currently owe Ola?",
                    "answerable": False,
                    "challenges": ["unobservable"],
                    "support": [],
                    "gold": {},
                },
            ],
        }
        f = d / "gold" / "questions" / f"{cp['id']}.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(questions))
    # Mark the hand-made gold as current so `wcb run` does not try to rebuild it.
    (d / "gold" / BUILD_STAMP).write_text(json.dumps(build_stamp(d)))
    return d


@pytest.fixture
def fake_world(tmp_path: Path) -> Path:
    return build_world(tmp_path / "worlds" / "fake")


@pytest.fixture
def agent_log(tmp_path: Path) -> Path:
    """File the fake agent appends '<phase> <date>' to, once per session."""
    return tmp_path / "agent.log"


@pytest.fixture
def make_adapter(tmp_path: Path, agent_log: Path):
    """Write the fake agent and an adapter file for it; returns the adapter path."""

    def make(
        *,
        mode: str = "normal",
        fail_date: str | None = None,
        ingest_timeout: float = 30,
        query_timeout: float = 30,
        cmd: list[str] | str | None = None,
        directory: Path | None = None,
        extra: dict | None = None,
        env_extra: dict | None = None,
    ) -> Path:
        adir = directory or tmp_path / "adapter"
        adir.mkdir(parents=True, exist_ok=True)
        (adir / "agent.py").write_text(FAKE_AGENT)
        env = {"FAKE_MODE": mode, "FAKE_LOG": str(agent_log), "LITERAL": "day-{date}"}
        if fail_date:
            env["FAKE_FAIL_DATE"] = fail_date
        env.update(env_extra or {})
        data = {
            "name": "fake-agent",
            "version": "1.0.0",
            "model": "test/fake-model",
            "cmd": cmd
            or [
                sys.executable,
                "{adapter_dir}/agent.py",
                "--workspace",
                "{workspace}",
                "--prompt",
                "{prompt}",
                "--date",
                "{date}",
                "--phase",
                "{phase}",
                "--track",
                "{track}",
                "--session-dir",
                "{session_dir}",
            ],
            "ingest": {"timeout_s": ingest_timeout},
            "query": {"timeout_s": query_timeout},
            "env": env,
            "env_passthrough": ["WCB_TEST_PASSTHROUGH"],
            **(extra or {}),
        }
        path = adir / "adapter.yaml"
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        return path

    return make


def read_log(path: Path) -> list[str]:
    return path.read_text().splitlines() if path.exists() else []


@pytest.fixture
def agent_sessions(agent_log: Path):
    """Callable returning the '<phase> <date>' lines the fake agent logged so far."""
    return lambda: read_log(agent_log)
