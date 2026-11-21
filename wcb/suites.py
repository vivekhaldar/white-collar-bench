"""Reduced benchmark suites: cheaper runs for comparing harnesses and models (docs/lite.md).

A suite is a fixed set of public worlds plus a day limit (``--max-days``). Every suite is a
prefix-subset of a full run, so ``wcb score --suite <name>`` can also rescore a full run as if it
had been run as the suite. Suite scores are reported as ``WCB-<suite>`` and are comparable only
with other scores of the same suite, never with full WCB scores.

Changing a suite's worlds or day limit makes old scores incomparable: add a new suite name
instead of editing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath


@dataclass(frozen=True)
class Suite:
    name: str
    worlds: tuple[str, ...]  # world names under worlds/, as given to --world
    max_days: int  # episode days played in every world
    description: str = ""

    @property
    def world_ids(self) -> tuple[str, ...]:
        """World IDs as recorded in run.json (each world's directory name is its ID)."""
        return tuple(PurePosixPath(w).name for w in self.worlds)

    @property
    def label(self) -> str:
        return f"WCB-{self.name}"

    def describe(self) -> dict:
        return {"name": self.name, "worlds": list(self.worlds), "max_days": self.max_days}


_DEV = tuple(
    f"dev/{w}"
    for w in (
        "gen-s1-w1", "gen-s2-w1", "gen-s3-w1", "gen-s4-w2", "gen-s5-small", "gen-s6-w1",
        "gen-s7-w2", "gen-s8-w4", "gen-s9-large", "gen-s10-w2-small",
    )
)  # fmt: skip

SUITES: dict[str, Suite] = {
    s.name: s
    for s in (
        Suite(
            "lite",
            ("pilot", *_DEV),
            max_days=2,
            description="every public world, first two episode days (checkpoint cp1)",
        ),
        Suite(
            "micro",
            ("pilot", "dev/gen-s1-w1", "dev/gen-s4-w2", "dev/gen-s5-small", "dev/gen-s9-large"),
            max_days=2,
            description="five worlds stratified by size and length, first two episode days",
        ),
    )
}


def get_suite(name: str) -> Suite:
    try:
        return SUITES[name]
    except KeyError:
        raise ValueError(
            f"unknown suite {name!r}; choose one of: {', '.join(sorted(SUITES))}"
        ) from None
