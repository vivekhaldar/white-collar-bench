"""Grade a run directory and build the report: `wcb score <run_dir>` (docs/scoring.md).

`score_run` reads the run directory written by `wcb run` (docs/formats.md §6), grades every
answers file against the world's gold questions, computes store integrity for every
ingestion-day snapshot (Track A), aggregates, and writes `report.json` and `report.md`.

**Per question** (`wcb.grade.answers.score_question`): a score in [0, 1]. A missing answers file
scores every question of its checkpoint 0. Store-path citations are checked against the store
the answers came from: `snapshots/<checkpoint date>/` for the agent's answers, the world's
`gold/oracle-store/<checkpoint date>/` for oracle-store answers.

**Aggregation** (all aggregate scores are reported on a 0-100 scale):

1. *Buckets.* A question's bucket is its type (`point`, `list`, ...); every unanswerable
   question goes to its own bucket, `unanswerable`, whatever its type.
2. *Checkpoint score* = mean over the buckets present at the checkpoint of the bucket's mean
   question score (macro-average), so numerous list questions do not dominate.
3. *Episode score* (one world, one repeat) = mean over the episode's checkpoints.
4. *World score* = mean over the world's repeats.
5. *WCB score* = 100 x mean over worlds. The 95% confidence interval is a percentile
   bootstrap over worlds (`BOOTSTRAP_SAMPLES` resamples, fixed seed `BOOTSTRAP_SEED`); with a
   single world it is degenerate (both ends equal the score).

The **Synthesis score** applies the same aggregation to the oracle-store answers
(`answers/<cp>.oracle.json`); **Ingestion cost** = Synthesis - WCB. **SIS**
(`wcb.grade.integrity.store_integrity`) is computed for every episode day that has a
snapshot; an episode's SIS is the mean over its days, and the final-day SIS is reported
separately. Both are averaged over repeats, then over worlds.

Missing pieces never stop scoring: missing answers score 0, missing snapshots skip SIS for
that day, an answer the grader cannot handle (`grader_error`) scores 0, and every such gap is
listed in the report's `notes`.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import random
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wcb import __version__
from wcb.grade import report as report_render
from wcb.grade.answers import QuestionScore, ScoreContext, score_answers
from wcb.grade.integrity import METRICS, store_integrity
from wcb.grade.judge import make_judge
from wcb.suites import Suite, get_suite
from wcb.util.io import read_json, write_json, write_text
from wcb.world.model import World

#: Version of the scoring rules and report layout. Bump when either changes.
SCORER_VERSION = "0.2"
#: Bootstrap resamples for confidence intervals, and the fixed seed that makes them repeatable.
BOOTSTRAP_SAMPLES = 2000
BOOTSTRAP_SEED = 20270101
#: Number of worst-scoring questions shown as failure samples.
N_FAILURE_SAMPLES = 10
#: Bucket for unanswerable questions in the macro-average.
UNANSWERABLE = "unanswerable"
#: Report order of buckets (others follow alphabetically).
BUCKET_ORDER = ("point", "list", "status", "brief", "change", "temporal", "priority", UNANSWERABLE)


# ---------------------------------------------------------------- report object
@dataclass
class Report:
    """The result of `score_run`. `data` is exactly what `report.json` holds."""

    data: dict

    def summary_text(self) -> str:
        """A few lines with the headline numbers, as printed by `wcb score`."""
        return report_render.summary_text(self.data)

    def markdown(self) -> str:
        """The human-readable report (`report.md`)."""
        return report_render.render_markdown(self.data)

    def write(self, out_dir: Path) -> None:
        """Write `report.json` and `report.md` into `out_dir` (created if needed)."""
        out_dir = Path(out_dir)
        write_json(out_dir / "report.json", self.data)
        write_text(out_dir / "report.md", self.markdown())


# ---------------------------------------------------------------- entry point
def score_run(
    run_dir: Path,
    judge: str = "heuristic",
    judge_model: str | None = None,
    out_dir: Path | None = None,
    suite: str | None = None,
) -> Report:
    """Grade the run in `run_dir`, write `report.json` and `report.md`, and return the report.

    `suite` (wcb/suites.py) scores only that suite's worlds and days, so a full run also yields
    its suite score. A run made with `wcb run --suite` is scored as its suite without it.

    `judge` is `heuristic` or `llm` (`wcb.grade.judge.make_judge`); LLM decisions are cached in
    `<out_dir>/judge-cache.jsonl`. `out_dir` defaults to `<run_dir>/scores`. Raises
    FileNotFoundError when `run.json` or a world directory it names is missing.
    """
    run_dir = Path(run_dir)
    meta = load_run_meta(run_dir)
    out_dir = Path(out_dir) if out_dir else run_dir / "scores"
    out_dir.mkdir(parents=True, exist_ok=True)
    judge_obj = make_judge(judge, judge_model, cache_path=out_dir / "judge-cache.jsonl")
    plan = RunPlan.from_meta(run_dir, meta, suite=suite)

    if hasattr(judge_obj, "recording"):
        # Model judges: one pass records every decision the cache lacks, those are asked in
        # parallel, and the real pass below reads them from the cache.
        judge_obj.recording(True)
        for entry in plan.world_entries:
            score_world(plan, entry, judge_obj, Accumulator())
        judge_obj.fetch_pending(int(os.environ.get("WCB_JUDGE_WORKERS", "") or 16))
    acc = Accumulator()
    worlds = [score_world(plan, entry, judge_obj, acc) for entry in plan.world_entries]
    data = assemble_report(plan, worlds, acc, judge, judge_model, judge_obj, out_dir)
    report = Report(data)
    report.write(out_dir)
    return report


# ---------------------------------------------------------------- run metadata
def load_run_meta(run_dir: Path) -> dict:
    """`run.json` as a dict. Raises FileNotFoundError if it is missing, ValueError if invalid."""
    f = Path(run_dir) / "run.json"
    if not f.is_file():
        raise FileNotFoundError(
            f"no run.json in {run_dir}; is this a run directory from 'wcb run'?"
        )
    meta = read_json(f)
    if not isinstance(meta, dict):
        raise ValueError(f"{f} must hold a JSON object")
    return meta


@dataclass
class RunPlan:
    """What to score, derived from `run.json`.

    `agent`: score the agent's answers and stores (False for `--skip-ingest` runs).
    `oracle`: score oracle-store answers (Track A; from `run.json`'s `oracle`, or detected from
    the presence of `answers/*.oracle.json` files when the key is absent).
    """

    run_dir: Path
    meta: dict
    track: str
    agent: bool
    oracle: bool
    max_days: int | None
    world_entries: list[dict]
    notes: list[str] = field(default_factory=list)
    suite: Suite | None = None

    @classmethod
    def from_meta(cls, run_dir: Path, meta: dict, suite: str | None = None) -> RunPlan:
        track = str(meta.get("track") or "A").upper()
        options = meta.get("options") or {}
        skip_ingest = bool(options.get("skip_ingest"))
        if "oracle" in meta:
            oracle = bool(meta["oracle"])
        else:
            oracle = any(Path(run_dir).glob("*/r*/answers/*.oracle.json"))
        notes = []
        if skip_ingest:
            notes.append(
                "run used --skip-ingest: only oracle-store answers exist, so the WCB score, SIS "
                "and ingestion cost are not reported"
            )
        if track != "A":
            notes.append(f"Track {track}: store integrity (SIS) is Track A only and is skipped")
        if track != "A" and oracle:
            oracle = False
        entries = [w for w in meta.get("worlds") or [] if isinstance(w, dict) and w.get("id")]
        if not entries:
            notes.append("run.json lists no worlds; nothing was scored")
        max_days = options.get("max_days")
        max_days = int(max_days) if max_days else None
        suite_obj = None
        if suite or options.get("suite"):
            suite_obj = get_suite(suite or options["suite"])
            ran = {str(w["id"]) for w in entries}
            missing = [w for w in suite_obj.world_ids if w not in ran]
            if missing:
                raise ValueError(
                    f"cannot score {run_dir} as suite {suite_obj.name}: it has no results for "
                    f"{', '.join(missing)}"
                )
            if max_days is not None and max_days < suite_obj.max_days:
                raise ValueError(
                    f"cannot score {run_dir} as suite {suite_obj.name}: it played {max_days} "
                    f"day(s), the suite needs {suite_obj.max_days}"
                )
            entries = [w for w in entries if str(w["id"]) in suite_obj.world_ids]
            max_days = suite_obj.max_days
            notes.append(
                f"scored as suite {suite_obj.name} ({len(entries)} worlds, first {max_days} "
                f"episode day(s)): the headline is {suite_obj.label}, comparable only with other "
                f"{suite_obj.label} scores (docs/lite.md)"
            )
        return cls(
            run_dir=Path(run_dir),
            meta=meta,
            track=track,
            agent=not skip_ingest,
            oracle=oracle,
            max_days=max_days,
            world_entries=entries,
            notes=notes,
            suite=suite_obj,
        )


# ---------------------------------------------------------------- gold access
class WorldGold:
    """A world plus cached gold state and gold questions for scoring.

    Reads `gold/state/<date>.json` and `gold/questions/<cp>.json` when they exist and computes
    them (`state_at`, `build_questions`) when they do not, adding a note.
    """

    def __init__(self, world: World, max_days: int | None, notes: list[str]):
        self.world = world
        self.notes = notes
        all_days = world.episode_days()
        self.all_days = all_days
        self.days = all_days[:max_days] if max_days else all_days
        self.checkpoints = [c for c in world.checkpoints() if c["date"] in self.days]
        self._states: dict[str, dict] = {}
        self._docs: dict[str, dict] = {}

    @classmethod
    def load(cls, entry: dict, max_days: int | None, notes: list[str]) -> WorldGold:
        path = Path(str(entry.get("path") or ""))
        if not (path / "world.yaml").is_file():
            from wcb.paths import resolve_world

            try:
                path = resolve_world(str(entry["id"]))
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"world {entry['id']!r}: no world.yaml at {entry.get('path')!r} (from run.json); "
                    "the world directory must be available to score the run"
                ) from None
        cls._check_gold(path, entry, notes)
        return cls(World.load(path), max_days, notes)

    @staticmethod
    def _check_gold(path: Path, entry: dict, notes: list[str]) -> None:
        """Rebuild stale gold, and note when the gold differs from the gold the run was made
        against (run.json records each world's gold/BUILD.json)."""
        from wcb.world.build import BUILD_STAMP, ensure_built

        wid = entry.get("id")
        if (path / "world.jsonl").is_file():
            res = ensure_built(path)
            if res is not None:
                notes.append(f"{wid}: gold was missing or stale; rebuilt it before scoring")
        stamp = path / "gold" / BUILD_STAMP
        then = entry.get("gold")
        now = read_json(stamp) if stamp.is_file() else None
        if then and now and then != now:
            what = ("gold version " f"{then.get('gold_version')} -> {now.get('gold_version')}"
                    if then.get("gold_version") != now.get("gold_version")
                    else "the world's sources changed")
            notes.append(
                f"{wid}: the gold differs from the gold this run was made against ({what}); "
                "answers are graded against the current gold"
            )

    def day_index(self, date: str) -> int | None:
        """1-based position of `date` among the world's episode days."""
        return self.all_days.index(date) + 1 if date in self.all_days else None

    def state(self, date: str) -> dict:
        if date not in self._states:
            f = self.world.dir / "gold" / "state" / f"{date}.json"
            if f.is_file():
                self._states[date] = read_json(f)
            else:
                from wcb.world.state import state_at

                self.notes.append(f"{self.world.id}: gold/state/{date}.json missing; computed it")
                self._states[date] = state_at(self.world, date)
        return self._states[date]

    def questions(self, cp: dict) -> dict:
        cp_id = cp["id"]
        if cp_id not in self._docs:
            f = self.world.dir / "gold" / "questions" / f"{cp_id}.json"
            if f.is_file():
                self._docs[cp_id] = read_json(f)
            else:
                from wcb.questions.build import build_questions

                self.notes.append(
                    f"{self.world.id}: gold/questions/{cp_id}.json missing; built the questions "
                    "from questions.yaml (run 'wcb world build')"
                )
                docs = build_questions(self.world, {cp["date"]: self.state(cp["date"])})
                self._docs[cp_id] = docs.get(cp_id) or {"questions": []}
        return self._docs[cp_id]

    def oracle_store(self, date: str) -> Path:
        return self.world.dir / "gold" / "oracle-store" / date


# ---------------------------------------------------------------- accumulation
@dataclass
class Scored:
    """One graded question in one episode, with what is needed for reports."""

    world: str
    repeat: int
    checkpoint: str
    date: str
    store: str  # 'agent' or 'oracle'
    question: dict
    answer: Any
    score: QuestionScore

    @property
    def bucket(self) -> str:
        return question_bucket(self.score)

    def row(self) -> dict:
        s = self.score
        return {
            "world": self.world,
            "repeat": self.repeat,
            "checkpoint": self.checkpoint,
            "store": self.store,
            "id": s.id,
            "type": s.type,
            "bucket": self.bucket,
            "template": s.template,
            "challenges": list(s.challenges),
            "answerable": s.answerable,
            "valid": s.valid,
            "abstained": s.abstained,
            "base": round(s.base, 4),
            "citation": None if s.citation is None else round(s.citation, 4),
            "score": round(s.score, 4),
        }


@dataclass
class Accumulator:
    """Everything collected while scoring, before aggregation."""

    scored: list[Scored] = field(default_factory=list)
    sessions: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def question_bucket(s: QuestionScore) -> str:
    """The macro-average bucket: the question type, or `unanswerable`."""
    return s.type if s.answerable else UNANSWERABLE


# ---------------------------------------------------------------- scoring
def score_world(plan: RunPlan, entry: dict, judge: Any, acc: Accumulator) -> dict:
    """Score every repeat of one world. Returns the world's section of the report."""
    gold = WorldGold.load(entry, plan.max_days, acc.notes)
    wid = gold.world.id
    repeats = _repeat_numbers(plan.run_dir / str(entry["id"]), entry.get("repeats"))
    episodes = [score_episode(plan, gold, str(entry["id"]), k, judge, acc) for k in repeats]
    world = {
        "id": wid,
        "path": str(gold.world.dir),
        "days": gold.days,
        "n_days": len(gold.all_days),
        "checkpoints": [{**c, "day_index": gold.day_index(c["date"])} for c in gold.checkpoints],
        "repeats": episodes,
    }
    world["score"] = mean(e["score"] for e in episodes)
    world["synthesis"] = mean(e["synthesis"] for e in episodes)
    world["ingestion_cost"] = diff(world["synthesis"], world["score"])
    world["sis"] = mean((e["sis"] or {}).get("mean") for e in episodes)
    world["sis_final"] = mean((e["sis"] or {}).get("final") for e in episodes)
    return world


def _repeat_numbers(world_run_dir: Path, declared: Any) -> list[int]:
    """Repeats to score: 1..declared, or the r<k> directories present when not declared."""
    if isinstance(declared, int) and declared >= 1:
        return list(range(1, declared + 1))
    found = sorted(
        int(p.name[1:]) for p in world_run_dir.glob("r*") if p.is_dir() and p.name[1:].isdigit()
    )
    return found or [1]


def score_episode(
    plan: RunPlan, gold: WorldGold, run_world_id: str, k: int, judge: Any, acc: Accumulator
) -> dict:
    """Score one episode (`<run>/<world>/r<k>/`): answers per checkpoint, SIS per day, sessions."""
    ep_dir = plan.run_dir / run_world_id / f"r{k}"
    tag = f"{gold.world.id} r{k}"
    if not ep_dir.is_dir():
        acc.notes.append(f"{tag}: episode directory missing; every answer scores 0")
    checkpoints = []
    for cp in gold.checkpoints:
        doc = gold.questions(cp)
        row: dict[str, Any] = {
            "id": cp["id"],
            "date": cp["date"],
            "label": cp.get("label"),
            "day_index": gold.day_index(cp["date"]),
            "n_questions": len(doc.get("questions") or []),
        }
        for store, enabled in (("agent", plan.agent), ("oracle", plan.oracle)):
            key = "score" if store == "agent" else "synthesis"
            if not enabled:
                row[key], row[f"{key}_buckets"] = None, {}
                continue
            scored = score_checkpoint(gold, ep_dir, cp, doc, store, judge, acc, tag, k, track=plan.track)
            value, buckets = checkpoint_score([s.score for s in scored])
            row[key] = pct(value)
            row[f"{key}_buckets"] = {b: pct(v) for b, v in buckets.items()}
        row["ingestion_cost"] = diff(row["synthesis"], row["score"])
        checkpoints.append(row)
    episode = {
        "repeat": k,
        "checkpoints": checkpoints,
        "score": mean(c["score"] for c in checkpoints),
        "synthesis": mean(c["synthesis"] for c in checkpoints),
    }
    episode["ingestion_cost"] = diff(episode["synthesis"], episode["score"])
    episode["sis"] = (
        # SIS checks store records, not answers: a panel judge leaves it to its heuristic.
        episode_sis(gold, ep_dir, getattr(judge, "heuristic", judge), acc.notes, tag)
        if plan.agent and plan.track == "A"
        else None
    )
    # Sessions after the last scored day (a full run scored as a suite) do not count.
    acc.sessions += [
        r for r in collect_sessions(ep_dir, gold.world.id, k)
        if not r["date"] or r["date"] <= gold.days[-1]
    ]
    return episode


def score_checkpoint(
    gold: WorldGold,
    ep_dir: Path,
    cp: dict,
    doc: dict,
    store: str,
    judge: Any,
    acc: Accumulator,
    tag: str,
    k: int,
    *, track: str = "A",
) -> list[Scored]:
    """Grade one answers file (`answers/<cp>.json` or `answers/<cp>.oracle.json`)."""
    suffix = ".oracle.json" if store == "oracle" else ".json"
    answers_file = ep_dir / "answers" / f"{cp['id']}{suffix}"
    answers, problem = read_answers(answers_file)
    if problem:
        acc.notes.append(f"{tag}: answers/{answers_file.name} {problem}; its questions score 0")
    if store == "oracle":
        store_root = gold.oracle_store(cp["date"])
    else:
        store_root = ep_dir / "snapshots" / cp["date"]
    if not store_root.is_dir():
        acc.notes.append(
            f"{tag}: no {store} store for {cp['date']} ({store_root}); store-path citations "
            "count as invalid"
        )
        store_root = None
    ctx = ScoreContext.from_state(gold.world, gold.state(cp["date"]), store_root=store_root, track=track)
    results = score_answers(doc, answers, judge, ctx)
    for s in results:
        if s.details.get("grader_error"):
            acc.notes.append(
                f"{tag}: {cp['id']} {s.id} ({store}) could not be graded "
                f"({s.details['grader_error']}); it scores 0"
            )
    by_id = {q["id"]: q for q in doc.get("questions") or []}
    scored = [
        Scored(gold.world.id, k, cp["id"], cp["date"], store, by_id[s.id], answers.get(s.id), s)
        for s in results
    ]
    acc.scored += scored
    return scored


def read_answers(path: Path) -> tuple[dict, str | None]:
    """(answers, problem): `{}` plus 'is missing' or 'is not a JSON object' when unusable."""
    if not path.is_file():
        return {}, "is missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return {}, "is not valid JSON"
    if not isinstance(data, dict):
        return {}, "is not a JSON object"
    return data, None


def checkpoint_score(scores: list[QuestionScore]) -> tuple[float | None, dict[str, float]]:
    """(macro-average over buckets, bucket -> mean question score); None with no questions."""
    groups: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        groups[question_bucket(s)].append(s.score)
    buckets = {
        b: sum(v) / len(v) for b, v in sorted(groups.items(), key=lambda kv: bucket_key(kv[0]))
    }
    return (sum(buckets.values()) / len(buckets) if buckets else None), buckets


def episode_sis(
    gold: WorldGold, ep_dir: Path, judge: Any, notes: list[str], tag: str
) -> dict | None:
    """SIS for every episode day with a snapshot; None (with a note) when there are none."""
    if not (ep_dir / "snapshots").is_dir():
        notes.append(f"{tag}: no snapshots; SIS not computed for this episode")
        return None
    days = []
    for date in gold.days:
        snap = ep_dir / "snapshots" / date
        if not snap.is_dir():
            notes.append(f"{tag}: no snapshot for {date}; SIS skipped for that day")
            continue
        r = store_integrity(snap, gold.state(date), gold.world, judge)
        days.append({"date": date, **sis_row(r)})
    if not days:
        return None
    return {
        "days": days,
        "mean": mean(d["sis"] for d in days),
        "final": days[-1]["sis"],
        "final_date": days[-1]["date"],
    }


def sis_row(result: dict) -> dict:
    """A compact per-day SIS row: the score, the six metrics and counts of the main errors."""
    d = result["details"]
    return {
        "sis": round(result["sis"], 2),
        **{m: round(result[m], 4) for m in METRICS},
        "errors": {
            "entity_fp": d["entities"]["fp"],
            "entity_fn": d["entities"]["fn"],
            "wrong_merges": len(d["entities"]["wrong_merges"]),
            "loop_fp": d["loops"]["fp"],
            "loop_fn": d["loops"]["fn"],
            "stale": len(d["freshness"]["stale"]),
            "ungrounded": len(d["groundedness"]["ungrounded"]),
            "validator_errors": d["validity"]["errors"],
        },
        "missing_entities": d["entities"]["missing"],
        "false_positive_records": d["entities"]["false_positives"],
        "missing_loops": d["loops"]["missing"],
        "unmatched_loop_records": d["loops"]["unmatched_records"],
        "stale_records": d["freshness"]["stale"],
    }


# ---------------------------------------------------------------- sessions and efficiency
def collect_sessions(ep_dir: Path, world: str, k: int) -> list[dict]:
    """One row per `sessions/*/session.json`, with wall time and usage.

    Token counts come from `metered_usage` (written by `wcb run --meter`) when present, else from
    the agent's self-reported `usage`. Cost and tool calls are always self-reported.
    """
    rows = []
    for f in sorted((ep_dir / "sessions").glob("*/session.json")):
        try:
            s = read_json(f)
        except (OSError, ValueError):
            continue
        if not isinstance(s, dict):
            continue
        name = f.parent.name
        usage = dict(s.get("usage")) if isinstance(s.get("usage"), dict) else {}
        metered = s.get("metered_usage") if isinstance(s.get("metered_usage"), dict) else None
        if metered is not None:
            usage["input_tokens"] = sum(
                _num(metered.get(k)) or 0
                for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
            )
            usage["output_tokens"] = _num(metered.get("output_tokens")) or 0
        store = s.get("store") or ("oracle" if name.endswith("query-oracle") else "agent")
        phase = s.get("phase") or ("query" if ".query" in name else "ingest")
        rows.append(
            {
                "world": world,
                "repeat": k,
                "session": name,
                "group": "query_oracle" if store == "oracle" else str(phase),
                "phase": phase,
                "date": s.get("date"),
                "checkpoint": s.get("checkpoint"),
                "store": store,
                "status": s.get("status") or _session_status(s),
                "wall_s": _num(s.get("wall_s")),
                "usage_reported": bool(s.get("usage")) if isinstance(s.get("usage"), dict) else False,
                "usage_metered": metered is not None,
                **{key: _num(usage.get(key)) for key in USAGE_KEYS},
            }
        )
    return rows


#: Numeric usage fields read from `session.json` (docs/formats.md §5).
USAGE_KEYS = ("input_tokens", "output_tokens", "cost_usd", "tool_calls")


def _session_status(s: dict) -> str:
    if s.get("timed_out"):
        return "timeout"
    return "ok" if s.get("exit_code") == 0 else "failed"


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def summarize_sessions(rows: list[dict]) -> dict:
    """Totals and per-session means of wall time, tokens, cost and tool calls for a group."""
    out: dict[str, Any] = {
        "sessions": len(rows),
        "ok": sum(1 for r in rows if r["status"] == "ok"),
        "timeouts": sum(1 for r in rows if r["status"] == "timeout"),
        "failures": sum(1 for r in rows if r["status"] in ("failed", "error")),
        "usage_reported": sum(1 for r in rows if r["usage_reported"]),
        "usage_metered": sum(1 for r in rows if r.get("usage_metered")),
    }
    for key in ("wall_s", *USAGE_KEYS):
        vals = [r[key] for r in rows if r[key] is not None]
        out[key] = {"total": sum(vals) if vals else None, "mean": mean(vals)}
    return out


def efficiency(sessions: list[dict], n_episodes: int) -> dict:
    """The report's efficiency section (docs/scoring.md "Efficiency")."""
    groups = {
        g: [r for r in sessions if r["group"] == g] for g in ("ingest", "query", "query_oracle")
    }
    summary = {g: summarize_sessions(rows) for g, rows in groups.items()}
    agent = groups["ingest"] + groups["query"]
    totals = summarize_sessions(agent)
    per_day = _grouped(groups["ingest"], ("world", "date"))
    per_query = _grouped(groups["query"] + groups["query_oracle"], ("world", "checkpoint", "store"))
    return {
        "summary": summary,
        "per_episode": {
            key: (
                totals[key]["total"] / n_episodes
                if totals[key]["total"] is not None and n_episodes
                else None
            )
            for key in ("wall_s", *USAGE_KEYS)
        },
        "per_ingest_day": per_day,
        "per_query_session": per_query,
    }


def _grouped(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    """Rows grouped by `keys`, with the mean (over repeats) of wall time and usage."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in keys)].append(r)
    out = []
    for key in sorted(groups, key=lambda t: tuple("" if v is None else str(v) for v in t)):
        rs = groups[key]
        item = dict(zip(keys, key, strict=True))
        item["n"] = len(rs)
        item["statuses"] = sorted({r["status"] for r in rs})
        for k in ("wall_s", *USAGE_KEYS):
            item[k] = mean(r[k] for r in rs)
        out.append(item)
    return out


# ---------------------------------------------------------------- breakdowns
def bucket_key(name: str) -> tuple[int, str]:
    return (BUCKET_ORDER.index(name) if name in BUCKET_ORDER else len(BUCKET_ORDER), name)


def breakdown(scored: list[Scored], key_fn, *, agent: bool, oracle: bool) -> dict[str, dict]:
    """Mean question score (0-100) per key for agent and oracle answers, with counts.

    `key_fn(scored) -> list of keys` (a question can carry several challenge tags).
    """
    groups: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"agent": [], "oracle": []})
    for s in scored:
        for key in key_fn(s):
            groups[key][s.store].append(s.score.score)
    out = {}
    for key, g in groups.items():
        wcb = pct(mean(g["agent"])) if agent else None
        syn = pct(mean(g["oracle"])) if oracle else None
        out[key] = {
            "n": len(g["agent"]) if agent else len(g["oracle"]),
            "wcb": wcb,
            "synthesis": syn,
            "ingestion_cost": diff(syn, wcb),
        }
    return out


def checkpoint_breakdown(worlds: list[dict]) -> list[dict]:
    """Per world and checkpoint: scores averaged over repeats, with the checkpoint's position."""
    out = []
    for w in worlds:
        for cp in w["checkpoints"]:
            rows = [c for e in w["repeats"] for c in e["checkpoints"] if c["id"] == cp["id"]]
            wcb, syn = mean(c["score"] for c in rows), mean(c["synthesis"] for c in rows)
            out.append(
                {
                    "world": w["id"],
                    "checkpoint": cp["id"],
                    "date": cp["date"],
                    "label": cp.get("label"),
                    "day_index": cp.get("day_index"),
                    "n_days": w["n_days"],
                    "n_questions": rows[0]["n_questions"] if rows else 0,
                    "wcb": wcb,
                    "synthesis": syn,
                    "ingestion_cost": diff(syn, wcb),
                }
            )
    return out


def sis_by_day(worlds: list[dict]) -> list[dict]:
    """Per world and episode day: SIS and its sub-metrics averaged over repeats."""
    out = []
    for w in worlds:
        per_date: dict[str, list[dict]] = defaultdict(list)
        for e in w["repeats"]:
            for d in (e["sis"] or {}).get("days", []):
                per_date[d["date"]].append(d)
        for date in sorted(per_date):
            rows = per_date[date]
            item = {"world": w["id"], "date": date, "n_repeats": len(rows)}
            item["sis"] = mean(r["sis"] for r in rows)
            for m in METRICS:
                item[m] = mean(r[m] for r in rows)
            out.append(item)
    return out


def failure_samples(scored: list[Scored], store: str, n: int = N_FAILURE_SAMPLES) -> list[dict]:
    """The `n` lowest-scoring questions (score < 1) with gold and predicted answers."""
    pool = [s for s in scored if s.store == store and s.score.score < 1.0]
    pool.sort(key=lambda s: (s.score.score, s.world, s.repeat, s.checkpoint, s.score.id))
    out = []
    for s in pool[:n]:
        q = s.question
        gold = q.get("gold") or {}
        out.append(
            {
                "world": s.world,
                "repeat": s.repeat,
                "checkpoint": s.checkpoint,
                "store": s.store,
                "id": s.score.id,
                "type": s.score.type,
                "template": s.score.template,
                "text": q.get("text"),
                "answerable": s.score.answerable,
                "challenges": list(s.score.challenges),
                "score": round(s.score.score, 4),
                "base": round(s.score.base, 4),
                "citation": s.score.citation,
                "gold": {k: v for k, v in gold.items() if k != "facts"}
                if s.score.answerable
                else "abstain",
                "predicted": s.answer,
                "details": s.score.details,
            }
        )
    return out


# ---------------------------------------------------------------- assembly
def assemble_report(
    plan: RunPlan,
    worlds: list[dict],
    acc: Accumulator,
    judge_kind: str,
    judge_model: str | None,
    judge_obj: Any,
    out_dir: Path,
) -> dict:
    """Put the report together (the layout is documented in docs/scoring.md)."""
    world_scores = [w["score"] for w in worlds if w["score"] is not None]
    world_syn = [w["synthesis"] for w in worlds if w["synthesis"] is not None]
    wcb, synthesis = mean(world_scores), mean(world_syn)
    n_episodes = sum(len(w["repeats"]) for w in worlds)
    primary = "agent" if plan.agent else "oracle"
    headline = {
        "track": plan.track,
        "suite": plan.suite.name if plan.suite else None,
        "label": plan.suite.label if plan.suite else "WCB",
        "wcb": wcb,
        "wcb_ci95": bootstrap_ci(world_scores),
        "synthesis": synthesis,
        "synthesis_ci95": bootstrap_ci(world_syn),
        "ingestion_cost": diff(synthesis, wcb),
        "sis": mean(w["sis"] for w in worlds),
        "sis_final": mean(w["sis_final"] for w in worlds),
        "n_worlds": len(worlds),
        "n_episodes": n_episodes,
        "n_questions": sum(1 for s in acc.scored if s.store == primary),
    }
    meta = plan.meta
    return {
        "report_version": SCORER_VERSION,
        "scored_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "scorer": {"version": SCORER_VERSION, "wcb_version": __version__},
        "run": {
            "dir": str(plan.run_dir),
            "track": plan.track,
            "adapter": meta.get("adapter"),
            "wcb_version": meta.get("wcb_version"),
            "status": meta.get("status"),
            "started_at": meta.get("started_at"),
            "finished_at": meta.get("finished_at"),
            "options": meta.get("options") or {},
            "suite": plan.suite.describe() if plan.suite else None,
            "scored": {"agent": plan.agent, "oracle": plan.oracle},
        },
        "judge": {
            "kind": judge_kind,
            "name": getattr(judge_obj, "name", judge_kind),
            "model": judge_model,
            "calls": getattr(judge_obj, "calls", None),
            "escalated": getattr(judge_obj, "escalated", None),
        },
        "output": {"dir": str(out_dir)},
        "headline": headline,
        "worlds": worlds,
        "breakdowns": {
            "by_type": _sorted_buckets(
                breakdown(acc.scored, lambda s: [s.bucket], agent=plan.agent, oracle=plan.oracle)
            ),
            "by_challenge": dict(
                sorted(
                    breakdown(
                        acc.scored,
                        lambda s: s.score.challenges,
                        agent=plan.agent,
                        oracle=plan.oracle,
                    ).items()
                )
            ),
            "by_checkpoint": checkpoint_breakdown(worlds),
        },
        "sis_by_day": sis_by_day(worlds),
        "efficiency": efficiency(acc.sessions, n_episodes),
        "failures": failure_samples(acc.scored, primary),
        "questions": [s.row() for s in acc.scored],
        "notes": list(dict.fromkeys(plan.notes + acc.notes)),
    }


def _sorted_buckets(d: dict[str, dict]) -> dict[str, dict]:
    return {k: d[k] for k in sorted(d, key=bucket_key)}


# ---------------------------------------------------------------- numeric helpers
def mean(values: Iterable[float | None]) -> float | None:
    """Mean of the non-None values, or None when there are none."""
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def pct(x: float | None) -> float | None:
    """A [0, 1] score on the 0-100 scale (None stays None)."""
    return None if x is None else 100.0 * x


def diff(a: float | None, b: float | None) -> float | None:
    """a - b, or None if either is missing (used for Ingestion cost = Synthesis - WCB)."""
    return None if a is None or b is None else a - b


def bootstrap_ci(
    values: list[float], samples: int = BOOTSTRAP_SAMPLES, seed: int = BOOTSTRAP_SEED
) -> list[float] | None:
    """95% percentile-bootstrap interval of the mean of `values`.

    Resamples `values` with replacement `samples` times using `random.Random(seed)`, so the
    interval is repeatable. One value gives the degenerate interval [v, v]; none gives None.
    """
    if not values:
        return None
    if len(values) == 1:
        return [values[0], values[0]]
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(samples))
    lo = means[int(0.025 * (samples - 1))]
    hi = means[int(round(0.975 * (samples - 1)))]
    return [lo, hi]
