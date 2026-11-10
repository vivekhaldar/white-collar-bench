"""Build a world's derived files (`wcb world build`).

Everything under `gold/` and every `inbox/<date>/manifest.json` is derived from the authored
world (`world.yaml`, `world.jsonl`, `questions.yaml`, artifact files) and must never be edited
by hand (docs/formats.md §1). The build:

1. runs `check_world` and stops, writing nothing, if it finds errors;
2. regenerates `inbox/<date>/manifest.json` for every delivery date and episode day
   (docs/formats.md §1.5);
3. computes the knowable gold state for every date in `world.all_dates()` and writes
   `gold/state/<date>.json` (§2);
4. renders the oracle store for `seed.end` and every episode day into
   `gold/oracle-store/<date>/`, then checks it for planted secrets and, when the contract
   validator is available, validates it;
5. builds the gold questions per checkpoint into `gold/questions/<cp>.json` (§3.2);
6. writes `gold/calibration.json` (the same content as `wcb world stats`).

Output is deterministic: rebuilding an unchanged world rewrites identical bytes, so a
rebuild shows no diff. Stale derived files (dates or checkpoints that no longer exist) are
removed.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wcb.store.oracle import render_oracle_store
from wcb.util.io import write_json
from wcb.util.issues import Issue, error, warning
from wcb.world.check import check_world
from wcb.world.model import World
from wcb.world.state import state_at
from wcb.world.stats import compute_stats, read_question_docs


@dataclass
class BuildResult:
    """Outcome of `build_world`: whether it succeeded, issues found, and files written.

    `written` holds paths relative to the world directory, in the order they were written.
    """

    ok: bool
    issues: list[Issue] = field(default_factory=list)
    written: list[str] = field(default_factory=list)

    def format(self) -> str:
        """Human summary: each issue, then counts of the files written."""
        lines = [i.format() for i in self.issues]
        n_err = sum(1 for i in self.issues if i.severity == "error")
        n_warn = len(self.issues) - n_err
        if not self.written:
            lines.append(f"build aborted, nothing written: {n_err} error(s), {n_warn} warning(s)")
            return "\n".join(lines)
        lines.append("wrote " + ", ".join(_written_summary(self.written)))
        lines.append(
            f"{'built' if self.ok else 'build FAILED'}: {n_err} error(s), {n_warn} warning(s)"
        )
        return "\n".join(lines)


def build_world(world_dir: Path) -> BuildResult:
    """Check the world, then regenerate manifests and everything under `gold/`."""
    world_dir = Path(world_dir).resolve()
    issues = check_world(world_dir)
    if _errors(issues):
        return BuildResult(False, issues, [])
    world = World.load(world_dir)
    written: list[str] = []
    written += write_manifests(world)
    states = {d: state_at(world, d) for d in world.all_dates()}
    written += write_states(world, states)
    written += write_oracle_stores(world, states, issues)
    docs = build_question_docs(world, states, issues)
    if docs is not None:
        written += write_questions(world, docs)
    final = states[world.all_dates()[-1]]
    stats = compute_stats(world, final, read_question_docs(world.dir))
    write_json(world.dir / "gold" / "calibration.json", stats)
    written.append("gold/calibration.json")
    return BuildResult(not _errors(issues), issues, written)


# ---------------------------------------------------------------- steps
def manifest(world: World, date: str) -> dict[str, Any]:
    """The agent-visible manifest for one inbox date (artifacts by received_at, then id)."""
    return {"date": date, "artifacts": [a.manifest_entry() for a in world.artifacts_on(date)]}


def write_manifests(world: World) -> list[str]:
    """Write a manifest for every delivery date and every episode day; drop stale ones."""
    dates = sorted({a.date for a in world.artifacts.values()} | set(world.episode_days()))
    inbox = world.dir / "inbox"
    for stale in sorted(inbox.glob("*/manifest.json")):
        if stale.parent.name not in dates:
            stale.unlink()
    written = []
    for d in dates:
        write_json(inbox / d / "manifest.json", manifest(world, d))
        written.append(f"inbox/{d}/manifest.json")
    return written


def write_states(world: World, states: dict[str, dict]) -> list[str]:
    """Write `gold/state/<date>.json` for each date; drop files for dates that no longer exist."""
    out = world.dir / "gold" / "state"
    _remove_stale(out, "*.json", {f"{d}.json" for d in states})
    written = []
    for d, state in states.items():
        write_json(out / f"{d}.json", state)
        written.append(f"gold/state/{d}.json")
    return written


def oracle_dates(world: World) -> list[str]:
    """Dates with an oracle store: the end of the seed window and every episode day."""
    return sorted({world.seed_end, *world.episode_days()})


def write_oracle_stores(world: World, states: dict[str, dict], issues: list[Issue]) -> list[str]:
    """Render `gold/oracle-store/<date>/` afresh for each oracle date and validate it."""
    root = world.dir / "gold" / "oracle-store"
    dates = oracle_dates(world)
    if root.is_dir():
        for stale in sorted(p for p in root.iterdir() if p.is_dir() and p.name not in dates):
            shutil.rmtree(stale)
    written = []
    for d in dates:
        out = root / d
        if out.exists():
            shutil.rmtree(out)
        render_oracle_store(world, states[d], out)
        issues.extend(check_oracle_store(out, states[d], label=f"gold/oracle-store/{d}"))
        written += sorted(
            f"gold/oracle-store/{d}/{p.relative_to(out).as_posix()}" for p in out.rglob("*.md")
        )
    return written


def check_oracle_store(store: Path, state: dict, label: str) -> list[Issue]:
    """Problems with a rendered oracle store: leaked secrets and contract violations.

    Uses `wcb.contract.validate.validate_store` when it is available. A missing CONTRACT.md is
    expected (the runner adds it) and is not reported.
    """
    issues = []
    for f in sorted(store.rglob("*.md")):
        text = f.read_text(encoding="utf-8")
        for secret in state.get("secrets", []):
            if secret and secret in text:
                issues.append(
                    error(
                        "oracle.secret",
                        f"planted secret {secret!r} leaked into the oracle store",
                        f"{label}/{f.relative_to(store).as_posix()}",
                    )
                )
    try:
        from wcb.contract.validate import validate_store
    except ImportError:
        return issues
    for i in validate_store(store, delivered=set(state.get("delivered", []))):
        if "CONTRACT.md" in f"{i.path or ''} {i.message}":
            continue
        issues.append(
            Issue(
                i.severity, f"oracle.{i.code}", i.message, f"{label}/{i.path}" if i.path else label
            )
        )
    return issues


def build_question_docs(
    world: World, states: dict[str, dict], issues: list[Issue]
) -> dict[str, dict] | None:
    """Gold question documents per checkpoint, or None (with a warning) if unavailable."""
    try:
        from wcb.questions.build import build_questions
    except ImportError as e:
        issues.append(warning("questions.skipped", f"gold questions not built: {e}"))
        return None
    return build_questions(world, states)


def write_questions(world: World, docs: dict[str, dict]) -> list[str]:
    """Write `gold/questions/<cp>.json` in checkpoint order; drop files for old checkpoints."""
    out = world.dir / "gold" / "questions"
    _remove_stale(out, "*.json", {f"{cp}.json" for cp in docs})
    order = [c["id"] for c in world.checkpoints()]
    written = []
    for cp in sorted(docs, key=lambda c: (order.index(c) if c in order else len(order), c)):
        write_json(out / f"{cp}.json", docs[cp])
        written.append(f"gold/questions/{cp}.json")
    return written


# ---------------------------------------------------------------- helpers
def _errors(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "error"]


def _remove_stale(directory: Path, pattern: str, keep: set[str]) -> None:
    if directory.is_dir():
        for f in sorted(directory.glob(pattern)):
            if f.name not in keep:
                f.unlink()


def _written_summary(written: list[str]) -> list[str]:
    """Counts of written files by kind, e.g. '7 manifests', '3 oracle stores (66 files)'."""
    manifests = sum(1 for w in written if w.startswith("inbox/"))
    states = sum(1 for w in written if w.startswith("gold/state/"))
    oracle = [w for w in written if w.startswith("gold/oracle-store/")]
    stores = len({w.split("/")[2] for w in oracle})
    questions = sum(1 for w in written if w.startswith("gold/questions/"))
    parts = [
        f"{manifests} manifest(s)",
        f"{states} state file(s)",
        f"{stores} oracle store(s) ({len(oracle)} files)",
        f"{questions} question file(s)",
    ]
    if "gold/calibration.json" in written:
        parts.append("gold/calibration.json")
    return parts
