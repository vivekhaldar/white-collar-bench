#!/usr/bin/env python3
"""How well reduced suites (wcb/suites.py) reproduce full-run results, from saved score reports.

    python scripts/suite_fidelity.py results/<run-a> results/<run-b> [...]

Each argument is a directory holding `scores-track-a.json` and/or `scores-track-b.json` (a
`report.json` from `wcb score`, as kept under results/). For every suite it recomputes, from
the per-question rows, the score the run would have had as that suite, the agent-session cost
of the days and checkpoints the suite plays, and the error against the full score. With two or
more runs it also reports the error in every pairwise gap (run X minus run Y, per track), which
is what a comparison relies on. No model calls; docs/lite.md records the output.
"""

from __future__ import annotations

import itertools
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wcb.suites import SUITES  # noqa: E402


def view(report: dict, suite) -> tuple[float, float]:
    """(score, agent-session cost in USD) of `report` restricted to `suite` (None: full run)."""
    worlds = {w["id"]: w for w in report["worlds"]}
    keep = set(suite.world_ids) if suite else set(worlds)
    last = {w: worlds[w]["days"][(suite.max_days if suite else len(worlds[w]["days"])) - 1]
            for w in keep}  # fmt: skip
    cps = {(w, c["id"]) for w in keep for c in worlds[w]["checkpoints"] if c["date"] <= last[w]}
    by = defaultdict(lambda: defaultdict(list))
    for q in report["questions"]:
        if q["store"] == "agent" and (q["world"], q["checkpoint"]) in cps:
            by[(q["world"], q["checkpoint"])][q["bucket"]].append(q["score"])
    per_world = defaultdict(list)
    for (w, _), buckets in by.items():
        per_world[w].append(st.mean(st.mean(v) for v in buckets.values()))
    score = 100 * st.mean(st.mean(v) for v in per_world.values())
    eff = report["efficiency"]
    cost = sum(d["cost_usd"] or 0 for d in eff["per_ingest_day"]
               if d["world"] in keep and d["date"] <= last[d["world"]])  # fmt: skip
    cost += sum(d["cost_usd"] or 0 for d in eff["per_query_session"]
                if d.get("store") != "oracle" and (d["world"], d["checkpoint"]) in cps)  # fmt: skip
    return score, cost


def main(argv: list[str]) -> int:
    runs = {}
    for arg in argv:
        for track in ("a", "b"):
            f = Path(arg) / f"scores-track-{track}.json"
            if f.is_file():
                runs[(Path(arg).name, track.upper())] = json.loads(f.read_text("utf-8"))
    if not runs:
        print(__doc__)
        return 2
    suites = {"full": None, **SUITES}
    res = {(s, k): view(r, suite) for s, suite in suites.items() for k, r in runs.items()}

    print("| Run | Track | " + " | ".join(f"{s} score" for s in suites) + " | "
          + " | ".join(f"{s} $" for s in suites) + " |")  # fmt: skip
    print("|---|---|" + "---:|" * (2 * len(suites)))
    for name, track in runs:
        k = (name, track)
        print(f"| {name} | {track} | " + " | ".join(f"{res[(s, k)][0]:.1f}" for s in suites)
              + " | " + " | ".join(f"{res[(s, k)][1]:.2f}" for s in suites) + " |")  # fmt: skip

    print("\nScore error (suite - full) and pairwise gap error, per track:")
    for s in SUITES:
        errs = [res[(s, k)][0] - res[("full", k)][0] for k in runs]
        line = f"- {s}: score error {min(errs):+.1f} to {max(errs):+.1f}"
        gaps = []
        for (x, tx), (y, ty) in itertools.combinations(runs, 2):
            if tx != ty:
                continue
            lite = res[(s, (x, tx))][0] - res[(s, (y, ty))][0]
            full = res[("full", (x, tx))][0] - res[("full", (y, ty))][0]
            gaps.append(f"{x} - {y} track {tx}: full {full:+.1f}, {s} {lite:+.1f} "
                        f"(error {lite - full:+.1f})")  # fmt: skip
        print(line)
        for g in gaps:
            print(f"    {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
