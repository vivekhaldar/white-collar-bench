#!/usr/bin/env python3
"""Summarize the Claude Opus 5.5 lite/micro run (copied from the GPT-6.1 Sol run's analyze.py): scores, loss decomposition, failures, tokens, cost.

WCB_SCORES selects the reports: `scores` (the scorer the run was made with) or `scores-fixed`
(rescored with the date-history and acceptance-hedge fixes; the default here).

    python results/2026-11-21-claude-opus-5.5-pi-lite/analyze.py [runs/claude-opus-5.5-pi-lite] > out.md

Reads `<base>/<model>/track-<t>/scores-<suite>/report.json` (written by config/run_all.py)
plus the raw answers, gold questions and metering logs of the measured runs. Losses use the
headline weights (bucket within checkpoint, checkpoint within world, world), so the components
of a run add up to 100 minus its score. Cost is computed from metered tokens at LiteLLM's
listed prices; the agent's self-reported cost is shown next to it.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "runs/claude-opus-5.5-pi-lite"
MODELS = {"opus": "claude-opus-5.5"}
SCORES = os.environ.get("WCB_SCORES", "scores-fixed")
PRICES = {  # USD per million tokens (LiteLLM /model/info)
    "claude-haiku-5.5": dict(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125),
    "claude-sonnet-5.5": dict(input=2.0, output=10.0, cache_read=0.10, cache_write=2.5),
    "gpt-6.1-sol": dict(input=2.0, output=10.0, cache_read=0.10, cache_write=2.5),
    "claude-opus-5.5": dict(input=4.0, output=20.0, cache_read=0.20, cache_write=5.0),
}
BUCKETS = ("point", "list", "status", "brief", "change", "temporal", "priority", "unanswerable")
COMPONENTS = ("invalid", "wrong_abstention", "answered_unanswerable", "base_zero",
              "base_partial", "citation_penalty")  # fmt: skip


def report(model, track, suite):
    f = BASE / model / f"track-{track.lower()}" / f"{SCORES}-{suite}" / "report.json"
    return json.loads(f.read_text()) if f.is_file() else None


def weighted(rows):
    by_cp = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_cp[(r["world"], r["checkpoint"])][r["bucket"]].append(r)
    n_cp = defaultdict(int)
    for w, _ in by_cp:
        n_cp[w] += 1
    for (w, _), buckets in by_cp.items():
        for qs in buckets.values():
            for r in qs:
                r["w"] = 100 / len(qs) / len(buckets) / n_cp[w] / len(n_cp)
    return rows


def components(r):
    loss = 1 - r["score"]
    if not r["valid"]:
        return {"invalid": loss}
    if not r["answerable"]:
        return {"answered_unanswerable": loss} if loss > 0 else {}
    if r["abstained"]:
        return {"wrong_abstention": loss}
    out = {}
    if r["base"] < 1:
        out["base_zero" if r["base"] == 0 else "base_partial"] = 1 - r["base"]
    if r["base"] - r["score"] > 1e-12:
        out["citation_penalty"] = r["base"] - r["score"]
    return out


def metered(run_dir, worlds, last_day):
    """Metered tokens and calls of agent sessions within the suite (oracle sessions separate)."""
    tot = defaultdict(lambda: defaultdict(float))
    for line in (run_dir / "meter.jsonl").read_text().splitlines():
        r = json.loads(line)
        world, _, session, _ = r["tag"].split("/", 3)
        if world not in worlds:
            continue
        date_or_cp = session.split(".")[0]
        group = "oracle" if session.endswith("query-oracle") else (
            "query" if ".query" in session else "ingest")  # fmt: skip
        if group == "ingest" and date_or_cp != "seed" and date_or_cp > last_day[world]:
            continue
        if group != "ingest" and date_or_cp not in worlds[world]:
            continue
        u = r.get("usage") or {}
        g = tot[group]
        g["calls"] += 1
        g["errors"] += not (200 <= int(r.get("status") or 0) < 300)
        for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                  "cache_creation_input_tokens"):  # fmt: skip
            g[k] += u.get(k) or 0
    return tot


def cost(g, model):
    p = PRICES[model]
    return (g["input_tokens"] * p["input"] + g["output_tokens"] * p["output"]
            + g["cache_read_input_tokens"] * p["cache_read"]
            + g["cache_creation_input_tokens"] * p["cache_write"]) / 1e6  # fmt: skip


def gold_and_answers(rep, run_dir, row):
    world = next(w for w in rep["worlds"] if w["id"] == row["world"])
    gold = json.loads((Path(world["path"]) / "gold/questions" / f"{row['checkpoint']}.json").read_text())
    g = next(q for q in gold["questions"] if q["id"] == row["id"])
    suffix = ".oracle.json" if row["store"] == "oracle" else ".json"
    ans_f = run_dir / row["world"] / f"r{row['repeat']}" / "answers" / f"{row['checkpoint']}{suffix}"
    a = json.loads(ans_f.read_text()).get(row["id"]) if ans_f.is_file() else None
    return g, a


def short(x, n=220):
    s = json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x
    return s if len(s) <= n else s[: n - 1] + "…"


def gist(g, a):
    """Compact gold vs predicted text for a failure line."""
    gold = g.get("gold")
    if not g.get("answerable", True):
        gold_s = "abstain"
    elif isinstance(gold, dict) and "value" in gold:
        gold_s = gold["value"]
    elif isinstance(gold, dict) and "items" in gold:
        gold_s = "; ".join(i.get("what") or i.get("summary") or "" for i in gold["items"]) or "[]"
    elif isinstance(gold, dict) and "rubric" in gold:
        gold_s = "; ".join(i["text"] for i in gold["rubric"])
    elif isinstance(gold, dict) and "must_include" in gold:
        gold_s = "; ".join(i["what"] for i in gold["must_include"])
    elif isinstance(gold, dict) and "date" in gold:
        gold_s = gold["date"]
    else:
        gold_s = short(gold)
    if a is None:
        pred = "(no answer)"
    elif a.get("abstain"):
        pred = "abstain"
    elif "value" in a:
        pred = str(a["value"])
    elif "items" in a:
        pred = "; ".join(i.get("text", "") for i in a["items"]) or "[]"
    elif "summary" in a:
        pred = a["summary"]
    elif "date" in a:
        pred = a["date"]
    else:
        pred = short(a)
    return short(gold_s, 160), short(pred, 200)


def main():
    out = []
    p = out.append
    runs = {(m, t): report(m, t, "lite") for m in MODELS for t in "AB"}
    runs = {k: v for k, v in runs.items() if v}
    p("## Headline\n")
    p("| Model | Track | WCB-lite | 95% CI | WCB-micro | Synthesis (lite) | SIS (lite) |")
    p("|---|---|---:|---|---:|---:|---:|")
    for (m, t), rep in runs.items():
        mic = report(m, t, "micro")
        h, hm = rep["headline"], (mic or {}).get("headline", {})
        ci = h.get("wcb_ci95") or [None, None]
        fmt = lambda x: "–" if x is None else f"{x:.1f}"  # noqa: E731
        p(f"| {m} | {t} | {fmt(h['wcb'])} | {fmt(ci[0])}–{fmt(ci[1])} | {fmt(hm.get('wcb'))} "
          f"| {fmt(h.get('synthesis'))} | {fmt(h.get('sis'))} |")  # fmt: skip

    p("\n## Per world (WCB-lite world score)\n")
    worlds = [w["id"] for w in next(iter(runs.values()))["worlds"]]
    p("| World | " + " | ".join(f"{m} {t}" for m, t in runs) + " |")
    p("|---|" + "---:|" * len(runs))
    for w in worlds:
        cells = []
        for rep in runs.values():
            ws = next((x for x in rep["worlds"] if x["id"] == w), None)
            cells.append(f"{ws['score']:.1f}" if ws and ws["score"] is not None else "–")
        p(f"| {w} | " + " | ".join(cells) + " |")

    p("\n## By bucket (mean question score; agent store, oracle store in brackets for A)\n")
    p("| Bucket | " + " | ".join(f"{m} {t}" for m, t in runs) + " |")
    p("|---|" + "---:|" * len(runs))
    for b in BUCKETS:
        cells = []
        for rep in runs.values():
            bt = rep["breakdowns"]["by_type"].get(b, {})
            s = bt.get("wcb")
            o = bt.get("synthesis")
            cells.append(("–" if s is None else f"{s / 100:.2f}")
                         + (f" ({o / 100:.2f})" if o is not None else ""))  # fmt: skip
        p(f"| {b} | " + " | ".join(cells) + " |")

    p("\n## Loss decomposition (WCB-lite points; questions affected)\n")
    p("| Model | Track | Lost | " + " | ".join(COMPONENTS) + " |")
    p("|---|---|---:|" + "---:|" * len(COMPONENTS))
    for (m, t), rep in runs.items():
        for store in ("agent", "oracle"):
            rows = weighted([dict(r) for r in rep["questions"] if r["store"] == store])
            if not rows:
                continue
            agg, cnt = defaultdict(float), defaultdict(int)
            for r in rows:
                for c, v in components(r).items():
                    agg[c] += r["w"] * v
                    cnt[c] += 1
            label = t if store == "agent" else f"{t} oracle"
            p(f"| {m} | {label} | {sum(agg.values()):.2f} | "
              + " | ".join(f"{agg[c]:.2f} ({cnt[c]})" for c in COMPONENTS) + " |")  # fmt: skip

    p("\n## By planted challenge (mean agent score; tags overlap)\n")
    tags = sorted({c for rep in runs.values() for r in rep["questions"] for c in r["challenges"]})
    p("| Challenge | n | " + " | ".join(f"{m} {t}" for m, t in runs) + " |")
    p("|---|---:|" + "---:|" * len(runs))
    for tag in tags:
        cells, n = [], 0
        for rep in runs.values():
            xs = [r["score"] for r in rep["questions"] if r["store"] == "agent" and tag in r["challenges"]]
            n = max(n, len(xs))
            cells.append(f"{sum(xs) / len(xs):.2f}" if xs else "–")
        p(f"| {tag} | {n} | " + " | ".join(cells) + " |")

    p("\n## Sessions, tokens and cost (lite; micro in the second table)\n")
    for suite in ("lite", "micro"):
        p(f"\n### {suite}\n")
        p("| Model | Track | Sessions | Incomplete | Failed | Calls | Input (uncached) | Cache read "
          "| Cache write | Output | Agent $ | Oracle $ | Self-reported agent $ |")
        p("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for m in MODELS:
            for t in "AB":
                rep = report(m, t, suite)
                if not rep:
                    continue
                run_dir = Path(rep["run"]["dir"])
                cps = {w["id"]: {c["id"] for c in w["checkpoints"]} for w in rep["worlds"]}
                last = {w["id"]: w["days"][-1] for w in rep["worlds"]}
                tot = metered(run_dir, cps, last)
                agent = defaultdict(float)
                for g in ("ingest", "query"):
                    for k, v in tot[g].items():
                        agent[k] += v
                sessions, incomplete, failed, self_cost = 0, 0, 0, 0.0
                for w in rep["worlds"]:
                    for f in sorted((run_dir / w["id"] / "r1" / "sessions").glob("*/session.json")):
                        s = json.loads(f.read_text())
                        name = f.parent.name
                        if name.endswith("query-oracle"):
                            continue
                        key = name.split(".")[0]
                        if (".query" in name and key not in cps[w["id"]]) or (
                                ".ingest" in name and key != "seed" and key > last[w["id"]]):
                            continue
                        sessions += 1
                        incomplete += bool(s.get("incomplete"))
                        failed += s.get("status") not in (None, "ok")
                        self_cost += (s.get("usage") or {}).get("cost_usd") or 0
                fm = lambda x: f"{x / 1e6:.2f}M"  # noqa: E731
                p(f"| {m} | {t} | {sessions} | {incomplete} | {failed} | {int(agent['calls'])} "
                  f"| {fm(agent['input_tokens'])} | {fm(agent['cache_read_input_tokens'])} "
                  f"| {fm(agent['cache_creation_input_tokens'])} | {fm(agent['output_tokens'])} "
                  f"| {cost(agent, MODELS[m]):.2f} | {cost(tot['oracle'], MODELS[m]):.2f} "
                  f"| {self_cost:.2f} |")  # fmt: skip

    p("\n## Lowest-scoring agent answers (lite)\n")
    for (m, t), rep in runs.items():
        run_dir = Path(rep["run"]["dir"])
        rows = sorted((r for r in rep["questions"] if r["store"] == "agent" and r["score"] < 0.5),
                      key=lambda r: (r["score"], r["world"], r["checkpoint"], r["id"]))  # fmt: skip
        p(f"\n### {m} {t}: {len(rows)} answers below 0.5\n")
        for r in rows[:25]:
            g, a = gold_and_answers(rep, run_dir, r)
            gold_s, pred = gist(g, a)
            p(f"- {r['world']} {r['checkpoint']} {r['id']} `{r['template']}` "
              f"score {r['score']:.2f} (base {r['base']:.2f}): {g['text']}  \n"
              f"  gold: {gold_s}  \n  predicted: {pred}")  # fmt: skip
    print("\n".join(out))


if __name__ == "__main__":
    main()
