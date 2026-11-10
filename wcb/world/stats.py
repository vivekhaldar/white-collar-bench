"""Calibration statistics for a world (`wcb world stats`, `gold/calibration.json`).

The numbers mirror the calibration targets in docs/plan.md §1 ("What the real store
teaches"), so a generated or hand-authored world can be compared with them at a glance:
cast size, inputs per day and their channel mix, loops created per workday, loop shape
(kind, owner, evidence basis, endorsement, hard due dates), status at the end of the world,
loop lifetimes, planted challenges and the question mix.

Two vantage points are used, and each section says which:

- **world**: the full hidden timeline in `world.jsonl` (flow counts: artifacts, events,
  commitments created per day);
- **gold**: the knowable state at the last date (loop shape and status), which is what a
  perfect store would contain at the end of the episode.

All output is deterministic: dictionaries are sorted by key and shares are rounded to three
decimals.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from wcb.util.dates import business_days_between, date_of, date_range, is_business_day
from wcb.util.io import read_json
from wcb.world.model import CLOSED_STATUSES, World
from wcb.world.state import state_at


def world_stats(world_dir: Path) -> dict:
    """Calibration statistics for the world at `world_dir`.

    Question statistics come from `gold/questions/*.json` and are `None` until the world has
    been built.
    """
    world = World.load(world_dir)
    final = state_at(world, world.all_dates()[-1])
    return compute_stats(world, final, read_question_docs(world.dir))


def read_question_docs(world_dir: Path) -> list[dict[str, Any]] | None:
    """The built gold question documents, in file-name order, or None if there are none."""
    files = sorted((Path(world_dir) / "gold" / "questions").glob("*.json"))
    return [read_json(f) for f in files] or None


def compute_stats(
    world: World, final_state: dict, question_docs: list[dict[str, Any]] | None
) -> dict:
    """Assemble every statistics section from a loaded world and its final gold state."""
    return {
        "world": world.id,
        "dates": _dates(world),
        "entities": _entities(world),
        "artifacts": _artifacts(world),
        "commitments": _commitment_flow(world, final_state),
        "loops": _loop_shape(world, final_state),
        "events_by_type": _sorted(Counter(str(e.get("type")) for e in world.events)),
        "challenges": _sorted(Counter(t for a in world.artifacts.values() for t in a.challenges)),
        "questions": _questions(question_docs),
    }


# ---------------------------------------------------------------- sections
def _dates(world: World) -> dict[str, Any]:
    return {
        "seed_start": world.seed_start,
        "seed_end": world.seed_end,
        "seed_delivery_days": len(world.seed_dates()),
        "episode_days": len(world.episode_days()),
        "checkpoints": len(world.checkpoints()),
        "final": world.all_dates()[-1],
    }


def _entities(world: World) -> dict[str, Any]:
    """Cast size (world). `in_loops` counts non-worker people named on any commitment."""
    creates = world.entity_events()
    people = [e for e in creates.values() if e.get("kind") == "person"]
    minor = [e for e in people if (e.get("attrs") or {}).get("_minor")]
    on_loops = {
        p
        for e in world.events
        if e.get("type") == "commitment.create"
        for p in [e.get("debtor"), e.get("creditor"), *(e.get("others") or [])]
    }
    return {
        "people": {
            "total": len(people),
            "non_minor": len(people) - len(minor),
            "minor": len(minor),
            "in_loops": len(on_loops & set(creates) - {world.worker}),
        },
        "orgs": sum(1 for e in creates.values() if e.get("kind") == "org"),
        "projects": sum(1 for e in creates.values() if e.get("kind") == "project"),
    }


def _artifacts(world: World) -> dict[str, Any]:
    """Inputs per delivery date by channel, and the share that is noise (world)."""
    arts = sorted(world.artifacts.values(), key=lambda a: (a.received_at, a.id))
    episode = set(world.episode_days())
    per_day: dict[str, dict[str, Any]] = {}
    for a in arts:
        day = per_day.setdefault(a.date, {"total": 0, "noise": 0, "by_channel": Counter()})
        day["total"] += 1
        day["noise"] += int(a.noise)
        day["by_channel"][a.channel] += 1
    for day in per_day.values():
        day["by_channel"] = _sorted(day["by_channel"])
    episode_counts = [per_day.get(d, {}).get("total", 0) for d in world.episode_days()]
    return {
        "total": len(arts),
        "seed": sum(1 for a in arts if a.date not in episode),
        "episode": sum(1 for a in arts if a.date in episode),
        "per_episode_day_mean": _mean(episode_counts),
        "noise_share": _share(sum(a.noise for a in arts), len(arts)),
        "by_channel": _sorted(Counter(a.channel for a in arts)),
        "per_day": dict(sorted(per_day.items())),
    }


def _commitment_flow(world: World, final_state: dict) -> dict[str, Any]:
    """Commitments created per day (world). The workday mean spans seed start to the last day."""
    created = Counter(date_of(e["t"]) for e in world.events if e.get("type") == "commitment.create")
    span = date_range(world.seed_start, world.all_dates()[-1])
    workdays = sum(1 for d in span if is_business_day(d))
    return {
        "total": sum(created.values()),
        "knowable_at_end": len(final_state["loops"]),
        "created_per_day": _sorted(created),
        "created_per_workday_mean": round(sum(created.values()) / workdays, 3) if workdays else 0.0,
    }


def _loop_shape(world: World, final_state: dict) -> dict[str, Any]:
    """Loop shape and status at the final date (gold: knowable loops and decisions only).

    Owner categories: `joint` when the commitment has `others`; otherwise `worker` when the
    worker is the debtor, else `others`. Lifetime is measured in business days from creation
    to the last change that closed the loop (done or dropped).
    """
    loops = list(final_state["loops"].values())
    decisions = list(final_state["decisions"].values())
    worker = final_state["worker"]
    lifetimes = [
        business_days_between(lp["created"], _closed_on(lp))
        for lp in loops
        if lp["status"] in CLOSED_STATUSES
    ]
    by_project = Counter(str(lp.get("project") or "(none)") for lp in loops)
    top2 = sum(n for _, n in by_project.most_common(2)) if loops else 0
    return {
        "commitments": len(loops),
        "decisions": len(decisions),
        "kind": _dist([lp["kind"] for lp in loops] + ["decision"] * len(decisions)),
        "owner": _dist([_owner_category(lp, worker) for lp in loops]),
        "basis": _dist([str(lp.get("basis")) for lp in loops]),
        "accepted_share": _share(sum(1 for lp in loops if lp["accepted"]), len(loops)),
        "suggested_at_create_share": _share(
            sum(1 for lp in loops if not _accepted_at_create(lp)), len(loops)
        ),
        "hard_due_share": _share(sum(1 for lp in loops if lp.get("due")), len(loops)),
        "final_status": _dist([lp["status"] for lp in loops]),
        "decision_status": _sorted(Counter(d["status"] for d in decisions)),
        "people_per_loop": _summary(
            [len({lp["debtor"], lp["creditor"], *lp.get("others", [])}) for lp in loops]
        ),
        "log_entries_per_loop": _summary([len(lp["history"]) for lp in loops]),
        "lifetime_business_days": _summary(lifetimes),
        "by_project": dict(sorted(by_project.items())),
        "top2_project_share": _share(top2, len(loops)),
    }


def _questions(docs: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Question mix from the built gold questions, or None before `wcb world build`."""
    if docs is None:
        return None
    qs = [q for d in docs for q in d.get("questions", [])]
    unanswerable = sum(1 for q in qs if not q.get("answerable", True))
    return {
        "total": len(qs),
        "by_checkpoint": {str(d.get("checkpoint")): len(d.get("questions", [])) for d in docs},
        "by_template": _sorted(Counter(str(q.get("template")) for q in qs)),
        "by_type": _sorted(Counter(str(q.get("type")) for q in qs)),
        "answerable": len(qs) - unanswerable,
        "unanswerable": unanswerable,
        "unanswerable_share": _share(unanswerable, len(qs)),
        "challenges": _sorted(Counter(t for q in qs for t in q.get("challenges") or [])),
    }


