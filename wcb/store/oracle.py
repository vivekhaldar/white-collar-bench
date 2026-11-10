"""Render the oracle store: a correct Track A store for a date, from gold state.

The oracle store is what a perfect ingestor would have written by the end of a date
(contract/CONTRACT.md, docs/formats.md §2). It serves two purposes:

- the **seed store** that Track A episodes start from (the oracle store for `seed.end`);
- the **oracle-store query runs** that measure synthesis alone (docs/scoring.md, "Error
  attribution"): the same adapter answers the checkpoint questions against this store.

Everything here is a deterministic function of the world and the gold state, so rebuilding a
world produces byte-identical stores. Record IDs are stable across dates (see `record_ids`).
What the renderer writes:

- `people/`: one record per knowable person (minor people, `attrs._minor`, are skipped);
  the worker is `people/me`.
- `orgs/`, `projects/`: one record per knowable org and project.
- `loops/`: one record per knowable commitment and decision (a decision is a loop with
  `kind: decision`).
- `logs/<date>.md`: one bullet per delivered artifact, for every delivery date so far.

Attributes whose key starts with `_` are hidden metadata and are never rendered. The runner
adds `CONTRACT.md`; this module does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wcb.questions.templates import shared_projects
from wcb.util import frontmatter
from wcb.util.io import write_text
from wcb.util.text import normalize, slugify
from wcb.world.model import ACTIVE_STATUSES, World

FOLDER = {"person": "people", "org": "orgs", "project": "projects"}
WORKER_RECORD = "people/me"

# Evidence basis implied by an input's channel, for evidence entries after the first.
CHANNEL_BASIS = {
    "calendar": "scheduled",
    "transcript": "reported",
    "meeting_notes": "reported",
    "email": "received",
    "chat": "received",
    "document": "received",
    "note": "sent",
}

# Project attributes shown in front matter or in `## Current state` rather than `## Knowledge`.
PROJECT_STATE_ATTRS = ("status", "owner", "summary", "phase", "target_date", "blocker", "next_step")
PROJECT_STRUCTURE_ATTRS = ("parent", "split_into", "merged_into")
PERSON_FRONT_ATTRS = ("org", "role", "email", "relationship")


# ---------------------------------------------------------------- record IDs
def record_ids(world: World) -> dict[str, str]:
    """Map world object IDs (p-/o-/pr-/c-/d-) to store record IDs, stable across dates.

    - The worker is `people/me`.
    - People, orgs and projects get the slug of their canonical name, e.g. `people/cora-velez`.
    - Commitments get the slug of the `what` in their *create* event (later rewording does not
      rename the record); decisions get the slug of their `what`. Both live in `loops/`.
    - Collisions are disambiguated with `-2`, `-3`, ... in the order the objects become
      knowable (the date their create event is first revealed, then world event order; never
      revealed last), so a suffix never hints at an object that is not yet knowable. Minor
      entities are numbered after all others so that they never push a real entity's slug.
    """
    worker = world.worker
    ids: dict[str, str] = {worker: WORKER_RECORD}
    taken: set[str] = {WORKER_RECORD}
    known_on = world.known_on()
    pos = {id(e): i for i, e in enumerate(world.events)}

    def reveal_order(e: dict[str, Any]) -> tuple[str, int]:
        return (known_on.get(str(e.get("id")), "~"), pos[id(e)])

    creates = sorted(world.entity_events().values(), key=lambda e: (_is_minor(e), *reveal_order(e)))
    for e in creates:
        eid, folder = e.get("entity"), FOLDER.get(e.get("kind", ""))
        if eid == worker or not eid or not folder:
            continue
        ids[eid] = _claim(f"{folder}/{slugify(e.get('name') or eid)}", taken)
    loop_creates = sorted(
        (e for e in world.events if e.get("type") in ("commitment.create", "decision.make")),
        key=reveal_order,
    )
    for e in loop_creates:
        oid = e["commitment"] if e["type"] == "commitment.create" else e["decision"]
        if oid not in ids:
            ids[oid] = _claim(f"loops/{slugify(e.get('what') or oid)}", taken)
    return ids


def _claim(base: str, taken: set[str]) -> str:
    rid, n = base, 2
    while rid in taken:
        rid, n = f"{base}-{n}", n + 1
    taken.add(rid)
    return rid


def _is_minor(entity: dict[str, Any]) -> bool:
    return bool((entity.get("attrs") or {}).get("_minor"))


# ---------------------------------------------------------------- entry points
def render_oracle_store(world: World, state: dict, out_dir: Path) -> None:
    """Write the oracle store for `state['date']` into `out_dir`.

    `out_dir` should be empty or absent: files are written, never deleted. The store is
    complete and passes `wcb validate store` once the runner adds CONTRACT.md.
    """
    for rid, text in oracle_records(world, state).items():
        write_text(Path(out_dir) / f"{rid}.md", text)


def oracle_records(world: World, state: dict) -> dict[str, str]:
    """Record ID -> file text for the oracle store of `state['date']` (pure; no IO)."""
    ctx = _Ctx.create(world, state)
    records: dict[str, str] = {}
    for eid, ent in ctx.entities.items():
        if eid not in ctx.rendered:
            continue
        render = {"person": _person, "org": _org, "project": _project}[ent["kind"]]
        records[ctx.ids[eid]] = render(ctx, eid, ent)
    for cid, loop in state["loops"].items():
        records[ctx.ids[cid]] = _loop(ctx, cid, loop)
    for did, dec in state["decisions"].items():
        records[ctx.ids[did]] = _decision(ctx, did, dec)
    for date in sorted({world.artifacts[aid].date for aid in state["delivered"]}):
        records[f"logs/{date}"] = _daily_log(ctx, date)
    for eid, rid in sorted(ctx.stubs.items(), key=lambda kv: kv[1]):
        records[rid] = _stub(ctx, eid, rid)
    return dict(sorted(records.items()))


# ---------------------------------------------------------------- shared context
@dataclass
class _Ctx:
    """Everything the record renderers share, computed once per store."""

    world: World
    state: dict[str, Any]
    ids: dict[str, str]  # world ID -> record ID (all objects in the world)
    creates: dict[str, dict[str, Any]]  # entity ID -> its entity.create event (whole world)
    entities: dict[str, dict[str, Any]]  # knowable entities from the state
    rendered: set[str]  # IDs that get a full record: knowable non-minor entities, loops, decisions
    delivered_rank: dict[str, int]  # artifact ID -> delivery order
    event_artifacts: dict[str, list[str]]  # knowable event ID -> revealing artifacts
    forms: dict[str, list[str]]  # knowable entity ID -> surface forms used in inputs so far
    ambiguous: set[str]  # normalized forms shared by several knowable entities
    stubs: dict[str, str] = field(default_factory=dict)  # world ID -> stub record ID
    _people_cache: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def create(cls, world: World, state: dict[str, Any]) -> _Ctx:
        entities = state["entities"]
        rendered = {k for k, v in entities.items() if not v["attrs"].get("_minor")}
        forms = _known_forms(world, state)
        return cls(
            world=world,
            state=state,
            ids=record_ids(world),
            creates=world.entity_events(),
            entities=entities,
            rendered=rendered | set(state["loops"]) | set(state["decisions"]),
            delivered_rank={aid: i for i, aid in enumerate(state["delivered"])},
            event_artifacts={e["id"]: list(e["artifacts"]) for e in state["events"]},
            forms=forms,
            ambiguous=_ambiguous_forms(state, forms),
        )

    @property
    def date(self) -> str:
        return self.state["date"]

    @property
    def worker(self) -> str:
        return self.state["worker"]

    def ref(self, wid: Any, *, stub: bool = True) -> str | None:
        """Record ID for a world entity, or None.

        Rendered entities always resolve. Otherwise, with `stub=True`, a minimal stub record is
        registered so the link still resolves (front matter needs this; a checked world never
        triggers it for loops). With `stub=False`, unrendered entities return None.
        """
        if not isinstance(wid, str) or wid not in self.ids:
            return None
        if wid in self.rendered or wid in self.stubs:
            return self.ids[wid]
        if not stub or wid not in self.creates:
            return None
        self.stubs[wid] = self.ids[wid]
        return self.ids[wid]

    def link(self, wid: Any) -> str | None:
        """`[[record]]` for a rendered (or already stubbed) object, else None."""
        rid = self.ref(wid, stub=False)
        return f"[[{rid}]]" if rid else None

    def name(self, wid: str) -> str:
        ent = self.entities.get(wid) or self.creates.get(wid)
        return ent["name"] if ent else wid

    def link_or_name(self, wid: str) -> str:
        return self.link(wid) or self.name(wid)

    def cite(self, artifacts: list[str]) -> str:
        """`[src: a, b]` for delivered artifacts in delivery order, or '' when there are none."""
        arts = sorted(
            {a for a in artifacts if a in self.delivered_rank}, key=self.delivered_rank.__getitem__
        )
        return f"[src: {', '.join(arts)}]" if arts else ""

    def events_about(self, wid: str) -> list[dict[str, Any]]:
        """Knowable events whose subjects include `wid`, oldest first."""
        return [e for e in self.state["events"] if wid in e["subjects"]]


# ---------------------------------------------------------------- people
def _person(ctx: _Ctx, pid: str, ent: dict[str, Any]) -> str:
    attrs = _public(ent["attrs"])
    events = ctx.events_about(pid)
    meta: dict[str, Any] = {
        "id": ctx.ids[pid],
        "type": "person",
        "name": ent["name"],
        "aliases": _aliases(ctx, pid, ent, extra=_as_list(attrs.get("email"))),
    }
    if attrs.get("org"):
        org = ctx.ref(attrs["org"])
        if org:
            meta["org"] = org
    for key in ("role", "email", "relationship"):
        if attrs.get(key) is not None:
            meta[key] = attrs[key]
    meta["created"] = events[0]["date"] if events else ctx.date
    meta["updated"] = _last_date(events, ctx.date)
    body = [
        "## Context",
        "",
        _person_context(ctx, pid, ent, attrs),
        "",
        "## Threads",
        "",
        *(_person_threads(ctx, pid) or ["No active threads."]),
        "",
        "## Log",
        "",
        *_log_lines(ctx, events),
    ]
    return frontmatter.dump(meta, "\n".join(body))


def _person_context(ctx: _Ctx, pid: str, ent: dict[str, Any], attrs: dict[str, Any]) -> str:
    """One paragraph of durable facts: role, organization, relationship, other attributes."""
    parts: list[str] = []
    if pid == ctx.worker:
        parts.append("This is the worker, the person this store is kept for.")
    role, org = attrs.get("role"), attrs.get("org")
    org_txt = (
        f"{ctx.name(org)} ({ctx.link(org)})"
        if org and ctx.link(org)
        else (ctx.name(org) if org else "")
    )
    if role and org_txt:
        parts.append(f"{str(role).strip().rstrip('.')} at {org_txt}.")
    elif role:
        parts.append(_sentence(role))
    elif org_txt:
        parts.append(f"Works at {org_txt}.")
    if attrs.get("relationship"):
        parts.append(f"Relationship to the worker: {attrs['relationship']}.")
    for key, value in attrs.items():
        if key not in PERSON_FRONT_ATTRS:
            parts.append(f"{_label(key)}: {_value_text(ctx, value)}.")
    if not parts:
        parts.append("No details recorded yet.")
    cite = ctx.cite(ent["evidence"])
    return " ".join(parts + ([cite] if cite else []))


def _person_threads(ctx: _Ctx, pid: str) -> list[str]:
    """Links to the projects the person currently shares with the worker and their active loops.

    Shared projects follow the `person_brief` gold (`shared_projects`): the person is the
    owner, sponsor or a member of a project that is not done, cancelled or merged, or shares
    an accepted active loop on it with the worker.
    """
    lines = []
    for prid, _how in shared_projects(ctx.state, ctx.worker, pid):
        if prid in ctx.rendered:
            ent = ctx.entities[prid]
            status = _public(ent["attrs"]).get("status") or "active"
            lines.append(f"- [[{ctx.ids[prid]}]]: {ent['name']} ({status})")
    for cid, loop in ctx.state["loops"].items():
        if loop["status"] in ACTIVE_STATUSES and pid in _loop_people(loop):
            lines.append(f"- [[{ctx.ids[cid]}]]: {loop['what']} ({_loop_flags(loop)})")
    return lines


# ---------------------------------------------------------------- orgs
def _org(ctx: _Ctx, oid: str, ent: dict[str, Any]) -> str:
    attrs = _public(ent["attrs"])
    events = ctx.events_about(oid)
    meta: dict[str, Any] = {
        "id": ctx.ids[oid],
        "type": "org",
        "name": ent["name"],
        "aliases": _aliases(ctx, oid, ent, extra=[attrs.get("domain")]),
    }
    for key in ("kind", "domain"):
        if attrs.get(key) is not None:
            meta[key] = attrs[key]
    meta["created"] = events[0]["date"] if events else ctx.date
    meta["updated"] = _last_date(events, ctx.date)
    facts = [f"Kind: {attrs['kind']}." if attrs.get("kind") else ""]
    facts.append(f"Email domain: {attrs['domain']}." if attrs.get("domain") else "")
    facts += [
        f"{_label(k)}: {_value_text(ctx, v)}."
        for k, v in attrs.items()
        if k not in ("kind", "domain")
    ]
    facts.append(ctx.cite(ent["evidence"]))
    people = [
        f"- [[{ctx.ids[p]}]]: {e['name']}"
        for p, e in ctx.entities.items()
        if e["kind"] == "person" and p in ctx.rendered and _public(e["attrs"]).get("org") == oid
    ]
    body = [
        "## Context",
        "",
        " ".join(f for f in facts if f) or "No details recorded yet.",
        "",
        "## People",
        "",
        *(people or ["No people recorded."]),
        "",
        "## Log",
        "",
        *_log_lines(ctx, events),
    ]
    return frontmatter.dump(meta, "\n".join(body))


# ---------------------------------------------------------------- projects
def _project(ctx: _Ctx, prid: str, ent: dict[str, Any]) -> str:
    attrs = _public(ent["attrs"])
    events = [e for e in ctx.state["events"] if e.get("project") == prid or prid in e["subjects"]]
    meta: dict[str, Any] = {
        "id": ctx.ids[prid],
        "type": "project",
        "name": ent["name"],
        "aliases": _aliases(ctx, prid, ent),
        "status": attrs.get("status") or "active",
        "owner": ctx.ref(attrs.get("owner")) or ctx.ref(ctx.worker),
    }
    people = _project_people(ctx, prid)
    if people:
        meta["people"] = sorted({ctx.ids[p] for p in people})
    orgs = [o for o in _as_list(attrs.get("orgs")) if ctx.ref(o, stub=False)]
    if orgs:
        meta["orgs"] = sorted({ctx.ids[o] for o in orgs})
    if attrs.get("target_date"):
        meta["target_date"] = attrs["target_date"]
    if attrs.get("parent"):
        meta["parent"] = ctx.ref(attrs["parent"])
    if attrs.get("split_into"):
        meta["split_into"] = [r for r in (ctx.ref(p) for p in _as_list(attrs["split_into"])) if r]
    if attrs.get("merged_into"):
        meta["merged_into"] = ctx.ref(attrs["merged_into"])
    meta["created"] = events[0]["date"] if events else ctx.date
    meta["updated"] = _last_date(events, ctx.date)
    body = [
        "## Current state",
        "",
        _current_state(ctx, ent, attrs, events),
        "",
        "## Knowledge",
        "",
        *(_knowledge(ctx, ent, attrs) or ["No durable knowledge recorded yet."]),
        "",
        "## Log",
        "",
        *_log_lines(ctx, events),
    ]
    return frontmatter.dump(meta, "\n".join(body))


def _current_state(
    ctx: _Ctx, ent: dict[str, Any], attrs: dict[str, Any], events: list[dict[str, Any]]
) -> str:
    """The single `As of` paragraph: summary, status, phase, target, blocker, next step.

    Dated by the latest knowable project event. Cites the artifacts of the events on that
    date plus the artifacts that set each value shown.
    """
    as_of = _last_date(events, ctx.date)
    parts = [f"As of {as_of}:"]
    if attrs.get("summary"):
        parts.append(_sentence(str(attrs["summary"])))
    parts.append(f"Status: {attrs.get('status') or 'active'}.")
    for key, label in (
        ("phase", "Phase"),
        ("target_date", "Target date"),
        ("blocker", "Blocker"),
        ("next_step", "Next step"),
    ):
        if attrs.get(key):
            parts.append(f"{label}: {_sentence(str(attrs[key]))}")
    sources = [a for e in events if e["date"] == as_of for a in e["artifacts"]]
    for key in ("summary", "status", "phase", "target_date", "blocker", "next_step"):
        if key in attrs:
            sources += _attr_sources(ctx, ent, key)
    cite = ctx.cite(sources)
    return " ".join(parts + ([cite] if cite else []))


def _knowledge(ctx: _Ctx, ent: dict[str, Any], attrs: dict[str, Any]) -> list[str]:
    """Durable context bullets: sponsor, organizations, members and any other attributes."""
    lines = []
    labels = {"sponsor": "Sponsor", "orgs": "Organizations", "members": "Members"}
    keys = [k for k in labels if k in attrs] + [
        k
        for k in attrs
        if k not in labels and k not in PROJECT_STATE_ATTRS + PROJECT_STRUCTURE_ATTRS
    ]
    for key in keys:
        value = attrs[key]
        if value in (None, "", []):
            continue
        cite = ctx.cite(_attr_sources(ctx, ent, key))
        text = f"- {labels.get(key) or _label(key)}: {_value_text(ctx, value)}"
        lines.append(f"{text} {cite}" if cite else text)
    return lines


def _project_people(ctx: _Ctx, prid: str) -> list[str]:
    """Rendered people involved in a project: owner, sponsor, members, everyone on its loops
    and its decision makers."""
    if prid in ctx._people_cache:
        return ctx._people_cache[prid]
    attrs = _public(ctx.entities[prid]["attrs"])
    people = [attrs.get("owner"), attrs.get("sponsor"), *_as_list(attrs.get("members"))]
    for loop in ctx.state["loops"].values():
        if loop.get("project") == prid:
            people += _loop_people(loop)
    for dec in ctx.state["decisions"].values():
        if dec.get("project") == prid:
            people += dec.get("by") or []
    people = [p for p in dict.fromkeys(people) if isinstance(p, str) and p in ctx.rendered]
    ctx._people_cache[prid] = people
    return people


# ---------------------------------------------------------------- loops
def _loop(ctx: _Ctx, cid: str, loop: dict[str, Any]) -> str:
    owner, counterparty = ctx.ref(loop["debtor"]), ctx.ref(loop["creditor"])
    meta: dict[str, Any] = {
        "id": ctx.ids[cid],
        "type": "loop",
        "kind": loop["kind"],
        "title": loop["what"],
        "owner": owner,
        "counterparty": counterparty,
        "status": loop["status"],
        "accepted": bool(loop["accepted"]),
        "due": loop.get("due"),
        "others": [r for r in (ctx.ref(p) for p in loop.get("others") or []) if r],
        "project": ctx.ref(loop.get("project")),
        "created": loop["created"],
        "updated": loop["updated"],
        "evidence": _loop_evidence(ctx, loop),
    }
    prefix = "" if loop["accepted"] else "Suggested, not yet accepted: "
    line = f"{prefix}[[{owner}]] owes [[{counterparty}]]: {_sentence(loop['what'])}"
    if meta["project"]:
        line += f" Project: [[{meta['project']}]]."
    log = [_log_line(h["date"], h["summary"], ctx.cite(h["artifacts"])) for h in loop["history"]]
    return frontmatter.dump(meta, "\n".join([line, "", "## Log", "", *log]))


def _loop_evidence(ctx: _Ctx, loop: dict[str, Any]) -> list[dict[str, str]]:
    """One entry per artifact behind the loop's history, oldest first.

    The first entry carries the loop's own `basis`; later ones derive it from the channel.
    """
    arts = [a for h in loop["history"] for a in h["artifacts"]]
    return _evidence(ctx, arts, first_basis=loop.get("basis"))


def _decision(ctx: _Ctx, did: str, dec: dict[str, Any]) -> str:
    by = [p for p in dec.get("by") or [] if isinstance(p, str)]
    owners = [r for r in (ctx.ref(p) for p in by) if r]
    events = ctx.events_about(did)
    reversed_ = dec["status"] == "reversed"
    meta: dict[str, Any] = {
        "id": ctx.ids[did],
        "type": "loop",
        "kind": "decision",
        "title": dec["what"],
        "owner": owners[0] if owners else ctx.ref(ctx.worker),
        "counterparty": None,
        "status": "reversed" if reversed_ else "done",
        "accepted": True,
        "others": owners[1:],
        "project": ctx.ref(dec.get("project")),
        "outcome": dec["what"],
        "decided_on": dec["made_on"],
    }
    if reversed_:
        meta["reversed_on"] = dec["reversed_on"]
    meta["created"] = dec["made_on"]
    meta["updated"] = _last_date(events, dec["made_on"])
    meta["evidence"] = _evidence(
        ctx, [a for e in events for a in e["artifacts"]] or dec["evidence"]
    )
    deciders = ", ".join(f"[[{r}]]" for r in owners) or "the worker"
    line = f"Decision by {deciders}: {_sentence(dec['what'])}"
    if reversed_:
        reason = f": {_sentence(dec['reason'])}" if dec.get("reason") else "."
        line += f" Reversed on {dec['reversed_on']}{reason}"
    if meta["project"]:
        line += f" Project: [[{meta['project']}]]."
    log = []
    for e in events:
        summary = e["summary"]
        if e["type"] == "decision.reverse" and dec.get("reason"):
            summary = f"{summary} (reason: {dec['reason']})"
        log.append(_log_line(e["date"], summary, ctx.cite(e["artifacts"])))
    return frontmatter.dump(meta, "\n".join([line, "", "## Log", "", *log]))


def _evidence(
    ctx: _Ctx, artifacts: list[str], first_basis: str | None = None
) -> list[dict[str, str]]:
    """Contract evidence entries, one per distinct artifact, in the given order."""
    out: list[dict[str, str]] = []
    for aid in dict.fromkeys(artifacts):
        a = ctx.world.artifacts.get(aid)
        if a is None or aid not in ctx.delivered_rank:
            continue
        basis = (first_basis if not out else None) or CHANNEL_BASIS.get(a.channel, "received")
        out.append({"source": aid, "basis": basis, "date": a.date})
    return out


def _loop_people(loop: dict[str, Any]) -> list[str]:
    return [loop["debtor"], loop["creditor"], *(loop.get("others") or [])]


def _loop_flags(loop: dict[str, Any]) -> str:
    flags = [loop["status"]]
    if loop.get("due"):
        flags.append(f"due {loop['due']}")
    if not loop.get("accepted", True):
        flags.append("suggested")
    return ", ".join(flags)


# ---------------------------------------------------------------- daily logs
def _daily_log(ctx: _Ctx, date: str) -> str:
    """One bullet per artifact delivered on `date`: what it changed, with links.

    Events that only concern unrendered (minor) entities, such as a newsletter sender, are
    not changes to the store, so an artifact revealing only those gets "no change".
    """
    by_id = {e["id"]: e for e in ctx.state["events"]}
    lines = []
    for a in ctx.world.artifacts_on(date):
        events = [
            by_id[eid] for eid in a.reveals if eid in by_id and _touches_store(ctx, by_id[eid])
        ]
        if not events:
            lines.append(f"- {a.id} ({a.channel}): {a.title}: no change")
            continue
        summaries = "; ".join(e["summary"] for e in events)
        targets = [
            s for e in events for s in [*e["subjects"], e.get("project")] if s and s != ctx.worker
        ]
        links = [link for link in dict.fromkeys(ctx.link(t) for t in targets) if link]
        see = f" (see {', '.join(links)})" if links else ""
        lines.append(f"- {a.id} ({a.channel}): {a.title}: {summaries}{see}")
    meta = {"id": f"logs/{date}", "type": "log", "date": date}
    return frontmatter.dump(meta, "\n".join(lines))


def _touches_store(ctx: _Ctx, event: dict[str, Any]) -> bool:
    return any(s in ctx.rendered for s in event["subjects"]) or event.get("project") in ctx.rendered


# ---------------------------------------------------------------- stubs
def _stub(ctx: _Ctx, eid: str, rid: str) -> str:
    """A minimal record for an entity that a link needs but that is not rendered in full."""
    kind = ctx.creates[eid]["kind"]
    meta: dict[str, Any] = {"id": rid, "type": kind, "name": ctx.name(eid), "aliases": []}
    note = "Mentioned in other records; no details are known yet."
    if kind == "project":
        meta.update({"status": "active", "owner": WORKER_RECORD, "updated": ctx.date})
        return frontmatter.dump(meta, f"## Current state\n\nAs of {ctx.date}: {note}\n")
    meta["updated"] = ctx.date
    return frontmatter.dump(meta, f"## Context\n\n{note}\n")


# ---------------------------------------------------------------- helpers
def _public(attrs: dict[str, Any]) -> dict[str, Any]:
    """Attributes without hidden metadata (keys starting with `_`)."""
    return {k: v for k, v in attrs.items() if not k.startswith("_")}


def _known_forms(world: World, state: dict[str, Any]) -> dict[str, list[str]]:
    """Knowable entity ID -> its surface forms that some delivered input has used.

    Contract rule 12: every recorded fact traces to an input, so a form (a nickname, a
    transcript's misspelling) becomes an alias only once an artifact delivered by the state's
    date uses it (`World.form_first_seen`).
    """
    first = world.form_first_seen()
    date = state["date"]
    return {
        eid: [
            f
            for f in ent.get("surface_forms") or []
            if isinstance(f, str) and first.get(eid, {}).get(f, "~") <= date
        ]
        for eid, ent in state["entities"].items()
    }


def _ambiguous_forms(state: dict[str, Any], forms: dict[str, list[str]]) -> set[str]:
    """Normalized names, known surface forms and emails shared by several knowable entities.

    Only entities knowable at the date count, so a homonym who appears later is not hinted at.
    """
    owners: dict[str, set[str]] = {}
    for eid, ent in state["entities"].items():
        email = (ent.get("attrs") or {}).get("email")
        for f in [ent.get("name", ""), *forms.get(eid, []), *_as_list(email)]:
            key = normalize(f).lstrip("@") if isinstance(f, str) else ""
            if key:
                owners.setdefault(key, set()).add(eid)
    return {k for k, v in owners.items() if len(v) > 1}


def _aliases(ctx: _Ctx, eid: str, ent: dict[str, Any], extra: list[Any] | None = None) -> list[str]:
    """Known surface forms (plus email or domain) that belong unambiguously to this entity.

    Only forms some delivered input has used count (`_known_forms`). Contract rule 2: an
    alias shared with another knowable entity, such as the first name of two different
    people, is left out.
    """
    name_key = normalize(ent["name"])
    out: list[str] = []
    seen = {name_key}
    for form in [*ctx.forms.get(eid, []), *(extra or [])]:
        if not isinstance(form, str) or not form.strip():
            continue
        key = normalize(form)
        if key in seen or key.lstrip("@") in ctx.ambiguous:
            continue
        seen.add(key)
        out.append(form)
    return out


def _attr_sources(ctx: _Ctx, ent: dict[str, Any], attr: str) -> list[str]:
    """Artifacts of the event that set the attribute's current value."""
    history = ent.get("attr_history", {}).get(attr) or []
    return ctx.event_artifacts.get(history[-1]["event"], []) if history else []


def _log_lines(ctx: _Ctx, events: list[dict[str, Any]]) -> list[str]:
    return [_log_line(e["date"], e["summary"], ctx.cite(e["artifacts"])) for e in events] or [
        "No entries yet."
    ]


def _log_line(date: str, summary: str, cite: str) -> str:
    return f"- {date}: {summary}" + (f" {cite}" if cite else "")


def _last_date(events: list[dict[str, Any]], default: str) -> str:
    return max((e["date"] for e in events), default=default)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _value_text(ctx: _Ctx, value: Any) -> str:
    """Attribute value as prose: entity IDs become links or names, lists are comma-joined."""
    if isinstance(value, (list, tuple)):
        return ", ".join(_value_text(ctx, v) for v in value)
    if isinstance(value, str) and value in ctx.creates:
        return ctx.link_or_name(value)
    return str(value)


def _label(key: str) -> str:
    return key.replace("_", " ").capitalize()


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."
