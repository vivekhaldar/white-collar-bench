"""Episode runner: ``wcb run`` (docs/scoring.md "Episode protocol", docs/formats.md sections 5-6).

For every world and repeat the runner plays one episode:

1. **Start.** Track A: the workspace is a copy of the world's seed oracle store
   (``gold/oracle-store/<seed_end>/``) plus ``CONTRACT.md``. Track B: an empty workspace plus
   ``GOALS.md``, then one *seed ingestion session* that receives every seed date's inbox at once.
2. **Each episode day.** The day's inbox is placed at ``inbox/<date>/`` and the adapter's ingest
   command runs in a fresh process. Afterwards every process the session started is killed,
   permissions in the workspace are restored and special files deleted (``normalize_tree``), and
   ``inbox/`` and ``.wcb/`` are removed. If the session failed (non-zero exit, timeout, or a store
   the runner cannot copy) the store is restored to its state before the session. The store is
   then snapshotted to ``snapshots/<date>/`` and committed to the workspace's git history. Before
   the next session, a workspace that no longer matches that snapshot is reverted to it.
3. **Checkpoints.** After a checkpoint day's ingestion, a query session runs on a throwaway,
   read-only copy of the store with ``.wcb/questions.json`` and ``.wcb/answer-schema.json``. The
   answers are kept; every change to the copy is discarded.
4. **Oracle sessions (Track A).** After the episode, each checkpoint's questions are asked again
   against the world's oracle store for that date, to measure synthesis alone.

Workspaces live outside the run directory and the repository (system temp by default), so an
agent that explores ``..`` finds neither gold nor earlier results. At the end of an episode the
final store is copied to ``<run>/<world>/r<k>/workspace/`` and the temporary workspace is deleted.

Everything an agent sees is the workspace, the prompt and the environment variables documented
in docs/formats.md section 5. See docs/running.md for the competitor-facing guide.
"""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from wcb import __version__
from wcb.meter import MeterProxy, summarize
from wcb.paths import contract_dir, repo_root, resolve_split, resolve_world
from wcb.runner import prompts
from wcb.runner.adapter import Adapter, load_adapter
from wcb.runner.workspace import (
    QUERY_PREFIX,
    SNAPSHOT_EXCLUDE,
    WORKSPACE_PREFIX,
    Git,
    copy_tree,
    is_within,
    make_read_only,
    new_temp_dir,
    normalize_tree,
    remove_tree,
    restore,
    snapshot,
    tree_changes,
    tree_diff,
    tree_files,
)
from wcb.util.dates import DATE_RE
from wcb.util.io import read_json, write_json
from wcb.world.build import BUILD_STAMP, ensure_built
from wcb.world.model import World

KILL_GRACE_S = 10.0
"""Seconds between SIGTERM and SIGKILL when a session times out."""

INTERRUPT_GRACE_S = 2.0
"""Seconds between SIGTERM and SIGKILL when the runner itself is interrupted."""

MAX_ANSWERS_BYTES = 20_000_000
MAX_USAGE_BYTES = 1_000_000


@dataclass
class RunConfig:
    """Options for one ``wcb run`` invocation (built by wcb/cli.py from the command line)."""

    adapter: Path  # adapter YAML file
    worlds: list[str]  # world names (e.g. 'pilot', 'dev/w01') or paths
    split: str | None  # run every world in this split, e.g. 'dev'
    track: str  # 'A' or 'B'
    repeats: int  # independent episodes per world: r1, r2, ...
    out: Path  # run directory
    oracle: bool = True  # Track A: also query the oracle store at each checkpoint
    max_days: int | None = None  # stop after this many episode days
    workspace_root: Path | None = None  # where temporary workspaces go (default: system temp)
    resume: bool = False  # skip sessions that completed in an earlier invocation
    skip_ingest: bool = False  # run only oracle query sessions
    meter: bool = False  # route model calls through the metering proxy (wcb/meter.py)
    meter_bind: str = "127.0.0.1"  # address the proxy listens on
    meter_host: str | None = None  # address sessions use to reach it (default: meter_bind)
    build: bool = True  # build worlds whose gold is missing or stale (wcb world build)


# ====================================================================== entry point
def run(cfg: RunConfig) -> int:
    """Run an adapter over the configured worlds. Returns the process exit code.

    The return value is 0 when the run completed, even if some agent sessions failed or timed
    out: those are part of the result and are recorded in each ``session.json``. Problems with
    the configuration (invalid adapter, unbuilt world, non-empty output directory) raise
    ``ValueError`` or ``FileNotFoundError`` with a message that says how to fix them.
    """
    t0 = time.monotonic()
    _validate_options(cfg)
    oracle = bool(cfg.oracle) and cfg.track == "A"
    adapter = load_adapter(Path(cfg.adapter))
    plans = _plan_worlds(cfg)
    for plan in plans:
        if cfg.build:
            ensure_built(plan.dir, echo=lambda m: _log(f"wcb run: {m}"))
        _check_built(plan, cfg.track, agent=not cfg.skip_ingest, oracle=oracle)
    out = Path(cfg.out).expanduser().resolve()
    ws_root = _check_workspace_root(cfg.workspace_root, out, plans)

    _log(
        f"wcb run: adapter {adapter.name} {adapter.version} (model: {adapter.model}) "
        f"from {adapter.path}"
    )
    mode = (
        "oracle-only (--skip-ingest)" if cfg.skip_ingest else f"oracle {'on' if oracle else 'off'}"
    )
    _log(
        f"wcb run: track {cfg.track}, {mode}, {len(plans)} world(s) x {cfg.repeats} repeat(s) "
        f"-> {out}"
    )
    meta = _start_run_json(out, cfg, adapter, plans, oracle)
    for w in adapter.warnings:
        _warn(w)
    for k in adapter.missing_passthrough():
        _warn(f"env_passthrough: {k} is not set in your environment, so sessions will not get it")
    if cfg.track == "B" and cfg.oracle and not cfg.skip_ingest:
        _log("wcb run: Track B has no oracle store; oracle sessions are skipped")
    if shutil.which("git") is None and not cfg.skip_ingest:
        _warn("git is not installed; workspaces will have no git history (snapshots still work)")

    ctx = _Context(cfg=cfg, adapter=adapter, out=out, ws_root=ws_root, oracle=oracle)
    if cfg.meter:
        ctx.meter = MeterProxy(out / "meter.jsonl", host=cfg.meter_bind).start()
        _log(
            f"wcb run: metering model calls via http://{cfg.meter_host or cfg.meter_bind}:"
            f"{ctx.meter.port} (log: {ctx.meter.log_path}); upstreams: "
            + ", ".join(f"{k} -> {v}" for k, v in sorted(ctx.meter.upstreams.items()))
        )
    status = "error"
    try:
        with _sigterm_as_interrupt():
            for plan in plans:
                for k in range(1, cfg.repeats + 1):
                    _Episode(ctx, plan, k).run()
        status = "completed"
    except KeyboardInterrupt:
        status = "interrupted"
        _log("wcb run: interrupted; continue later with the same command plus --resume")
        raise
    finally:
        if ctx.meter is not None:
            ctx.meter.stop()
        meta["status"] = status
        meta["finished_at"] = _now()
        write_json(out / "run.json", meta)

    c = ctx.counts
    ran = c["ok"] + c["failed"] + c["timeout"] + c["error"]
    _log(
        f"wcb run: finished in {time.monotonic() - t0:.1f}s: {ran} session(s) "
        f"({c['ok']} ok, {c['failed']} failed, {c['timeout']} timed out, {c['error']} could not "
        f"start), {c['skipped']} skipped"
    )
    _log(f"wcb run: results in {out}; next: wcb score {shlex.quote(str(out))}")
    return 0


