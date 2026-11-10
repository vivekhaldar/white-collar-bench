"""Question templates: visible text and gold answers (docs/questions.md, docs/formats.md §3).

A question spec in `questions.yaml` names a template and its parameters. For each checkpoint the
builder (`wcb.questions.build`) renders the question text and derives the gold answer from the
knowable gold state at the checkpoint date (docs/formats.md §2). Every template is a pair of
pure functions of ``(params, world, state)``:

- ``text``: the default question text an agent sees (a spec's own ``text`` overrides it);
- ``gold``: ``(answerable, gold, support)``. ``gold`` has the shape for the template's type
  (docs/formats.md §3.2); ``support`` lists the delivered artifact IDs that carry the evidence.
  When the target is not knowable at the checkpoint the question is **unanswerable** and the
  result is ``(False, {}, [])``: the correct answer is to abstain.

Conventions used throughout:

- *W* is the worker (``world.worker``). A loop is **active** when its status is ``open``,
  ``waiting`` or ``blocked``. Only **accepted** loops count in list answers; suggested loops
  (``accepted: false``) are not commitments yet.
- Entity names in question text are canonical names unless the spec's params set
  ``name_form`` (an alias, such as ``Samir``).
- Supports are artifact IDs in delivery order.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from wcb.questions.rubric import (
    CLEARED_WORDS,
    LOOP_STATUS_WORDS,
    MERGE_WORDS,
    REVERSAL_WORDS,
    SPLIT_WORDS,
    WORKER_WORDS,
    date_group,
    distinctive_tokens,
    entity_forms,
    flatten,
    group,
    is_date,
    is_entity,
    is_number,
    loop_keyword_group,
    number_items,
    previous_value,
    rubric_item,
    stale_value_groups,
    status_group,
    text_groups,
    value_groups,
)
from wcb.util.dates import MONTHS, next_business_day, parse_date
from wcb.util.text import tokens
from wcb.world.model import ACTIVE_STATUSES, CLOSED_STATUSES, World

Gold = tuple[bool, dict[str, Any], list[str]]
UNANSWERABLE: Gold = (False, {}, [])

QTYPES = ("point", "list", "status", "brief", "change", "temporal", "priority")

# Attributes whose value is an entity ID and is answered with that entity's name.
ENTITY_ATTRS = ("owner", "sponsor", "org", "parent", "merged_into")
# Project attributes whose `fact.set` counts as a state change (project_changes, latest change).
CHANGE_ATTRS = ("status", "phase", "owner", "target_date", "blocker", "sponsor", "next_step")
CHANGE_EVENT_TYPES = (
    "commitment.create",
    "commitment.update",
    "commitment.resolve",
    "decision.make",
    "decision.reverse",
    "project.split",
    "project.merge",
)
# Project statuses after which nobody is "working on" the project any more.
CLOSED_PROJECT_STATUSES = ("done", "cancelled", "merged")

MAX_STATUS_LOOPS = 6  # active loops listed in a project_status rubric
MAX_BRIEF_LOOPS = 5  # loops per direction in a person_brief rubric
FOCUS_K = 10  # items considered in a focus_tomorrow answer
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass(frozen=True)
class Template:
    """A question template: its name, question type, parameters and two pure functions.

    ``render(params, world, state) -> str`` gives the default text; ``answer(params, world,
    state) -> (answerable, gold, support)`` gives the gold answer at the state's date.
    """

    name: str
    qtype: str  # point | list | status | brief | change | temporal | priority
    params: tuple[str, ...]  # required parameters
    render: Callable[[dict, World, dict], str] = field(repr=False, compare=False)
    answer: Callable[[dict, World, dict], Gold] = field(repr=False, compare=False)

    def text(self, params: dict, world: World, state: dict) -> str:
        """Default question text for these params."""
        return self.render(params, world, state)

    def gold(self, params: dict, world: World, state: dict) -> Gold:
        """``(answerable, gold, support)``; ``(False, {}, [])`` when unanswerable."""
        answerable, gold, support = self.answer(params, world, state)
        if not answerable:
            return UNANSWERABLE
        return True, gold, support


# ================================================================ shared helpers
def entity_name(world: World, state: dict, eid: str) -> str:
    """Canonical name of an entity: from gold state when knowable, else from the world."""
    ent = state["entities"].get(eid) or world.entity_events().get(eid)
    return str(ent["name"]) if ent else str(eid)


def display_name(world: World, state: dict, eid: str, params: dict) -> str:
    """The name used in question text: ``params['name_form']`` if given, else canonical."""
    form = params.get("name_form")
    return str(form) if form else entity_name(world, state, eid)


def entity_accept(world: World, state: dict, eid: str) -> list[str]:
    """Accepted answer strings for an entity: canonical name and surface forms."""
    ent = state["entities"].get(eid) or world.entity_events().get(eid)
    if not ent:
        return [str(eid)]
    return _dedup([str(ent["name"]), *(str(f) for f in ent.get("surface_forms") or [])])


def knowable(state: dict, eid: str, kind: str | None = None) -> bool:
    """Whether an entity is in the gold state (optionally of the given kind)."""
    ent = state["entities"].get(eid)
    return ent is not None and (kind is None or ent.get("kind") == kind)


def support_union(state: dict, *lists: Iterable[str]) -> list[str]:
    """Union of artifact ID lists, deduplicated, in delivery order."""
    order = {a: i for i, a in enumerate(state.get("delivered", []))}
    ids = {a for lst in lists for a in lst}
    return sorted(ids, key=lambda a: (order.get(a, len(order)), a))


def event_support(world: World, state: dict, eid: str | None) -> list[str]:
    """Delivered artifacts that reveal an event (``world.revealing_artifacts()``)."""
    if not eid:
        return []
    delivered = set(state.get("delivered", []))
    return [a for a in world.revealing_artifacts().get(eid, []) if a in delivered]


def attr_event(world: World, state: dict, eid: str, attr: str) -> str | None:
    """ID of the knowable event that last set ``attr`` on entity ``eid``.

    Usually the last entry of the entity's ``attr_history``. Splits and merges set ``parent``,
    ``split_into``, ``merged_into`` and a ``merged`` status without a history entry, so the
    latest such event touching the entity wins when it is later.
    """
    ent = state["entities"].get(eid)
    if ent is None:
        return None
    hist = (ent.get("attr_history") or {}).get(attr) or []
    best = hist[-1]["event"] if hist else None
    pos = {e["id"]: i for i, e in enumerate(state["events"])}
    for ev in state["events"]:
        raw = world.by_id.get(ev["id"], {})
        sets_attr = False
        if ev["type"] == "project.merge" and attr in ("status", "merged_into"):
            sets_attr = eid in raw.get("projects", []) and eid != raw.get("into")
        elif ev["type"] == "project.split":
            sets_attr = (attr == "split_into" and raw.get("project") == eid) or (
                attr == "parent" and eid in (raw.get("into") or [])
            )
        if sets_attr and (best is None or pos[ev["id"]] > pos.get(best, -1)):
            best = ev["id"]
    return best


def attr_support(world: World, state: dict, eid: str, attr: str) -> list[str]:
    """Delivered artifacts revealing the event that last set an attribute."""
    return event_support(world, state, attr_event(world, state, eid, attr))


def public_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    """Attributes without hidden metadata (keys starting with ``_``)."""
    return {k: v for k, v in attrs.items() if not str(k).startswith("_")}


def is_active(loop: dict) -> bool:
    return loop.get("status") in ACTIVE_STATUSES


def is_accepted_active(loop: dict) -> bool:
    """Accepted and active: the loops that count in list answers."""
    return bool(loop.get("accepted")) and is_active(loop)


def direction(loop: dict, worker: str) -> str:
    """``i_owe`` when the worker is the debtor, ``owed_to_me`` when the worker is the creditor
    and someone else the debtor, otherwise ``other``."""
    if loop["debtor"] == worker:
        return "i_owe"
    if loop["creditor"] == worker:
        return "owed_to_me"
    return "other"


def counterparty(loop: dict, worker: str) -> str:
    """The other side of a loop: the creditor when the worker owes it, else the debtor."""
    return loop["creditor"] if loop["debtor"] == worker else loop["debtor"]


def list_item(world: World, state: dict, cid: str) -> dict[str, Any]:
    """A loop as a list-answer gold item (docs/formats.md §3.2)."""
    loop = state["loops"][cid]
    return {
        "loop": cid,
        "what": loop["what"],
        "counterparty": counterparty(loop, world.worker),
        "direction": direction(loop, world.worker),
        "status": loop["status"],
        "due": loop.get("due"),
        "keywords": group(loop.get("keywords") or []),
        "support": list(loop.get("evidence") or []),
    }


def by_due(cid_loop: tuple[str, dict]) -> tuple[str, str]:
    """Sort key: earliest due first, undated last, then loop ID."""
    cid, loop = cid_loop
    return (loop.get("due") or "9999-99-99", cid)


def select_loops(state: dict, pred: Callable[[dict], bool]) -> list[str]:
    """IDs of knowable loops matching ``pred``, in loop-ID order."""
    return sorted(cid for cid, loop in state["loops"].items() if pred(loop))


def list_gold(world: World, state: dict, cids: list[str]) -> Gold:
    """An answerable list gold; an empty list is a valid answer."""
    items = [list_item(world, state, cid) for cid in cids]
    return True, {"items": items}, support_union(state, *(i["support"] for i in items))


def loop_what(world: World, state: dict, cid: str) -> str:
    """A loop's description: current if knowable, else as created in the world."""
    loop = state["loops"].get(cid)
    if loop:
        return str(loop["what"])
    raw = _creating_event(world, "commitment.create", "commitment", cid)
    return str(raw.get("what", cid)) if raw else str(cid)


