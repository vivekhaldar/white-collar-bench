#!/usr/bin/env python3
"""Regenerate the committed dev worlds (worlds/dev/) from their fixed seeds.

    python scripts/make_dev_worlds.py              # regenerate all of them in place
    python scripts/make_dev_worlds.py --check      # regenerate into a temp dir and compare

Run it after any change to the generator, then review the diff, rerun the privacy scan
(docs/privacy.md) and commit. `--check` exits 1 if the committed worlds differ from what the
current generator produces (built gold and manifests are ignored: the build derives them).
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wcb.world.generate import generate_world  # noqa: E402

# (world id, seed, weeks, size). Covers 1-, 2- and 4-week episodes and every size.
DEV_WORLDS = [
    ("gen-s1-w1", 1, 1, "standard"),
    ("gen-s2-w1", 2, 1, "standard"),
    ("gen-s3-w1", 3, 1, "standard"),
    ("gen-s4-w2", 4, 2, "standard"),
    ("gen-s5-small", 5, 1, "small"),
    ("gen-s6-w1", 6, 1, "standard"),
    ("gen-s7-w2", 7, 2, "standard"),
    ("gen-s8-w4", 8, 4, "standard"),
    ("gen-s9-large", 9, 1, "large"),
    ("gen-s10-w2-small", 10, 2, "small"),
]


def _authored_files(d: Path) -> set[str]:
    """Files written by the generator itself (not gold or manifests, which the build derives)."""
    return {p.relative_to(d).as_posix() for p in d.rglob("*")
            if p.is_file() and "gold" not in p.relative_to(d).parts and p.name != "manifest.json"}


def _differs(a: Path, b: Path) -> list[str]:
    fa, fb = _authored_files(a), _authored_files(b)
    out = sorted(fa ^ fb)
    out += [f for f in sorted(fa & fb) if not filecmp.cmp(a / f, b / f, shallow=False)]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="compare instead of overwriting")
    ap.add_argument("--out", type=Path, default=ROOT / "worlds" / "dev")
    a = ap.parse_args()
    status = 0
    with tempfile.TemporaryDirectory() as tmp:
        for wid, seed, weeks, size in DEV_WORLDS:
            dest = Path(tmp) / wid if a.check else a.out / wid
            if not a.check and dest.exists():
                shutil.rmtree(dest)
            generate_world(seed=seed, weeks=weeks, size=size, world_id=wid, out_dir=dest,
                           build=not a.check, version=1)
            if a.check:
                diff = _differs(a.out / wid, dest) if (a.out / wid).is_dir() else ["(missing)"]
                print(f"{wid}: {'differs: ' + ', '.join(diff[:5]) if diff else 'matches'}")
                status = status or (1 if diff else 0)
            else:
                print(f"generated {dest}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
