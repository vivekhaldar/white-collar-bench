"""Judge agreement: sample judge decisions, label them, and measure agreement (plan milestone M4).

Grading needs two kinds of judgement (docs/judge.md): `same_item` (does a predicted list or
change item describe the same thing as a gold item?) and `rubric` (does an answer cover a
checklist item: covered, missing or contradicted?). This module measures how often judges agree
with each other and with people on those decisions:

1. `collect_decisions(run_dirs)` re-grades scored runs with a recording heuristic judge and
   returns every distinct decision it was asked for, with the heuristic verdict.
2. `sample_decisions(decisions, n, seed)` draws a stratified sample: both decision kinds, and
   within each kind every verdict the heuristic gave, as evenly as the pool allows.
3. Labels are added per labeller: `label_with_judge` for a judge (the LLM judge, say), and
   `wcb judge label` for a person, who sees exactly the prompt the LLM judge sees and never the
   other labels.
4. `agreement(records)` reports Cohen's kappa and raw agreement for every pair of labellers,
   per decision kind.

A sample file is JSONL: one decision per line with `id`, `kind`, `inputs` and `labels`
(labeller name to verdict: `true`/`false` for `same_item`, `covered`/`missing`/`contradicted`
for `rubric`; `null` while unlabelled).
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

from wcb.grade.judge import HeuristicJudge, rubric_prompt, same_item_prompt

KINDS = ("same_item", "rubric")
RUBRIC_VERDICTS = ("covered", "missing", "contradicted")


# ---------------------------------------------------------------- collecting
@dataclass
class RecordingJudge:
    """Wraps a judge and records each distinct decision it makes."""

    inner: Any = field(default_factory=HeuristicJudge)
    records: dict[str, dict] = field(default_factory=dict)
    label: str = "heuristic"

    @property
    def name(self) -> str:
        return getattr(self.inner, "name", self.label)

    def same_item(self, pred: dict, gold: dict, *, kind: str) -> bool:
        verdict = bool(self.inner.same_item(pred, gold, kind=kind))
        self._add("same_item", {"pred": pred, "gold": gold, "kind": kind}, verdict)
        return verdict

    def rubric(self, answer_text: str, item: dict, facts: dict) -> str:
        verdict = self.inner.rubric(answer_text, item, facts)
        self._add("rubric", {"answer_text": answer_text, "item": item, "facts": facts}, verdict)
        return verdict

    def _add(self, kind: str, inputs: dict, verdict: Any) -> None:
        rid = decision_id(kind, inputs)
        if rid not in self.records:
            self.records[rid] = {"id": rid, "kind": kind, "inputs": inputs,
                                 "labels": {self.label: verdict}}


def decision_id(kind: str, inputs: dict) -> str:
    """Stable ID of a decision: a hash of exactly what a judge is shown."""
    return hashlib.sha256(prompt_for({"kind": kind, "inputs": inputs}).encode()).hexdigest()[:16]


def collect_decisions(run_dirs: list[Path]) -> list[dict]:
    """Every distinct judge decision made while grading the runs, with the heuristic verdict."""
    from wcb.grade.score import Accumulator, RunPlan, load_run_meta, score_world

    rec = RecordingJudge()
    for run_dir in run_dirs:
        run_dir = Path(run_dir)
        plan = RunPlan.from_meta(run_dir, load_run_meta(run_dir))
        for entry in plan.world_entries:
            score_world(plan, entry, rec, Accumulator())
    return sorted(rec.records.values(), key=lambda r: r["id"])


# ---------------------------------------------------------------- sampling
def sample_decisions(decisions: list[dict], n: int, seed: int = 0) -> list[dict]:
    """Up to `n` decisions, split evenly between kinds and, within a kind, between the
    heuristic's verdicts (so rare verdicts such as `contradicted` are represented)."""
    rng = random.Random(seed)
    strata: dict[str, dict[str, list[dict]]] = {}
    for d in decisions:
        verdict = json.dumps(d["labels"].get("heuristic"))
        strata.setdefault(d["kind"], {}).setdefault(verdict, []).append(d)
    for by_verdict in strata.values():
        for pool in by_verdict.values():
            rng.shuffle(pool)
    out: list[dict] = []
    kinds = sorted(strata)
    for i, kind in enumerate(kinds):
        quota = (n - len(out)) // (len(kinds) - i)
        out += _round_robin(strata[kind], quota)
    return sorted(out, key=lambda d: d["id"])


def _round_robin(by_verdict: dict[str, list[dict]], quota: int) -> list[dict]:
    pools = [list(v) for _, v in sorted(by_verdict.items())]
    out: list[dict] = []
    while len(out) < quota and any(pools):
        for pool in pools:
            if pool and len(out) < quota:
                out.append(pool.pop())
    return out


