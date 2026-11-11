#!/usr/bin/env python3
"""Regrade saved point answers with the current point grader, to measure a grader change.

    python scripts/regrade_points.py                       # the Qwen3.8-27B + Pi evidence
    python scripts/regrade_points.py --all                 # also print unchanged results
    python scripts/regrade_points.py --json out.json       # write every row as JSON

Reads point answers from the evidence files of a results directory (default
`results/2026-11-11-qwen3.8-27b-pi/evidence`):

* `track-a-nine-false-negatives.json`: `changes[]` (Track A, agent store);
* `track-b-scorer-examples.json`: `examples[]` of type point (Track B);
* `track-b-scorer-diagnostics.json`: `zero_nonabstaining_points[]` (Track B).

Each answer is graded by `wcb.grade.answers.grade_point` against the question of the same
world, checkpoint and ID in the current gold files (build them first with
`wcb world build --all --if-stale`). Questions whose text no longer matches the saved one
(regenerated worlds) are reported as `stale` and not graded. Only the base score is
computed: citations are a separate concern. Every saved answer scored 0 originally, so the
rows printed by default are the ones the current grader credits.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wcb.grade.answers import ScoreContext, grade_point  # noqa: E402
from wcb.grade.judge import HeuristicJudge  # noqa: E402
from wcb.world.model import World  # noqa: E402

DEFAULT_EVIDENCE = ROOT / "results" / "2026-11-11-qwen3.8-27b-pi" / "evidence"


def candidates(evidence: Path) -> list[dict]:
    """Saved point answers: {track, world, checkpoint, id, question (or gold), answer}."""
    out = []
    path = evidence / "track-a-nine-false-negatives.json"
    if path.exists():
        for c in json.loads(path.read_text())["changes"]:
            out.append(
                {
                    "track": "A",
                    "world": c["world"],
                    "checkpoint": c["checkpoint"],
                    "id": c["question"],
                    "question": None,
                    "gold": c["gold_value"],
                    "answer": c["original_answer"],
                }
            )
    path = evidence / "track-b-scorer-examples.json"
    if path.exists():
        doc = json.loads(path.read_text())
        for ex in doc["examples"]:
            if ex["actual_answer"].get("type") == "point":
                out.append(
                    {
                        "track": "B",
                        "world": doc["world"],
                        "checkpoint": doc["checkpoint"],
                        "id": ex["id"],
                        "question": ex["question"],
                        "answer": ex["actual_answer"],
                    }
                )
    path = evidence / "track-b-scorer-diagnostics.json"
    if path.exists():
        for c in json.loads(path.read_text())["zero_nonabstaining_points"]:
            out.append(
                {
                    "track": "B",
                    "world": c["world"],
                    "checkpoint": c["checkpoint"],
                    "id": c["id"],
                    "question": c["question"],
                    "answer": c["predicted"],
                }
            )
    seen, unique = set(), []
    for c in out:
        key = (c["track"], c["world"], c["checkpoint"], c["id"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def world_root(world_id: str) -> Path:
    return ROOT / "worlds" / ("pilot" if world_id == "pilot" else f"dev/{world_id}")


def regrade(cands: list[dict]) -> list[dict]:
    judge = HeuristicJudge()
    worlds: dict[str, World] = {}
    rows = []
    for c in cands:
        root = world_root(c["world"])
        doc = json.loads((root / "gold" / "questions" / f"{c['checkpoint']}.json").read_text())
        q = next((q for q in doc["questions"] if q["id"] == c["id"]), None)
        row = {k: c[k] for k in ("track", "world", "checkpoint", "id")}
        row["value"] = c["answer"].get("value")
        if (
            q is None
            or (c["question"] is not None and q["text"] != c["question"])
            or ("gold" in c and (q.get("gold") or {}).get("value") != c["gold"])
        ):
            rows.append({**row, "status": "stale"})
            continue
        if c["world"] not in worlds:
            worlds[c["world"]] = World.load(root)
        state = json.loads((root / "gold" / "state" / f"{doc['date']}.json").read_text())
        ctx = ScoreContext.from_state(worlds[c["world"]], state)
        base, details = grade_point(q, c["answer"], judge, ctx)
        details.pop("value", None)
        rows.append(
            {
                **row,
                "status": "graded",
                "question": q["text"],
                "template": q.get("template"),
                "gold": (q.get("gold") or {}).get("value"),
                "base": base,
                "details": details,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    ap.add_argument("--all", action="store_true", help="also print answers still scoring 0")
    ap.add_argument("--json", type=Path, help="write every row to this file")
    args = ap.parse_args(argv)
    rows = regrade(candidates(args.evidence))
    graded = [r for r in rows if r["status"] == "graded"]
    credited = [r for r in graded if r["base"] > 0]
    for r in rows:
        if r["status"] == "graded" and (args.all or r["base"] > 0):
            print(
                f"{r['base']:.0f} {r['track']} {r['world']} {r['checkpoint']} {r['id']} "
                f"[{r['template']}] {r['question']}\n    gold:  {r['gold']}\n"
                f"    value: {r['value']}\n    details: {json.dumps(r['details'])}"
            )
    stale = [r for r in rows if r["status"] == "stale"]
    for r in stale:
        print(f"stale {r['track']} {r['world']} {r['checkpoint']} {r['id']}")
    print(f"{len(rows)} answers, {len(graded)} graded, {len(stale)} stale, {len(credited)} credited")
    if args.json:
        args.json.write_text(json.dumps(rows, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