def decision_what(world: World, state: dict, did: str) -> str:
    dec = state["decisions"].get(did)
    if dec:
        return str(dec["what"])
    raw = _creating_event(world, "decision.make", "decision", did)
    return str(raw.get("what", did)) if raw else str(did)


def point_answer(world: World, state: dict, attr: str, value: Any) -> dict[str, Any]:
    """Point gold for an attribute value (docs/formats.md §3.2).

    ``entity`` for entity-valued attributes (value = canonical name, accept = name and surface
    forms); ``date`` for ISO dates; ``number`` for numeric values; otherwise ``text``.
    """
    if isinstance(value, str) and (attr in ENTITY_ATTRS or is_entity(world, value)):
        return {
            "kind": "entity",
            "value": entity_name(world, state, value),
            "entity": value,
            "accept": entity_accept(world, state, value),
        }
    if is_date(value):
        return {"kind": "date", "value": value, "entity": None, "accept": [value]}
    if is_number(value):
        return {"kind": "number", "value": value, "entity": None, "accept": [str(value)]}
    if isinstance(value, list):
        text = ", ".join(
            entity_name(world, state, v) if is_entity(world, v) else str(v) for v in value
        )
        return {"kind": "text", "value": text, "entity": None, "accept": [text]}
    return {"kind": "text", "value": str(value), "entity": None, "accept": [str(value)]}


