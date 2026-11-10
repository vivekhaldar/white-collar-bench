"""Shared state for the artifact renderers (docs/generator.md, "Renderers").

`RenderContext` indexes a plan and its simulation once, so that every renderer can ask:

- who a person is (name, first name, role, organization, email, chat handle, voice);
- what a world event says, and what the loop, decision or project looked like just before
  it (so that a due-date change can name the old date, a transfer the old owner);
- which name form a communication uses for a person (aliases and collisions), and which
  people the communication introduces for the first time;
- a deterministic random generator per artifact.

Nothing here writes files. All randomness is drawn from `random.Random` instances keyed by
the world seed and an artifact or communication ID.
"""

from __future__ import annotations

import copy
import random
import re
from dataclasses import dataclass, field
from typing import Any

from wcb.util.dates import parse_date
from wcb.world.comms import Communication


@dataclass
class Rendered:
    """One artifact file produced by a renderer.

    `content` is text (written as UTF-8) or bytes; `writer`, when set, writes the file itself
    (binary office formats). `text` is the searchable text used for keyword and secret checks.
    """

    artifact: str
    ext: str
    title: str
    content: str | bytes | None = None
    writer: Any = None
    text: str = ""
    secrets: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)
    reveals: list[str] | None = None  # None: the communication's reveals


