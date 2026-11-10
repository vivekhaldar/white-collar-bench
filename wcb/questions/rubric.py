"""Keyword and rubric helpers shared by the question templates (docs/questions.md).

Status and brief questions are graded against a checklist of rubric items (docs/formats.md
§3.3). The heuristic judge marks an item *covered* when every keyword group has at least one
match in the answer, and *contradicted* when every `stale` group matches but the item is not
covered. This module turns gold values into such groups:

- a project status becomes one group of synonyms (``active`` -> ``in progress``, ``on track``...);
- a date becomes one group of its prose variants (``2027-02-05``, ``5 feb``, ``february 5th``...);
- an entity becomes one group of its name and surface forms;
- free text becomes one group per distinctive token (at most two), so every group is a word a
  correct answer would plausibly use.

Every keyword is a lowercase string. Everything here is a pure function of its arguments.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from wcb.util.dates import DATE_RE, text_variants
from wcb.util.text import normalize, tokens

if TYPE_CHECKING:
    from wcb.world.model import World

# fmt: off
# Synonyms for each project status (contract `status` values). Used as one any-of group.
STATUS_SYNONYMS: dict[str, list[str]] = {
    "active": ["active", "in progress", "underway", "on track", "ongoing", "moving"],
    "paused": ["paused", "on hold"],
    "dormant": ["dormant", "stalled", "inactive", "quiet"],
    "done": ["done", "complete", "completed", "finished", "closed", "delivered"],
    "cancelled": ["cancelled", "canceled", "dropped", "shelved"],
    "merged": ["merged", "folded into"],
}

# Words an answer uses when a loop changes status (latest-change rubric items).
LOOP_STATUS_WORDS: dict[str, list[str]] = {
    "done": [
        "done", "complete", "completed", "finished", "closed", "resolved",
        "sent", "delivered", "returned", "submitted", "received",
    ],
    "dropped": ["dropped", "cancelled", "canceled", "abandoned", "no longer", "scrapped"],
    "waiting": ["waiting", "pending", "awaiting", "on hold"],
    "blocked": ["blocked", "stuck", "held up"],
    "open": ["open", "reopened", "outstanding"],
}

REVERSAL_WORDS = [
    "reversed", "reversal", "reverse", "overturned", "undone", "undid", "rescinded",
    "scrapped", "abandoned", "no longer", "changed",
]
SPLIT_WORDS = ["split", "spun out", "spun off", "split out", "carved out", "separate"]
MERGE_WORDS = ["merged", "folded into", "combined", "absorbed"]
# Words for an attribute set to null (a blocker cleared). Not "none": it turns up in almost
# any status answer ("overdue items: none").
CLEARED_WORDS = [
    "cleared", "resolved", "removed", "no longer", "unblocked", "fixed", "lifted", "ended",
    "is over", "no blocker", "no blockers",
]
# How answers, which address the worker, refer to the worker taking something over ("it's
# yours now", "handed to you", "owner: me"). Accepted alongside the worker's names.
WORKER_WORDS = ["me", "myself", "mine", "you", "yourself", "yours"]

# Words too generic to identify anything in an answer.
GENERIC_WORDS = frozenset(
    """
    project projects update updates updated status current currently new next step steps work
    working team phase item items thing things task tasks pending waiting need needs needed
    still will would should could can get got set make made also just some any all now then
    than being been not but has had after before until who what when which there here
    """.split()
)
# fmt: on

_ISO_DATE_IN_TEXT = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMBER = re.compile(r"^-?\d[\d,]*(\.\d+)?$")


# ---------------------------------------------------------------- keyword groups
def group(words: Iterable[Any]) -> list[str]:
    """One any-of keyword group: normalized lowercase strings, deduplicated, in order."""
    out: list[str] = []
    for w in words:
        if w is None:
            continue
        k = normalize(str(w))
        if k and k not in out:
            out.append(k)
    return out


def groups(*gs: Iterable[Any]) -> list[list[str]]:
    """Several keyword groups; empty groups are dropped (an empty group could never match)."""
    out = [group(g) for g in gs]
    return [g for g in out if g]


def status_group(status: str) -> list[str]:
    """Synonyms of a project status, e.g. ``paused`` -> ``["paused", "on hold"]``."""
    return group(STATUS_SYNONYMS.get(status, [status]))


def date_group(date: str) -> list[str]:
    """Prose variants of an ISO date (``wcb.util.dates.text_variants``)."""
    return group(text_variants(date))


def entity_forms(world: World, state: dict, eid: str) -> list[str]:
    """Name and surface forms of an entity, lowercased. Falls back to the world's definition
    when the entity is not knowable, and to the ID itself when it does not exist."""
    ent = state.get("entities", {}).get(eid)
    if ent is None:
        ent = world.entity_events().get(eid)
    if ent is None:
        return group([eid])
    return group([ent.get("name"), *(ent.get("surface_forms") or [])])


def loop_keyword_group(world: World, state: dict, loop: dict) -> list[str]:
    """A loop's keywords as one rubric group, without keywords that only name its context.

    Generated and hand-written loops carry keywords such as ``["api contract v2", "Fulmar"]``.
    As alternatives in one group, the project's name would cover every loop of the project in
    any answer that mentions it, so keywords made only of words from the names of the loop's
    project, debtor, creditor or others are dropped (unless nothing else is left).
    """
    kws = [k for k in loop.get("keywords") or [] if isinstance(k, str) and k.strip()]
    context: set[str] = set()
    for eid in (loop.get("project"), loop.get("debtor"), loop.get("creditor"), *(loop.get("others") or [])):
        if isinstance(eid, str) and eid:
            for form in entity_forms(world, state, eid):
                context |= set(tokens(form))
    specific = [k for k in kws if not set(tokens(k)) <= context]
    return group(specific or kws)


def is_date(value: Any) -> bool:
    return isinstance(value, str) and bool(DATE_RE.match(value))


def is_number(value: Any) -> bool:
    """True for ints and floats (not bools) and for strings such as ``180000`` or ``1,250.5``."""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    return isinstance(value, str) and bool(_NUMBER.match(value.strip()))


def is_entity(world: World, value: Any) -> bool:
    """True when `value` is the ID of an entity defined anywhere in the world."""
    return isinstance(value, str) and value in world.entity_events()


def distinctive_tokens(text: str, n: int = 2, avoid: Iterable[str] = ()) -> list[str]:
    """Up to `n` distinctive words of `text`, in their original order.

    Stopwords, generic words (``project``, ``update``...), very short words, ISO dates and any
    word in `avoid` (typically the project's own name) are skipped. Longer words are preferred,
    since they tend to be more specific.
    """
    avoid_set = set(avoid)
    cleaned = _ISO_DATE_IN_TEXT.sub(" ", str(text))
    cands: list[str] = []
    for t in tokens(cleaned):
        if t in GENERIC_WORDS or t in avoid_set or t in cands:
            continue
        if len(t) < 3 and not t.isdigit():
            continue
        cands.append(t)
    ranked = sorted(range(len(cands)), key=lambda i: (-len(cands[i]), i))[:n]
    return [cands[i] for i in sorted(ranked)]


def text_groups(text: str, n: int = 2, avoid: Iterable[str] = ()) -> list[list[str]]:
    """Keyword groups for free text: one date group per ISO date it contains, then one group
    per distinctive token."""
    out = [date_group(d) for d in _ISO_DATE_IN_TEXT.findall(str(text))]
    out += [[t] for t in distinctive_tokens(text, n=n, avoid=avoid)]
    return out


def value_groups(
    world: World, state: dict, attr: str, value: Any, avoid: Iterable[str] = ()
) -> list[list[str]]:
    """Keyword groups for an attribute value, by its shape.

    - ``status``: one group of status synonyms;
    - entity ID: one group of the entity's name and surface forms;
    - ISO date: one group of date variants;
    - number: one group with the number as written and without thousands separators;
    - list: one group with the forms of every element;
    - other text: see `text_groups`.
    """
    if value is None:
        return []
    if attr == "status" and isinstance(value, str):
        return [status_group(value)]
    if isinstance(value, list):
        forms: list[str] = []
        for v in value:
            forms += entity_forms(world, state, v) if is_entity(world, v) else group([v])
        return groups(forms)
    if is_entity(world, value):
        return [entity_forms(world, state, value)]
    if is_date(value):
        return [date_group(value)]
    if is_number(value):
        s = str(value)
        return groups([s, s.replace(",", "")])
    return text_groups(str(value), avoid=avoid)


def stale_value_groups(
    world: World, state: dict, attr: str, previous: Any, current: Any, avoid: Iterable[str] = ()
) -> list[list[str]]:
    """Groups describing a superseded value, or ``[]`` when there is none.

    For free text, words shared with the current value are dropped first, so that mentioning
    the current value never looks like a contradiction.
    """
    if previous is None or previous == current:
        return []
    shape_is_text = not (
        (attr == "status")
        or isinstance(previous, list)
        or is_entity(world, previous)
        or is_date(previous)
        or is_number(previous)
    )
    if not shape_is_text:
        return value_groups(world, state, attr, previous, avoid=avoid)
    shared = set(tokens(str(current))) if current is not None else set()
    return text_groups(str(previous), avoid=set(avoid) | shared)


def flatten(gs: Iterable[Iterable[str]]) -> list[str]:
    """All keywords of several groups as one deduplicated list."""
    return group(w for g in gs for w in g)


# ---------------------------------------------------------------- attribute history
def previous_value(entity: dict, attr: str) -> Any:
    """The most recent knowable value of `attr` that differs from the current one, or None.

    Clearing an attribute (value ``None``) is not a value. A ``merged`` status is set by
    ``project.merge`` outside `attr_history`, so the last recorded status is then the previous.
    """
    current = (entity.get("attrs") or {}).get(attr)
    for h in reversed((entity.get("attr_history") or {}).get(attr, [])):
        v = h.get("value")
        if v is not None and v != current:
            return v
    return None


# ---------------------------------------------------------------- rubric items
def rubric_item(
    text: str,
    keywords: list[list[str]],
    *,
    critical: bool = False,
    stale: list[list[str]] | None = None,
    support: list[str] | None = None,
    aspect: str = "",
    weight: int | None = None,
) -> dict[str, Any]:
    """A rubric item (docs/formats.md §3.3) without its ID; `number_items` assigns IDs.

    `weight` defaults to 2 for critical items and 1 otherwise. `aspect` names what the item
    checks (``status``, ``phase``, ``latest_change``...), for reports and debugging.
    """
    return {
        "id": "",
        "aspect": aspect,
        "text": text,
        "weight": int(weight if weight is not None else (2 if critical else 1)),
        "critical": bool(critical),
        "keywords": [g for g in (group(g) for g in keywords) if g],
        "stale": [g for g in (group(g) for g in (stale or [])) if g],
        "support": list(support or []),
    }


def number_items(items: list[dict[str, Any]], start: int = 1) -> list[dict[str, Any]]:
    """Assign IDs ``r1``, ``r2``... in order (in place) and return the list."""
    for i, item in enumerate(items, start):
        item["id"] = f"r{i}"
    return items


def normalize_extra_item(spec: Any) -> dict[str, Any]:
    """A rubric item from a spec's ``extra_rubric`` entry.

    Accepts a plain string (the item text, with no keywords) or a mapping with ``text`` and
    optional ``keywords``, ``stale``, ``critical``, ``weight`` and ``support``. A keyword group
    may be written as a single string.
    """
    if isinstance(spec, str):
        spec = {"text": spec}
    if not isinstance(spec, dict) or not spec.get("text"):
        raise ValueError(f"extra_rubric entry needs a 'text': {spec!r}")

    def as_groups(raw: Any) -> list[list[str]]:
        return [[g] if isinstance(g, str) else list(g) for g in (raw or [])]

    return rubric_item(
        str(spec["text"]),
        as_groups(spec.get("keywords")),
        critical=bool(spec.get("critical", False)),
        stale=as_groups(spec.get("stale")),
        support=[str(s) for s in spec.get("support") or []],
        aspect="extra",
        weight=spec.get("weight"),
    )