# ---------------------------------------------------------------- loop helpers
def _owner_category(loop: dict[str, Any], worker: str) -> str:
    if loop.get("others"):
        return "joint"
    return "worker" if loop["debtor"] == worker else "others"


def _accepted_at_create(loop: dict[str, Any]) -> bool:
    first = loop["history"][0]["changes"] if loop.get("history") else {}
    return bool(first.get("accepted", loop["accepted"]))


def _closed_on(loop: dict[str, Any]) -> str:
    closing = [h["date"] for h in loop["history"] if h["changes"].get("status") in CLOSED_STATUSES]
    return closing[-1] if closing else loop["updated"]


# ---------------------------------------------------------------- numeric helpers
def _dist(values: Iterable[str]) -> dict[str, Any]:
    """Counts and shares of each value: {"n", "counts", "shares"}."""
    counts = Counter(values)
    n = sum(counts.values())
    return {
        "n": n,
        "counts": _sorted(counts),
        "shares": {k: _share(v, n) for k, v in sorted(counts.items())},
    }


def _summary(values: list[float]) -> dict[str, Any]:
    """n, median, p75 and p90 (linear interpolation between closest ranks)."""
    xs = sorted(values)
    return {
        "n": len(xs),
        "median": _percentile(xs, 50),
        "p75": _percentile(xs, 75),
        "p90": _percentile(xs, 90),
    }


def _percentile(sorted_xs: list[float], p: float) -> float | None:
    if not sorted_xs:
        return None
    k = (len(sorted_xs) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(sorted_xs) - 1)
    return round(sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (k - lo), 3)


def _share(part: float, whole: float) -> float:
    return round(part / whole, 3) if whole else 0.0


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def _sorted(counter: Counter) -> dict[str, int]:
    return {str(k): v for k, v in sorted(counter.items(), key=lambda kv: str(kv[0]))}
