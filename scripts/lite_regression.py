#!/usr/bin/env python3
"""Rescore the saved lite runs with the current grader and gold, and diff against the baseline.

    python scripts/lite_regression.py                 # table + per-question changes vs baseline
    python scripts/lite_regression.py --write-baseline   # record the current scores as the baseline
    python scripts/lite_regression.py --allow-calls   # ask the panel for decisions not in the cache

The runs are the eight lite runs of 2026-11-21 (Claude Opus/Sonnet/Haiku 5.5 and GPT-6.1 Sol,
Tracks A and B, Pi harness), packed in results/2026-11-21-lite-model-comparison/regression/
lite-runs.tar.gz with only what scoring reads (answers, run.json, the checkpoint snapshot).
Panel decisions come from the committed judge caches (rescored/v6-panel/*.jsonl.gz), so a
rescore makes no model calls. Changed prompts from the high-severity fixes use the independent
Luna/Sol in-session votes in regression/subscription-panel.jsonl. Other missing decisions
are counted as `uncached`; with --allow-calls they are fetched (needs OPENAI_BASE_URL and
OPENAI_API_KEY for the panel models, see docs/judge.md) and the cache is extended.

Use it to check a grader or gold fix (GitHub issues #16-#30): every issue names the questions
whose scores should change. A fix passes when those questions move as stated and every other
change is explained.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wcb.grade.score as S  # noqa: E402
from wcb.grade.judge import (  # noqa: E402
    SYSTEM_PROMPT,
    LLMJudge,
    PanelJudge,
    majority,
    parse_verdict,
    parse_yes_no,
)
from wcb.grade.score import Accumulator, RunPlan, load_run_meta, score_world  # noqa: E402
from wcb.llm.client import make_client  # noqa: E402

HERE = ROOT / "results/2026-11-21-lite-model-comparison"
BUNDLE = HERE / "regression/lite-runs.tar.gz"
BASELINE = HERE / "regression/baseline.json"
CACHES = HERE / "rescored/v6-panel"
MODELS = ("opus", "sonnet", "haiku", "sol")
PANEL = ("openai:claude-sonnet-5.5", "openai:gpt-6.1-sol")


class ReplayJudge(LLMJudge):
    """Look up a replacement panelist's recorded vote only on an original cache miss."""

    def __init__(self, original, replacement, supplement):
        super().__init__(make_client(original), samples=1)
        self.replacement = replacement
        self.supplement = supplement

    def _decide(self, what, prompt, parse, tie_order):
        if self.cache_key(prompt) not in self._cache:
            fingerprint = hashlib.sha256((SYSTEM_PROMPT + "\n" + prompt).encode()).hexdigest()
            row = self.supplement.get(fingerprint)
            if row and row["kind"] == what and row["prompt"] == prompt:
                return parse(row["votes"][self.replacement])
        return super()._decide(what, prompt, parse, tie_order)


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


def cached_decisions(path: Path) -> dict:
    """{key: decision}, re-derived from each row's raw judge outputs with the current parsers,
    so a parser change (e.g. #26) takes effect without new calls."""
    out = {}
    for line in gzip.decompress(path.read_bytes()).decode("utf-8").splitlines():
        row = json.loads(line)
        if row["kind"] == "rubric":
            vals, tie = [parse_verdict(o) for o in row["outputs"]], ("missing", "covered", "contradicted")
        else:
            vals, tie = [parse_yes_no(o) for o in row["outputs"]], (False, True)
        out[row["key"]] = majority(vals, tie)
    return out


def rescore(runs: Path, model: str, track: str, allow_calls: bool) -> tuple[dict, int]:
    """Per-question scores {key: score} (agent store) and the number of uncached decisions."""
    cache = cached_decisions(CACHES / f"judge-cache-{model}-track-{track}.jsonl.gz")
    supplement = {}
    for line in (HERE / "regression/subscription-panel.jsonl").read_text().splitlines():
        row = json.loads(line)
        supplement[row["id"]] = row
    panel = PanelJudge([ReplayJudge(original, replacement, supplement)
                        for original, replacement in zip(PANEL, ("gpt-6-luna", "gpt-6.1-sol"), strict=True)])
    for j in panel.panel:
        j._cache.update(cache)
    run = runs / model / f"track-{track}/measured"
    meta = load_run_meta(run)
    for entry in meta["worlds"]:
        name = entry["id"]
        directory = ROOT / "worlds" / ("pilot" if name == "pilot" else f"dev/{name}")
        entry["path"] = str(directory)
    plan = RunPlan.from_meta(run, meta, suite="lite")
    panel.recording(True)
    for entry in plan.world_entries:
        score_world(plan, entry, panel, Accumulator())
    uncached = sum(len(j.pending) for j in panel.panel)
    if uncached and allow_calls:
        # New decisions go to a side file next to the committed cache; merge it by hand.
        for j in panel.panel:
            j.cache_path = CACHES / f"judge-cache-{model}-track-{track}.new.jsonl"
        panel.fetch_pending()
        panel.recording(False)
    # Without --allow-calls, recording stays on: an uncached decision returns the heuristic's
    # default (the panel's tie order) instead of calling a model.
    acc = Accumulator()
    for entry in plan.world_entries:
        score_world(plan, entry, panel, acc)
    rows = [s.row() for s in acc.scored if s.store == "agent"]
    weights(rows)
    return {f"{r['world']}/{r['checkpoint']}/{r['id']}": [round(r["score"], 4), r["w"]] for r in rows}, uncached


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write-baseline", action="store_true", help="save current scores as the baseline")
    ap.add_argument("--allow-calls", action="store_true", help="fetch decisions missing from the cache")
    ap.add_argument("--min-delta", type=float, default=0.01, help="smallest per-question change to list")
    a = ap.parse_args()
    S.episode_sis = lambda *_, **__: None  # store integrity is not in the headline
    base = json.loads(BASELINE.read_text()) if BASELINE.is_file() else None
    out: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(BUNDLE) as tf:
            tf.extractall(tmp, filter="data")
        for m in MODELS:
            for t in "ab":
                qs, uncached = rescore(Path(tmp), m, t, a.allow_calls)
                head = 100 - sum(w * (1 - s) for s, w in qs.values())
                out[f"{m}-{t}"] = {"headline": round(head, 2), "uncached": uncached, "questions": qs}
    print(f"{'run':10s} {'baseline':>9s} {'now':>7s} {'delta':>7s} {'uncached':>9s}")
    for k, v in out.items():
        b = base[k]["headline"] if base else float("nan")
        print(f"{k:10s} {b:9.2f} {v['headline']:7.2f} {v['headline'] - b:+7.2f} {v['uncached']:9d}")
    if any(v["uncached"] for v in out.values()) and not a.allow_calls:
        print("\nuncached > 0: the change altered judge inputs; those decisions defaulted to the "
              "heuristic. Rerun with --allow-calls for exact scores.")
    if base and not a.write_baseline:
        print("\nper-question changes (score before -> after, headline points):")
        for k, v in out.items():
            for q, (s, w) in sorted(v["questions"].items()):
                s0 = base[k]["questions"].get(q, [None])[0]
                if s0 is None or abs(s - s0) >= a.min_delta:
                    print(f"  {k:8s} {q:32s} {s0 if s0 is not None else 'new':>6} -> {s:.3f}  "
                          f"({(s - (s0 or 0)) * w:+.2f})")
    if a.write_baseline and any(v["uncached"] for v in out.values()) and not a.allow_calls:
        print("Baseline retained because the panel replay is incomplete.")
        return 1
    if a.write_baseline:
        BASELINE.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(f"\nwrote {BASELINE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