# ====================================================================== setup
def _validate_options(cfg: RunConfig) -> None:
    if cfg.track not in ("A", "B"):
        raise ValueError(f"unknown track {cfg.track!r}; use --track A or --track B")
    if cfg.repeats < 1:
        raise ValueError("--repeats must be at least 1")
    if cfg.max_days is not None and cfg.max_days < 1:
        raise ValueError("--max-days must be at least 1")
    if cfg.skip_ingest and cfg.track != "A":
        raise ValueError(
            "--skip-ingest runs only oracle-store query sessions, which exist only in Track A"
        )
    if cfg.skip_ingest and not cfg.oracle:
        raise ValueError("--skip-ingest together with --no-oracle leaves nothing to run")


@dataclass
class _WorldPlan:
    """A world and the part of its episode this run covers."""

    dir: Path
    world: World
    days: list[str]  # episode days to play, in order (after --max-days)
    checkpoints: list[dict[str, Any]]  # checkpoints whose date is in `days`
    seed_dates: list[str]  # inbox directories dated within the seed window

    @property
    def id(self) -> str:
        return self.world.id

    def inbox(self, date: str) -> Path:
        return self.dir / "inbox" / date

    def oracle_store(self, date: str) -> Path:
        return self.dir / "gold" / "oracle-store" / date

    def questions_file(self, cp_id: str) -> Path:
        return self.dir / "gold" / "questions" / f"{cp_id}.json"


def _plan_worlds(cfg: RunConfig) -> list[_WorldPlan]:
    paths: list[Path] = [resolve_world(s) for s in (cfg.worlds or [])]
    if cfg.split:
        found = resolve_split(cfg.split)
        if not found:
            raise FileNotFoundError(
                f"no worlds found in split {cfg.split!r} (looked for worlds/{cfg.split}/*/world.yaml); "
                "list available worlds with 'wcb world list'"
            )
        paths += found
    if not paths:
        raise ValueError(
            "no worlds to run: pass --world <name or path> (repeatable) or --split <split>"
        )
    unique = list(dict.fromkeys(p.resolve() for p in paths))

    plans: list[_WorldPlan] = []
    seen: dict[str, Path] = {}
    for d in unique:
        try:
            world = World.load(d)
            seed_start, seed_end = world.seed_start, world.seed_end
        except (KeyError, TypeError) as e:
            raise ValueError(
                f"{d}/world.yaml: missing or malformed field {e}; see docs/formats.md §1.1"
            ) from e
        if world.id in seen:
            raise ValueError(
                f"two worlds share the id {world.id!r} ({seen[world.id]} and {d}); "
                "their results would collide in the run directory"
            )
        seen[world.id] = d
        all_days = world.episode_days()
        if not all_days:
            raise ValueError(f"{d}/world.yaml: episode.days is empty; nothing to run")
        days = all_days[: cfg.max_days] if cfg.max_days else all_days
        checkpoints = []
        for cp in world.checkpoints():
            if cp["date"] not in all_days:
                raise ValueError(
                    f"{d}/world.yaml: checkpoint {cp['id']} is dated {cp['date']}, which is not an "
                    f"episode day; run 'wcb world check {d}'"
                )
            if cp["date"] in days:
                checkpoints.append(cp)
        inbox = d / "inbox"
        dated = (
            sorted(p.name for p in inbox.iterdir() if p.is_dir() and DATE_RE.match(p.name))
            if inbox.is_dir()
            else []
        )
        seed_dates = [x for x in dated if seed_start <= x <= seed_end]
        stray = [x for x in dated if x not in seed_dates and x not in all_days]
        if stray:
            _warn(
                f"world {world.id}: inbox dates {', '.join(stray)} are neither seed dates nor "
                "episode days and are never delivered"
            )
        plans.append(_WorldPlan(d, world, days, checkpoints, seed_dates))
    return plans


def _check_built(plan: _WorldPlan, track: str, *, agent: bool, oracle: bool) -> None:
    """Fail early, with a fix, if the files a run needs have not been built."""
    missing: list[str] = []

    def need_dir(p: Path) -> None:
        if not p.is_dir():
            missing.append(str(p.relative_to(plan.dir)) + "/")

    def need_file(p: Path) -> None:
        if not p.is_file():
            missing.append(str(p.relative_to(plan.dir)))

    seed_end = plan.world.seed_end
    if agent and track == "A":
        need_dir(plan.oracle_store(seed_end))
    if agent:
        # An episode day with no inbox directory at all is delivered as an empty inbox.
        for d in plan.days:
            if plan.inbox(d).is_dir():
                need_file(plan.inbox(d) / "manifest.json")
        if track == "B":
            for d in plan.seed_dates:
                need_file(plan.inbox(d) / "manifest.json")
    for cp in plan.checkpoints:
        need_file(plan.questions_file(cp["id"]))
        if oracle:
            need_dir(plan.oracle_store(cp["date"]))
    if missing:
        shown = "\n".join(f"  - {m}" for m in missing[:10])
        more = f"\n  - ... and {len(missing) - 10} more" if len(missing) > 10 else ""
        raise FileNotFoundError(
            f"world {plan.id} ({plan.dir}) is not built; missing:\n{shown}{more}\n"
            f"Build it first with: wcb world build {shlex.quote(str(plan.dir))}"
        )
    for cp in plan.checkpoints:
        _visible_questions(plan, cp)  # validates the file's shape