# ---------------------------------------------------------------- labelling
def prompt_for(record: dict) -> str:
    """The text a labeller sees: the LLM judge's prompt for this decision."""
    i = record["inputs"]
    if record["kind"] == "same_item":
        return same_item_prompt(i["pred"], i["gold"], i["kind"])
    return rubric_prompt(i["answer_text"], i["item"], i["facts"])


def label_with_judge(records: list[dict], judge: Any, name: str,
                     progress: Callable[[int, int], None] | None = None) -> int:
    """Add `name`'s verdict to every record that lacks one. Returns how many were labelled."""
    todo = [r for r in records if r["labels"].get(name) is None]
    for k, r in enumerate(todo, 1):
        i = r["inputs"]
        if r["kind"] == "same_item":
            r["labels"][name] = bool(judge.same_item(i["pred"], i["gold"], kind=i["kind"]))
        else:
            r["labels"][name] = judge.rubric(i["answer_text"], i["item"], i["facts"])
        if progress:
            progress(k, len(todo))
    return len(todo)


def parse_human_label(kind: str, text: str) -> bool | str | None:
    """A typed answer as a verdict: y/n for same_item; c/m/x for rubric. None if unrecognized."""
    t = text.strip().lower()
    if kind == "same_item":
        return {"y": True, "yes": True, "n": False, "no": False}.get(t)
    return {"c": "covered", "covered": "covered", "m": "missing", "missing": "missing",
            "x": "contradicted", "contradicted": "contradicted"}.get(t)


def read_sample(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def write_sample(path: Path, records: list[dict]) -> None:
    """Write atomically, so an interrupted labelling session never truncates the file."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"
                           for r in records), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------- agreement
def cohen_kappa(a: list[Any], b: list[Any]) -> float | None:
    """Cohen's kappa for two raters' paired labels. None if undefined (no items, or both raters
    always gave the same single label, in which case chance agreement is 1)."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    cats = sorted({json.dumps(x) for x in a} | {json.dumps(x) for x in b})
    ka = [json.dumps(x) for x in a]
    kb = [json.dumps(x) for x in b]
    po = sum(x == y for x, y in zip(ka, kb, strict=True)) / n
    pe = sum((ka.count(c) / n) * (kb.count(c) / n) for c in cats)
    if pe >= 1.0:
        return None
    return (po - pe) / (1 - pe)


def agreement(records: list[dict]) -> list[dict]:
    """Pairwise agreement between labellers, per decision kind: n, raw agreement, kappa, and
    the confusion counts (`"<a's verdict> / <b's verdict>"`)."""
    rows = []
    for kind in KINDS:
        recs = [r for r in records if r["kind"] == kind]
        names = sorted({k for r in recs for k, v in r["labels"].items() if v is not None})
        for x, y in combinations(names, 2):
            pairs = [(r["labels"][x], r["labels"][y]) for r in recs
                     if r["labels"].get(x) is not None and r["labels"].get(y) is not None]
            if not pairs:
                continue
            a, b = [p[0] for p in pairs], [p[1] for p in pairs]
            confusion: dict[str, int] = {}
            for p, q in pairs:
                key = f"{_short(p)} / {_short(q)}"
                confusion[key] = confusion.get(key, 0) + 1
            rows.append({
                "kind": kind, "a": x, "b": y, "n": len(pairs),
                "agreement": sum(p == q for p, q in pairs) / len(pairs),
                "kappa": cohen_kappa(a, b),
                "confusion": dict(sorted(confusion.items())),
            })
    return rows


def _short(v: Any) -> str:
    return {True: "yes", False: "no"}.get(v, str(v)) if isinstance(v, bool) else str(v)


def format_agreement(rows: list[dict], target: float = 0.8) -> str:
    """A plain-text table; pairs below the target kappa are marked."""
    if not rows:
        return "no pair of labellers has labelled the same decisions yet"
    lines = [f"{'kind':10} {'labellers':32} {'n':>4} {'agree':>6} {'kappa':>6}"]
    for r in rows:
        k = "n/a" if r["kappa"] is None else f"{r['kappa']:.2f}"
        flag = "" if r["kappa"] is None or r["kappa"] >= target else f"  < {target}"
        pair = f"{r['a']} vs {r['b']}"
        lines.append(f"{r['kind']:10} {pair:32} {r['n']:>4} {r['agreement']:>6.0%} {k:>6}{flag}")
        lines.append("           " + ", ".join(f"{c}: {n}" for c, n in r["confusion"].items()))
    return "\n".join(lines)
