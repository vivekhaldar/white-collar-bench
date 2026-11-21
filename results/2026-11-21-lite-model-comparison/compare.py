#!/usr/bin/env python3
"""Cross-model summary of the four WCB-lite runs on Pi (Haiku, Sonnet and Opus 5.5, GPT-6.1 Sol).

    python results/2026-11-21-lite-model-comparison/compare.py > results/2026-11-21-lite-model-comparison/data.json

Reads each run's measured sessions and its `scores-<suite>` (original scorer) and
`scores-fixed-<suite>` (rescored with the date-history and acceptance-hedge fixes) reports
under runs/, and prints one JSON document: headlines, bucket and per-world scores, per-session
turns, wall time and tokens, cost (Pi's per-session cost, billed; list price for Sol is twice its flex rate),
and the lite suite's wall-clock duration. The figures and tables in README.md and the slide
deck come from this output.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = {
    "Haiku 5.5": ("claude-haiku-5.5", ROOT / "runs/claude-5.5-pi-lite/haiku", ROOT / "runs/claude-5.5-pi-lite"),
    "Sonnet 5.5": ("claude-sonnet-5.5", ROOT / "runs/claude-5.5-pi-lite/sonnet", ROOT / "runs/claude-5.5-pi-lite"),
    "Opus 5.5": ("claude-opus-5.5", ROOT / "runs/claude-opus-5.5-pi-lite/opus", ROOT / "runs/claude-opus-5.5-pi-lite"),
    "GPT-6.1 Sol": ("gpt-6.1-sol", ROOT / "runs/gpt-6.1-sol-pi-lite/sol", ROOT / "runs/gpt-6.1-sol-pi-lite"),
}  # fmt: skip
PRICES = {  # USD per million tokens, LiteLLM /model/info list prices
    "claude-haiku-5.5": dict(input=0.10, output=0.50, cache_read=0.01, cache_write=0.125),
    "claude-sonnet-5.5": dict(input=2.0, output=10.0, cache_read=0.10, cache_write=2.5),
    "claude-opus-5.5": dict(input=4.0, output=20.0, cache_read=0.20, cache_write=5.0),
    "gpt-6.1-sol": dict(input=2.0, output=10.0, cache_read=0.10, cache_write=2.5),
}
#: LiteLLM serves gpt-6.1-sol at the flex tier (half of list); see the Sol report.
BILLED = {"gpt-6.1-sol": 0.5}
TOKENS = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def headline(path: Path) -> dict:
    return json.loads(path.read_text())["headline"]


def report(run: Path, track: str, name: str) -> dict:
    return json.loads((run / f"track-{track}" / name / "report.json").read_text())


def cost(u: dict, model: str) -> float:
    p = PRICES[model]
    return (u["input_tokens"] * p["input"] + u["output_tokens"] * p["output"]
            + u["cache_read_input_tokens"] * p["cache_read"]
            + u["cache_creation_input_tokens"] * p["cache_write"]) / 1e6  # fmt: skip


def in_suite(rep: dict) -> tuple[dict, dict]:
    """Per world: the suite's checkpoint IDs and last episode day."""
    return ({w["id"]: {c["id"] for c in w["checkpoints"]} for w in rep["worlds"]},
            {w["id"]: w["days"][-1] for w in rep["worlds"]})  # fmt: skip


def keep(world: str, session: str, cps: dict, last: dict) -> bool:
    if world not in cps:
        return False
    key, kind = session.split(".", 1)
    if kind.startswith("query"):
        return key in cps[world]
    return key == "seed" or key <= last[world]


def sessions(run: Path, track: str, suite: str) -> list[dict]:
    """Turns and wall time of the sessions inside the suite (Pi's session records)."""
    cps, last = in_suite(report(run, track, f"scores-{suite}"))
    out = []
    for w in cps:
        for f in sorted((run / f"track-{track}" / "measured" / w / "r1" / "sessions").glob("*/session.json")):
            name = f.parent.name
            if not keep(w, name, cps, last):
                continue
            s = json.loads(f.read_text())
            u = s.get("usage") or {}
            kind = name.split(".", 1)[1]
            out.append(dict(world=w, track=track.upper(), session=name,
                            kind="oracle" if kind == "query-oracle" else kind.split("-")[0],
                            turns=u.get("turns"), wall_s=s.get("wall_s"), status=s.get("status"),
                            cost_usd=u.get("cost_usd") or 0.0,
                            incomplete=bool((u.get("termination") or {}).get("incomplete"))))  # fmt: skip
    return out