class RenderContext:
    """Indexes over a plan and its simulation, shared by all renderers."""

    def __init__(self, plan: dict, sim: Any, *, seed: int, rewriter: Any = None):
        self.plan = plan
        self.sim = sim
        self.seed = seed
        self.rewriter = rewriter
        self.worker: str = plan["worker"]
        self.tz: str = plan["setting"]["timezone"]
        self.setting = plan["setting"]
        self.people: dict[str, dict] = {p["id"]: p for p in plan["people"]}
        self.orgs: dict[str, dict] = {o["id"]: o for o in plan["orgs"]}
        self.events: dict[str, dict] = {e["id"]: e for e in sim.events}
        self.umbrella = self.orgs[self.setting["umbrella"]]
        self.central = self.orgs[self.setting["central"]]
        self.workspace = self.setting.get("chat_workspace") or self.umbrella["slug"]
        self.first_names: set[str] = {p["first"] for p in plan["people"] if p.get("last")}
        self.by_first: dict[str, list[str]] = {}
        for p in plan["people"]:
            if p.get("last"):
                self.by_first.setdefault(p["first"], []).append(p["id"])
        self.collisions: set[str] = {
            pid for pair in plan.get("collisions", {}).get("first_names", []) for pid in pair
        }
        self.homophones: list[str] = list(plan.get("collisions", {}).get("homophones", []))
        self.plan_projects: dict[str, dict] = {p["id"]: p for p in plan["projects"]}
        self.projects: dict[str, dict] = {}
        self.loop_create: dict[str, dict] = {}
        self.dec_create: dict[str, dict] = {}
        self.loop_before: dict[str, dict] = {}  # event id -> loop state just before the event
        self.proj_before: dict[str, dict] = {}  # event id -> project attrs just before the event
        self._index_events()
        self.comm_by_id: dict[str, Communication] = {c.id: c for c in sim.comms}
        self.first_revealer: dict[str, str] = {}  # event id -> first communication revealing it
        for c in sorted(sim.comms, key=lambda c: (c.received_at, c.id)):
            for a in c.acts:
                self.first_revealer.setdefault(a.event, c.id)
        self.entity_known: dict[str, str] = {}  # entity id -> first delivery date revealing it
        self.introduced_in: dict[str, str] = {}  # entity id -> comm that first reveals it
        for c in sorted(sim.comms, key=lambda c: (c.received_at, c.id)):
            for a in c.acts:
                e = self.events.get(a.event)
                if e and e["type"] == "entity.create":
                    ent = e["entity"]
                    if ent not in self.entity_known or c.date < self.entity_known[ent]:
                        self.entity_known[ent] = c.date
                        self.introduced_in.setdefault(ent, c.id)
        self.thread_history: dict[str, list[dict]] = {}
        self.mangled: dict[str, dict[str, str]] = {}  # comm id -> name -> transcript misspelling
        self.children: dict[str, list[Communication]] = {}  # comm id -> attachments
        for c in sim.comms:
            if c.parent:
                self.children.setdefault(c.parent, []).append(c)
        self.injection_artifact: str | None = None

    # ------------------------------------------------------------ indexing
    def _index_events(self) -> None:
        loops: dict[str, dict] = {}
        projs: dict[str, dict] = {}
        for e in self.sim.events:
            et = e["type"]
            if et == "entity.create" and e["kind"] == "project":
                pp = self.plan_projects.get(e["entity"], {})
                self.projects[e["entity"]] = {
                    "id": e["entity"],
                    "name": e["name"],
                    "short": pp.get("short") or e["name"],
                    "kw": pp.get("kw") or e["name"].lower(),
                    "code": pp.get("code"),
                    "surface_forms": list(e.get("surface_forms") or []),
                    "attrs": copy.deepcopy(e.get("attrs") or {}),
                    "unit": pp.get("unit"),
                    "vendors": list(pp.get("vendors") or []),
                    "topic": pp.get("topic"),
                }
                projs[e["entity"]] = copy.deepcopy(e.get("attrs") or {})
            elif et == "fact.set" and e["subject"] in projs:
                self.proj_before[e["id"]] = copy.deepcopy(projs[e["subject"]])
                projs[e["subject"]][e["attribute"]] = e.get("value")
            elif et == "commitment.create":
                self.loop_create[e["commitment"]] = e
                loops[e["commitment"]] = {
                    k: copy.deepcopy(e.get(k))
                    for k in ("what", "debtor", "creditor", "others", "project", "status", "due",
                              "accepted", "kind", "keywords")
                }
            elif et in ("commitment.update", "commitment.resolve"):
                cur = loops.get(e["commitment"])
                if cur is None:
                    continue
                self.loop_before[e["id"]] = copy.deepcopy(cur)
                if et == "commitment.resolve":
                    cur["status"] = e["status"]
                else:
                    for k, v in (e.get("changes") or {}).items():
                        cur[k] = copy.deepcopy(v)
            elif et == "decision.make":
                self.dec_create[e["decision"]] = e
            elif et == "project.merge":
                for p in e.get("projects") or []:
                    if p in projs:
                        projs[p]["status"] = "merged"

    # ------------------------------------------------------------ randomness
    def rng(self, *key: Any) -> random.Random:
        return random.Random("wcb-render:" + ":".join(str(k) for k in (self.seed, *key)))

    # ------------------------------------------------------------ people
    def person(self, pid: str | None) -> dict:
        return self.people.get(pid or "", {})

    def is_bot(self, pid: str | None) -> bool:
        p = self.person(pid)
        return bool(p) and not p.get("last")

    def full(self, pid: str | None) -> str:
        p = self.person(pid)
        return p.get("name", pid or "someone")

    def first(self, pid: str | None) -> str:
        p = self.person(pid)
        if not p:
            return pid or "someone"
        return p["first"] if p.get("last") else p["name"]

    def form(self, pid: str | None, comm: Communication | None = None) -> str:
        """How `comm` refers to a person: its planned name form, else the first name.

        People who share a first name are named in full unless the communication plants the
        collision (its name form is the bare first name)."""
        if comm is not None:
            f = (comm.extra.get("name_forms") or {}).get(pid or "")
            if f:
                return f
        if pid in self.collisions:
            return self.full(pid)
        return self.first(pid)

    def call_name(self, pid: str | None, comm: Communication | None = None) -> str:
        """What someone is called in a greeting or sign-off: their nickname or first name.

        A planted name form is used only when it is a name (never a role phrase)."""
        p = self.person(pid)
        f = (comm.extra.get("name_forms") or {}).get(pid or "") if comm is not None else None
        if f and f in (p.get("nickname"), p.get("first")):
            return f
        return self.first(pid)

    def display_name(self, pid: str | None, comm: Communication | None = None) -> str:
        """A chat display name: the planted nickname or bare first name, else the full name."""
        p = self.person(pid)
        f = (comm.extra.get("name_forms") or {}).get(pid or "") if comm is not None else None
        if f and f in (p.get("nickname"), p.get("first")):
            return f
        return self.full(pid)

    def role(self, pid: str | None) -> str:
        return str(self.person(pid).get("role") or "")

    def short_role(self, pid: str | None) -> str:
        """The role without a trailing ', <organization>'."""
        r = self.role(pid)
        org = self.org_of(pid)
        if org and r.endswith(", " + org["name"]):
            r = r[: -len(org["name"]) - 2]
        return r

    def org_of(self, pid: str | None) -> dict | None:
        return self.orgs.get(self.person(pid).get("org") or "")

    def email(self, pid: str | None) -> str:
        return str(self.person(pid).get("email") or f"{pid}@unknown.example")

    def handle(self, pid: str | None) -> str:
        h = self.person(pid).get("handle")
        return h or "@" + re.sub(r"[^a-z0-9]+", "", self.first(pid).lower())

    def voice(self, pid: str | None) -> str:
        if pid == self.worker:
            return "terse"
        return str(self.person(pid).get("voice") or "formal")

    def address(self, pid: str) -> str:
        """`Name <email>` for email headers."""
        name = self.full(pid)
        if any(ch in name for ch in ',."()'):
            name = '"' + name.replace('"', "") + '"'
        return f"{name} <{self.email(pid)}>"

    def signature(self, pid: str) -> list[str]:
        org = self.org_of(pid)
        lines = [self.full(pid), self.short_role(pid)]
        if org and org["role"] in ("central",):
            lines.append(f"{org['name']}, {self.umbrella['name']}")
        elif org:
            lines.append(org["name"])
        return [x for x in lines if x]

    # ------------------------------------------------------------ projects
    def project(self, pid: str | None) -> dict | None:
        return self.projects.get(pid or "")

    def pname(self, pid: str | None) -> str:
        p = self.project(pid)
        return p["name"] if p else ""

    def pshort(self, pid: str | None) -> str:
        p = self.project(pid)
        return p["short"] if p else ""

    # ------------------------------------------------------------ communications
    def introduces(self, comm: Communication) -> set[str]:
        """Entities whose `entity.create` this communication reveals first."""
        return {
            self.events[a.event]["entity"]
            for a in comm.acts
            if self.events[a.event]["type"] == "entity.create"
            and self.introduced_in.get(self.events[a.event]["entity"]) == comm.id
        }

    def org_short(self, oid: str | None) -> str:
        o = self.orgs.get(oid or "")
        return o["short"] if o else ""


# ---------------------------------------------------------------- date words
def day_words(date: str, style: int = 0) -> str:
    """A date in prose: 0 'Thursday 8 April', 1 'Thu 8 Apr', 2 'April 8', 3 '8 April'."""
    d = parse_date(date)
    month, wd = d.strftime("%B"), d.strftime("%A")
    return (
        f"{wd} {d.day} {month}",
        f"{wd[:3]} {d.day} {month[:3]}",
        f"{month} {d.day}",
        f"{d.day} {month}",
    )[style % 4]


def time_words(t: str) -> str:
    """'2027-04-06T14:30:00-07:00' -> '2:30pm'."""
    h, m = int(t[11:13]), int(t[14:16])
    suffix = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d}{suffix}" if m else f"{h12}{suffix}"
