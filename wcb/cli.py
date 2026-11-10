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
    from wcb.paths import resolve_world
    from wcb.world.build import build_world

    res = build_world(resolve_world(a.world))
    print(res.format())
    return 0 if res.ok else 1


def cmd_world_stats(a) -> int:
    from wcb.paths import resolve_world
    from wcb.world.stats import world_stats

    stats = world_stats(resolve_world(a.world))
    print(json.dumps(stats, indent=2))
    return 0


def cmd_world_list(a) -> int:
    from wcb.paths import worlds_dir
    from wcb.util.io import read_yaml

    root = worlds_dir()
    for p in sorted(root.glob("**/world.yaml")):
        meta = read_yaml(p)
        rel = p.parent.relative_to(root)
        cps = len(meta.get("checkpoints", []))
        days = len(meta.get("episode", {}).get("days", []))
        print(f"{str(rel):24} {days} days, {cps} checkpoints  {meta.get('title', '')}")
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
        seed=a.seed, weeks=a.weeks, out_dir=Path(a.out), world_id=a.id, size=a.size, llm=a.llm
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
    )
    return run(cfg)


def cmd_score(a) -> int:
    from wcb.grade.score import score_run

    report = score_run(
        Path(a.run_dir), judge=a.judge, judge_model=a.judge_model, out_dir=Path(a.out) if a.out else None
    )
    print(report.summary_text())
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
    wb.add_argument("world")
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
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("score", help="grade a run directory and write a report")
    s.add_argument("run_dir")
    s.add_argument("--judge", choices=["heuristic", "llm"], default="heuristic")
    s.add_argument("--judge-model", help="model for --judge llm (see docs/judge.md)")
    s.add_argument("--out", help="output directory (default: <run_dir>/scores)")
    s.set_defaults(fn=cmd_score)

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
