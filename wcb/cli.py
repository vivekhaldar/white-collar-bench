"""Command-line interface: `wcb <command>`.

Each subcommand imports its implementation lazily so that `wcb --help` stays fast and a
missing optional dependency only affects the command that needs it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wcb import __version__


def _print_issues(issues, as_json: bool) -> int:
    errors = [i for i in issues if i.severity == "error"]
    if as_json:
        print(json.dumps([i.to_dict() for i in issues], indent=2))
    else:
        for i in issues:
            print(i.format())
        print(f"{len(errors)} error(s), {len(issues) - len(errors)} warning(s)")
    return 1 if errors else 0


# ---------------------------------------------------------------- validate
def cmd_validate_store(a) -> int:
    from wcb.contract.validate import validate_store

    return _print_issues(validate_store(Path(a.store)), a.json)


def cmd_validate_answers(a) -> int:
    from wcb.contract.validate import validate_answers

    return _print_issues(validate_answers(Path(a.answers), Path(a.questions) if a.questions else None), a.json)


# ---------------------------------------------------------------- world
def cmd_world_check(a) -> int:
    from wcb.paths import resolve_world
    from wcb.world.check import check_world

    return _print_issues(check_world(resolve_world(a.world)), a.json)


def cmd_world_build(a) -> int:
    from wcb.paths import resolve_world, worlds_dir
    from wcb.world.build import build_world, gold_status

    if a.all:
        dirs = [p.parent for p in sorted(worlds_dir().glob("**/world.yaml"))]
    elif a.world:
        dirs = [resolve_world(w) for w in a.world]
    else:
        print("wcb world build: name one or more worlds, or pass --all", file=sys.stderr)
        return 2
    status = 0
    for d in dirs:
        if a.if_stale and gold_status(d) is None:
            print(f"{d}: gold is current")
            continue
        res = build_world(d)
        if len(dirs) > 1:
            print(f"== {d}")
        print(res.format())
        status = status or (0 if res.ok else 1)
    return status


def cmd_world_stats(a) -> int:
    from wcb.paths import resolve_world
    from wcb.world.stats import world_stats

    stats = world_stats(resolve_world(a.world))
    print(json.dumps(stats, indent=2))
    return 0


def cmd_world_list(a) -> int:
    from wcb.paths import worlds_dir
    from wcb.util.io import read_yaml
    from wcb.world.build import gold_status

    root = worlds_dir()
    for p in sorted(root.glob("**/world.yaml")):
        meta = read_yaml(p)
        rel = p.parent.relative_to(root)
        cps = len(meta.get("checkpoints", []))
        days = len(meta.get("episode", {}).get("days", []))
        gold = "gold current" if gold_status(p.parent) is None else "gold not built or stale"
        print(f"{str(rel):20} {days:>2} days, {cps:>2} checkpoints, {gold:23}  {meta.get('title', '')}")
    return 0


def cmd_world_questions(a) -> int:
    from wcb.paths import resolve_world
    from wcb.util.io import read_json

    w = resolve_world(a.world)
    for f in sorted((w / "gold" / "questions").glob("*.json")):
        if a.checkpoint and f.stem != a.checkpoint:
            continue
        data = read_json(f)
        print(f"# {data['checkpoint']} ({data['date']})")
        for q in data["questions"]:
            flag = "" if q.get("answerable", True) else "  [unanswerable]"
            print(f"  {q['id']:7} {q['type']:9} {q['text']}{flag}")
    return 0


# ---------------------------------------------------------------- generate
def cmd_generate(a) -> int:
    from wcb.world.generate import generate_world

    out = generate_world(
        seed=a.seed, weeks=a.weeks, out_dir=Path(a.out), world_id=a.id, size=a.size, llm=a.llm,
        llm_model=a.llm_model, build=not a.no_build,
    )
    print(f"generated {out}")
    return 0


# ---------------------------------------------------------------- run / score
def cmd_run(a) -> int:
    from wcb.runner.episode import RunConfig, run

    cfg = RunConfig(
        adapter=Path(a.adapter),
        worlds=a.world or [],
        split=a.split,
        track=a.track,
        repeats=a.repeats,
        out=Path(a.out),
        oracle=a.oracle,
        max_days=a.max_days,
        workspace_root=Path(a.workspace_root) if a.workspace_root else None,
        resume=a.resume,
        skip_ingest=a.skip_ingest,
        meter=a.meter,
        meter_bind=a.meter_bind,
        meter_host=a.meter_host,
        build=a.build,
    )
    return run(cfg)


def cmd_score(a) -> int:
    from wcb.grade.score import score_run

    report = score_run(
        Path(a.run_dir), judge=a.judge, judge_model=a.judge_model, out_dir=Path(a.out) if a.out else None
    )
    print(report.summary_text())
    return 0


def cmd_doctor(a) -> int:
    from wcb.runner.doctor import doctor, format_result

    res = doctor(Path(a.adapter), world=a.world, track=a.track, out=Path(a.out) if a.out else None)
    print(format_result(res))
    return 0 if res.ok else 1


def cmd_bundle(a) -> int:
    from wcb.bundle import bundle_run

    out = Path(a.out) if a.out else Path(a.run_dir).resolve().with_suffix(".tar.gz")
    m = bundle_run(Path(a.run_dir), out, logs=a.logs, snapshots=a.snapshots)
    for n in m["notes"]:
        print(f"note: {n}", file=sys.stderr)
    print(f"wrote {out} ({len(m['files'])} files + MANIFEST.json)")
    return 0


def cmd_meter_serve(a) -> int:
    import time

    from wcb.meter import MeterProxy

    with MeterProxy(Path(a.log), host=a.host, port=a.port) as p:
        print(f"wcb meter: listening on http://{p.host}:{p.port}, logging to {a.log}", flush=True)
        for prov, url in sorted(p.upstreams.items()):
            print(f"  {prov:9} -> {url}    base URL for tag T: {p.base_url('T', prov)}", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    return 0


def cmd_meter_summary(a) -> int:
    from wcb.meter import summarize

    print(json.dumps(summarize(Path(a.log), a.tag), indent=2))
    return 0


# ---------------------------------------------------------------- privacy
def cmd_privacy_scan(a) -> int:
    from wcb.privacy.scan import scan

    stats: dict = {}
    findings = scan(Path(a.private_repo), [Path(p) for p in a.paths], min_len=a.min_len, stats=stats)
    rank = {"low": 0, "medium": 1, "high": 2}
    shown = [f for f in findings if rank.get(f.severity, 0) >= rank[a.min_severity]]
    for f in shown:
        print(f.format())
    if stats:
        print(
            f"scanned {stats.get('corpus_files', '?')} corpus file(s) and "
            f"{stats.get('private_files', '?')} private file(s)",
            file=sys.stderr,
        )
    print(f"{len(shown)} potential leak(s) at severity >= {a.min_severity} ({len(findings)} total)")
    return 1 if shown else 0


# ---------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wcb", description="white-collar-bench command-line tools")
    p.add_argument("--version", action="version", version=f"wcb {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="validate a store or an answers file").add_subparsers(
        dest="what", required=True
    )
    vs = v.add_parser("store", help="check a store against the Track A contract")
    vs.add_argument("store")
    vs.add_argument("--json", action="store_true")
    vs.set_defaults(fn=cmd_validate_store)
    va = v.add_parser("answers", help="check an answers file against the answer schema")
    va.add_argument("answers")
    va.add_argument("--questions", help="questions.json, to check IDs and types")
    va.add_argument("--json", action="store_true")
    va.set_defaults(fn=cmd_validate_answers)

    w = sub.add_parser("world", help="build, check and inspect worlds").add_subparsers(
        dest="what", required=True
    )
    wc = w.add_parser("check", help="consistency checks on a world")
    wc.add_argument("world")
    wc.add_argument("--json", action="store_true")
    wc.set_defaults(fn=cmd_world_check)
    wb = w.add_parser("build", help="derive manifests, gold state, oracle stores and questions")
    wb.add_argument("world", nargs="*", help="world paths or names under worlds/")
    wb.add_argument("--all", action="store_true", help="build every world under worlds/")
    wb.add_argument("--if-stale", action="store_true",
                    help="skip worlds whose gold is already current (gold/BUILD.json)")
    wb.set_defaults(fn=cmd_world_build)
    wst = w.add_parser("stats", help="calibration statistics")
    wst.add_argument("world")
    wst.set_defaults(fn=cmd_world_stats)
    wl = w.add_parser("list", help="list available worlds")
    wl.set_defaults(fn=cmd_world_list)
    wq = w.add_parser("questions", help="print a world's questions")
    wq.add_argument("world")
    wq.add_argument("--checkpoint")
    wq.set_defaults(fn=cmd_world_questions)

    g = sub.add_parser("generate", help="generate a synthetic world")
    g.add_argument("--seed", type=int, required=True)
    g.add_argument("--weeks", type=int, default=1)
    g.add_argument("--size", choices=["small", "standard", "large"], default="standard")
    g.add_argument("--id", help="world id (default: gen-s<seed>-w<weeks>)")
    g.add_argument("--out", required=True, help="output directory")
    g.add_argument("--llm", action="store_true", help="rewrite artifact prose with an LLM")
    g.add_argument("--llm-model", help="model spec for --llm, e.g. 'cmd:claude -p' or 'anthropic:<model>'")
    g.add_argument("--no-build", action="store_true", help="skip `wcb world build` after generating")
    g.set_defaults(fn=cmd_generate)

    r = sub.add_parser("run", help="run an agent adapter over one or more worlds")
    r.add_argument("--adapter", required=True)
    r.add_argument("--world", action="append", help="world path or name (repeatable)")
    r.add_argument("--split", help="run every world in a split, e.g. dev")
    r.add_argument("--track", choices=["A", "B"], default="A")
    r.add_argument("--repeats", type=int, default=1)
    r.add_argument("--out", required=True)
    r.add_argument("--oracle", action=argparse.BooleanOptionalAction, default=True,
                   help="also run query sessions against oracle stores (Track A)")
    r.add_argument("--max-days", type=int, help="stop after this many episode days")
    r.add_argument("--workspace-root", help="where to create workspaces (default: system temp)")
    r.add_argument("--resume", action="store_true", help="skip sessions that already completed")
    r.add_argument("--skip-ingest", action="store_true",
                   help="only run oracle query sessions (measures synthesis alone)")
    r.add_argument("--meter", action="store_true",
                   help="route sessions' model calls through a metering proxy (docs/running.md)")
    r.add_argument("--meter-bind", default="127.0.0.1", help="address the metering proxy listens on")
    r.add_argument("--meter-host", help="address sessions use to reach the proxy (default: --meter-bind)")
    r.add_argument("--build", action=argparse.BooleanOptionalAction, default=True,
                   help="build worlds whose gold is missing or stale first (default: on)")
    r.set_defaults(fn=cmd_run)

    dr = sub.add_parser("doctor", help="smoke-test an adapter on the mini world and explain failures")
    dr.add_argument("--adapter", required=True)
    dr.add_argument("--world", help="world to use (default: the two-day mini fixture world)")
    dr.add_argument("--track", choices=["A", "B"], default="A")
    dr.add_argument("--out", help="run directory (default: a new temporary directory)")
    dr.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("score", help="grade a run directory and write a report")
    s.add_argument("run_dir")
    s.add_argument("--judge", choices=["heuristic", "llm"], default="heuristic")
    s.add_argument("--judge-model", help="model for --judge llm (see docs/judge.md)")
    s.add_argument("--out", help="output directory (default: <run_dir>/scores)")
    s.set_defaults(fn=cmd_score)

    b = sub.add_parser("bundle", help="pack a scored run into a .tar.gz for reporting results")
    b.add_argument("run_dir")
    b.add_argument("--out", help="archive path (default: <run_dir>.tar.gz)")
    b.add_argument("--logs", action="store_true", help="include session logs and agent transcripts")
    b.add_argument("--snapshots", action="store_true", help="include the daily store snapshots")
    b.set_defaults(fn=cmd_bundle)

    me = sub.add_parser("meter", help="model-call metering proxy").add_subparsers(
        dest="what", required=True
    )
    ms = me.add_parser("serve", help="run the proxy in the foreground")
    ms.add_argument("--log", required=True, help="JSONL file to append call records to")
    ms.add_argument("--host", default="127.0.0.1")
    ms.add_argument("--port", type=int, default=8787)
    ms.set_defaults(fn=cmd_meter_serve)
    mu = me.add_parser("summary", help="token totals from a meter log")
    mu.add_argument("log")
    mu.add_argument("--tag", help="only calls with this tag (a session name)")
    mu.set_defaults(fn=cmd_meter_summary)

    pv = sub.add_parser("privacy", help="privacy tools").add_subparsers(dest="what", required=True)
    ps = pv.add_parser("scan", help="check benchmark content for terms from a private repository")
    ps.add_argument("--private-repo", required=True)
    ps.add_argument("--min-len", type=int, default=4)
    ps.add_argument("--min-severity", choices=["low", "medium", "high"], default="low",
                    help="only report (and fail on) findings at or above this severity")
    ps.add_argument("paths", nargs="+")
    ps.set_defaults(fn=cmd_privacy_scan)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.fn(args) or 0)
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    except (FileNotFoundError, ValueError) as e:
        print(f"wcb: error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
