#!/usr/bin/env python3
"""Check the generator's name pools against a private repository, and optionally prune them.

    python scripts/check_name_pools.py --private-repo ~/projects/private-repo
    python scripts/check_name_pools.py --private-repo ~/projects/private-repo --fix

Every first name, surname, nickname and homophone in `wcb/world/names.py` is written as a line
of prose to a temporary file and scanned with `wcb privacy scan` (prose, because the scanner
treats source code more leniently). With `--fix`, flagged names are removed from the pools.
Only counts are printed, so the output never lists which names occur in the private repository.
Regenerate any committed worlds afterwards (docs/generator.md).
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wcb.privacy.scan import scan  # noqa: E402
from wcb.world import names as N  # noqa: E402

NAMES_PY = ROOT / "wcb" / "world" / "names.py"


def pool_names() -> set[str]:
    out = set(N.FIRST_NAMES) | set(N.SURNAMES) | set(N.NICKNAMES) | set(N.NICKNAMES.values())
    for a, b in N.HOMOPHONE_PAIRS:
        out |= {a, b}
    return out


def flagged(private_repo: Path) -> set[str]:
    with tempfile.TemporaryDirectory() as tmp:
        corpus = Path(tmp) / "names.md"
        corpus.write_text(
            "\n\n".join(f"{n} met with the team today." for n in sorted(pool_names())) + "\n"
        )
        return {f.term for f in scan(private_repo, [corpus], min_len=3)}


def prune(flag: set[str]) -> int:
    src = NAMES_PY.read_text(encoding="utf-8")
    removed = 0
    for block in ("_FIRST_RAW", "_SURNAME_RAW"):
        m = re.search(rf'({block} = """\n)(.*?)(\n""")', src, re.S)
        toks = m.group(2).split()
        kept = [t for t in toks if t not in flag]
        removed += len(toks) - len(kept)
        body = "\n".join(textwrap.wrap(" ".join(kept), width=99))
        src = src[: m.start(2)] + body + src[m.end(2) :]
    lines = []
    for line in src.splitlines(keepends=True):
        m = re.match(r'\s+\("([^"]+)", "([^"]+)"\),\s*$', line) or re.match(
            r'\s+"([^"]+)": "([^"]+)",\s*$', line
        )
        if m and (m.group(1) in flag or m.group(2) in flag):
            removed += 1
            continue
        lines.append(line)
    NAMES_PY.write_text("".join(lines), encoding="utf-8")
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--private-repo", required=True, type=Path)
    ap.add_argument("--fix", action="store_true", help="remove flagged names from the pools")
    a = ap.parse_args()
    flag = flagged(a.private_repo.expanduser())
    print(f"{len(pool_names())} pool names checked; {len(flag)} also occur in the private repository")
    if flag and a.fix:
        print(f"removed {prune(flag)} entries from {NAMES_PY.relative_to(ROOT)}; "
              "regenerate committed worlds")
    return 1 if flag and not a.fix else 0


if __name__ == "__main__":
    raise SystemExit(main())