def metered(run: Path, track: str, suite: str) -> dict:
    """Tokens per session from the runner's metering proxy (uncached input, cache read and
    write and output are separate there; Pi's own `input_tokens` includes cached input)."""
    cps, last = in_suite(report(run, track, f"scores-{suite}"))
    out: dict = defaultdict(lambda: dict.fromkeys(TOKENS, 0))
    for line in (run / f"track-{track}" / "measured" / "meter.jsonl").read_text().splitlines():
        r = json.loads(line)
        world, _, session, _ = r["tag"].split("/", 3)
        if keep(world, session, cps, last):
            u = r.get("usage") or {}
            for k in TOKENS:
                out[(world, session)][k] += u.get(k) or 0
    return out


def main() -> None:
    data: dict = {"models": {}}
    for label, (model, run, base) in RUNS.items():
        m: dict = {"model": model, "scores": {}, "buckets": {}, "worlds": {}, "usage": {}}
        for suite in ("lite", "micro"):
            for t in "ab":
                o = headline(run / f"track-{t}/scores-{suite}/report.json")
                n = headline(run / f"track-{t}/scores-fixed-{suite}/report.json")
                m["scores"][f"{suite}-{t}"] = dict(
                    original=o["wcb"], rescored=n["wcb"], ci95=n["wcb_ci95"],
                    synthesis=n.get("synthesis"), ingestion_cost=n.get("ingestion_cost"), sis=n.get("sis"),
                    synthesis_original=o.get("synthesis"))  # fmt: skip
        for t in "ab":
            rep = report(run, t, "scores-fixed-lite")
            m["buckets"][t] = {b: dict(agent=v.get("wcb"), oracle=v.get("synthesis"))
                               for b, v in rep["breakdowns"]["by_type"].items()}  # fmt: skip
            m["worlds"][t] = {w["id"]: w["score"] for w in rep["worlds"]}
        for suite in ("lite", "micro"):
            ss = [s for t in "ab" for s in sessions(run, t, suite)]
            meter = {(t.upper(), *k): v for t in "ab" for k, v in metered(run, t, suite).items()}
            for s in ss:
                s.update(meter.get((s["track"], s["world"], s["session"]), dict.fromkeys(TOKENS, 0)))
            agent = [s for s in ss if s["kind"] != "oracle"]
            tot = {k: sum(s[k] for s in agent) for k in TOKENS}
            otot = {k: sum(s[k] for s in ss if s["kind"] == "oracle") for k in TOKENS}
            ingest = [s for s in agent if s["kind"] == "ingest" and s["session"] != "seed.ingest"]
            # Pi's own per-session cost splits cache writes from uncached input (the metering
            # proxy cannot for gpt-6.1-sol) and applies Sol's flex tier, so it is the billed
            # figure; it equals the metered list-price cost for the Claude models.
            billed = sum(s["cost_usd"] for s in ss)
            list_ = billed / BILLED.get(model, 1.0)
            m["usage"][suite] = dict(
                sessions=len(agent), failed=sum(s["status"] != "ok" for s in agent),
                incomplete=sum(s["incomplete"] for s in agent),
                tokens=tot, oracle_tokens=otot,
                tokens_total=sum(tot.values()) + sum(otot.values()),
                cost_list_usd=list_, cost_billed_usd=billed, cost_metered_list_usd=cost(tot, model) + cost(otot, model),
                agent_cost_list_usd=cost(tot, model),
                per_track_cost_list_usd={t.upper(): cost({k: sum(s[k] for s in agent if s["track"] == t.upper())
                                                          for k in TOKENS}, model) for t in "ab"},
                ingest_turns_median=statistics.median(s["turns"] for s in ingest),
                ingest_turns_p90=sorted(s["turns"] for s in ingest)[int(0.9 * (len(ingest) - 1))],
                ingest_wall_median_s=statistics.median(s["wall_s"] for s in ingest),
                ingest_output_median=statistics.median(s["output_tokens"] for s in ingest),
                query_turns_median=statistics.median(s["turns"] for s in agent if s["kind"] == "query"),
                query_wall_median_s=statistics.median(s["wall_s"] for s in agent if s["kind"] == "query"),
                session_hours=sum(s["wall_s"] for s in ss) / 3600,
            )  # fmt: skip
            if suite == "lite":
                m["ingest_sessions"] = [dict(turns=s["turns"], wall_s=s["wall_s"], output=s["output_tokens"],
                                             track=s["track"]) for s in ingest]  # fmt: skip
        started = json.loads((base / "started.json").read_text())["started_at"]
        finished = max(json.loads(line)["finished_at"] for line in (base / "outcomes.jsonl").read_text().splitlines())
        m["elapsed_min_all_models_in_run"] = (
            datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds() / 60  # fmt: skip
        data["models"][label] = m
    print(json.dumps(data, indent=1))


if __name__ == "__main__":
    main()