def _visible_questions(plan: _WorldPlan, cp: dict[str, Any]) -> dict[str, Any]:
    """The agent-visible questions for a checkpoint (docs/formats.md §3.4): id, type, text only."""
    f = plan.questions_file(cp["id"])
    try:
        data = read_json(f)
        qs = [
            {"id": str(q["id"]), "type": str(q["type"]), "text": str(q["text"])}
            for q in data["questions"]
        ]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(
            f"{f} is malformed ({type(e).__name__}: {e}); rebuild it with "
            f"'wcb world build {plan.dir}'"
        ) from e
    return {"date": cp["date"], "questions": qs}


def _check_workspace_root(root: Path | None, out: Path, plans: list[_WorldPlan]) -> Path | None:
    """Refuse workspace locations from which an agent could reach results or gold."""
    base = Path(root).expanduser().resolve() if root else Path(tempfile.gettempdir()).resolve()
    if is_within(base, out):
        raise ValueError(
            f"workspace root {base} is inside the run directory {out}; agents could read earlier "
            "answers and snapshots. Use a directory outside it (the default is the system temp dir)."
        )
    for plan in plans:
        if is_within(base, plan.dir):
            raise ValueError(
                f"workspace root {base} is inside world {plan.id} ({plan.dir}); agents could read "
                "gold. Use a directory outside the world."
            )
    repo = repo_root()
    if repo is not None and is_within(base, repo):
        _warn(
            f"workspaces will be created inside the repository ({base}); an agent exploring "
            "parent directories could find worlds/ and gold. Prefer a directory outside it."
        )
    return base if root else None


def _start_run_json(
    out: Path, cfg: RunConfig, adapter: Adapter, plans: list[_WorldPlan], oracle: bool
) -> dict[str, Any]:
    run_file = out / "run.json"
    worlds = [
        {"id": p.id, "path": str(p.dir), "repeats": cfg.repeats, "gold": _gold_stamp(p.dir)}
        for p in plans
    ]
    if cfg.resume and run_file.is_file():
        old = read_json(run_file)
        if old.get("track") != cfg.track:
            raise ValueError(
                f"{out} holds a Track {old.get('track')} run; it cannot be resumed as Track "
                f"{cfg.track}. Use the original --track or a new --out."
            )
        old_adapter = old.get("adapter") or {}
        if old_adapter.get("name") != adapter.name:
            raise ValueError(
                f"{out} was run with adapter {old_adapter.get('name')!r}, not {adapter.name!r}; "
                "resume with the same adapter or use a new --out"
            )
        if old_adapter.get("sha256") != adapter.sha256:
            _warn(
                "the adapter file changed since this run started; new sessions use the new version"
            )
        merged = {w["id"]: dict(w) for w in old.get("worlds", [])}
        for w in worlds:
            prev = merged.get(w["id"])
            merged[w["id"]] = {**w, "repeats": max(w["repeats"], prev["repeats"])} if prev else w
        meta = {
            **old,
            "adapter": adapter.describe(),
            "oracle": bool(old.get("oracle")) or oracle,
            "worlds": list(merged.values()),
            "finished_at": None,
            "status": "running",
            "options": _merge_options(old.get("options") or {}, _options(cfg)),
            "resumed_at": [*old.get("resumed_at", []), _now()],
            "resumed_with": [
                *old.get("resumed_with", []),
                {"command_line": shlex.join(sys.argv), "options": _options(cfg)},
            ],
        }
    else:
        if cfg.resume:
            _warn(f"--resume: no run.json in {out}; starting a new run")
        elif out.exists() and any(out.iterdir()):
            raise ValueError(
                f"output directory {out} is not empty; pass --resume to continue the run in it, "
                "or choose a new --out"
            )
        meta = {
            "wcb_version": __version__,
            "adapter": adapter.describe(),
            "track": cfg.track,
            "oracle": oracle,
            "worlds": worlds,
            "started_at": _now(),
            "finished_at": None,
            "status": "running",
            "command_line": shlex.join(sys.argv),
            "options": _options(cfg),
        }
    out.mkdir(parents=True, exist_ok=True)
    write_json(run_file, meta)
    return meta


def _options(cfg: RunConfig) -> dict[str, Any]:
    """The ``options`` block of run.json for one invocation."""
    return {
        "max_days": cfg.max_days,
        "skip_ingest": cfg.skip_ingest,
        "workspace_root": str(cfg.workspace_root) if cfg.workspace_root else None,
        "meter": cfg.meter,
    }


