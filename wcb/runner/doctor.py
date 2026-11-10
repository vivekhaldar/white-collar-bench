"""`wcb doctor`: smoke-test an adapter on the tiny mini world and explain what went wrong.

The doctor loads the adapter, checks that its commands and environment look runnable, then
plays the two-day mini world (2 ingestion and 2 query sessions; a seed session too in Track B)
without oracle sessions. It inspects every session, validates the stores and answer files, and
scores the run, printing a checklist with a hint for each problem. A full benchmark run uses the
same runner, so an adapter that passes here is wired up correctly.
"""

from __future__ import annotations

import os
import shlex
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from wcb.paths import repo_root
from wcb.util.io import read_json

OK, WARN, FAIL = "ok", "warn", "FAIL"


@dataclass
class Check:
    level: str  # ok | warn | FAIL
    text: str
    hint: str = ""

    def format(self) -> str:
        tag = {OK: "[ok]  ", WARN: "[warn]", FAIL: "[FAIL]"}[self.level]
        out = f"  {tag} {self.text}"
        if self.hint:
            out += "\n" + "\n".join(f"         {line}" for line in self.hint.splitlines())
        return out


@dataclass
class DoctorResult:
    checks: list[Check] = field(default_factory=list)
    run_dir: Path | None = None
    summary: str = ""

    @property
    def ok(self) -> bool:
        return all(c.level != FAIL for c in self.checks)

    def add(self, level: str, text: str, hint: str = "") -> None:
        self.checks.append(Check(level, text, hint))


def default_world() -> Path:
    """The mini fixture world shipped with the repository."""
    root = repo_root()
    if root is None or not (root / "tests" / "fixtures" / "mini-world" / "world.yaml").is_file():
        raise FileNotFoundError(
            "the mini world (tests/fixtures/mini-world) was not found; run wcb doctor from a "
            "checkout of the repository or pass --world"
        )
    return root / "tests" / "fixtures" / "mini-world"


def doctor(
    adapter_path: Path,
    *,
    world: str | Path | None = None,
    track: str = "A",
    out: Path | None = None,
    echo=print,
) -> DoctorResult:
    """Run the checks, printing progress with `echo`. Returns the collected checks."""
    from wcb.runner.adapter import AdapterError, load_adapter

    res = DoctorResult()
    try:
        adapter = load_adapter(Path(adapter_path))
    except (AdapterError, FileNotFoundError) as e:
        res.add(FAIL, f"adapter file {adapter_path} is invalid", str(e))
        return res
    echo(f"wcb doctor: adapter {adapter.name} {adapter.version} (model: {adapter.model})")
    res.add(OK, f"adapter file is valid: {adapter.path}")
    for w in adapter.warnings:
        res.add(WARN, w)
    for k in adapter.missing_passthrough():
        res.add(
            WARN,
            f"env_passthrough: {k} is not set here, so sessions will not get it",
            f"export {k}=... before running, or remove it from env_passthrough",
        )
    _check_commands(adapter, track, res)

    world_path = Path(world) if world is not None else default_world()
    run_dir = Path(out) if out is not None else Path(tempfile.mkdtemp(prefix="wcb-doctor-"))
    res.run_dir = run_dir
    for c in res.checks:
        echo(c.format())
    n = len(res.checks)
    echo(f"wcb doctor: running a track {track} episode on {world_path.name} into {run_dir}")

    from wcb.runner.episode import RunConfig, run

    cfg = RunConfig(
        adapter=adapter.path, worlds=[str(world_path)], split=None, track=track, repeats=1,
        out=run_dir, oracle=False,
    )
    try:
        run(cfg)
    except (ValueError, FileNotFoundError) as e:
        res.add(FAIL, "the runner refused to start", str(e))
        for c in res.checks[n:]:
            echo(c.format())
        return res

    ep = next((p for p in sorted(run_dir.glob("*/r1")) if p.is_dir()), None)
    if ep is None:
        res.add(FAIL, "the run produced no episode directory", f"look in {run_dir}")
    else:
        _check_sessions(ep, res)
        if track == "A":
            _check_stores(ep, res)
        _check_answers(ep, res)
        _score(run_dir, res)
    for c in res.checks[n:]:
        echo(c.format())
    return res


# ---------------------------------------------------------------- checks
def _check_commands(adapter, track: str, res: DoctorResult) -> None:
    phases = ["ingest", "query"] + (["seed"] if track == "B" and "seed" in adapter.phases else [])
    seen: set[str] = set()
    path = os.pathsep.join(
        [os.path.dirname(sys.executable or ""), os.environ.get("PATH", os.defpath)]
    )
    for phase in phases:
        if phase not in adapter.phases:
            continue
        spec = adapter.phases[phase]
        prog = _program(spec.cmd)
        if not prog or prog in seen:
            continue
        seen.add(prog)
        if "{" in prog:
            continue  # a placeholder; resolved per session
        if "/" in prog:
            p = Path(prog).expanduser()
            if not p.is_absolute():
                p = adapter.dir / p
            found = p.exists()
        else:
            found = shutil.which(prog, path=path) is not None
        if found:
            res.add(OK, f"{phase} command found: {prog}")
        else:
            res.add(
                FAIL, f"{phase} command not found: {prog}",
                "install it or put it on PATH; sessions get PATH from your environment, with "
                "the running Python's directory first",
            )


