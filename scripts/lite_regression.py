#!/usr/bin/env python3
"""Rescore the saved lite runs with the current grader and gold, and diff against the baseline.

    python scripts/lite_regression.py                 # table + per-question changes vs baseline
    python scripts/lite_regression.py --write-baseline   # record the current scores as the baseline
    python scripts/lite_regression.py --allow-calls   # ask the panel for decisions not in the cache

The runs are the eight lite runs of 2026-11-21 (Claude Opus/Sonnet/Haiku 5.5 and GPT-6.1 Sol,
Tracks A and B, Pi harness), packed in results/2026-11-21-lite-model-comparison/regression/
lite-runs.tar.gz with only what scoring reads (answers, run.json, the checkpoint snapshot).
The configured cross-family panel uses Claude Sonnet 5.5 and GPT-6.1 Sol, one vote
each and no referee. The eight original per-run caches and a shared cache of new
raw outputs supply those same models’ votes. --allow-calls fills missing votes
through LiteLLM (OPENAI_BASE_URL and OPENAI_API_KEY or LITELLM_API_KEY), including
follow-up decisions that only become reachable after the first votes arrive.

Use it to check a grader or gold fix (GitHub issues #16-#30): every issue names the questions
whose scores should change. A fix passes when those questions move as stated and every other
change is explained.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wcb.grade.score as S  # noqa: E402
from wcb.grade.judge import DEFAULT_PANEL, LLMJudge, PanelJudge, load_cache  # noqa: E402
from wcb.grade.score import Accumulator, RunPlan, load_run_meta, score_world  # noqa: E402
from wcb.llm.client import make_client  # noqa: E402

HERE = ROOT / "results/2026-11-21-lite-model-comparison"
BUNDLE = HERE / "regression/lite-runs.tar.gz"
BASELINE = HERE / "regression/baseline.json"
CACHES = HERE / "rescored/v6-panel"
MODELS = ("opus", "sonnet", "haiku", "sol")
PANEL_CACHE = HERE / "regression/default-panel-cache.jsonl"


def weights(rows: list[dict]) -> None:
    """Headline weight per question: world mean of checkpoint means of bucket means (docs/scoring.md)."""
    by_cp: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_cp[(r["world"], r["checkpoint"])][r["bucket"]].append(r)
    n_cp: dict = defaultdict(int)
    for w, _ in by_cp:
        n_cp[w] += 1
    for (w, _), buckets in by_cp.items():
        for qs in buckets.values():
            for r in qs:
                r["w"] = 100 / len(qs) / len(buckets) / n_cp[w] / len(n_cp)


def rescore(runs: Path, model: str, track: str, allow_calls: bool, penalties: list | None = None) -> tuple[dict, int]:
    """Per-question scores and the number of configured-panel votes still missing."""
    cache = load_cache(CACHES / f"judge-cache-{model}-track-{track}.jsonl.gz")
    panel = PanelJudge([
        LLMJudge(make_client(spec), samples=1, cache_path=PANEL_CACHE)
        for spec in DEFAULT_PANEL.split(",")
    ])
    for judge in panel.panel:
        judge._cache.update(cache)
    run = runs / model / f"track-{track}/measured"
    meta = load_run_meta(run)
    for entry in meta["worlds"]:
        name = entry["id"]
        directory = ROOT / "worlds" / ("pilot" if name == "pilot" else f"dev/{name}")
        entry["path"] = str(directory)
    plan = RunPlan.from_meta(run, meta, suite="lite")
    while True:
        panel.recording(True)
        acc = Accumulator()
        for entry in plan.world_entries:
            score_world(plan, entry, panel, acc)
        uncached = sum(len(j.pending) for j in panel.judges)
        if not uncached or not allow_calls:
            break
        if not os.environ.get("OPENAI_BASE_URL") or not os.environ.get("OPENAI_API_KEY"):
            raise SystemExit("--allow-calls needs OPENAI_BASE_URL and OPENAI_API_KEY or LITELLM_API_KEY.")
        # A first-round vote can change assignments or trigger a second evidence review.
        # Persist each raw response as it arrives, then discover misses on the new path.
        panel.fetch_pending()
    if penalties is not None:
        for s in acc.scored:
            if s.store == "agent" and s.score.citation is not None:
                for invalid in s.score.details.get("citations", {}).get("invalid", []):
                    penalties.append({"arm": f"{model}-{track}", "world": s.world, "checkpoint": s.checkpoint,
                                      "qid": s.score.id, **invalid})
    rows = [s.row() for s in acc.scored if s.store == "agent"]
    weights(rows)
    return {f"{r['world']}/{r['checkpoint']}/{r['id']}": [round(r["score"], 4), r["w"]] for r in rows}, uncached


def sample_penalties(penalties: list[dict], n: int = 50, seed: int = 27) -> list[dict]:
    """Sample citation occurrences without replacement, with equal representation by arm."""
    arms = defaultdict(list)
    for row in penalties:
        arms[row["arm"]].append(row)
    rng = random.Random(seed)
    for arm in sorted(arms):
        arms[arm].sort(key=lambda r: (r["world"], r["checkpoint"], r["qid"], r["cite"], r.get("item", -1)))
        rng.shuffle(arms[arm])
    sample = []
    while len(sample) < n and any(arms.values()):
        for arm in sorted(arms):
            if arms[arm] and len(sample) < n:
                sample.append(arms[arm].pop())
    return sample


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write-baseline", action="store_true", help="save current scores as the baseline")
    ap.add_argument("--allow-calls", action="store_true", help="fetch decisions missing from the cache")
    ap.add_argument("--min-delta", type=float, default=0.00005, help="smallest per-question change to list")
    ap.add_argument("--citation-sample", type=Path, metavar="PATH", help="write 50 sampled residual citations to JSON")
    a = ap.parse_args()
    if a.allow_calls and not os.environ.get("OPENAI_API_KEY") and os.environ.get("LITELLM_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["LITELLM_API_KEY"]
    S.episode_sis = lambda *_, **__: None  # store integrity is not in the headline
    base = json.loads(BASELINE.read_text()) if BASELINE.is_file() else None
    out: dict = {}
    penalties = [] if a.citation_sample else None
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(BUNDLE) as tf:
            tf.extractall(tmp, filter="data")
        for m in MODELS:
            for t in "ab":
                qs, uncached = rescore(Path(tmp), m, t, a.allow_calls, penalties)
                head = 100 - sum(w * (1 - s) for s, w in qs.values())
                out[f"{m}-{t}"] = {"headline": round(head, 2), "uncached": uncached, "questions": qs}
    print(f"{'run':10s} {'baseline':>9s} {'now':>7s} {'delta':>7s} {'uncached':>9s}")
    for k, v in out.items():
        b = base[k]["headline"] if base else float("nan")
        print(f"{k:10s} {b:9.2f} {v['headline']:7.2f} {v['headline'] - b:+7.2f} {v['uncached']:9d}")
    if any(v["uncached"] for v in out.values()):
        print("\nuncached > 0: the change altered judge inputs; those decisions defaulted to the "
              "heuristic. Rerun with --allow-calls for exact scores.")
    if base and not a.write_baseline:
        print("\nper-question changes (score before -> after, headline points):")
        for k, v in out.items():
            for q, (s, w) in sorted(v["questions"].items()):
                s0 = base[k]["questions"].get(q, [None])[0]
                if s0 is None or abs(s - s0) >= a.min_delta:
                    print(f"  {k:8s} {q:32s} {s0 if s0 is not None else 'new':>6} -> {s:.4f}  "
                          f"({(s - (s0 or 0)) * w:+.2f})")
    if a.citation_sample and penalties is not None:
        a.citation_sample.write_text(json.dumps(sample_penalties(penalties), indent=2) + "\n")
    if a.write_baseline and any(v["uncached"] for v in out.values()):
        print("Baseline retained because configured-panel votes are missing.")
        return 1
    if a.write_baseline:
        BASELINE.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(f"\nwrote {BASELINE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
