"""Gold support widened along the world's event threads (docs/formats.md §3.2).

A template's `support` names the artifacts it used to derive the gold answer: for a loop, its
evidence; for a change, the artifacts that reveal that one event. Other delivered artifacts
can carry the same evidence. An email that reports "sent Kian the plan" supports a claim about
that commitment as well as the note that first recorded it. `widen_support` adds them,
deterministically, from the event log: every artifact delivered by the checkpoint that
reveals an event about the same object.

**Threads.** Each knowable event belongs to one thread, the object it is about:

| Event | Thread |
|---|---|
| `commitment.create`, `.update`, `.resolve` | the commitment |
| `decision.make`, `.reverse` | the decision |
| `fact.set` | the subject's attribute (`subject`, `attribute`) |
| `entity.create`, `project.split`, `project.merge` | the event alone |

An `entity.create` also opens the thread of every attribute it sets, and a split or merge the
threads of the project attributes it sets (`split_into`, `parent`; `status`, `merged_into`),
so the artifact that introduced a person also supports their role.

**What is widened** (`widen_support`):

- *list* and *priority* items (`loop`): the commitment's whole thread;
- *change* items (`event`): the event and every later event on its thread ("later updates");
- *status* and *brief* questions: no rubric item changes, but the question's support also
  covers the objects in the gold `facts` the judge sees: loops and decisions (whole thread),
  recent events (from the event on), the subject's attributes (whole thread) and, for
  briefs, the attribute that makes each shared project shared (`owner`, `sponsor`,
  `members`);
- *point* and *temporal* questions are unchanged: their support is the evidence for the one
  value asked, and earlier or later values on the same thread are not that evidence.

Every item keeps what the template gave it. A list, change or priority question's support is
its old support plus the support of its items (for priority, the worker's loops: never the
distractors). Supports stay in delivery order (`support_union`).
"""

from __future__ import annotations

from typing import Any

from wcb.questions.templates import support_union
from wcb.world.model import World

Thread = tuple[str, ...]

#: Brief `shared_projects[].involvement` -> the project attribute that makes it shared.
INVOLVEMENT_ATTR = {"owner": "owner", "sponsor": "sponsor", "member": "members"}


def primary_thread(raw: dict[str, Any]) -> Thread:
    """The object an event is about (see the module docstring)."""
    t = raw.get("type", "")
    if t.startswith("commitment."):
        return ("commitment", str(raw.get("commitment")))
    if t.startswith("decision."):
        return ("decision", str(raw.get("decision")))
    if t == "fact.set":
        return ("attr", str(raw.get("subject")), str(raw.get("attribute")))
    return ("event", str(raw.get("id")))


def event_threads(raw: dict[str, Any]) -> list[Thread]:
    """Every thread an event belongs to: its primary thread plus attributes it sets."""
    out = [primary_thread(raw)]
    t = raw.get("type")
    if t == "entity.create":
        out += [("attr", str(raw.get("entity")), str(a)) for a in raw.get("attrs") or {}]
    elif t == "project.split":
        out.append(("attr", str(raw.get("project")), "split_into"))
        out += [("attr", str(p), "parent") for p in raw.get("into") or []]
    elif t == "project.merge":
        into = raw.get("into")
        for p in raw.get("projects") or []:
            if p != into:
                out += [("attr", str(p), "status"), ("attr", str(p), "merged_into")]
    return out


class ThreadIndex:
    """Knowable events of one gold state, grouped by thread, with their delivered artifacts."""

    def __init__(self, world: World, state: dict):
        self.state = state
        self.pos: dict[str, int] = {}
        self.primary: dict[str, Thread] = {}
        self.threads: dict[Thread, list[tuple[int, list[str]]]] = {}
        for i, ev in enumerate(state.get("events") or []):
            raw = {**world.by_id.get(ev["id"], {}), "id": ev["id"], "type": ev["type"]}
            self.pos[ev["id"]] = i
            self.primary[ev["id"]] = primary_thread(raw)
            arts = list(ev.get("artifacts") or [])
            for th in event_threads(raw):
                self.threads.setdefault(th, []).append((i, arts))

    def thread(self, key: Thread, since: int = -1) -> list[str]:
        """Artifacts revealing the thread's events at or after position `since`."""
        return support_union(
            self.state, *(arts for i, arts in self.threads.get(key, []) if i >= since)
        )

    def loop(self, cid: Any) -> list[str]:
        return self.thread(("commitment", str(cid))) if cid else []

    def decision(self, did: Any) -> list[str]:
        return self.thread(("decision", str(did))) if did else []

    def event_onward(self, eid: Any) -> list[str]:
        """The event's artifacts and those of every later event on its primary thread."""
        if eid not in self.pos:
            return []
        return self.thread(self.primary[eid], self.pos[eid])

    def attr(self, eid: Any, attr: Any) -> list[str]:
        return self.thread(("attr", str(eid), str(attr))) if eid and attr else []


def widen_support(
    qtype: str, gold: dict, support: list[str], world: World, state: dict
) -> tuple[dict, list[str]]:
    """``(gold, support)`` with item and question support widened (module docstring).

    Returns a new gold dict; the input is not modified. Unanswerable questions (gold ``{}``)
    and point and temporal questions come back unchanged.
    """
    if not gold or qtype in ("point", "temporal"):
        return gold, list(support)
    idx = ThreadIndex(world, state)
    if qtype in ("list", "change"):
        items = [_widen_item(it, idx) for it in gold.get("items") or []]
        support = support_union(state, support, *(it.get("support") or [] for it in items))
        return {**gold, "items": items}, support
    if qtype == "priority":
        out = dict(gold)
        for key in ("must_include", "worker_active", "distractors"):
            if key in gold:
                out[key] = [_widen_item(it, idx) for it in gold.get(key) or []]
        worker = [*(out.get("must_include") or []), *(out.get("worker_active") or [])]
        support = support_union(state, support, *(it.get("support") or [] for it in worker))
        return out, support
    if qtype in ("status", "brief"):
        return gold, support_union(state, support, *_facts_support(gold.get("facts") or {}, idx))
    return gold, list(support)


def _widen_item(item: dict, idx: ThreadIndex) -> dict:
    """A list, priority or change gold item with its thread's artifacts added to `support`."""
    if not isinstance(item, dict):
        return item
    extra = idx.loop(item.get("loop")) if item.get("loop") else idx.event_onward(item.get("event"))
    return {**item, "support": support_union(idx.state, item.get("support") or [], extra)}


def _facts_support(facts: dict, idx: ThreadIndex) -> list[list[str]]:
    """Artifact lists for every object in a status or brief question's `facts`."""
    out: list[list[str]] = []
    subject = facts.get("project") or facts.get("person")
    for section in ("attrs", "superseded"):
        out += [idx.attr(subject, a) for a in facts.get(section) or {}]
    for section in ("active_loops", "i_owe", "owed_to_me"):
        out += [idx.loop(lp.get("loop")) for lp in facts.get(section) or []]
    out += [idx.decision(d.get("decision")) for d in facts.get("decisions") or []]
    out += [idx.event_onward(ev.get("event")) for ev in facts.get("recent_events") or []]
    for sp in facts.get("shared_projects") or []:
        attr = INVOLVEMENT_ATTR.get(sp.get("involvement"))
        if attr:
            out.append(idx.attr(sp.get("project"), attr))
    return out