def _program(cmd: list[str] | str) -> str:
    """First word of a command, skipping VAR=value assignments in shell strings."""
    if isinstance(cmd, list):
        return cmd[0] if cmd else ""
    try:
        words = shlex.split(cmd)
    except ValueError:
        return ""
    for w in words:
        if "=" in w and not w.startswith(("/", ".")) and w.split("=", 1)[0].isidentifier():
            continue
        return w if w not in ("exec", "env") else ""
    return ""


def _check_sessions(ep: Path, res: DoctorResult) -> None:
    sessions = sorted(
        (ep / "sessions").glob("*/session.json"),
        key=lambda f: (str(read_json(f).get("started_at") or ""), f.parent.name),
    )
    if not sessions:
        res.add(FAIL, "no sessions ran", f"look in {ep}")
        return
    for f in sessions:
        s = read_json(f)
        name = f.parent.name
        wall = s.get("wall_s")
        took = f" in {wall:.1f}s" if isinstance(wall, (int, float)) else ""
        if s.get("status") == "ok":
            extra = ""
            ans = s.get("answers")
            if isinstance(ans, dict) and "questions" in ans:
                extra = f", answered {ans.get('answered', 0)}/{ans.get('questions')}"
            res.add(OK, f"session {name}: ok{took}{extra}")
            continue
        tail = _tail(f.parent / "stderr.log") or _tail(f.parent / "stdout.log")
        hint = f"logs: {f.parent}/stderr.log"
        if s.get("timed_out"):
            hint = f"raise timeout_s in the adapter (now {s.get('timeout_s')}s); " + hint
        notes = "; ".join(str(n) for n in s.get("notes") or [])
        if notes:
            hint += f"\nnotes: {notes}"
        if tail:
            hint += "\nlast stderr lines:\n" + tail
        res.add(FAIL, f"session {name}: {s.get('status')} (exit {s.get('exit_code')}){took}", hint)
    usage_seen = any(isinstance(read_json(f).get("usage"), dict) for f in sessions)
    if not usage_seen:
        res.add(
            WARN, "no session reported usage",
            "write <session_dir>/usage.json (docs/formats.md section 6) so runs report cost "
            "and tokens",
        )


def _check_stores(ep: Path, res: DoctorResult) -> None:
    from wcb.contract.validate import validate_store

    snaps = sorted(p for p in (ep / "snapshots").iterdir() if p.is_dir()) if (
        ep / "snapshots"
    ).is_dir() else []
    if not snaps:
        res.add(FAIL, "no store snapshots were taken", f"look in {ep}")
        return
    last = snaps[-1]
    issues = validate_store(last)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        shown = "\n".join(i.format() for i in errors[:8])
        more = f"\n... and {len(errors) - 8} more" if len(errors) > 8 else ""
        res.add(
            FAIL, f"final store ({last.name}) has {len(errors)} contract error(s)",
            f"{shown}{more}\nrerun: wcb validate store {last}",
        )
    else:
        res.add(OK, f"final store ({last.name}) passes the contract validator "
                    f"({len(issues)} warning(s))")
    changed = _changed_files(snaps[0], last)
    if changed:
        res.add(OK, f"ingestion changed {changed} store file(s) since the seed store")
    else:
        res.add(
            WARN, "ingestion did not change the store",
            "expected for the null baseline; otherwise check that your agent writes into the "
            "workspace it was given ({workspace} / $WCB_WORKSPACE)",
        )


def _changed_files(a: Path, b: Path) -> int:
    def files(root: Path) -> dict[str, bytes]:
        return {
            str(p.relative_to(root)): p.read_bytes()
            for p in root.rglob("*")
            if p.is_file() and ".git" not in p.relative_to(root).parts
        }

    fa, fb = files(a), files(b)
    return sum(1 for k in set(fa) | set(fb) if fa.get(k) != fb.get(k))


def _check_answers(ep: Path, res: DoctorResult) -> None:
    from wcb.contract.validate import validate_answers

    for qdir in sorted((ep / "sessions").glob("*.query")):
        cp = qdir.name.split(".")[0]
        ans = ep / "answers" / f"{cp}.json"
        if not ans.is_file():
            res.add(
                FAIL, f"{cp}: no answers file",
                "the query session must write .wcb/answers.json in the workspace",
            )
            continue
        questions = qdir / "questions.json"
        issues = validate_answers(ans, questions if questions.is_file() else None)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            res.add(
                FAIL, f"{cp}: answers file has {len(errors)} error(s)",
                "\n".join(i.format() for i in errors[:8])
                + f"\nrerun: wcb validate answers {ans} --questions {questions}",
            )
        else:
            res.add(OK, f"{cp}: answers file is valid")


def _score(run_dir: Path, res: DoctorResult) -> None:
    from wcb.grade.score import score_run

    try:
        report = score_run(run_dir)
    except Exception as e:  # report, do not crash the doctor
        res.add(FAIL, "scoring failed", f"{type(e).__name__}: {e}")
        return
    res.summary = report.summary_text()
    res.add(OK, "scored the run (heuristic judge); the null baseline gets 16.7 WCB on mini")


def _tail(path: Path, n: int = 6) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join("  " + line[:200] for line in lines[-n:])


def format_result(res: DoctorResult) -> str:
    lines = []
    if res.summary:
        lines.append(res.summary.strip())
    fails = sum(c.level == FAIL for c in res.checks)
    warns = sum(c.level == WARN for c in res.checks)
    verdict = "PASS" if res.ok else "FAIL"
    lines.append(f"wcb doctor: {verdict} ({fails} failure(s), {warns} warning(s))"
                 + (f"; run directory {res.run_dir}" if res.run_dir else ""))
    return "\n".join(lines)
