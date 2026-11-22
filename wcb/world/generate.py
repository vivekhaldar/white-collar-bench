"""Generate a complete synthetic world from a seed (`wcb generate`, docs/generator.md).

Pipeline: plan (`wcb.world.planner`) -> simulate (`wcb.world.simulator`) -> render artifacts
(`wcb.render`) -> write `world.yaml`, `world.jsonl` and `plan.yaml` -> compute gold states ->
generate `questions.yaml` (`wcb.questions.generate`) -> `wcb world check` (any error raises) ->
optionally `wcb world build`.

Output is deterministic: the same arguments produce byte-identical files. The optional LLM
rewrite (`llm=True`) is the only exception; its results are cached under `.wcb-cache/`.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from wcb.util.io import dump_yaml, write_text
from wcb.world.planner import GENERATOR_VERSION, make_plan
from wcb.world.simulator import simulate

# Files and directories that generate_world owns inside the output directory.
AUTHORED = ("world.yaml", "world.jsonl", "questions.yaml", "plan.yaml")
DERIVED_DIRS = ("inbox", "gold")


class GenerationError(RuntimeError):
    """The generated world failed its checks or build."""


def generate_world(
    *,
    seed: int,
    weeks: int = 1,
    out_dir: Path,
    world_id: str | None = None,
    size: str = "standard",
    llm: bool = False,
    llm_model: str | None = None,
    build: bool = True,
    version: int = GENERATOR_VERSION,
) -> Path:
    """Generate a world into `out_dir` and return its path.

    Existing generated files in `out_dir` (`world.yaml`, `world.jsonl`, `questions.yaml`,
    `plan.yaml`, `inbox/`, `gold/`) are replaced; anything else is left alone. Raises
    `GenerationError` if `wcb world check` reports an error or the build fails.
    """
    from wcb.questions.generate import generate_questions
    from wcb.render import render_world
    from wcb.world.check import check_world
    from wcb.world.model import World
    from wcb.world.state import state_at

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in AUTHORED:
        if (out / name).exists():
            (out / name).unlink()
    for name in DERIVED_DIRS:
        if (out / name).is_dir():
            shutil.rmtree(out / name)

    plan = make_plan(seed, weeks=weeks, size=size, world_id=world_id, version=version)
    sim = simulate(plan, seed)
    rewriter = _rewriter(llm, llm_model)
    emits, ctx = render_world(plan, sim, out, seed=seed, rewriter=rewriter)

    meta = dict(sim.meta)
    meta["generator"] = {
        "kind": "wcb-gen",
        "version": version,
        "seed": seed,
        "weeks": weeks,
        "size": size,
        "setting": plan["setting"]["key"],
        "llm": bool(llm),
    }
    write_text(out / "world.yaml", dump_yaml(meta))
    rows = sorted(
        [(e["t"], 0, i, e) for i, e in enumerate(sim.events)] + [(e["t"], 1, i, e) for i, e in enumerate(emits)],
        key=lambda r: (r[0], r[1], r[2]),
    )
    _write_jsonl(out / "world.jsonl", [r[3] for r in rows])
    write_text(out / "plan.yaml", dump_yaml(_plan_doc(plan, sim, ctx)))

    world = World.load(out)
    dates = sorted({c["date"] for c in world.checkpoints()} | {world.seed_end})
    states = {d: state_at(world, d) for d in dates}
    specs = generate_questions(world, states, seed=seed)
    write_text(out / "questions.yaml", dump_yaml(specs))

    issues = check_world(out)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        raise GenerationError(
            f"generated world {out} has {len(errors)} check error(s):\n"
            + "\n".join(i.format() for i in errors[:30])
        )
    if build:
        from wcb.world.build import build_world

        result = build_world(out)
        if not result.ok:
            errs = [i for i in result.issues if i.severity == "error"]
            raise GenerationError(
                f"building {out} failed:\n" + "\n".join(i.format() for i in errs[:30])
            )
    return out


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    import json

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def _plan_doc(plan: dict, sim: Any, ctx: Any) -> dict:
    """plan.yaml: the plan plus what maintainers need to audit a generated world."""
    doc = dict(plan)
    doc["audit"] = {
        "unrevealed": dict(sim.unrevealed),
        "instruction_injection": ctx.injection_artifact,
        "attachments": sorted(c.artifacts[0] for c in sim.comms if c.kind == "document"),
    }
    return doc


def _rewriter(llm: bool, llm_model: str | None) -> Any:
    if not llm:
        return None
    import os

    from wcb.render.llm import Rewriter

    spec = llm_model or os.environ.get("WCB_GEN_LLM_MODEL")
    if not spec:
        raise ValueError("llm=True needs llm_model (a model spec such as 'cmd:claude -p') or $WCB_GEN_LLM_MODEL")
    return Rewriter(spec)
