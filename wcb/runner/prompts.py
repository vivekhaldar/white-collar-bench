"""Standard session prompts (docs/scoring.md, "Standard prompts").

The runner gives the agent exactly one of these texts per session, with the simulated date
filled in. They are fixed benchmark text: they contain no knowledge about any particular world,
and adapters must not add any (an adapter may wrap the prompt in its own generic system prompt).

Templates use ``{name}`` placeholders, filled by :func:`render`:

- ``{date}``: the simulated current date, ``YYYY-MM-DD``.
- ``{inbox_dirs}``: (seed prompt only) the seed inbox directories, for example
  ``inbox/2027-02-15/`` and ``inbox/2027-02-16/``.

Track A prompts refer to "the store" and ``CONTRACT.md``. Track B prompts refer to "your files"
and ``GOALS.md``, the one-paragraph goal statement that replaces the contract.
"""

from __future__ import annotations

import re

INGEST_A = (
    "Today is {date}. New inputs are in `inbox/{date}/` (see `manifest.json`). "
    "Incorporate them into the store following `CONTRACT.md`. "
    "Inputs will not be available after this session."
)
"""Track A ingestion prompt, verbatim from docs/scoring.md."""

QUERY_A = (
    "Today is {date}. Answer every question in `.wcb/questions.json` using the store. "
    "Write `.wcb/answers.json` following `.wcb/answer-schema.json`. Cite sources. "
    "Abstain when the store does not support an answer. Do not modify the store."
)
"""Track A query prompt, verbatim from docs/scoring.md. Also used for oracle-store sessions."""

INGEST_B = (
    "Today is {date}. New inputs are in `inbox/{date}/` (see `manifest.json`). "
    "Incorporate them into your files following `GOALS.md`. "
    "Inputs will not be available after this session."
)
"""Track B ingestion prompt: the Track A text with `GOALS.md` in place of `CONTRACT.md`."""

SEED_B = (
    "Today is {date}. Your inputs so far, up to and including today, are in {inbox_dirs}, "
    "one directory per date "
    "(each has a `manifest.json`). "
    "Incorporate them into your files following `GOALS.md`. "
    "Inputs will not be available after this session."
)
"""Track B seed ingestion prompt: one session that receives every seed date's inbox at once."""

QUERY_B = (
    "Today is {date}. Answer every question in `.wcb/questions.json` using your files. "
    "Write `.wcb/answers.json` following `.wcb/answer-schema.json`. Cite sources. "
    "Abstain when your files do not support an answer. Do not modify your files."
)
"""Track B query prompt: the Track A text with "your files" in place of "the store"."""

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def render(template: str, **values: str) -> str:
    """Fill ``{name}`` placeholders in a prompt template.

    Every placeholder in the template must be given a value, and every value must be used, so a
    typo fails loudly instead of sending a half-filled prompt to the agent.

    >>> render(INGEST_A, date="2027-03-01").startswith("Today is 2027-03-01.")
    True
    """
    names = set(_PLACEHOLDER.findall(template))
    missing = names - values.keys()
    unused = values.keys() - names
    if missing:
        raise ValueError(f"prompt template needs values for: {', '.join(sorted(missing))}")
    if unused:
        raise ValueError(f"prompt template has no placeholder for: {', '.join(sorted(unused))}")
    return _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)


def ingest_prompt(track: str, date: str) -> str:
    """The daily ingestion prompt for ``track`` ('A' or 'B')."""
    return render(INGEST_A if _track(track) == "A" else INGEST_B, date=date)


def seed_prompt(date: str, seed_dates: list[str]) -> str:
    """The Track B seed ingestion prompt. ``date`` is the last seed date; ``seed_dates`` lists
    every seed inbox directory placed in the workspace, oldest first."""
    if not seed_dates:
        raise ValueError("a seed prompt needs at least one seed date")
    dirs = [f"`inbox/{d}/`" for d in sorted(seed_dates)]
    if len(dirs) == 1:
        listed = dirs[0]
    elif len(dirs) == 2:
        listed = f"{dirs[0]} and {dirs[1]}"
    else:
        listed = ", ".join(dirs[:-1]) + f" and {dirs[-1]}"
    return render(SEED_B, date=date, inbox_dirs=listed)


def query_prompt(track: str, date: str) -> str:
    """The query prompt for ``track`` ('A' or 'B'). Oracle-store sessions use Track A's text."""
    return render(QUERY_A if _track(track) == "A" else QUERY_B, date=date)


def _track(track: str) -> str:
    if track not in ("A", "B"):
        raise ValueError(f"unknown track {track!r}; expected 'A' or 'B'")
    return track