def _merge_options(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """The run-wide ``options`` after a resume: what every invocation together has covered.

    The scorer reads ``max_days`` and ``skip_ingest`` to decide what to score, so a resume that
    extends a run must extend them too: ``max_days`` is unlimited (``None``) if any invocation
    was, otherwise the largest; ``skip_ingest`` stays true only if every invocation skipped
    ingestion; ``meter`` is true if any invocation metered. Each invocation's own options are
    kept in ``resumed_with``.
    """
    days = [old.get("max_days", None), new.get("max_days")]
    return {
        **old,
        **new,
        "max_days": None if None in days else max(int(d) for d in days),
        "skip_ingest": bool(old.get("skip_ingest")) and bool(new.get("skip_ingest")),
        "meter": bool(old.get("meter")) or bool(new.get("meter")),
    }


def _gold_stamp(world_dir: Path) -> dict[str, Any] | None:
    """The world's gold/BUILD.json, so run.json records which gold the run was made against."""
    stamp = world_dir / "gold" / BUILD_STAMP
    return read_json(stamp) if stamp.is_file() else None


# ====================================================================== episodes
@dataclass
class _Context:
    cfg: RunConfig
    adapter: Adapter
    out: Path
    ws_root: Path | None
    oracle: bool
    counts: Counter = field(default_factory=Counter)
    meter: MeterProxy | None = None


class _Episode:
    """One world played once by the agent: ``<run>/<world>/r<k>/``.

    The episode moves through *steps* (initial store, seed session, ingest days, queries). With
    ``--resume``, the longest prefix of steps that completed earlier is skipped. From the first
    step that has to run, every later agent step runs again, because it depends on the store.
    """

    def __init__(self, ctx: _Context, plan: _WorldPlan, k: int):
        self.ctx = ctx
        self.plan = plan
        self.k = k
        self.track = ctx.cfg.track
        self.dir = ctx.out / plan.id / f"r{k}"
        self.tag = f"[{plan.id} r{k}]"
        self.ws: Path | None = None  # live workspace, in sync with self.current
        self.git: Git | None = None
        self.current: Path | None = None  # snapshot holding the current store
        self.rerun = not ctx.cfg.resume  # once True, every later agent step runs
        self.state: dict[str, Any] = {}
        self._git_warned = False
        self.meter_tag: str | None = None  # tag of the running session's metered calls

    # ------------------------------------------------------------ paths
    def snap(self, date: str) -> Path:
        return self.dir / "snapshots" / date

    def session_dir(self, name: str) -> Path:
        return self.dir / "sessions" / name

    def answers_file(self, cp_id: str, oracle: bool) -> Path:
        return self.dir / "answers" / (f"{cp_id}.oracle.json" if oracle else f"{cp_id}.json")

    # ------------------------------------------------------------ driver
    def run(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.ctx.cfg.skip_ingest:
            self._load_state()
            try:
                self._agent_episode()
            except BaseException:
                if self.ws is not None:
                    self._save_state("interrupted")
                    _log(f"{self.tag} workspace kept at {self.ws} for --resume")
                raise
            self._finish()
        if self.ctx.oracle:
            for cp in self.plan.checkpoints:
                sd = self.session_dir(f"{cp['id']}.query-oracle")
                if (
                    self.ctx.cfg.resume
                    and _session_finished(sd)
                    and self.answers_file(cp["id"], True).is_file()
                ):
                    self._skip(f"{cp['id']} query-oracle")
                else:
                    self._query(cp, oracle=True)

    def _agent_episode(self) -> None:
        plan = self.plan
        seed_end = plan.world.seed_end
        if self.track == "A":
            if not self.rerun and self.snap(seed_end).is_dir():
                self.current = self.snap(seed_end)
                self._skip("seed store")
            else:
                self.rerun = True
                self._new_workspace()
                copy_tree(plan.oracle_store(seed_end), self.ws, exclude=SNAPSHOT_EXCLUDE)
                shutil.copyfile(contract_dir() / "CONTRACT.md", self.ws / "CONTRACT.md")
                self._commit("wcb: seed store")
                self._snapshot(seed_end)
                _log(
                    f"{self.tag} seed store {seed_end}: {len(tree_files(self.ws))} files in "
                    f"workspace {self.ws}"
                )
        else:
            sd = self.session_dir("seed.ingest")
            seed_done = not plan.seed_dates or _ingest_completed(sd)
            if not self.rerun and seed_done and self.snap(seed_end).is_dir():
                self.current = self.snap(seed_end)
                self._skip("seed ingest")
            else:
                self.rerun = True
                self._new_workspace()
                shutil.copyfile(contract_dir() / "GOALS-TRACK-B.md", self.ws / "GOALS.md")
                self._commit("wcb: initial workspace")
                self._snapshot(seed_end)  # the pre-seed state, restored if the seed session fails
                _log(f"{self.tag} empty workspace {self.ws} with GOALS.md")
                if plan.seed_dates:
                    self._ingest(
                        seed_end,
                        "seed.ingest",
                        plan.seed_dates,
                        prompts.seed_prompt(seed_end, plan.seed_dates),
                        label=f"seed ingest ({len(plan.seed_dates)} dates)",
                        seed=True,
                    )
                else:
                    _warn(f"world {plan.id} has no seed inbox directories; no seed session")

        by_date: dict[str, list[dict[str, Any]]] = {}
        for cp in plan.checkpoints:
            by_date.setdefault(cp["date"], []).append(cp)
        for d in plan.days:
            if (
                not self.rerun
                and _ingest_completed(self.session_dir(f"{d}.ingest"))
                and self.snap(d).is_dir()
            ):
                self.current = self.snap(d)
                self._skip(f"{d} ingest")
            else:
                self.rerun = True
                self._ensure_workspace()
                self._ingest(
                    d, f"{d}.ingest", [d], prompts.ingest_prompt(self.track, d), label=f"{d} ingest"
                )
            for cp in by_date.get(d, []):
                done = _session_finished(self.session_dir(f"{cp['id']}.query"))
                if not self.rerun and done and self.answers_file(cp["id"], False).is_file():
                    self._skip(f"{cp['id']} query")
                else:
                    self._ensure_workspace()
                    self._query(cp, oracle=False)

    def _finish(self) -> None:
        """Copy the final store to <run>/<world>/r<k>/workspace/ and delete the temp workspace."""
        final = self.dir / "workspace"
        if self.current is not None and (self.ws is not None or not final.is_dir()):
            snapshot(self.current, final)  # the final store is the last snapshot
        if self.ws is not None:
            try:
                remove_tree(self.ws)
            except OSError as e:
                _warn(f"{self.tag} could not delete workspace {self.ws}: {e}")
            self.ws = None
        self._save_state("done")

    # ------------------------------------------------------------ workspace
    def _new_workspace(self) -> None:
        old = self.state.get("workspace")
        if old and Path(old).is_dir() and Path(old).name.startswith(WORKSPACE_PREFIX):
            try:
                remove_tree(Path(old))  # left over from an interrupted attempt
            except OSError as e:
                _warn(f"{self.tag} could not delete the old workspace {old}: {e}")
        self.ws = new_temp_dir(self.ctx.ws_root, WORKSPACE_PREFIX)
        self.git = Git(self.ws)
        self.git.init()
        self._save_state("running")

    def _ensure_workspace(self) -> None:
        """Make sure a live workspace holds the current store (only needed after --resume)."""
        if self.ws is not None:
            return
        assert self.current is not None, "no snapshot to rebuild the workspace from"
        old = self.state.get("workspace")
        if old and Path(old).is_dir():
            try:
                normalize_tree(Path(old))
                restore(Path(old), self.current)
            except OSError as e:
                _warn(f"{self.tag} cannot reuse workspace {old} ({e}); rebuilding it")
                old = None
        if old and Path(old).is_dir():
            self.ws = Path(old)
            self.git = Git(self.ws)
            self.git.init()
            self._commit(f"wcb: resumed from snapshot {self.current.name}")
            _log(
                f"{self.tag} resuming in workspace {self.ws} (store from snapshots/{self.current.name})"
            )
        else:
            self.ws = new_temp_dir(self.ctx.ws_root, WORKSPACE_PREFIX)
            self.git = Git(self.ws)
            self.git.init()
            copy_tree(self.current, self.ws)
            self._commit(f"wcb: rebuilt from snapshot {self.current.name}")
            _log(f"{self.tag} rebuilt workspace {self.ws} from snapshots/{self.current.name}")
        self._save_state("running")

    def _snapshot(self, date: str) -> None:
        assert self.ws is not None
        snapshot(self.ws, self.snap(date))
        self.current = self.snap(date)

    def _reset_workspace(self, notes: list[str]) -> None:
        """Put the current snapshot back into the workspace. If the workspace cannot be cleaned
        (an agent left files the runner may not delete), continue in a new one."""
        assert self.ws is not None and self.current is not None
        try:
            normalize_tree(self.ws)
            restore(self.ws, self.current)
            return
        except OSError as e:
            error = f"{type(e).__name__}: {e}"
        old, self.ws = self.ws, new_temp_dir(self.ctx.ws_root, WORKSPACE_PREFIX)
        msg = (
            f"workspace {old} could not be cleaned ({error}); continuing in {self.ws}, rebuilt "
            f"from snapshots/{self.current.name} (git history is not carried over; delete the "
            "old directory by hand)"
        )
        notes.append(msg)
        _warn(f"{self.tag} {msg}")
        self.git = Git(self.ws)
        self.git.init()
        copy_tree(self.current, self.ws)
        self._commit(f"wcb: rebuilt from snapshot {self.current.name}")
        self._save_state("running")

    def _check_drift(self, notes: list[str]) -> None:
        """Before a session, make sure the workspace still holds the latest snapshot.

        Nothing may change the store between sessions (docs/running.md section 11). If something
        did, such as a process that escaped its session or an edit by hand, the change is
        reverted and noted, so it is never credited to the next session.
        """
        assert self.ws is not None and self.current is not None
        # inbox/ and .wcb/ are never in a snapshot and are removed after every session.
        changed = tree_diff(self.ws, self.current, exclude=(".git",))
        if not changed:
            return
        msg = (
            f"the workspace changed after snapshots/{self.current.name} was taken "
            f"({_some(changed)}); reverted before this session"
        )
        notes.append(msg)
        _warn(f"{self.tag} {msg}")
        self._reset_workspace(notes)

    def _commit(self, message: str, notes: list[str] | None = None) -> None:
        ok = self.git is None or self.git.commit(message) or not self.git.enabled
        if self.git is not None and self.git.notes:
            for n in self.git.notes:
                _warn(f"{self.tag} git: {n}")
                if notes is not None:
                    notes.append(f"git: {n}")
            self.git.notes.clear()
        if ok:
            return
        if not self._git_warned:
            self._git_warned = True
            _warn(
                f"{self.tag} git: {self.git.error} (history may be incomplete; snapshots are unaffected)"
            )

    def _load_state(self) -> None:
        f = self.dir / "state.json"
        self.state = read_json(f) if self.ctx.cfg.resume and f.is_file() else {}

    def _save_state(self, status: str) -> None:
        self.state.update(
            world=self.plan.id,
            world_path=str(self.plan.dir),
            repeat=self.k,
            track=self.track,
            # After the episode the temp workspace is deleted; its path stays for reference.
            workspace=str(self.ws) if self.ws is not None else self.state.get("workspace"),
            current_snapshot=self.current.name if self.current is not None else None,
            status=status,
            updated_at=_now(),
        )
        write_json(self.dir / "state.json", self.state)

    def _fresh_session_dir(self, name: str) -> Path:
        sd = self.session_dir(name)
        remove_tree(sd)
        sd.mkdir(parents=True)
        return sd

    # ------------------------------------------------------------ sessions
    def _ingest(
        self,
        date: str,
        name: str,
        inbox_dates: list[str],
        prompt: str,
        *,
        label: str,
        seed: bool = False,
    ) -> None:
        assert self.ws is not None and self.current is not None
        sd = self._fresh_session_dir(name)
        notes: list[str] = []
        self._check_drift(notes)
        ws = self.ws
        for d in inbox_dates:
            dst = ws / "inbox" / d
            if self.plan.inbox(d).is_dir():
                copy_tree(self.plan.inbox(d), dst)
            else:
                write_json(dst / "manifest.json", {"date": d, "artifacts": []})
                notes.append(f"the world has no inbox/{d}/; delivered an empty inbox")

        result = self._execute("ingest", date, ws, prompt, sd, track=self.track)

        if not ws.is_dir():
            ws.mkdir(parents=True)
            notes.append("the agent deleted its workspace directory; it was recreated")
        _tidy(ws, notes)
        usage = _collect_usage(ws, sd, notes)
        termination = _termination(usage, notes, "ingest")
        try:
            for n in ("inbox", ".wcb"):
                remove_tree(ws / n)
            if not result.ok:
                restore(ws, self.current)
                notes.append(
                    f"session {result.status}; store restored to snapshots/{self.current.name}"
                )
            # Before the snapshot: in a Track B seed session it replaces the current one.
            changes = tree_changes(self.current, ws)
            self._snapshot(date)
        except OSError as e:
            # Something the session left behind cannot be read or deleted (e.g. files owned by
            # another user). The session fails and the store goes back to the last snapshot.
            result.store_error = f"{type(e).__name__}: {e}"
            notes.append(
                f"the runner could not clean up or snapshot the store after the session "
                f"({result.store_error}); session failed; store restored to "
                f"snapshots/{self.current.name}"
            )
            self._reset_workspace(notes)
            changes = tree_changes(self.current, self.ws)
            self._snapshot(date)
        what = "seed" if seed else date
        suffix = "" if result.ok else f" (session {result.status}; store restored)"
        self._commit(f"wcb: after {what} ingest{suffix}", notes)

        record = self._record(result, "ingest", date, None, "agent", usage, notes)
        _add_termination(record, termination)
        record["store_changes"] = changes
        self._add_metered(record)
        if seed:
            record["seed_dates"] = list(inbox_dates)
        write_json(sd / "session.json", record)
        self._report(label, result, _incomplete_tag(termination))
        if result.ok and not any(changes.values()):
            _log(f"{self.tag} {label}: the session changed nothing in the store")

    def _query(self, cp: dict[str, Any], *, oracle: bool) -> None:
        cp_id, date = cp["id"], cp["date"]
        name = f"{cp_id}.query-oracle" if oracle else f"{cp_id}.query"
        sd = self._fresh_session_dir(name)
        questions = _visible_questions(self.plan, cp)
        write_json(sd / "questions.json", questions)
        track = "A" if oracle else self.track
        notes: list[str] = []
        qws = new_temp_dir(self.ctx.ws_root, QUERY_PREFIX)
        try:
            if oracle:
                copy_tree(self.plan.oracle_store(date), qws, exclude=SNAPSHOT_EXCLUDE)
                shutil.copyfile(contract_dir() / "CONTRACT.md", qws / "CONTRACT.md")
            else:
                assert self.ws is not None
                self._check_drift(notes)
                copy_tree(self.ws, qws, exclude=("inbox", ".wcb"))  # keeps .git history
            wcb_dir = qws / ".wcb"
            wcb_dir.mkdir()
            write_json(wcb_dir / "questions.json", questions)
            shutil.copyfile(
                contract_dir() / "answers" / "answers.schema.json", wcb_dir / "answer-schema.json"
            )
            make_read_only(qws, keep=(".wcb",))
            prompt = prompts.query_prompt(track, date)
            result = self._execute("query", date, qws, prompt, sd, track=track)
            if not qws.is_dir():
                qws.mkdir(parents=True)
                notes.append("the agent deleted its workspace directory")
            _tidy(qws, notes)
            usage = _collect_usage(qws, sd, notes)
            termination = _termination(usage, notes, "query")
            answers, answers_status = _read_answers(qws, sd, notes)
        finally:
            try:
                remove_tree(qws)
            except OSError as e:
                _warn(f"{self.tag} could not delete query workspace {qws}: {e}")

        write_json(sd / "answers.json", answers)
        write_json(self.answers_file(cp_id, oracle), answers)
        ids = {q["id"] for q in questions["questions"]}
        answered = len(ids & set(answers))
        record = self._record(
            result, "query", date, cp_id, "oracle" if oracle else "agent", usage, notes
        )
        record["answers"] = {"status": answers_status, "answered": answered, "questions": len(ids)}
        _add_termination(record, termination)
        self._add_metered(record)
        write_json(sd / "session.json", record)
        extra = f"  answers {answered}/{len(ids)}"
        if answers_status != "ok":
            extra += f" ({answers_status})"
        extra += _incomplete_tag(termination)
        self._report(f"{cp_id} {'query-oracle' if oracle else 'query'} ({date})", result, extra)

    def _execute(
        self, phase: str, date: str, workdir: Path, prompt: str, sd: Path, *, track: str
    ) -> ProcessResult:
        prompt_file = sd / "prompt.md"
        prompt_file.write_text(prompt + "\n", encoding="utf-8")
        values = {
            "workspace": str(workdir),
            "prompt": str(prompt_file),
            "prompt_text": prompt,
            "date": date,
            "phase": phase,
            "track": track,
            "session_dir": str(sd),
        }
        cmd, cwd, timeout_s = self.ctx.adapter.command(phase, values)
        env = self.ctx.adapter.environment(values)
        if self.ctx.meter is not None:
            self.meter_tag = f"{self.plan.id}/r{self.k}/{sd.name}/{time.time_ns()}"
            env.update(self.ctx.meter.session_env(self.meter_tag, host=self.ctx.cfg.meter_host))
        result = run_process(cmd, cwd, env, timeout_s, sd / "stdout.log", sd / "stderr.log")
        result.cmd = cmd
        result.timeout_s = timeout_s
        return result

    def _record(
        self,
        result: ProcessResult,
        phase: str,
        date: str,
        checkpoint: str | None,
        store: str,
        usage: dict[str, Any] | None,
        notes: list[str],
    ) -> dict[str, Any]:
        """session.json (docs/formats.md §6) plus timeout_s, status, world, repeat, track, notes."""
        if result.error:
            notes.append(result.error)
        return {
            "phase": phase,
            "date": date,
            "checkpoint": checkpoint,
            "store": store,
            "cmd": result.cmd,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "wall_s": result.wall_s,
            "timeout_s": result.timeout_s,
            "started_at": result.started_at,
            "finished_at": result.finished_at,
            "usage": usage,
            "status": result.status,
            "world": self.plan.id,
            "repeat": self.k,
            "track": self.track,
            "notes": notes,
        }

    def _add_metered(self, record: dict[str, Any]) -> None:
        """With --meter, add the proxy's usage totals for the session that just ran."""
        if self.ctx.meter is not None and self.meter_tag:
            record["metered_usage"] = summarize(self.ctx.meter.log_path, self.meter_tag)
            self.meter_tag = None

    def _report(self, label: str, result: ProcessResult, extra: str = "") -> None:
        self.ctx.counts[result.status] += 1
        _log(
            f"{self.tag} {label:<30} {result.status:<7} exit={result.exit_code} "
            f"{result.wall_s:7.1f}s{extra}"
        )

    def _skip(self, label: str) -> None:
        self.ctx.counts["skipped"] += 1
        _log(f"{self.tag} {label:<30} skipped (completed earlier)")


# ====================================================================== session files
def _read_session(sd: Path) -> dict[str, Any] | None:
    try:
        data = read_json(sd / "session.json")
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _ingest_completed(sd: Path) -> bool:
    """An ingest session counts as completed for --resume only if it exited 0 in time and its
    store could be snapshotted (status ``ok``)."""
    s = _read_session(sd)
    return (
        bool(s)
        and s.get("exit_code") == 0
        and not s.get("timed_out")
        and s.get("status", "ok") == "ok"
    )


def _session_finished(sd: Path) -> bool:
    """A query session counts as completed for --resume once it reached any final state."""
    s = _read_session(sd)
    return bool(s) and bool(s.get("finished_at"))


def _agent_file(workdir: Path, name: str) -> Path | None:
    """``<workdir>/.wcb/<name>``, or None if the agent made it (or ``.wcb``) a symbolic link.

    The runner never follows links out of a workspace, so an agent cannot make it copy files
    from elsewhere on the machine into the run directory.
    """
    d = workdir / ".wcb"
    if d.is_symlink() or (d / name).is_symlink():
        return None
    return d / name


def _tidy(workdir: Path, notes: list[str]) -> None:
    """After a session: undo permission changes and delete special files (normalize_tree)."""
    removed = normalize_tree(workdir)
    if removed:
        notes.append(
            f"deleted special files (FIFOs, sockets, devices) in the workspace: {_some(removed)}"
        )


def _some(items: list[str], n: int = 5) -> str:
    """'a, b, c' or 'a, b, c, d, e and 7 more'."""
    more = f" and {len(items) - n} more" if len(items) > n else ""
    return ", ".join(items[:n]) + more


def _collect_usage(workdir: Path, sd: Path, notes: list[str]) -> dict[str, Any] | None:
    """Copy ``.wcb/usage.json`` to the session directory and return it parsed (or None)."""
    try:
        f = _agent_file(workdir, "usage.json")
        if f is None:
            notes.append(".wcb/usage.json is a symbolic link; ignored")
            return None
        if not f.is_file():
            return None
        if f.stat().st_size > MAX_USAGE_BYTES:
            notes.append(f".wcb/usage.json is larger than {MAX_USAGE_BYTES} bytes; ignored")
            return None
        raw = f.read_bytes()
    except OSError as e:
        notes.append(f".wcb/usage.json could not be read ({type(e).__name__}: {e}); ignored")
        return None
    (sd / "usage.json").write_bytes(raw)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        notes.append(f".wcb/usage.json is not valid JSON ({e}); copied as-is")
        return None
    if not isinstance(data, dict):
        notes.append(".wcb/usage.json is not a JSON object; copied as-is")
        return None
    return data


def _termination(
    usage: dict[str, Any] | None, notes: list[str], phase: str
) -> dict[str, Any] | None:
    """The ``termination`` object an agent reported in ``.wcb/usage.json``, or None.

    When it says the agent did not finish normally (``incomplete: true``, e.g. its final
    response was cut off by an output-token limit), a note says so. Nothing else changes: the
    session's status, the store and the answers stay as the agent left them.
    """
    if not isinstance(usage, dict) or "termination" not in usage:
        return None
    t = usage["termination"]
    if not isinstance(t, dict) or not isinstance(t.get("incomplete", False), bool):
        notes.append(".wcb/usage.json termination is not a {reason, incomplete} object; ignored")
        return None
    if t.get("incomplete"):
        kept = "its store changes are kept" if phase == "ingest" else "its answers are scored"
        notes.append(
            f"the agent reported that it did not finish normally (termination reason "
            f"{t.get('reason')!r}); {kept} as written"
        )
    return t


def _add_termination(record: dict[str, Any], termination: dict[str, Any] | None) -> None:
    if termination is not None:
        record["termination"] = termination
        if termination.get("incomplete"):
            record["incomplete"] = True


def _incomplete_tag(termination: dict[str, Any] | None) -> str:
    if termination is None or not termination.get("incomplete"):
        return ""
    return f"  incomplete ({termination.get('reason')})"


def _read_answers(workdir: Path, sd: Path, notes: list[str]) -> tuple[dict[str, Any], str]:
    """Read ``.wcb/answers.json``. Missing or invalid answers become ``{}`` with a note."""
    try:
        f = _agent_file(workdir, "answers.json")
        if f is None:
            notes.append(".wcb/answers.json is a symbolic link; recorded empty answers {}")
            return {}, "invalid"
        if not f.is_file():
            notes.append(".wcb/answers.json was not written; recorded empty answers {}")
            return {}, "missing"
        if f.stat().st_size > MAX_ANSWERS_BYTES:
            notes.append(
                f".wcb/answers.json is larger than {MAX_ANSWERS_BYTES} bytes; recorded empty "
                "answers {}"
            )
            return {}, "too_large"
        raw = f.read_bytes()
    except OSError as e:
        notes.append(
            f".wcb/answers.json could not be read ({type(e).__name__}: {e}); recorded empty "
            "answers {}"
        )
        return {}, "unreadable"
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        (sd / "answers.raw.json").write_bytes(raw)
        notes.append(
            f".wcb/answers.json is not valid JSON ({e}); recorded empty answers {{}} "
            "(original saved as answers.raw.json)"
        )
        return {}, "invalid_json"
    if not isinstance(data, dict):
        (sd / "answers.raw.json").write_bytes(raw)
        notes.append(
            ".wcb/answers.json must be a JSON object mapping question IDs to answers; recorded "
            "empty answers {} (original saved as answers.raw.json)"
        )
        return {}, "not_object"
    return data, "ok"


# ====================================================================== processes
@dataclass
class ProcessResult:
    """Outcome of one agent process."""

    exit_code: int | None
    timed_out: bool
    wall_s: float
    started_at: str
    finished_at: str
    error: str | None = None  # set when the command could not be started
    cmd: list[str] | str | None = None
    timeout_s: float | None = None
    store_error: str | None = None  # set when the runner could not read or copy the store after

    @property
    def status(self) -> str:
        """'ok', 'failed' (non-zero exit, or a store the runner could not read), 'timeout', or
        'error' (could not start)."""
        if self.error:
            return "error"
        if self.timed_out:
            return "timeout"
        return "ok" if self.exit_code == 0 and not self.store_error else "failed"

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def run_process(
    cmd: list[str] | str,
    cwd: Path | None,
    env: dict[str, str],
    timeout_s: float,
    stdout_path: Path,
    stderr_path: Path,
) -> ProcessResult:
    """Run one agent process in its own process group, with a wall-clock timeout.

    A string ``cmd`` runs with ``/bin/sh -c``. stdin is empty; stdout and stderr go to the given
    files. On timeout every process of the session gets SIGTERM, then SIGKILL after
    :data:`KILL_GRACE_S` seconds. When the main process exits, every process it left running is
    killed, so no agent process outlives its session.

    "Every process of the session" is the main process's process group plus, on Linux, every
    descendant of the main process, including ones that left the group with ``setsid()`` or
    were daemonized: the runner makes itself a *child subreaper* while the session runs, so
    orphaned descendants are re-parented to the runner instead of to init and can be found.
    Elsewhere only the process group is signalled (see docs/running.md section 5).
    """
    argv = ["/bin/sh", "-c", cmd] if isinstance(cmd, str) else list(cmd)
    started_at = _now()
    t0 = time.monotonic()
    with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err, _child_subreaper():
        before = _child_pids()
        try:
            proc = subprocess.Popen(
                argv,
                cwd=str(cwd) if cwd is not None else None,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
        except OSError as e:
            msg = _start_error(e, argv, cwd, env)
            err.write(f"wcb: {msg}\n".encode())
            return ProcessResult(
                127, False, round(time.monotonic() - t0, 3), started_at, _now(), error=msg
            )
        timed_out = False
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _stop_session(proc, before, KILL_GRACE_S)
        except BaseException:
            _stop_session(proc, before, INTERRUPT_GRACE_S)
            raise
        finally:
            _kill_session(proc, before)  # stragglers, including ones that left the group
    return ProcessResult(
        proc.returncode, timed_out, round(time.monotonic() - t0, 3), started_at, _now()
    )


def _stop_session(proc: subprocess.Popen, before: set[int], grace: float) -> None:
    """SIGTERM every process of the session, then SIGKILL them if the main one is still running."""
    _signal_session(proc, before, signal.SIGTERM)
    try:
        proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        _kill_session(proc, before)
        proc.wait()


def _kill_session(proc: subprocess.Popen, before: set[int]) -> None:
    """SIGKILL every process of the session and reap the orphans re-parented to the runner.

    Repeats until none is left, because a process may fork, or have its children re-parented
    to the runner, while the others are being killed.
    """
    deadline = time.monotonic() + 5.0
    while True:
        pids = _signal_session(proc, before, signal.SIGKILL)
        for pid in pids:
            if pid != proc.pid:  # the main process is reaped by Popen
                with contextlib.suppress(OSError):
                    os.waitpid(pid, os.WNOHANG)
        if not _session_pids(proc, before) or time.monotonic() > deadline:
            return
        time.sleep(0.02)


def _signal_session(proc: subprocess.Popen, before: set[int], sig: int) -> list[int]:
    """Send ``sig`` to the session's process group and every other process of the session."""
    _signal_group(proc.pid, sig)
    pids = _session_pids(proc, before)
    for pid in pids:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, sig)
    return pids


def _session_pids(proc: subprocess.Popen, before: set[int]) -> list[int]:
    """Processes of the session that still need a signal or reaping (Linux; empty elsewhere).

    These are the runner's children that are not in ``before`` (the children it had before the
    session started), and all their descendants. Zombies are left out, except zombie children of
    the runner other than the main process (which ``Popen`` reaps): those still need reaping.
    """
    tree = _process_tree()
    stack = [(pid, state, True) for pid, state in tree.get(os.getpid(), []) if pid not in before]
    out: list[int] = []
    seen: set[int] = set()
    while stack:
        pid, state, direct = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        stack.extend((child, st, False) for child, st in tree.get(pid, []))
        if state not in ("Z", "X") or (direct and pid != proc.pid):
            out.append(pid)
    return out


def _process_tree() -> dict[int, list[tuple[int, str]]]:
    """parent pid -> [(child pid, state letter)] for every process, read from /proc (Linux)."""
    try:
        names = os.listdir("/proc")
    except OSError:
        return {}
    tree: dict[int, list[tuple[int, str]]] = {}
    for name in names:
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", "rb") as f:
                data = f.read()
            fields = data[data.rindex(b")") + 2 :].split()
            state, ppid = fields[0].decode(), int(fields[1])
        except (OSError, ValueError, IndexError):
            continue
        tree.setdefault(ppid, []).append((int(name), state))
    return tree


def _child_pids() -> set[int]:
    """The runner's current child processes (empty where /proc is missing)."""
    return {pid for pid, _ in _process_tree().get(os.getpid(), [])}


PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37


@contextlib.contextmanager
def _child_subreaper():
    """On Linux, make the runner a child subreaper (prctl(2)) for the duration of a session.

    Descendants orphaned during the session (a daemon, ``setsid cmd &``, Node's ``detached``)
    are then re-parented to the runner, where :func:`_kill_session` finds them. Elsewhere, or if
    prctl is unavailable, this does nothing.
    """
    prctl = _prctl()
    previous = ctypes.c_int(0)
    if prctl is None or prctl(PR_GET_CHILD_SUBREAPER, ctypes.byref(previous), 0, 0, 0) != 0:
        yield
        return
    prctl(PR_SET_CHILD_SUBREAPER, ctypes.c_ulong(1), 0, 0, 0)
    try:
        yield
    finally:
        prctl(PR_SET_CHILD_SUBREAPER, ctypes.c_ulong(1 if previous.value else 0), 0, 0, 0)


def _prctl():
    if not sys.platform.startswith("linux"):
        return None
    try:
        return ctypes.CDLL(None, use_errno=True).prctl
    except (OSError, AttributeError):
        return None


def _signal_group(pgid: int, sig: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, sig)


def _start_error(e: OSError, argv: list[str], cwd: Path | None, env: dict[str, str]) -> str:
    if cwd is not None and not Path(cwd).is_dir():
        return f"cannot start the agent: working directory {cwd} does not exist (check 'cwd' in the adapter)"
    if isinstance(e, FileNotFoundError):
        return (
            f"cannot start the agent: command {argv[0]!r} not found "
            f"(PATH={env.get('PATH', '')!r}; use an absolute path or {{adapter_dir}}/...)"
        )
    if isinstance(e, PermissionError):
        return f"cannot start the agent: permission denied for {argv[0]!r} (is it executable?)"
    return f"cannot start the agent: {e}"


INTERRUPT_SIGNALS = ("SIGTERM", "SIGHUP", "SIGQUIT")
"""Signals treated like Ctrl-C (SIGINT) while a run is in progress."""


@contextlib.contextmanager
def _sigterm_as_interrupt():
    """Treat SIGTERM, SIGHUP and SIGQUIT like Ctrl-C while running.

    Each raises KeyboardInterrupt, so the running session's processes are stopped, ``state.json``
    and ``run.json`` are marked ``interrupted``, and the run can be resumed. SIGHUP matters when
    the terminal or ssh connection that started ``wcb run`` goes away.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return

    def handler(signum, frame):
        raise KeyboardInterrupt(f"received signal {signum}")

    previous = {}
    for name in INTERRUPT_SIGNALS:
        sig = getattr(signal, name, None)
        if sig is not None:
            previous[sig] = signal.signal(sig, handler)
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


# ====================================================================== output
def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _log(msg: str) -> None:
    # A closed terminal (SIGHUP) must not turn an orderly interruption into a crash.
    with contextlib.suppress(OSError):
        print(msg, flush=True)


def _warn(msg: str) -> None:
    with contextlib.suppress(OSError):
        print(f"wcb run: warning: {msg}", file=sys.stderr, flush=True)