def since_text(date: str) -> str:
    """A date as written in change questions, e.g. ``2027-03-01`` -> ``Monday 1 March``."""
    d = parse_date(date)
    return f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1].capitalize()}"


def lower_first(text: str) -> str:
    """Lowercase the first letter unless the first word looks like an acronym or a name with
    internal capitals (``GL``, ``iOS``)."""
    first = text.split(" ", 1)[0]
    if not text or (len(first) > 1 and any(c.isupper() for c in first[1:])):
        return text
    return text[0].lower() + text[1:]


def name_tokens(world: World, state: dict, eid: str) -> set[str]:
    """Words of an entity's name and surface forms; never distinctive in answers about it."""
    return {t for form in entity_forms(world, state, eid) for t in tokens(form)}


def _creating_event(world: World, etype: str, key: str, oid: str) -> dict | None:
    return next((e for e in world.events if e.get("type") == etype and e.get(key) == oid), None)


def _dedup(xs: Iterable[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


# ================================================================ point: project_attr, person_attr
PROJECT_ATTR_TEXT = {
    "owner": "Who owns {P}?",
    "sponsor": "Who is the executive sponsor of {P}?",
    "target_date": "What is the current target date for {P}?",
    "budget": "What is the budget for {P}?",
    "phase": "What phase is {P} in?",
    "blocker": "What is currently blocking {P}?",
    "next_step": "What is the next step on {P}?",
    "status": "What is the current status of {P}: active, paused, dormant, done or cancelled?",
}
PERSON_ATTR_TEXT = {
    "role": "What is {X}'s role?",
    "org": "Which organization is {X} with?",
    "email": "What is {X}'s email address?",
    "relationship": "What is my working relationship with {X}?",
    "phone": "What is {X}'s direct phone number?",
    "office": "Which office or building does {X} work from?",
}


def _project_attr_text(params: dict, world: World, state: dict) -> str:
    attr = str(params["attribute"])
    tpl = PROJECT_ATTR_TEXT.get(attr, "What is the {A} of {P}?")
    return tpl.format(
        P=display_name(world, state, params["project"], params), A=attr.replace("_", " ")
    )


def _person_attr_text(params: dict, world: World, state: dict) -> str:
    attr = str(params["attribute"])
    tpl = PERSON_ATTR_TEXT.get(attr, "What is {X}'s {A}?")
    return tpl.format(
        X=display_name(world, state, params["person"], params), A=attr.replace("_", " ")
    )


def _attr_gold(world: World, state: dict, eid: str, kind: str, attr: str) -> Gold:
    """Current value of an entity attribute; unanswerable when the entity or value is unknown."""
    if not knowable(state, eid, kind) or attr.startswith("_"):
        return UNANSWERABLE
    value = state["entities"][eid]["attrs"].get(attr)
    if value is None or value == [] or value == "":
        return UNANSWERABLE
    return True, point_answer(world, state, attr, value), attr_support(world, state, eid, attr)


def _project_attr_gold(params: dict, world: World, state: dict) -> Gold:
    return _attr_gold(world, state, params["project"], "project", str(params["attribute"]))


def _person_attr_gold(params: dict, world: World, state: dict) -> Gold:
    return _attr_gold(world, state, params["person"], "person", str(params["attribute"]))


# ================================================================ point: loop_owner, loop_due
def _loop_owner_text(params: dict, world: World, state: dict) -> str:
    return f'Who is responsible for "{loop_what(world, state, params["commitment"])}"?'


def _loop_due_text(params: dict, world: World, state: dict) -> str:
    return f'When is "{loop_what(world, state, params["commitment"])}" due?'


def _last_change_support(loop: dict, key: str) -> list[str]:
    """Artifacts of the latest loop-history entry that set ``key``."""
    for h in reversed(loop.get("history") or []):
        if key in (h.get("changes") or {}):
            return list(h.get("artifacts") or [])
    return []


def _loop_owner_gold(params: dict, world: World, state: dict) -> Gold:
    loop = state["loops"].get(params["commitment"])
    if loop is None:
        return UNANSWERABLE
    gold = point_answer(world, state, "owner", loop["debtor"])
    if loop["debtor"] == world.worker:
        gold["accept"] = _dedup([*gold["accept"], "me", "myself"])
    return True, gold, _last_change_support(loop, "debtor")


def _loop_due_gold(params: dict, world: World, state: dict) -> Gold:
    loop = state["loops"].get(params["commitment"])
    if loop is None or not loop.get("due"):
        return UNANSWERABLE
    due = str(loop["due"])
    gold = {"kind": "date", "value": due, "entity": None, "accept": [due]}
    return True, gold, _last_change_support(loop, "due")


# ================================================================ list: i_owe, owed_to_me, project_loops
def _i_owe_text(params: dict, world: World, state: dict) -> str:
    return f"What do I currently owe {display_name(world, state, params['person'], params)}?"


def _owed_to_me_text(params: dict, world: World, state: dict) -> str:
    return f"What does {display_name(world, state, params['person'], params)} currently owe me?"


def _project_loops_text(params: dict, world: World, state: dict) -> str:
    return f"What loops are open on {display_name(world, state, params['project'], params)}?"


def owed_by_worker_to(state: dict, worker: str, person: str) -> list[str]:
    """Accepted active loops the worker owes ``person`` (as creditor or one of ``others``)."""
    return select_loops(
        state,
        lambda lp: (
            lp["debtor"] == worker
            and is_accepted_active(lp)
            and (lp["creditor"] == person or person in (lp.get("others") or []))
        ),
    )


def owed_to_worker_by(state: dict, worker: str, person: str) -> list[str]:
    """Accepted active loops ``person`` owes the worker."""
    return select_loops(
        state,
        lambda lp: lp["debtor"] == person and lp["creditor"] == worker and is_accepted_active(lp),
    )


def active_on_project(state: dict, project: str) -> list[str]:
    """Accepted active loops on a project."""
    return select_loops(state, lambda lp: lp.get("project") == project and is_accepted_active(lp))


def _i_owe_gold(params: dict, world: World, state: dict) -> Gold:
    person = params["person"]
    if not knowable(state, person):
        return UNANSWERABLE
    return list_gold(world, state, owed_by_worker_to(state, world.worker, person))


def _owed_to_me_gold(params: dict, world: World, state: dict) -> Gold:
    person = params["person"]
    if not knowable(state, person):
        return UNANSWERABLE
    return list_gold(world, state, owed_to_worker_by(state, world.worker, person))


def _project_loops_gold(params: dict, world: World, state: dict) -> Gold:
    project = params["project"]
    if not knowable(state, project, "project"):
        return UNANSWERABLE
    return list_gold(world, state, active_on_project(state, project))


# ================================================================ change: project_changes
def is_project_change(world: World, ev: dict, project: str) -> bool:
    """Whether a knowable state event is a state-changing event on ``project``.

    The event must concern the project (its ``project`` or one of its ``subjects``) and be a
    ``fact.set`` of a CHANGE_ATTRS attribute, a commitment or decision event, a split or merge,
    or the project's own ``entity.create``.
    """
    if ev.get("project") != project and project not in (ev.get("subjects") or []):
        return False
    raw = world.by_id.get(ev["id"], {})
    if ev["type"] == "fact.set":
        return raw.get("attribute") in CHANGE_ATTRS
    if ev["type"] == "entity.create":
        return raw.get("entity") == project
    return ev["type"] in CHANGE_EVENT_TYPES


def project_change_events(
    world: World, state: dict, project: str, since: str | None = None
) -> list[dict]:
    """Knowable state-changing events on a project dated after ``since`` (``since`` itself
    excluded), in world order."""
    return [
        ev
        for ev in state["events"]
        if is_project_change(world, ev, project) and (since is None or ev["date"] > since)
    ]


def on_suggested_loop(world: World, state: dict, ev: dict) -> bool:
    """Whether ``ev`` is a commitment event on a loop that is not accepted at the state date."""
    if not ev["type"].startswith("commitment."):
        return False
    loop = state["loops"].get(world.by_id.get(ev["id"], {}).get("commitment"))
    return loop is not None and not loop.get("accepted")


def status_change_events(world: World, state: dict, project: str) -> list[dict]:
    """`project_change_events` for status golds: only accepted loops count there, so events
    on suggested loops (a suggestion made, reworded or dropped) are skipped."""
    return [
        ev
        for ev in project_change_events(world, state, project)
        if not on_suggested_loop(world, state, ev)
    ]


def party_forms(world: World, state: dict, eid: str, *, worker_words: bool = True) -> list[str]:
    """An entity's names; for the worker also ``me``, ``you`` and similar words
    (`WORKER_WORDS`), since answers address the worker rather than name them."""
    forms = entity_forms(world, state, eid)
    return group([*forms, *WORKER_WORDS]) if worker_words and eid == world.worker else forms


def cleared_groups(
    world: World, state: dict, ev: dict, avoid: Iterable[str] = ()
) -> list[list[str]]:
    """Keyword groups for a ``fact.set`` to ``null``: "cleared" words, plus one group naming
    what was cleared, so that a stray "resolved" elsewhere in an answer does not cover the
    item. That group holds the words of the value it replaced and up to two distinctive words
    of the event's summary (not "cleared" words), or else the attribute's name."""
    raw = world.by_id.get(ev["id"], {})
    attr = str(raw.get("attribute", ""))
    ent = state["entities"].get(raw.get("subject")) or {}
    hist = (ent.get("attr_history") or {}).get(attr) or []
    idx = next((i for i, h in enumerate(hist) if h.get("event") == ev["id"]), len(hist))
    prev = next((h["value"] for h in reversed(hist[:idx]) if h.get("value") is not None), None)
    plain = set(avoid) | {t for w in CLEARED_WORDS for t in tokens(w, drop_stopwords=False)}
    what = group(
        [
            *flatten(value_groups(world, state, attr, prev, avoid=avoid)),
            *distinctive_tokens(str(ev.get("summary") or ""), avoid=plain),
        ]
    )
    return [g for g in (group(CLEARED_WORDS), what or group([attr.replace("_", " ")])) if g]


def event_groups(
    world: World,
    state: dict,
    ev: dict,
    project: str | None = None,
    avoid: Iterable[str] = (),
    *,
    worker_words: bool = True,
) -> list[list[str]]:
    """Keyword groups that describe what an event changed (for latest-change rubric items).

    ``project`` is the project being asked about; its own names are never a keyword group.
    ``avoid`` lists words that are not distinctive (usually that project's names).

    - commitment events: the loop's keywords; plus the new status words for a resolution or a
      status change, the new due date's variants, and the new debtor's names on a transfer;
    - decisions: the decision's keywords, plus reversal words for ``decision.reverse``;
    - ``fact.set``: groups for the new value (`value_groups`); for ``null``, "cleared" words
      and words of the value that was cleared (`cleared_groups`);
    - splits and merges: the names of the other projects involved, plus split or merge words;
    - ``entity.create`` of the project: distinctive words of its summary.

    When the new debtor or the new entity value is the worker, its group also accepts
    `WORKER_WORDS` (``you``, ``yours``, ``me``...) unless ``worker_words`` is false.
    """
    raw = world.by_id.get(ev["id"], {})
    t = ev["type"]
    if t.startswith("commitment."):
        loop = state["loops"].get(raw.get("commitment"), {})
        out = [loop_keyword_group(world, state, loop)]
        changes = (
            {"status": raw.get("status", "done")}
            if t == "commitment.resolve"
            else (raw.get("changes") or {})
        )
        if t != "commitment.create":
            if changes.get("status") in LOOP_STATUS_WORDS:
                out.append(group(LOOP_STATUS_WORDS[changes["status"]]))
            if is_date(changes.get("due")):
                out.append(date_group(changes["due"]))
            if isinstance(changes.get("debtor"), str):
                out.append(party_forms(world, state, changes["debtor"], worker_words=worker_words))
        return [g for g in out if g]
    if t.startswith("decision."):
        dec = state["decisions"].get(raw.get("decision"), {})
        out = [group(dec.get("keywords") or [])]
        if t == "decision.reverse":
            out.append(group(REVERSAL_WORDS))
        return [g for g in out if g]
    if t == "fact.set":
        value = raw.get("value")
        if value is None:
            return cleared_groups(world, state, ev, avoid=avoid)
        if isinstance(value, str) and value == world.worker:
            return [party_forms(world, state, value, worker_words=worker_words)]
        return value_groups(world, state, str(raw.get("attribute")), value, avoid=avoid)
    if t in ("project.split", "project.merge"):
        if t == "project.split":
            parties, words = [raw.get("project"), *(raw.get("into") or [])], SPLIT_WORDS
        else:
            parties, words = [*(raw.get("projects") or []), raw.get("into")], MERGE_WORDS
        names = [f for p in parties if p and p != project for f in entity_forms(world, state, p)]
        return [g for g in (group(names), group(words)) if g]
    return text_groups(ev.get("summary", ""), avoid=avoid)


def change_keywords(world: World, state: dict, ev: dict, project: str) -> list[str]:
    """Flat keywords for a change item: loop or decision keywords; for ``fact.set`` the
    attribute word plus the value's keywords; otherwise the flattened `event_groups`."""
    raw = world.by_id.get(ev["id"], {})
    t = ev["type"]
    if t.startswith("commitment."):
        return group(state["loops"].get(raw.get("commitment"), {}).get("keywords") or [])
    if t.startswith("decision."):
        return group(state["decisions"].get(raw.get("decision"), {}).get("keywords") or [])
    avoid = name_tokens(world, state, project)
    groups = event_groups(world, state, ev, project=project, avoid=avoid, worker_words=False)
    kws = flatten(groups)
    if t == "fact.set":
        return group([str(raw.get("attribute", "")).replace("_", " "), *kws])
    return kws


def change_item(world: World, state: dict, ev: dict, project: str) -> dict[str, Any]:
    """A knowable event on ``project`` as a change-answer gold item (docs/formats.md §3.2)."""
    return {
        "event": ev["id"],
        "summary": ev.get("summary", ""),
        "date": ev["date"],
        "type": ev["type"],
        "keywords": change_keywords(world, state, ev, project),
        "support": list(ev.get("artifacts") or []),
    }


def _project_changes_text(params: dict, world: World, state: dict) -> str:
    project = display_name(world, state, params["project"], params)
    return f"What changed on {project} since the end of {since_text(str(params['since']))}?"


def _project_changes_gold(params: dict, world: World, state: dict) -> Gold:
    project = params["project"]
    if not knowable(state, project, "project"):
        return UNANSWERABLE
    events = project_change_events(world, state, project, since=str(params["since"])[:10])
    items = [change_item(world, state, ev, project) for ev in events]
    return True, {"items": items}, support_union(state, *(i["support"] for i in items))


# ================================================================ status: project_status
def _project_status_text(params: dict, world: World, state: dict) -> str:
    return f"What is the status of {display_name(world, state, params['project'], params)}?"


def loop_fact(world: World, state: dict, cid: str) -> dict[str, Any]:
    """A compact description of a loop for the LLM judge's ``facts``."""
    loop = state["loops"][cid]
    return {
        "loop": cid,
        "what": loop["what"],
        "owner": entity_name(world, state, loop["debtor"]),
        "counterparty": entity_name(world, state, loop["creditor"]),
        "status": loop["status"],
        "due": loop.get("due"),
    }


def attrs_fact(world: World, state: dict, attrs: dict[str, Any]) -> dict[str, Any]:
    """Public attributes with entity IDs replaced by names."""

    def show(v: Any) -> Any:
        if isinstance(v, list):
            return [show(x) for x in v]
        return entity_name(world, state, v) if is_entity(world, v) else v

    return {k: show(v) for k, v in public_attrs(attrs).items()}


def event_fact(ev: dict) -> dict[str, Any]:
    return {
        "event": ev["id"],
        "date": ev["date"],
        "type": ev["type"],
        "summary": ev.get("summary", ""),
    }


def project_status_rubric(world: World, state: dict, project: str) -> list[dict[str, Any]]:
    """Rubric items for ``project_status``, in this order (critical items weigh 2):

    1. current status (critical), with the previous status as stale;
    2. phase, if set, with the previous phase as stale;
    3. the latest knowable state-changing event (critical), skipping events on suggested
       loops (`status_change_events`);
    4. blocker, if set (critical);
    5. target date, if set (critical), with the previous target date as stale;
    6. up to six accepted active loops, worker-owned first, then earliest due;
    7. next step, if set.
    """
    ent = state["entities"][project]
    attrs = ent["attrs"]
    name = ent["name"]
    avoid = name_tokens(world, state, project)
    items: list[dict[str, Any]] = []

    def attr_item(attr: str, text: str, *, critical: bool, aspect: str) -> None:
        value = attrs.get(attr)
        if value in (None, "", []):
            return
        prev = previous_value(ent, attr)
        items.append(
            rubric_item(
                text.format(v=value, prev=prev),
                value_groups(world, state, attr, value, avoid=avoid),
                critical=critical,
                stale=stale_value_groups(world, state, attr, prev, value, avoid=avoid),
                support=attr_support(world, state, project, attr),
                aspect=aspect,
            )
        )

    status = attrs.get("status")
    if status:
        kws = [status_group(status)]
        text = f"{name} is {status}"
        if status == "merged" and attrs.get("merged_into"):
            kws.append(entity_forms(world, state, attrs["merged_into"]))
            text = f"{name} has been merged into {entity_name(world, state, attrs['merged_into'])}"
        prev = previous_value(ent, "status")
        items.append(
            rubric_item(
                text,
                kws,
                critical=True,
                stale=[status_group(prev)] if prev and prev != status else [],
                support=attr_support(world, state, project, "status"),
                aspect="status",
            )
        )
    attr_item("phase", "Current phase: {v}", critical=False, aspect="phase")

    changes = status_change_events(world, state, project)
    if changes:
        latest = changes[-1]
        items.append(
            rubric_item(
                latest.get("summary") or latest["type"],
                event_groups(world, state, latest, project=project, avoid=avoid),
                critical=True,
                support=list(latest.get("artifacts") or []),
                aspect="latest_change",
            )
        )
    attr_item("blocker", "Current blocker: {v}", critical=True, aspect="blocker")
    if is_date(attrs.get("target_date")):
        prev = previous_value(ent, "target_date")
        moved = f" (moved from {prev})" if is_date(prev) else ""
        items.append(
            rubric_item(
                f"Current target date: {attrs['target_date']}{moved}",
                [date_group(attrs["target_date"])],
                critical=True,
                stale=[date_group(prev)] if is_date(prev) else [],
                support=attr_support(world, state, project, "target_date"),
                aspect="target_date",
            )
        )
    else:
        attr_item("target_date", "Current target date: {v}", critical=True, aspect="target_date")

    worker = world.worker
    loops = sorted(
        ((cid, state["loops"][cid]) for cid in active_on_project(state, project)),
        key=lambda p: (p[1]["debtor"] != worker, *by_due(p)),
    )[:MAX_STATUS_LOOPS]
    for _cid, loop in loops:
        items.append(
            rubric_item(
                f"{loop['what']} (owner: {entity_name(world, state, loop['debtor'])})",
                [loop_keyword_group(world, state, loop)],
                support=list(loop.get("evidence") or []),
                aspect="loop",
            )
        )
    attr_item("next_step", "Next step: {v}", critical=False, aspect="next_step")
    return number_items(items)


def project_status_facts(world: World, state: dict, project: str) -> dict[str, Any]:
    """Compact gold for the LLM judge: attributes, superseded values, loops, decisions, events."""
    ent = state["entities"][project]
    previous = {
        a: previous_value(ent, a)
        for a in ("status", "phase", "target_date", "owner", "blocker", "next_step")
        if previous_value(ent, a) is not None
    }
    return {
        "project": project,
        "name": ent["name"],
        "as_of": state["date"],
        "attrs": attrs_fact(world, state, ent["attrs"]),
        "superseded": attrs_fact(world, state, previous),
        "active_loops": [loop_fact(world, state, cid) for cid in active_on_project(state, project)],
        "decisions": [
            {
                "decision": did,
                "what": d["what"],
                "status": d["status"],
                "made_on": d.get("made_on"),
                "reversed_on": d.get("reversed_on"),
            }
            for did, d in sorted(state["decisions"].items())
            if d.get("project") == project
        ],
        "recent_events": [
            event_fact(ev) for ev in status_change_events(world, state, project)[-5:]
        ],
    }


def _project_status_gold(params: dict, world: World, state: dict) -> Gold:
    project = params["project"]
    if not knowable(state, project, "project"):
        return UNANSWERABLE
    rubric = project_status_rubric(world, state, project)
    gold = {"rubric": rubric, "facts": project_status_facts(world, state, project)}
    return True, gold, support_union(state, *(r["support"] for r in rubric))


# ================================================================ brief: person_brief
def _person_brief_text(params: dict, world: World, state: dict) -> str:
    return f"What am I working on with {display_name(world, state, params['person'], params)}?"


def shared_projects(state: dict, worker: str, person: str) -> list[tuple[str, str]]:
    """Projects shared with ``person`` as ``(project, how)`` in state order.

    A project counts when the person is its owner, sponsor or a member and it is not done,
    cancelled or merged; or when the person and the worker are both parties (debtor, creditor
    or others) to an accepted active loop on it. ``how`` is ``owner``, ``sponsor``, ``member``
    or ``loops``.
    """
    via_loops = set()
    for loop in state["loops"].values():
        parties = {loop["debtor"], loop["creditor"], *(loop.get("others") or [])}
        if (
            is_accepted_active(loop)
            and person in parties
            and worker in parties
            and loop.get("project")
        ):
            via_loops.add(loop["project"])
    out = []
    for pid, ent in state["entities"].items():
        if ent["kind"] != "project":
            continue
        attrs = ent["attrs"]
        how = None
        if attrs.get("status") not in CLOSED_PROJECT_STATUSES:
            if attrs.get("owner") == person:
                how = "owner"
            elif attrs.get("sponsor") == person:
                how = "sponsor"
            elif person in (attrs.get("members") or []):
                how = "member"
        if how is None and pid in via_loops:
            how = "loops"
        if how:
            out.append((pid, how))
    return out


def _shared_support(world: World, state: dict, project: str, how: str, person: str) -> list[str]:
    if how in ("owner", "sponsor"):
        return attr_support(world, state, project, how)
    if how == "member":
        return attr_support(world, state, project, "members")
    worker = world.worker
    return support_union(
        state,
        *(
            loop.get("evidence") or []
            for loop in state["loops"].values()
            if loop.get("project") == project
            and is_accepted_active(loop)
            and {person, worker} <= {loop["debtor"], loop["creditor"], *(loop.get("others") or [])}
        ),
    )


def person_brief_rubric(world: World, state: dict, person: str) -> list[dict[str, Any]]:
    """Rubric items for ``person_brief``, in this order:

    1. each shared project (weight 1), keyed on the project's names;
    2. up to five accepted active loops the worker owes the person (critical), earliest due first;
    3. up to five accepted active loops the person owes the worker (critical), earliest due first;
    4. the person's role, if known (weight 1), with a previous role as stale.

    If nothing applies, a single item says there is nothing shared.
    """
    worker = world.worker
    ent = state["entities"][person]
    name = ent["name"]
    items: list[dict[str, Any]] = []
    how_text = {
        "owner": "owner",
        "sponsor": "sponsor",
        "member": "a member",
        "loops": "a party to open loops",
    }
    for pid, how in shared_projects(state, worker, person):
        items.append(
            rubric_item(
                f"Shared project: {entity_name(world, state, pid)} ({name} is {how_text[how]})",
                [entity_forms(world, state, pid)],
                support=_shared_support(world, state, pid, how, person),
                aspect="shared_project",
            )
        )
    owed = [(c, state["loops"][c]) for c in owed_by_worker_to(state, worker, person)]
    for _cid, loop in sorted(owed, key=by_due)[:MAX_BRIEF_LOOPS]:
        due = f" (due {loop['due']})" if loop.get("due") else ""
        items.append(
            rubric_item(
                f"I owe {name}: {loop['what']}{due}",
                [loop_keyword_group(world, state, loop)],
                critical=True,
                support=list(loop.get("evidence") or []),
                aspect="i_owe",
            )
        )
    owing = [(c, state["loops"][c]) for c in owed_to_worker_by(state, worker, person)]
    for _cid, loop in sorted(owing, key=by_due)[:MAX_BRIEF_LOOPS]:
        due = f" (due {loop['due']})" if loop.get("due") else ""
        items.append(
            rubric_item(
                f"{name} owes me: {loop['what']}{due}",
                [loop_keyword_group(world, state, loop)],
                critical=True,
                support=list(loop.get("evidence") or []),
                aspect="owed_to_me",
            )
        )
    role = ent["attrs"].get("role")
    if role:
        org = ent["attrs"].get("org")
        at = f" at {entity_name(world, state, org)}" if org else ""
        avoid = name_tokens(world, state, person)
        items.append(
            rubric_item(
                f"{name} is {role}{at}",
                text_groups(str(role), avoid=avoid),
                stale=stale_value_groups(
                    world, state, "role", previous_value(ent, "role"), role, avoid=avoid
                ),
                support=attr_support(world, state, person, "role"),
                aspect="role",
            )
        )
    if not items:
        items.append(
            rubric_item(
                f"I have no shared projects or open loops with {name}",
                [
                    [
                        "nothing",
                        "none",
                        "no open",
                        "no shared",
                        "not working",
                        "no current",
                        "no active",
                    ]
                ],
                aspect="nothing_shared",
            )
        )
    return number_items(items)


def person_brief_facts(world: World, state: dict, person: str) -> dict[str, Any]:
    """Compact gold for the LLM judge: the person, shared projects, loops each way, events."""
    worker = world.worker
    ent = state["entities"][person]
    return {
        "person": person,
        "name": ent["name"],
        "as_of": state["date"],
        "attrs": attrs_fact(world, state, ent["attrs"]),
        "shared_projects": [
            {
                "project": pid,
                "name": entity_name(world, state, pid),
                "status": state["entities"][pid]["attrs"].get("status"),
                "involvement": how,
            }
            for pid, how in shared_projects(state, worker, person)
        ],
        "i_owe": [loop_fact(world, state, c) for c in owed_by_worker_to(state, worker, person)],
        "owed_to_me": [
            loop_fact(world, state, c) for c in owed_to_worker_by(state, worker, person)
        ],
        "recent_events": [
            event_fact(ev) for ev in state["events"] if person in (ev.get("subjects") or [])
        ][-5:],
    }


def _person_brief_gold(params: dict, world: World, state: dict) -> Gold:
    person = params["person"]
    if not knowable(state, person, "person"):
        return UNANSWERABLE
    rubric = person_brief_rubric(world, state, person)
    gold = {"rubric": rubric, "facts": person_brief_facts(world, state, person)}
    return True, gold, support_union(state, *(r["support"] for r in rubric))


# ================================================================ temporal: decision_date, event_date
def _decision_date_text(params: dict, world: World, state: dict) -> str:
    return f"When did we decide to {lower_first(decision_what(world, state, params['decision']))}?"


def _decision_date_gold(params: dict, world: World, state: dict) -> Gold:
    did = params["decision"]
    dec = state["decisions"].get(did)
    if dec is None:
        return UNANSWERABLE
    ev = next(
        (
            e
            for e in state["events"]
            if e["type"] == "decision.make" and did in (e.get("subjects") or [])
        ),
        None,
    )
    eid = ev["id"] if ev else None
    return (
        True,
        {"date": dec["made_on"], "event": eid},
        list(ev.get("artifacts") or []) if ev else [],
    )


def _event_date_text(params: dict, world: World, state: dict) -> str:
    raw = world.by_id.get(str(params["event"]), {})
    return f'When did this happen: "{raw.get("summary", params["event"])}"?'


def _event_date_gold(params: dict, world: World, state: dict) -> Gold:
    ev = next((e for e in state["events"] if e["id"] == params["event"]), None)
    if ev is None:
        return UNANSWERABLE
    return True, {"date": ev["date"], "event": ev["id"]}, list(ev.get("artifacts") or [])


# ================================================================ priority: focus_tomorrow
def _focus_tomorrow_text(params: dict, world: World, state: dict) -> str:
    return "What should I focus on tomorrow?"


def _focus_tomorrow_gold(params: dict, world: World, state: dict) -> Gold:
    """Worker-owned accepted active loops due by the next business day (overdue included).

    ``worker_active`` lists every worker-owned accepted active loop; ``distractors`` lists
    knowable loops that are closed or owed by someone else. Items are sorted by due date.
    """
    worker = world.worker
    tomorrow = next_business_day(state["date"])
    active = sorted(
        (
            (cid, loop)
            for cid, loop in state["loops"].items()
            if loop["debtor"] == worker and is_accepted_active(loop)
        ),
        key=by_due,
    )
    must = [cid for cid, loop in active if loop.get("due") and str(loop["due"]) <= tomorrow]
    distractors = select_loops(
        state, lambda lp: lp.get("status") in CLOSED_STATUSES or lp["debtor"] != worker
    )
    gold = {
        "tomorrow": tomorrow,
        "must_include": [list_item(world, state, c) for c in must],
        "worker_active": [list_item(world, state, c) for c, _ in active],
        "distractors": [list_item(world, state, c) for c in distractors],
        "k": FOCUS_K,
    }
    support = support_union(state, *(i["support"] for i in gold["worker_active"]))
    return True, gold, support


# ================================================================ registry
TEMPLATES: dict[str, Template] = {
    t.name: t
    for t in (
        Template(
            "project_attr",
            "point",
            ("project", "attribute"),
            _project_attr_text,
            _project_attr_gold,
        ),
        Template(
            "person_attr", "point", ("person", "attribute"), _person_attr_text, _person_attr_gold
        ),
        Template("loop_owner", "point", ("commitment",), _loop_owner_text, _loop_owner_gold),
        Template("loop_due", "point", ("commitment",), _loop_due_text, _loop_due_gold),
        Template("i_owe", "list", ("person",), _i_owe_text, _i_owe_gold),
        Template("owed_to_me", "list", ("person",), _owed_to_me_text, _owed_to_me_gold),
        Template("project_loops", "list", ("project",), _project_loops_text, _project_loops_gold),
        Template(
            "project_status", "status", ("project",), _project_status_text, _project_status_gold
        ),
        Template("person_brief", "brief", ("person",), _person_brief_text, _person_brief_gold),
        Template(
            "project_changes",
            "change",
            ("project", "since"),
            _project_changes_text,
            _project_changes_gold,
        ),
        Template(
            "decision_date", "temporal", ("decision",), _decision_date_text, _decision_date_gold
        ),
        Template("event_date", "temporal", ("event",), _event_date_text, _event_date_gold),
        Template("focus_tomorrow", "priority", (), _focus_tomorrow_text, _focus_tomorrow_gold),
    )
}
