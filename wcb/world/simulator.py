"""World simulator: step a plan day by day into world events and communications.

`simulate(plan, seed)` turns a plan (`wcb.world.planner.make_plan`) into

- **events**: `entity.create`, `fact.set`, `commitment.*`, `decision.*` and `project.*` world
  events (docs/formats.md §1.2), sorted by time and numbered `e-0001`...;
- **communications** (`wcb.world.comms`): the emails, chats, meetings, documents, notes and
  calendar items that reveal those events, each with artifact IDs assigned in delivery order;
- **meta**: the `world.yaml` content.

The simulator steps from the seed start to the last episode day. On each delivery day it

1. holds the day's meetings (recurring cadences and ad hoc project meetings);
2. runs the planted-challenge scenarios scheduled for the day (planner `challenges`);
3. applies scheduled loop transitions (bimodal lifetimes, docs/calibration.md);
4. moves projects between archetype phases and fires their beats;
5. creates the day's new loops (5-9 per weekday, rising over the period) from archetype beats;
6. seals the day: drops empty meetings, reveals the people each communication shows, and adds
   noise (about half of email) and filler until the day reaches its volume target.

Knowability is enforced as communications are built: whenever an act reveals an event, every
object the event depends on (the loop it updates, the people and project a loop names, the
entities in an attribute) is revealed by the same communication unless an earlier delivery
already revealed it. Deliberately unrevealed events (weak evidence, unobservable facts,
unreported closures) are listed in `Simulation.unrevealed`.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any

from wcb.util.dates import add_days, next_business_day, parse_date
from wcb.world import archetypes as A
from wcb.world.comms import CHANNEL_OF_KIND, PREFIX_CHANNEL, Act, Communication

ACTIVE = ("open", "waiting", "blocked")
WEEKDAY_LOOPS = (1.3, 1.2, 1.0, 0.9, 0.7, 0.2, 0.0)
WEEKDAY_VOLUME = (1.1, 1.06, 1.0, 0.96, 0.9, 0.33, 0.0)
BASIS_MIX = (("reported", 0.52), ("received", 0.21), ("sent", 0.22), ("scheduled", 0.03), ("inferred", 0.02))
OWNER_MIX = (("worker", 0.44), ("others", 0.47), ("joint", 0.09))
COVERAGE_MIX = (("transcript", 0.45), ("transcript+recap", 0.10), ("recap", 0.25), ("debrief", 0.15),
                ("voice_debrief", 0.05))
# Bimodal lifetimes: a loop closes fast (0-2 business days), slowly (3-20) or stays live. The
# worker clears their own items faster than others answer, so waiting loops pile up.
P_FAST = {"worker": 0.50, "others": 0.29}
P_MED = {"worker": 0.20, "others": 0.20}
P_SUGGEST_ASK = 0.65  # an incoming ask that the worker has not agreed to yet
P_SUGGEST_RECAP = 0.28  # an action an AI recap or meeting proposes
P_SUGGEST_PROPOSAL = 0.15  # a task proposed for the worker in a meeting, not yet taken on
P_UNREPORTED = 0.04  # a closure no communication ever reports
NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
DAY_START, DAY_END, EVENING_END = 7 * 60 + 30, 18 * 60 + 30, 21 * 60 + 30

PAST = {
    "send": "sent", "review": "reviewed", "return": "returned", "write": "wrote", "draft": "drafted",
    "deliver": "delivered", "register": "registered", "book": "booked", "confirm": "confirmed",
    "provision": "provisioned", "assemble": "assembled", "complete": "completed", "generate": "generated",
    "revise": "revised", "run": "ran", "scope": "scoped", "publish": "published", "set": "set",
    "configure": "configured", "rotate": "rotated", "circulate": "circulated", "answer": "answered",
    "add": "added", "collect": "collected", "countersign": "countersigned", "pull": "pulled",
    "line": "lined", "finish": "finished", "present": "presented", "comment": "commented", "hold": "held",
    "introduce": "introduced", "share": "shared", "update": "updated", "join": "joined", "order": "ordered",
    "turn": "turned", "propose": "proposed", "demo": "demoed", "groom": "groomed", "recruit": "recruited",
    "hand": "handed", "rebase": "rebased", "rewrite": "rewrote", "schedule": "scheduled", "post": "posted",
    "submit": "submitted", "check": "checked", "approve": "approved", "agree": "agreed",
    "summarize": "summarized", "deploy": "deployed", "walk": "walked", "look": "looked", "fix": "fixed",
    "get": "got", "pick": "picked", "close": "closed", "sign": "signed", "tell": "told", "chase": "chased",
}
PARTICLES = ("up", "together", "around", "into", "over", "through", "out")
ISSUES = ("timeout errors", "login loop", "export failures", "slow page loads", "missing roster sync",
          "duplicate notifications", "broken deep links", "stale cache")
ACCESS = ("sandbox access", "staging access", "dashboard access", "test tenant login", "API credentials")
DROP_REASONS = ("folded into a broader ask", "superseded by a decision", "no longer needed",
                "duplicate of another ask", "overtaken by events")
REOPEN_REASONS = ("the first version missed a section", "the numbers did not reconcile",
                  "the fix did not hold")
BLOCK_REASONS = ("waiting on an unsigned agreement", "waiting on access approval", "waiting on a vendor fix")


# ---------------------------------------------------------------- results
@dataclass
class Simulation:
    """The simulator's output. `meta` is the `world.yaml` content."""

    events: list[dict]
    comms: list[Communication]
    meta: dict
    unrevealed: dict[str, str] = field(default_factory=dict)  # event id -> reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "events": self.events,
            "comms": [c.to_dict() for c in self.comms],
            "unrevealed": dict(self.unrevealed),
        }

    def artifact_events(self) -> list[dict]:
        """Preview `artifact.emit` events for the communications (one per artifact ID).

        Renderers write the real ones; this preview lets tests and tools compute gold state
        without files. Event IDs continue after the last world event.
        """
        n = len(self.events)
        ext = {"em": ".eml", "ch": ".json", "mt": ".vtt", "mn": ".md", "nt": ".md", "ca": ".ics"}
        first: dict[str, str] = {c.id: c.artifacts[0] for c in self.comms if c.artifacts}
        out = []
        for c in self.comms:
            for aid in c.artifacts:
                n += 1
                prefix = aid[:2]
                suffix = ext.get(prefix) or "." + str(c.extra.get("format", "md"))
                out.append({
                    "id": f"e-{n:04d}", "t": c.received_at, "type": "artifact.emit", "artifact": aid,
                    "channel": PREFIX_CHANNEL[prefix], "path": f"inbox/{c.date}/{aid}{suffix}",
                    "received_at": c.received_at, "reveals": c.reveals(), "noise": c.noise,
                    "challenges": list(c.challenges), "secrets": list(c.secrets) if aid == c.artifacts[0] else [],
                    "title": c.subject or aid, "parent": first.get(c.parent) if c.parent else None,
                })
        return out

    def world(self):
        """An in-memory `wcb.world.model.World` with preview artifacts (no files)."""
        from wcb.world.model import Artifact, World

        rows = list(self.events) + self.artifact_events()
        events = [e for _, e in sorted(enumerate(rows), key=lambda p: (p[1]["t"], p[0]))]
        world = World(dir=Path("."), meta=self.meta, events=events, artifacts={}, by_id={})
        for e in events:
            world.by_id.setdefault(e["id"], e)
            if e["type"] == "artifact.emit":
                world.artifacts[e["artifact"]] = Artifact(
                    id=e["artifact"], channel=e["channel"], path=e["path"], received_at=e["received_at"],
                    reveals=list(e["reveals"]), noise=e["noise"], challenges=list(e["challenges"]),
                    secrets=list(e["secrets"]), title=e["title"], parent=e["parent"], event_id=e["id"],
                )
        return world


def simulate(plan: dict, seed: int) -> Simulation:
    """Simulate a plan. Deterministic in (plan, seed)."""
    return _Sim(plan, seed).run()


# ---------------------------------------------------------------- simulation state
@dataclass
class _Loop:
    id: str
    kind: str
    what: str
    debtor: str
    creditor: str
    others: list[str]
    project: str | None
    status: str
    due: str | None
    accepted: bool
    keywords: list[str]
    basis: str
    created: str
    last_t: str
    thread: str | None = None
    frozen: bool = False


@dataclass
class _Proj:
    id: str
    p: dict
    arch: A.Archetype
    phase: str
    status: str
    target: str | None
    blocker: str | None
    next_step: str | None
    owner: str
    sponsor: str
    members: list[str]
    weight: float
    uses: Counter = field(default_factory=Counter)
    nouns: set = field(default_factory=set)
    merged: bool = False
    decisions: list[str] = field(default_factory=list)
    since: str = ""  # first day the project can carry activity (projects born mid-day wait a day)

    @property
    def active(self) -> bool:
        return self.status == "active" and not self.merged


class _Sim:
    def __init__(self, plan: dict, seed: int):
        self.plan = plan
        self.seed = seed
        self.rng = random.Random(f"wcb-sim:{seed}:{plan['world_id']}")
        st = plan["setting"]
        self.tz = st["timezone"]
        self.vocab = NS(**st["vocab"])
        self.nouns = list(st["nouns"])
        self.W = plan["worker"]
        self.people = {p["id"]: p for p in plan["people"]}
        self.orgs = {o["id"]: o for o in plan["orgs"]}
        self.cal = plan["calendar"]
        self.days = sorted(set(self.cal["seed"]["days"]) | set(self.cal["episode"]["days"]))
        self.first_day, self.last_day = self.days[0], self.days[-1]
        self.episode_days = list(self.cal["episode"]["days"])
        self.first_names = {p["first"] for p in plan["people"] if p.get("last")}
        self.collab = next((p["id"] for p in plan["people"] if p.get("group") == "central" and p["weight"] >= 5), self.W)
        self.manager = next(p["id"] for p in plan["people"] if p.get("relationship") == "manager")
        self.mailbox = next(p["id"] for p in plan["people"] if p.get("group") == "mailbox")
        self.minors = [p["id"] for p in plan["people"] if p.get("tier") == "minor"]
        self.hub_id = next(p["id"] for p in plan["projects"] if p["archetype"] == "platform_hub")
        self.flagship_id = next(p["id"] for p in plan["projects"] if p["archetype"] == "flagship_pilot")
        self.projs: dict[str, _Proj] = {}
        self.plan_projects = {p["id"]: p for p in plan["projects"]}
        self.created_today = 0
        self.events: list[dict] = []
        self.ev: dict[str, dict] = {}
        self.comms: list[Communication] = []
        self.day_comms: list[Communication] = []
        self.known: dict[str, str] = {}
        self.ent_ev: dict[str, str] = {}
        self.loop_ev: dict[str, str] = {}
        self.dec_ev: dict[str, str] = {}
        self.loops: dict[str, _Loop] = {}
        self.dec: dict[str, dict] = {}
        self.agenda: dict[str, list[tuple]] = defaultdict(list)
        self.unrevealed: dict[str, str] = {}
        self.threads: dict[str, str] = {}
        self.sc: dict[tuple, dict] = {}
        self.seq = 0
        self.n_loops = 0
        self.n_dec = 0
        self.n_comm = 0
        self.n_thread = 0
        self.today = self.first_day
        self.recent: list[tuple[str, str]] = []  # (date, event id) of revealed state changes

    # ============================================================ driver
    def run(self) -> Simulation:
        self._init_entities()
        for ch in self.plan["challenges"]:
            if ch.get("setup"):
                self._schedule(ch["setup"], 0, "challenge", (ch, "setup"))
            for i, d in enumerate(ch.get("steps") or []):
                self._schedule(d, 1, "challenge", (ch, f"step{i}"))
            if not ch.get("steps"):
                self._schedule(ch["day"], 1, "challenge", (ch, "day"))
        for day in self.days:
            self._day(day)
        return self._finalize()

    def _schedule(self, day: str, prio: int, kind: str, payload: Any) -> None:
        self.seq += 1
        self.agenda[day].append((prio, self.seq, kind, payload))

    def _day(self, day: str) -> None:
        self.today = day
        self.day_comms = []
        self.created_today = 0
        wd = parse_date(day).weekday()
        if day == self.first_day:
            self._portfolio_note(day)
        if wd < 5:
            self._meetings(day)
        self._weekly_update(day)
        for _prio, _s, kind, payload in sorted(self.agenda.pop(day, []), key=lambda x: (x[0], x[1])):
            if kind == "challenge":
                self._challenge(day, *payload)
            elif kind == "loop":
                self._transition(day, *payload)
        if wd < 5:
            self._phase_moves(day)
            self._facts_and_decisions(day)
        self._new_loops(day)
        self._seal_day(day)

    # ============================================================ basic helpers
    def ts(self, day: str, minute: int) -> str:
        minute = max(0, min(int(minute), 23 * 60 + 59))
        return f"{day}T{minute // 60:02d}:{minute % 60:02d}:00{self.tz}"

    @staticmethod
    def minute(t: str) -> int:
        return int(t[11:13]) * 60 + int(t[14:16])

    def rand_minute(self, lo: int = DAY_START, hi: int = DAY_END) -> int:
        lo, hi = int(lo), int(hi)
        return self.rng.randint(lo, max(lo, hi))

    def bday(self, day: str, n: int) -> str:
        d = day
        for _ in range(n):
            d = next_business_day(d)
        return d

    def weekday(self, day: str) -> int:
        return parse_date(day).weekday()

    def pick(self, items: list, weights: list[float] | None = None):
        if not items:
            return None
        if weights is None:
            return self.rng.choice(items)
        if sum(weights) <= 0:
            return self.rng.choice(items)
        return self.rng.choices(items, weights=weights)[0]

    def mix(self, table) -> str:
        return self.pick([k for k, _ in table], [w for _, w in table])

    def first(self, pid: str) -> str:
        p = self.people[pid]
        return p["first"] if p.get("last") else p["name"]

    def pns(self, pid: str | None) -> NS:
        if pid is None:
            return NS(first="someone", name="someone", id=None)
        p = self.people[pid]
        return NS(first=self.first(pid), name=p["name"], id=pid)

    def _ok(self, pid: str | None, day: str) -> bool:
        if not pid or pid not in self.people:
            return False
        p = self.people[pid]
        if p.get("tier") == "minor":
            return False
        ap = p.get("appears")
        if ap and ap >= day:
            return False  # newcomers appear through their own scenario, then join in
        return pid in self.ent_ev

    # ============================================================ events
    def _ev(self, etype: str, t: str, summary: str, **fields: Any) -> dict:
        self.seq += 1
        e: dict[str, Any] = {"id": f"x{self.seq}", "t": t, "type": etype, "summary": summary}
        e.update(fields)
        e["_seq"] = self.seq
        self.events.append(e)
        self.ev[e["id"]] = e
        return e

    def _deps(self, e: dict) -> list[str]:
        out: list[str] = []

        def ent(x: Any) -> None:
            for v in x if isinstance(x, list) else [x]:
                if isinstance(v, str) and v != self.W and v in self.ent_ev:
                    out.append(self.ent_ev[v])

        et = e["type"]
        if et == "entity.create":
            a = e.get("attrs") or {}
            if e["kind"] == "person":
                ent(a.get("org"))
            elif e["kind"] == "project":
                for k in ("owner", "sponsor", "members", "orgs", "parent"):
                    ent(a.get(k))
        elif et == "fact.set":
            ent(e["subject"])
            if e["attribute"] in ("owner", "sponsor", "members", "orgs", "parent"):
                ent(e.get("value"))
        elif et == "commitment.create":
            ent([e["debtor"], e["creditor"], *(e.get("others") or [])])
            ent(e.get("project"))
        elif et == "commitment.update":
            out.append(self.loop_ev[e["commitment"]])
            ch = e["changes"]
            ent([ch.get("debtor"), ch.get("creditor"), *(ch.get("others") or [])])
            ent(ch.get("project"))
        elif et == "commitment.resolve":
            out.append(self.loop_ev[e["commitment"]])
        elif et == "decision.make":
            ent(list(e.get("by") or []))
            ent(e.get("project"))
        elif et == "decision.reverse":
            out.append(self.dec_ev[e["decision"]])
        elif et == "project.split":
            ent(e["project"])
            ent(list(e["into"]))
            for cid, target in (e.get("moves") or {}).items():
                out.append(self.loop_ev[cid])
                ent(target)
        elif et == "project.merge":
            ent(list(e["projects"]))
            ent(e["into"])
        return [d for d in out if d != e["id"]]

    def reveal(self, comm: Communication, eid: str, how: str = "direct", by: str | None = None,
               primary: bool = True) -> None:
        """Add an act to `comm`, first revealing every dependency not yet known by its delivery."""
        if eid in self.unrevealed:
            raise AssertionError(f"{eid} is deliberately unrevealed")
        if any(a.event == eid for a in comm.acts):
            return
        e = self.ev[eid]
        if e["t"] > comm.t:
            raise AssertionError(f"{comm.id} at {comm.t} cannot reveal {eid} at {e['t']}")
        rdate = comm.date
        for dep in self._deps(e):
            k = self.known.get(dep)
            if k is None or k > rdate:
                self.reveal(comm, dep, "direct", primary=False)
        if primary and eid in self.known and e["type"] != "entity.create":
            comm.extra.setdefault("_dup", []).append(eid)
        comm.acts.append(Act(eid, how, by))
        if eid not in self.known or rdate < self.known[eid]:
            self.known[eid] = rdate
        if primary and e["type"] != "entity.create":
            self.recent.append((rdate, eid))

    def hide(self, e: dict, reason: str) -> None:
        self.unrevealed[e["id"]] = reason

    # ============================================================ entities
    def _init_entities(self) -> None:
        t0 = self.ts(self.first_day, 6 * 60)
        plan = self.plan
        w = self.people[self.W]
        self._person_create(w, t0, summary=f"{w['name']}, {w['role']} (the worker)")
        for o in plan["orgs"]:
            kind_word = {"umbrella": "our organization", "central": "my team", "unit": f"a {self.vocab.unit_word}",
                         "vendor": "a vendor", "partner": "a partner"}[o["role"]]
            e = self._ev("entity.create", t0, f"{o['name']}, {kind_word}", entity=o["id"], kind="org", name=o["name"],
                         surface_forms=list(o["surface_forms"]), attrs={"kind": o["kind"], "domain": o["domain"]})
            self.ent_ev[o["id"]] = e["id"]
        for p in plan["people"]:
            if p["id"] == self.W or p.get("appears"):
                continue
            self._person_create(p, t0)
        for pp in plan["projects"]:
            self._project_create(pp, t0)

    def _person_create(self, p: dict, t: str, summary: str | None = None) -> dict:
        attrs: dict[str, Any] = {}
        if p.get("tier") == "minor":
            attrs = {"_minor": True, "role": p["role"], "email": p["email"]}
        else:
            if p.get("org"):
                attrs["org"] = p["org"]
            attrs["role"] = p["role"]
            attrs["email"] = p["email"]
            if p.get("relationship"):
                attrs["relationship"] = p["relationship"]
        if summary is None:
            org = self.orgs.get(p.get("org") or "")
            summary = f"{p['name']}, {p['role']}" if not org or org["name"] in p["role"] else f"{p['name']}, {p['role']} at {org['name']}"
        e = self._ev("entity.create", t, summary, entity=p["id"], kind="person", name=p["name"],
                     surface_forms=list(p["surface_forms"]), attrs=attrs)
        self.ent_ev[p["id"]] = e["id"]
        return e

    def _project_create(self, pp: dict, t: str, *, parent: str | None = None, summary: str | None = None) -> dict:
        arch = A.get(pp["archetype"])
        proj = _Proj(
            id=pp["id"], p=pp, arch=arch, phase=pp["phase"], status=pp["status"], target=pp.get("target_date"),
            blocker=None, next_step=None, owner=pp["owner"], sponsor=pp["sponsor"], members=list(pp["members"]),
            weight=float(pp["weight"]),
        )
        proj.since = t[:10] if t[:10] > self.first_day else ""
        self.projs[pp["id"]] = proj
        attrs: dict[str, Any] = {
            "status": proj.status, "owner": proj.owner, "summary": self._summary_text(proj),
            "phase": proj.phase,
        }
        if proj.target:
            attrs["target_date"] = proj.target
        attrs["sponsor"] = proj.sponsor
        attrs["members"] = list(proj.members)
        if pp.get("orgs"):
            attrs["orgs"] = list(pp["orgs"])
        if parent:
            attrs["parent"] = parent
        attrs["_archetype"] = arch.name
        attrs["_size"] = pp["size"]
        e = self._ev("entity.create", t, summary or f"{pp['name']}: {self._desc(proj)}", entity=pp["id"],
                     kind="project", name=pp["name"], surface_forms=list(pp["surface_forms"]), attrs=attrs)
        self.ent_ev[pp["id"]] = e["id"]
        return e

    # ============================================================ text
    def _ctx(self, proj: _Proj | None, **people: str | None) -> dict[str, Any]:
        v = self.vocab
        ctx: dict[str, Any] = {"v": v, "worker": self.pns(self.W), "n2": "two", "date": ""}
        if proj is not None:
            pp = proj.p
            unit = self.orgs.get(pp.get("unit") or "")
            vendors = [self.orgs[x] for x in pp.get("vendors") or []]
            partner = self.orgs.get(pp.get("partner") or "")
            hub = self.plan_projects[self.hub_id]
            ctx.update(
                proj=NS(short=pp["short"], kw=pp["kw"], name=pp["name"]),
                unit=NS(short=unit["short"], name=unit["name"]) if unit else NS(short="the unit", name="the unit"),
                vendor=NS(short=vendors[0]["short"], name=vendors[0]["name"]) if vendors else NS(short="the vendor", name=""),
                vendor2=NS(short=vendors[-1]["short"], name=vendors[-1]["name"]) if vendors else NS(short="the vendor", name=""),
                partner=NS(short=partner["short"], name=partner["name"]) if partner else NS(short="our partner", name=""),
                hub=NS(short=hub["short"], kw=hub["kw"]),
                topic=pp.get("topic") or "AI adoption", topic_a=pp.get("topic_a") or "an AI assistant",
                pivot=pp.get("pivot") or "a new problem", role=pp.get("role") or "specialist",
                n=NUMBER_WORDS.get(pp.get("n", 3), "three"),
                owner=self.pns(proj.owner), sponsor=self.pns(proj.sponsor),
                lead=self.pns(pp["cast"].get("lead")), cand=self.pns(pp["cast"].get("cand")),
            )
        else:
            topic = self.rng.choice([t for t, _ in self._setting_topics()])
            hub = self.plan_projects[self.hub_id]
            ctx.update(proj=NS(short="", kw="", name=""), topic=topic, n="three", hub=NS(short=hub["short"], kw=hub["kw"]))
        for k, pid in people.items():
            ctx[k] = self.pns(pid)
        return ctx

    def _setting_topics(self) -> list[tuple[str, str]]:
        from wcb.world.planner import SETTINGS

        return list(SETTINGS[self.plan["setting"]["key"]].topics)

    def fmt(self, template: str, ctx: dict[str, Any]) -> str:
        out = template.format_map(ctx)
        return " ".join(out.split())

    def _desc(self, proj: _Proj) -> str:
        return self.fmt(proj.arch.desc, self._ctx(proj, cp=proj.owner))

    def _summary_text(self, proj: _Proj) -> str:
        desc = self._desc(proj)
        if proj.merged:
            return desc + " Folded into another project."
        if proj.status == "done":
            return desc + " Completed."
        if proj.status in ("dormant", "paused"):
            return desc + f" Currently {proj.status}; no recent activity."
        if proj.status == "cancelled":
            return desc + " Cancelled."
        parts = ["Ongoing" if proj.phase == "ongoing" else f"Currently in {proj.phase}"]
        if proj.blocker:
            parts.append(f"blocked on {proj.blocker}")
        if proj.target:
            d = parse_date(proj.target)
            parts.append(f"target date {d.day} {d.strftime('%B')}")
        return desc + " " + "; ".join(parts) + "."

    @staticmethod
    def lower_first(s: str) -> str:
        w = s.split(" ", 1)[0]
        if len(w) > 1 and w.isupper():
            return s
        return s[:1].lower() + s[1:]

    def past(self, what: str, debtor: str) -> str:
        """'Send Ana the risk register' -> 'Bo sent me the risk register' (worker POV)."""
        verb, _, rest = what.partition(" ")
        pv = PAST.get(verb.lower())
        subj = "I" if debtor == self.W else self.first(debtor)
        wf = self.first(self.W)
        rest = rest.replace(f"{wf} ", "me ", 1) if rest.startswith(f"{wf} ") else rest
        if pv is None:
            return f"{subj} completed: {self.lower_first(what)}"
        return f"{subj} {pv} {rest}".strip()

    def subject_of(self, what: str) -> str:
        """A noun phrase for a loop: 'Send Ana the Heron risk register' -> 'Heron risk register'."""
        words = what.split()
        if not words:
            return what
        i = 1
        if i < len(words) and words[i].lower() in PARTICLES:
            i += 1
        if i < len(words) and words[i] in self.first_names:
            i += 1
        if i < len(words) and words[i].lower() in PARTICLES:
            i += 1
        if i < len(words) and words[i].lower() in ("the", "a", "an", "our"):
            i += 1
        rest = " ".join(words[i:]) or what
        return rest[:1].upper() + rest[1:]

    @staticmethod
    def date_words(d: str) -> str:
        x = parse_date(d)
        return f"{x.strftime('%A')} {x.day} {x.strftime('%B')}"

    # ============================================================ people selection
    def proj_people(self, proj: _Proj | None, day: str) -> list[str]:
        if proj is None:
            pool = [p["id"] for p in self.plan["people"] if p.get("tier") == "core" and p.get("group") != "mailbox"]
        else:
            c = proj.p["cast"]
            pool = list(proj.members) + [c["collab"]] + list(c.get("unit") or [])
        out = []
        for pid in pool:
            if pid != self.W and pid not in out and self._ok(pid, day):
                out.append(pid)
        return out

    def weight_of(self, pid: str, proj: _Proj | None) -> float:
        w = float(self.people[pid].get("weight") or 1.0)
        if proj is not None and pid in proj.members:
            w *= 1.5
        return max(w, 0.05)

    def pick_cp(self, proj: _Proj | None, day: str, exclude: set[str] = frozenset()) -> str | None:
        pool = [p for p in self.proj_people(proj, day) if p not in exclude]
        if proj is not None and self.collab not in exclude and self.collab not in pool and self.rng.random() < 0.12:
            pool.append(self.collab)
        return self.pick(pool, [self.weight_of(p, proj) for p in pool])

    def role(self, proj: _Proj | None, role: str, day: str, exclude: set[str] = frozenset()) -> str | None:
        if role == "worker":
            return self.W
        if role == "cp" or proj is None and role not in ("collab",):
            return self.pick_cp(proj, day, exclude)
        if role == "collab":
            return self.collab if self.collab not in exclude else self.pick_cp(proj, day, exclude)
        if role == "owner":
            pid = proj.owner
        elif role == "sponsor":
            pid = proj.sponsor
        else:
            val = proj.p["cast"].get(role)
            if isinstance(val, list):
                opts = [x for x in val if x not in exclude and self._ok(x, day)]
                pid = self.rng.choice(opts) if opts else None
            else:
                pid = val
        if pid in exclude or (pid != self.W and not self._ok(pid, day)):
            return None
        return pid

    # ============================================================ communications
    def _thread(self, key: str) -> str:
        if key not in self.threads:
            self.n_thread += 1
            self.threads[key] = f"th-{self.n_thread:04d}"
        return self.threads[key]

    def new_comm(self, day: str, kind: str, minute: int, sender: str | None, to: list[str] | None = None, *,
                 cc: list[str] | None = None, participants: list[str] | None = None, project: str | None = None,
                 subject: str = "", thread: str | None = None, noise: bool = False, draft: bool = False,
                 received: str | None = None, extra: dict | None = None, parent: str | None = None) -> Communication:
        self.n_comm += 1
        t = self.ts(day, minute)
        to = [x for x in (to or []) if x]
        if thread is None:
            if kind == "chat_dm" and sender and to:
                thread = self._thread("dm:" + ":".join(sorted([sender, to[0]])))
            elif kind == "chat_channel":
                thread = self._thread("ch:" + (subject or "general"))
            elif kind == "email":
                thread = self._thread(f"em:{self.n_comm}")
        if not subject:
            if kind == "chat_dm" and sender and to:
                subject = f"DM: {self.people[sender]['name']} / {self.people[to[0]]['name']}"
        c = Communication(
            id=f"cm-x{self.n_comm:05d}", t=t, channel=CHANNEL_OF_KIND[kind], kind=kind, sender=sender, to=to,
            cc=list(cc or []), participants=list(participants or []), project=project, thread=thread,
            subject=subject, noise=noise, draft=draft, received_at=received or t, extra=dict(extra or {}),
            parent=parent,
        )
        c.extra["_seq"] = self.n_comm
        self.comms.append(c)
        self.day_comms.append(c)
        return c

    def chat_channel_name(self, proj: _Proj | None) -> str:
        if proj is None:
            return "#general"
        return "#" + (proj.p.get("code") or proj.p["short"]).lower().replace(" ", "-")[:24] + "-core"

    def message(self, day: str, sender: str, recipient: str, proj: _Proj | None, *, lo: int = DAY_START,
                prefer: str | None = None, subject: str = "", reuse: float = 0.35, thread: str | None = None,
                cc: list[str] | None = None) -> tuple[Communication, str] | None:
        """A chat or email from sender to recipient today, at or after minute `lo`.

        Returns (comm, event time). May reuse an open message on the same thread."""
        if lo > EVENING_END:
            return None
        kind = prefer if prefer in ("email", "chat_dm", "chat_channel") else None
        if prefer == "email":
            kind = "email"
        elif prefer == "chat":
            kind = "chat_dm"
        if kind is None:
            kind = "chat_dm" if self.rng.random() < 0.64 else "email"
        if kind == "chat_dm" and proj is not None and self.rng.random() < 0.35 \
                and sender in proj.members + [self.W] and recipient in proj.members + [self.W]:
            kind = "chat_channel"
        if self.rng.random() < reuse:
            for c in reversed(self.day_comms):
                if c.kind != kind or c.sender != sender or c.noise or c.draft or c.extra.get("fixed"):
                    continue
                if self.minute(c.t) < lo or c.date != day:
                    continue
                if kind == "chat_channel" and c.subject != self.chat_channel_name(proj):
                    continue
                if kind != "chat_channel" and (not c.to or c.to[0] != recipient):
                    continue
                t = self.ts(day, self.rand_minute(max(lo, self.minute(c.t) - 40), self.minute(c.t)))
                return c, t
        hi = DAY_END if lo < DAY_END - 20 else EVENING_END
        m = self.rand_minute(lo, hi)
        if kind == "chat_channel":
            c = self.new_comm(day, kind, m, sender, [], participants=self._channel_members(proj), project=proj.id,
                              subject=self.chat_channel_name(proj))
        else:
            c = self.new_comm(day, kind, m, sender, [recipient], cc=cc, project=proj.id if proj else None,
                              subject=subject, thread=thread if kind == "email" else None)
        return c, c.t

    def _channel_members(self, proj: _Proj | None) -> list[str]:
        if proj is None:
            return [self.W]
        return [m for m in proj.members if self._ok(m, self.today) or m == self.W][:10]

    def meeting_for(self, day: str, proj: _Proj | None, parties: list[str], lo: int = 0) -> Communication | None:
        cands = []
        for c in self.day_comms:
            if c.kind != "meeting" or c.extra.get("fixed") or c.date != day:
                continue
            end = self.minute(c.t)
            if end - 5 < lo:
                continue
            if proj is not None and c.project == proj.id:
                cands.append((0, c))
            elif proj is None and c.project is None:
                cands.append((1, c))
            elif all(p in c.participants for p in parties if p):
                cands.append((2, c))
        if not cands:
            return None
        best = min(k for k, _ in cands)
        return self.rng.choice([c for k, c in cands if k == best])

    def in_meeting(self, c: Communication, lo: int = 0) -> str:
        start = self.minute(c.extra["start"])
        end = self.minute(c.t)
        return self.ts(c.t[:10], self.rand_minute(max(start + 3, lo), max(start + 3, lo, end - 3)))

    def new_meeting(self, day: str, title: str, start: int, minutes: int, organizer: str, attendees: list[str],
                    proj: _Proj | None, *, coverage: str | None = None, recurring: str | None = None) -> Communication:
        cov = coverage or self.mix(COVERAGE_MIX)
        parts = [organizer] + [a for a in attendees if a != organizer]
        parts = [p for p in parts if p == self.W or self._ok(p, day)]
        if self.W not in parts:
            parts.append(self.W)
        c = self.new_comm(day, "meeting", start + minutes, organizer, [], participants=parts,
                          project=proj.id if proj else None, subject=title,
                          extra={"coverage": cov, "start": self.ts(day, start), "end": self.ts(day, start + minutes),
                                 "recurring": recurring})
        return c

    def _place(self, day: str, *, mode: str, sender: str, recipient: str, proj: _Proj | None,
               after: str | None = None, prefer: str | None = None, subject: str = "",
               thread: str | None = None) -> tuple[Communication, str] | None:
        """Choose the communication that carries an event and the event's time."""
        lo = DAY_START - 30
        if after and after[:10] == day:
            lo = max(lo, self.minute(after) + 10)
        if mode == "meeting":
            m = self.meeting_for(day, proj, [sender, recipient], lo)
            if m is not None:
                return m, self.in_meeting(m, lo)
            mode = "message"
        if mode == "note":
            if lo > EVENING_END:
                return None
            for c in self.day_comms:
                if c.kind in ("note", "voice_memo") and c.sender == self.W and self.minute(c.t) >= lo \
                        and not c.extra.get("fixed"):
                    return c, self.ts(day, self.rand_minute(lo, self.minute(c.t)))
            m = self.rand_minute(max(lo, 16 * 60), EVENING_END) if self.rng.random() < 0.6 else self.rand_minute(lo, DAY_END)
            kind = "voice_memo" if self.weekday(day) == 5 or self.rng.random() < 0.15 else "note"
            label = parse_date(day).strftime("%a")
            c = self.new_comm(day, kind, m, self.W, [], project=None,
                              subject=f"{label} voice memo" if kind == "voice_memo" else f"{label} notes")
            return c, self.ts(day, max(lo, m - self.rng.randint(0, 5)))
        if mode == "calendar":
            if lo > DAY_END:
                return None
            m = self.rand_minute(lo, DAY_END)
            c = self.new_comm(day, "calendar_invite", m, sender, [recipient], project=proj.id if proj else None,
                              subject=subject or "Invite")
            self._join_link(c)
            return c, c.t
        return self.message(day, sender, recipient, proj, lo=lo, prefer=prefer, subject=subject, thread=thread)

    def _join_link(self, c: Communication) -> None:
        dom = self.plan["setting"]["video_domain"]
        mid = "".join(str(self.rng.randint(0, 9)) for _ in range(10))
        pwd = "".join(self.rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
        link = f"https://{dom}/j/{mid}?pwd={pwd}"
        code = "".join(str(self.rng.randint(0, 9)) for _ in range(6))
        c.secrets += [link, code]
        c.extra["join_link"] = link
        c.extra["passcode"] = code

    # ============================================================ meetings
    def _meetings(self, day: str) -> None:
        wd = self.weekday(day)
        week_index = (parse_date(day) - parse_date(self.first_day)).days // 7
        for cad in self.plan["cadences"]:
            if cad["kind"] != "meeting" or wd not in cad["weekdays"] or week_index % cad["every"]:
                continue
            proj = self.projs.get(cad["project"]) if cad["project"] else None
            if proj is not None and not proj.active:
                continue
            if cad["key"] == "standup" and self.rng.random() < 0.15:
                continue  # standups get skipped now and then
            hh, mm = (int(x) for x in cad["time"].split(":"))
            organizer = proj.owner if proj is not None and cad["key"] == "standup" else cad["organizer"]
            self.new_meeting(day, cad["title"], hh * 60 + mm + self.rng.choice([0, 0, 5]), cad["minutes"], organizer,
                             list(cad["attendees"]), proj, recurring=cad["key"])
        n_adhoc = self.pick([0, 1, 1, 2, 2, 3], None) if wd < 2 else self.pick([0, 1, 1, 2], None)
        projs = [p for p in self.live(day) if p.arch.phase(p.phase).activity > 0.2]
        for _ in range(n_adhoc):
            proj = self.pick(projs, [p.weight * p.arch.phase(p.phase).activity for p in projs])
            if proj is None:
                break
            ph = proj.arch.phase(proj.phase)
            title = self.fmt(self.rng.choice(ph.meetings), self._ctx(proj)) if ph.meetings else f"{proj.p['short']} check-in"
            title = title[:1].upper() + title[1:]
            attendees = [proj.owner] + [self.pick_cp(proj, day) for _ in range(self.rng.randint(1, 4))]
            attendees = [a for a in dict.fromkeys(attendees) if a]
            start = self.rng.choice([9, 10, 11, 13, 14, 15, 16]) * 60 + self.rng.choice([0, 0, 30])
            self.new_meeting(day, title, start, self.rng.choice([30, 30, 45, 60]), attendees[0], attendees, proj)

    # ============================================================ portfolio note and cadences
    def _portfolio_note(self, day: str) -> None:
        c = self.new_comm(day, "note", 8 * 60 + 5, self.W, [], subject="Portfolio map")
        c.extra["fixed"] = True
        for o in (self.plan["setting"]["umbrella"], self.plan["setting"]["central"]):
            self.reveal(c, self.ent_ev[o])
        for pid in self.projs:
            self.reveal(c, self.ent_ev[pid])
        # Long-standing loops on quiet projects predate the seed.
        t0 = self.ts(day, 7 * 60)
        for proj in list(self.projs.values()):
            if proj.p["archetype"] in ("placeholder", "stalled_discovery"):
                beats = [b for b in proj.arch.beats() if b.type == "loop"]
                if beats:
                    lp = self.loop_from_beat(day, proj, beats[0], t=t0, comm=c, how="direct", basis="sent",
                                             lifecycle=False, status="waiting")
                    if lp is not None:
                        lp.frozen = proj.p["size"] == "placeholder"

    def _weekly_update(self, day: str) -> None:
        cad = next((x for x in self.plan["cadences"] if x["key"] == "weekly_update"), None)
        if cad is None:
            return
        wd = self.weekday(day)
        friday = add_days(day, 4 - wd) if wd <= 4 else None
        if wd == 0:
            c = self.new_comm(day, "email", 6 * 60 + 50 + self.rng.randint(0, 15), self.mailbox, [self.W],
                              subject=f"Reminder: Friday status note due {self.date_words(friday)}")
            c.extra["fixed"] = True
            label = f"w/e {parse_date(friday).day} {parse_date(friday).strftime('%B')}"
            what = f"Send {self.first(self.manager)} the Friday status note for {label}"
            lp = self._commit(c.t, what=what, summary=f"Friday status note for {self.first(self.manager)} due {label}",
                              kind="ask", debtor=self.W, creditor=self.manager, others=[], project=None,
                              status="open", due=friday, accepted=True, basis="received",
                              keywords=["friday status note", label.lower()])
            self.reveal(c, self.loop_ev[lp.id])
            lp.frozen = True
            self.sc[("weekly", friday)] = {"loop": lp.id}
        elif wd == 4 and ("weekly", day) in self.sc:
            lp = self.loops[self.sc[("weekly", day)]["loop"]]
            if lp.status not in ACTIVE:
                return
            m = self.rand_minute(15 * 60 + 30, 17 * 60 + 30)
            c = self.new_comm(day, "email", m, self.W, [self.manager],
                              subject=f"Status note: {lp.what.rsplit(' for ', 1)[-1]}")
            c.extra["fixed"] = True
            e = self._resolve(lp, c.t, "done", f"I sent {self.first(self.manager)} the Friday status note for {lp.what.rsplit(' for ', 1)[-1]}")
            self.reveal(c, e["id"])
            # The update restates a few of the week's changes (duplicate signals).
            week_start = add_days(day, -4)
            recent = [eid for d, eid in self.recent if week_start <= d <= day and self.ev[eid]["t"] <= c.t
                      and self.ev[eid]["type"] in ("fact.set", "decision.make", "commitment.resolve")
                      and self.ev[eid].get("attribute") != "summary"]
            for eid in self.rng.sample(recent, min(3, len(recent))):
                self.reveal(c, eid)

    # ============================================================ commitments
    def _commit(self, t: str, *, what: str, summary: str, kind: str, debtor: str, creditor: str, others: list[str],
                project: str | None, status: str, due: str | None, accepted: bool, basis: str,
                keywords: list[str]) -> _Loop:
        self.n_loops += 1
        cid = f"c-x{self.n_loops:04d}"
        kws = _clean_keywords(keywords, what)
        e = self._ev("commitment.create", t, summary, commitment=cid, kind=kind, what=what, debtor=debtor,
                     creditor=creditor, others=list(others), project=project, status=status, due=due,
                     accepted=accepted, basis=basis, keywords=kws)
        self.loop_ev[cid] = e["id"]
        lp = _Loop(cid, kind, what, debtor, creditor, list(others), project, status, due, accepted, kws, basis, t, t)
        self.created_today += 1
        self.loops[cid] = lp
        return lp

    def _update(self, lp: _Loop, t: str, changes: dict, summary: str, **flags: Any) -> dict:
        e = self._ev("commitment.update", t, summary, commitment=lp.id, changes=dict(changes),
                     **({"project": lp.project} if lp.project else {}))
        for k, v in flags.items():
            e[k] = v
        for k, v in changes.items():
            if k == "debtor":
                lp.debtor = v
            elif k == "creditor":
                lp.creditor = v
            elif k == "others":
                lp.others = list(v)
            elif k in ("status", "due", "accepted", "project", "what", "keywords"):
                setattr(lp, k, v)
        lp.last_t = t
        return e

    def _resolve(self, lp: _Loop, t: str, status: str, summary: str) -> dict:
        e = self._ev("commitment.resolve", t, summary, commitment=lp.id, status=status,
                     **({"project": lp.project} if lp.project else {}))
        lp.status = status
        lp.last_t = t
        return e

    def loop_from_beat(self, day: str, proj: _Proj | None, beat: A.Beat, *, t: str | None = None,
                       comm: Communication | None = None, how: str | None = None, basis: str | None = None,
                       lifecycle: bool = True, joint: bool = False, status: str | None = None,
                       accepted: bool | None = None, due: str | None = None, force_due: bool = False,
                       debtor: str | None = None, creditor: str | None = None, by: str | None = None) -> _Loop | None:
        debtor = debtor or self.role(proj, beat.debtor, day)
        if debtor is None:
            return None
        creditor = creditor or self.role(proj, beat.creditor, day, exclude={debtor})
        if creditor is None or creditor == debtor:
            return None
        others: list[str] = []
        if beat.others or joint:
            o = self.role(proj, beat.others or "cp", day, exclude={debtor, creditor})
            if o is None:
                if beat.others:
                    return None
            else:
                others = [o]
        # Which vendor the text names: the vendor person's own org, else the next unused one.
        vendor_org = None
        for pid in (debtor, creditor):
            org = self.people[pid].get("org")
            if org and self.orgs.get(org, {}).get("kind") == "vendor":
                vendor_org = org
        names_vendor = "{vendor" in beat.what
        key = (beat.key, vendor_org or "") if names_vendor else (beat.key, "")
        if proj is not None and proj.uses[key] >= beat.max_uses:
            return None
        noun = None
        if "{noun}" in beat.what:
            noun = self.noun(proj)
        if beat.debtor == "cp":
            cp = debtor
        elif beat.creditor == "cp":
            cp = creditor
        elif beat.others == "cp" and others:
            cp = others[0]
        elif "{cp." in beat.what + beat.summary:  # a third person the text names
            cp = self.pick_cp(proj, day, {debtor, creditor}) or (creditor if creditor != self.W else debtor)
        else:
            cp = creditor if creditor != self.W else debtor
        ctx = self._ctx(proj, cp=cp, debtor=debtor, creditor=creditor, other=others[0] if others else cp)
        if proj is None:
            ctx["other"] = self.pns(others[0] if others else self.pick_cp(None, day, {debtor, creditor, cp}) or cp)
        if ctx["other"].id != ctx["cp"].id and ctx["other"].first == ctx["cp"].first:
            ctx["other"] = NS(first=ctx["other"].name, name=ctx["other"].name, id=ctx["other"].id)
        if noun:
            ctx["noun"] = noun
        if vendor_org:
            o = self.orgs[vendor_org]
            ctx["vendor"] = NS(short=o["short"], name=o["name"])
            vs = [x for x in (proj.p.get("vendors") if proj else []) if x != vendor_org]
            if vs:
                ctx["vendor2"] = NS(short=self.orgs[vs[0]]["short"], name=self.orgs[vs[0]]["name"])
        what = self.fmt(beat.what, ctx)
        summary = self.fmt(beat.summary, ctx)
        keywords = [self.fmt(k, ctx).lower() for k in beat.keywords]
        if proj is not None:
            proj.uses[key] += 1
            if noun:
                proj.nouns.add(noun)
        # Status, due date, acceptance and evidence basis.
        if status is None:
            status = beat.status or ("open" if debtor == self.W else
                                     ("waiting" if creditor == self.W and self.rng.random() < 0.85 else "open"))
        if due is None and (force_due or (beat.due and self.rng.random() < 0.4) or self.rng.random() < 0.006):
            lo, hi = beat.due or (2, 8)
            due = self.bday(day, self.rng.randint(lo, hi))
        if basis is None:
            basis = self.mix(BASIS_MIX)
            if beat.channel == "calendar":
                basis = "scheduled"
            elif beat.channel == "email" and basis == "reported" and self.rng.random() < 0.5:
                basis = "received" if debtor == self.W or creditor == self.W else "reported"
        if accepted is None:
            accepted = True
            if debtor == self.W and beat.kind == "ask" and basis in ("received", "reported") \
                    and self.rng.random() < P_SUGGEST_ASK:
                accepted = False
            elif basis in ("reported", "inferred") and debtor != self.W and self.rng.random() < P_SUGGEST_RECAP:
                accepted = False
            elif basis == "reported" and debtor == self.W and self.rng.random() < P_SUGGEST_PROPOSAL:
                accepted = False
            if basis == "inferred":
                accepted = False
        # Where it shows up.
        if comm is None:
            placed = self._place_create(day, proj, debtor, creditor, basis, beat, what)
            if placed is None:
                return None
            comm, t_ev, how2, by2 = placed
            t = t or t_ev
            how = how or how2
            by = by or by2
        t = t or comm.t
        lp = self._commit(t, what=what, summary=summary, kind=beat.kind, debtor=debtor, creditor=creditor,
                          others=others, project=proj.id if proj else None, status=status, due=due,
                          accepted=accepted, basis=basis, keywords=keywords)
        if comm.kind == "email":
            lp.thread = comm.thread
        if not how:
            hedge = debtor == self.W and beat.kind == "task" and basis in ("sent", "reported")
            how = "hedged" if (hedge and self.rng.random() < 0.15) else "direct"
        self.reveal(comm, self.loop_ev[lp.id], how, by)
        if lifecycle:
            self._plan_lifecycle(lp, day)
        return lp

    def noun(self, proj: _Proj | None) -> str:
        used = proj.nouns if proj else set()
        opts = [n for n in self.nouns if n not in used]
        if not opts:
            opts = [f"{n} v2" for n in self.nouns if f"{n} v2" not in used] or [f"{self.rng.choice(self.nouns)} addendum"]
        return self.rng.choice(opts)

    def _place_create(self, day: str, proj: _Proj | None, debtor: str, creditor: str, basis: str, beat: A.Beat,
                      what: str) -> tuple[Communication, str, str, str | None] | None:
        other = creditor if debtor == self.W else debtor if creditor == self.W else creditor
        subject = self.subject_of(what)
        prefer = {"email": "email", "chat": "chat"}.get(beat.channel or "")
        if basis == "reported":
            m = self.meeting_for(day, proj, [debtor, creditor])
            if m is not None:
                return m, self.in_meeting(m), "direct", debtor
            reporter = self.pick_cp(proj, day, {debtor, creditor}) or self.collab
            if reporter in (debtor, creditor, self.W):
                reporter = other
            r = self.message(day, reporter, self.W, proj, prefer=prefer, subject=subject)
            if r is None:
                return None
            return r[0], r[1], "second_hand", reporter
        if basis == "inferred":
            m = self.meeting_for(day, proj, [debtor, creditor])
            if m is not None and m.extra.get("coverage") in ("recap", "transcript+recap"):
                return m, self.in_meeting(m), "implied", None
            r = self._place(day, mode="note", sender=self.W, recipient=self.W, proj=proj)
            return (r[0], r[1], "implied", None) if r else None
        if basis == "scheduled":
            r = self._place(day, mode="calendar", sender=other if other != self.W else creditor,
                            recipient=self.W, proj=proj, subject=f"Invite: {subject}")
            return (r[0], r[1], "direct", None) if r else None
        if basis == "sent":
            if self.rng.random() < 0.12:
                r = self._place(day, mode="note", sender=self.W, recipient=self.W, proj=proj)
                return (r[0], r[1], "direct", None) if r else None
            r = self.message(day, self.W, other, proj, prefer=prefer, subject=subject)
            return (r[0], r[1], "direct", None) if r else None
        # received
        sender = other if other != self.W else creditor
        if sender == self.W:
            sender = debtor
        r = self.message(day, sender, self.W, proj, prefer=prefer, subject=subject)
        return (r[0], r[1], "direct", None) if r else None

    # ------------------------------------------------------------ lifecycles
    def _plan_lifecycle(self, lp: _Loop, day: str) -> None:
        rng = self.rng
        if not lp.accepted:
            r = rng.random()
            if r < 0.32:
                self._schedule(self.bday(day, rng.randint(1, 4)), 2, "loop", (lp.id, "endorse", {}))
            elif r < 0.42:
                self._schedule(self.bday(day, rng.randint(1, 5)), 2, "loop", (lp.id, "drop", {}))
            return
        r = rng.random()
        close_at: int | None = None
        who = "worker" if lp.debtor == self.W else "others"
        if r < P_FAST[who]:
            close_at = rng.choice([0, 0, 0, 0, 1, 1, 1, 2, 2])
        elif r < P_FAST[who] + P_MED[who]:
            close_at = int(round(math.exp(rng.uniform(math.log(3), math.log(20)))))
        if close_at is not None:
            action = "drop" if rng.random() < (0.05 if close_at <= 2 else 0.16) else "done"
            self._schedule(self.bday(day, close_at) if close_at else day, 3, "loop", (lp.id, action, {}))
            if action == "done" and rng.random() < 0.02:
                self._schedule(self.bday(day, close_at + rng.randint(1, 3)), 4, "loop", (lp.id, "reopen", {}))
        horizon = close_at if close_at is not None else 20
        if horizon >= 2:
            if rng.random() < (0.3 if lp.debtor != self.W else 0.05):
                self._schedule(self.bday(day, rng.randint(1, horizon - 1 if horizon > 1 else 1)), 2, "loop",
                               (lp.id, "toggle", {}))
            if rng.random() < 0.08:
                self._schedule(self.bday(day, rng.randint(1, horizon - 1 if horizon > 1 else 1)), 2, "loop",
                               (lp.id, "transfer", {}))
            if lp.due and rng.random() < 0.3:
                self._schedule(self.bday(day, rng.randint(1, max(1, horizon - 1))), 2, "loop", (lp.id, "due", {}))
            if rng.random() < 0.012:
                self._schedule(self.bday(day, rng.randint(1, max(1, horizon - 1))), 2, "loop", (lp.id, "block", {}))

    def _transition(self, day: str, cid: str, action: str, extra: dict) -> None:
        lp = self.loops.get(cid)
        before = (lp.status, lp.debtor, lp.due, lp.accepted, lp.last_t) if lp else None
        self._transition_once(day, cid, action, extra)
        if lp is None or lp.frozen or (lp.status, lp.debtor, lp.due, lp.accepted, lp.last_t) != before:
            return
        tries = int(extra.get("tries", 0))
        still_valid = (lp.status == "done") if action == "reopen" else (lp.status in ACTIVE)
        if still_valid and tries < 3 and action in ("done", "drop", "endorse", "toggle", "reopen"):
            nxt = self.bday(day, 1)
            if nxt <= self.last_day:
                self._schedule(nxt, 3, "loop", (cid, action, {**extra, "tries": tries + 1}))

    def _transition_once(self, day: str, cid: str, action: str, extra: dict) -> None:
        lp = self.loops.get(cid)
        if lp is None or lp.frozen:
            return
        if action == "reopen":
            if lp.status != "done":
                return
        elif action == "endorse":
            if lp.accepted or lp.status not in ACTIVE:
                return
        elif lp.status not in ACTIVE or (not lp.accepted and action != "drop"):
            return
        proj = self.projs.get(lp.project or "")
        rng = self.rng
        W = self.W
        if action == "done":
            if lp.debtor == W:
                mode = "meeting" if rng.random() < 0.15 else "message"
                placed = self._place(day, mode=mode, sender=W, recipient=lp.creditor, proj=proj, after=lp.last_t,
                                     thread=lp.thread, subject=self._re(lp))
                how = "direct"
            else:
                r = rng.random()
                if r < P_UNREPORTED and lp.creditor == W:
                    t = self.ts(day, self.rand_minute(max(DAY_START, self._lo(lp, day)), DAY_END))
                    if t <= lp.last_t:
                        return
                    e = self._resolve(lp, t, "done", self.past(lp.what, lp.debtor))
                    self.hide(e, "unreported closure")
                    lp.frozen = True
                    return
                if r < 0.62:
                    rec = lp.creditor if lp.creditor != lp.debtor else W
                    placed = self._place(day, mode="message", sender=lp.debtor, recipient=W if rec == W else rec,
                                         proj=proj, after=lp.last_t, thread=lp.thread, subject=self._re(lp))
                    how = "direct"
                elif r < 0.84:
                    placed = self._place(day, mode="meeting", sender=lp.debtor, recipient=W, proj=proj, after=lp.last_t)
                    how = "direct" if placed and placed[0].kind == "meeting" else "second_hand"
                elif r < 0.93 and lp.creditor == W:
                    placed = self._place(day, mode="message", sender=W, recipient=lp.debtor, proj=proj, after=lp.last_t)
                    how = "indirect"
                else:
                    reporter = self.pick_cp(proj, day, {lp.debtor, lp.creditor}) or self.collab
                    placed = self._place(day, mode="message", sender=reporter if reporter != W else lp.debtor,
                                         recipient=W, proj=proj, after=lp.last_t)
                    how = "second_hand"
            if placed is None:
                return
            comm, t = placed
            if t <= lp.last_t:
                return
            e = self._resolve(lp, t, "done", self.past(lp.what, lp.debtor))
            self.reveal(comm, e["id"], how, by=None if how != "second_hand" else comm.sender)
        elif action == "drop":
            mode = self.pick(["note", "message", "meeting"], [0.35, 0.4, 0.25])
            placed = self._place(day, mode=mode, sender=W, recipient=lp.debtor if lp.debtor != W else lp.creditor,
                                 proj=proj, after=lp.last_t)
            if placed is None or placed[1] <= lp.last_t:
                return
            reason = rng.choice(DROP_REASONS)
            e = self._resolve(lp, placed[1], "dropped", f"Dropped: {self.pov(lp.what)} ({reason})")
            self.reveal(placed[0], e["id"])
        elif action == "endorse":
            placed = self._place(day, mode="note" if rng.random() < 0.6 else "message", sender=W,
                                 recipient=lp.creditor if lp.creditor != W else lp.debtor, proj=proj, after=lp.last_t)
            if placed is None or placed[1] <= lp.last_t:
                return
            e = self._update(lp, placed[1], {"accepted": True}, self.endorse_summary(lp))
            self.reveal(placed[0], e["id"])
            self._plan_lifecycle(lp, day)
        elif action == "toggle":
            new = "waiting" if lp.status == "open" else "open"
            if lp.status == "blocked":
                new = "open"
            sender = W if new == "waiting" else (lp.debtor if lp.debtor != W else lp.creditor)
            other = lp.creditor if sender == W else W
            placed = self._place(day, mode="message", sender=sender, recipient=other if other != sender else lp.debtor,
                                 proj=proj, after=lp.last_t, thread=lp.thread, subject=self._re(lp))
            if placed is None or placed[1] <= lp.last_t:
                return
            who = self.first(lp.creditor if lp.debtor == W else lp.debtor)
            summary = (f"Waiting on {who}: {self.pov(lp.what)}" if new == "waiting"
                       else f"Back with {self.first(lp.debtor) if lp.debtor != W else 'me'}: {self.pov(lp.what)}")
            e = self._update(lp, placed[1], {"status": new}, summary)
            self.reveal(placed[0], e["id"])
        elif action == "transfer":
            pool = [p for p in self.proj_people(proj, day) if p not in (lp.debtor, lp.creditor, *lp.others)]
            same_org = [p for p in pool if self.people[p].get("org") == self.people[lp.debtor].get("org")]
            new = self.pick(same_org or pool)
            if new is None or lp.debtor == W and rng.random() < 0.5:
                return
            sender = lp.debtor
            placed = self._place(day, mode=self.pick(["message", "meeting"], [0.7, 0.3]), sender=sender,
                                 recipient=W if sender != W else new, proj=proj, after=lp.last_t)
            if placed is None or placed[1] <= lp.last_t:
                return
            old = lp.debtor
            e = self._update(lp, placed[1], {"debtor": new},
                             f"{self.subject_of(lp.what)} handed from {self.first(old) if old != W else 'me'} to {self.first(new)}")
            self.reveal(placed[0], e["id"])
        elif action == "due":
            placed = self._place(day, mode=self.pick(["message", "meeting"], [0.75, 0.25]),
                                 sender=lp.creditor if lp.creditor != W else lp.debtor, recipient=W, proj=proj,
                                 after=lp.last_t)
            if placed is None or placed[1] <= lp.last_t:
                return
            new_due = self.bday(lp.due or day, rng.choice([-1, 2, 3, 5]))
            if new_due <= day:
                new_due = self.bday(day, 2)
            if new_due == lp.due:
                return
            e = self._update(lp, placed[1], {"due": new_due},
                             f"{self.subject_of(lp.what)} now due {self.date_words(new_due)}", _supersedes=True)
            self.reveal(placed[0], e["id"])
        elif action == "block":
            placed = self._place(day, mode="meeting", sender=lp.debtor, recipient=W, proj=proj, after=lp.last_t)
            if placed is None or placed[1] <= lp.last_t:
                return
            e = self._update(lp, placed[1], {"status": "blocked"},
                             f"{self.subject_of(lp.what)} blocked: {rng.choice(BLOCK_REASONS)}")
            self.reveal(placed[0], e["id"])
            self._schedule(self.bday(day, rng.randint(2, 6)), 2, "loop", (lp.id, "toggle", {}))
        elif action == "reopen":
            placed = self._place(day, mode="message", sender=lp.creditor if lp.creditor != W else lp.debtor,
                                 recipient=W, proj=proj, after=lp.last_t, thread=lp.thread, subject=self._re(lp))
            if placed is None or placed[1] <= lp.last_t:
                return
            e = self._update(lp, placed[1], {"status": "open"},
                             f"Reopened: {self.pov(lp.what)} ({rng.choice(REOPEN_REASONS)})")
            self.reveal(placed[0], e["id"])
            self._schedule(self.bday(day, rng.randint(1, 4)), 3, "loop", (lp.id, "done", {}))

    def pov(self, what: str) -> str:
        """The `what` from the worker's point of view: 'send Ana the x' with the worker as 'me'."""
        wf = self.first(self.W)
        out = self.lower_first(what)
        for a, b in ((f" {wf}'s ", " my "), (f" {wf} ", " me "), (f" {wf}", " me")):
            if out.endswith(a.rstrip()) and a == f" {wf}":
                out = out[: -len(a)] + b.rstrip()
            out = out.replace(a, b)
        return out

    def endorse_summary(self, lp: _Loop) -> str:
        if lp.debtor == self.W:
            return f"I agreed to {self.lower_first(lp.what)}"
        return f"Confirmed as an action: {self.first(lp.debtor)} to {self.pov(lp.what)}"

    def _lo(self, lp: _Loop, day: str) -> int:
        return self.minute(lp.last_t) + 10 if lp.last_t[:10] == day else DAY_START

    def _re(self, lp: _Loop) -> str:
        return ("Re: " if lp.thread else "") + self.subject_of(lp.what)

    # ============================================================ projects
    def set_facts(self, proj: _Proj, t: str, changes: dict[str, Any], summary: str, comm: Communication | None,
                  *, how: str = "direct", hidden: str | None = None, supersedes: bool = False) -> list[dict]:
        """fact.set events for `changes`, plus a rewritten summary when status, phase, target date or
        blocker changes. Revealed in `comm` unless `hidden`."""
        out = []
        for attr, value in changes.items():
            old = {"status": proj.status, "phase": proj.phase, "target_date": proj.target,
                   "blocker": proj.blocker, "next_step": proj.next_step, "owner": proj.owner}.get(attr)
            if attr == "status":
                proj.status = value
            elif attr == "phase":
                proj.phase = value
            elif attr == "target_date":
                proj.target = value
            elif attr == "blocker":
                proj.blocker = value
            elif attr == "next_step":
                proj.next_step = value
            elif attr == "owner":
                proj.owner = value
            fields: dict[str, Any] = {"subject": proj.id, "attribute": attr, "value": value, "project": proj.id}
            if supersedes and attr == "target_date" and old:
                fields["_supersedes"] = True
            out.append(self._ev("fact.set", t, summary if len(out) == 0 else f"{proj.p['name']} {attr.replace('_', ' ')} updated",
                                **fields))
        if any(a in changes for a in ("status", "phase", "target_date", "blocker")):
            out.append(self._ev("fact.set", t, f"{proj.p['name']} summary updated", subject=proj.id,
                                attribute="summary", value=self._summary_text(proj), project=proj.id))
        for e in out:
            if hidden:
                self.hide(e, hidden)
            elif comm is not None:
                self.reveal(comm, e["id"], how)
        return out

    def _phase_moves(self, day: str) -> None:
        for proj in list(self.projs.values()):
            if proj.merged or proj.status in ("done", "cancelled") or proj.since >= day:
                continue
            ph = proj.arch.phase(proj.phase)
            for nxt, prob in ph.next:
                if self.rng.random() < prob:
                    self._enter_phase(day, proj, nxt)
                    break

    def _enter_phase(self, day: str, proj: _Proj, phase: str) -> None:
        new = proj.arch.phase(phase)
        sender = proj.owner if proj.owner != self.W else (proj.p["cast"].get("lead") or self.collab)
        mode = self.pick(["meeting", "message", "note"], [0.4, 0.45, 0.15])
        placed = self._place(day, mode=mode, sender=sender, recipient=self.W, proj=proj,
                             subject=f"{proj.p['name']}: moving to {phase}")
        if placed is None:
            return
        comm, t = placed
        changes: dict[str, Any] = {"phase": phase}
        if new.status != proj.status:
            changes["status"] = new.status
        label = f"{proj.p['name']} moved to {phase}" if new.status == "active" else \
            f"{proj.p['name']} is now {new.status}"
        if new.status == "dormant" and self.rng.random() < 0.5:
            self.set_facts(proj, t, changes, label, None, hidden="status lag: never announced")
            return
        self.set_facts(proj, t, changes, label, comm)
        ctx = self._ctx(proj)
        for b in new.on_enter:
            if b.type == "fact" and self.rng.random() < 0.8:
                val = self.fmt(b.value, ctx) if b.value else None
                self.set_facts(proj, t, {b.attr: val}, self.fmt(b.summary, ctx), comm)
        if new.status == "done" and proj.arch.name == "event_preparation":
            self._spawn_successor(day, proj, comm, t)

    def _spawn_successor(self, day: str, proj: _Proj, comm: Communication, t: str) -> None:
        topic = proj.p.get("topic") or "AI"
        name = f"{topic[:1].upper() + topic[1:]} Peer Network"
        pid = "pr-" + "-".join(name.lower().replace("'", "").split())
        if pid in self.projs:
            return
        pp = dict(proj.p)
        pp.update(id=pid, name=name, short=f"{topic} peer network", kw=f"{topic} peer network".lower(), code=None,
                  surface_forms=[f"the {topic} network", "the peer network"], archetype="relationship_thread",
                  size="small", phase="ongoing", status="active", target_date=None, weight=2.0,
                  members=list(proj.members)[:4])
        e = self._project_create(pp, t, parent=proj.id, summary=f"{name} spun up after the {proj.p['short']}")
        self.reveal(comm, e["id"])

    def _facts_and_decisions(self, day: str) -> None:
        rng = self.rng
        for proj in self.live(day):
            ph = proj.arch.phase(proj.phase)
            facts = [b for b in ph.beats if b.type == "fact"]
            for b in facts:
                if rng.random() < 0.02 * b.weight * ph.activity * (1.5 if proj.p["size"] == "flagship" else 1):
                    self.fact_beat(day, proj, b)
        if rng.random() < 0.18 * WEEKDAY_LOOPS[self.weekday(day)]:
            projs = [p for p in self.live(day) if p.arch.decisions]
            proj = self.pick(projs, [p.weight for p in projs])
            if proj is not None:
                self.decide(day, proj)

    def fact_beat(self, day: str, proj: _Proj, b: A.Beat, comm: Communication | None = None,
                  t: str | None = None) -> list[dict]:
        ctx = self._ctx(proj)
        if b.attr == "target_date":
            if not proj.target:
                return []
            lo, hi = (int(x) for x in b.value.lstrip("+").split(".."))
            new = self.bday(proj.target, self.rng.randint(lo, hi))
            ctx["date"] = f"{parse_date(new).day} {parse_date(new).strftime('%B')}"
            value: Any = new
        elif b.value == "":
            if not proj.blocker:
                return []
            value = None
        else:
            value = self.fmt(b.value, ctx)
            if b.attr == "blocker" and proj.blocker:
                return []
        if comm is None:
            sender = proj.owner if proj.owner != self.W else (proj.p["cast"].get("lead") or self.collab)
            placed = self._place(day, mode=self.pick(["meeting", "message"], [0.5, 0.5]), sender=sender,
                                 recipient=self.W, proj=proj, subject=f"{proj.p['name']} update")
            if placed is None:
                return []
            comm, t = placed
        return self.set_facts(proj, t or comm.t, {b.attr: value}, self.fmt(b.summary, ctx), comm,
                              supersedes=b.attr == "target_date")

    def decide(self, day: str, proj: _Proj, beat: A.Beat | None = None, *, comm: Communication | None = None,
               t: str | None = None, how: str = "direct") -> dict | None:
        beats = [b for b in proj.arch.decisions if proj.uses[(b.key, "")] < 1]
        beat = beat or (self.rng.choice(beats) if beats else None)
        if beat is None:
            return None
        by = []
        for r in beat.by:
            pid = self.role(proj, r, day, exclude=set(by))
            if pid:
                by.append(pid)
        if not by:
            by = [self.W]
        ctx = self._ctx(proj)
        what = self.fmt(beat.what, ctx)
        if comm is None:
            mode = self.pick(["meeting", "note", "message"], [0.5, 0.25, 0.25])
            sender = by[0] if by[0] != self.W else self.W
            placed = self._place(day, mode=mode, sender=sender, recipient=self.W if sender != self.W else proj.owner,
                                 proj=proj, subject=self.subject_of(what))
            if placed is None:
                return None
            comm, t = placed
        proj.uses[(beat.key, "")] += 1
        self.n_dec += 1
        did = f"d-x{self.n_dec:03d}"
        e = self._ev("decision.make", t or comm.t, self.fmt(beat.summary, ctx), decision=did, what=what, by=by,
                     project=proj.id, keywords=_clean_keywords([self.fmt(k, ctx).lower() for k in beat.keywords], what))
        self.dec_ev[did] = e["id"]
        self.dec[did] = {"id": did, "project": proj.id, "what": what, "reversed": False, "t": e["t"]}
        proj.decisions.append(did)
        self.reveal(comm, e["id"], how)
        return e

    # ============================================================ new loops
    def _new_loops(self, day: str) -> None:
        wd = self.weekday(day)
        span = max(1, len(self.days) - 1)
        ramp = 0.85 + 0.3 * (self.days.index(day) / span)
        mean = float(self.plan["setting"]["loops_per_day"]) * WEEKDAY_LOOPS[wd] * ramp
        n = max(0, int(round(self.rng.gauss(mean, max(1.0, mean * 0.25)))) - self.created_today)
        projs = self.live(day)
        weights = [p.weight * max(0.05, p.arch.phase(p.phase).activity) for p in projs]
        for _ in range(n):
            if self.rng.random() < 0.08 or not projs:
                self._unattached_loop(day)
                continue
            proj = self.pick(projs, weights)
            self.project_loop(day, proj)

    def project_loop(self, day: str, proj: _Proj, *, category: str | None = None, **kw: Any) -> _Loop | None:
        cat = category or self.mix(OWNER_MIX)
        ph = proj.arch.phase(proj.phase)
        beats = [b for b in ph.beats if b.type == "loop"]

        def fits(b: A.Beat) -> bool:
            if cat == "worker":
                return b.debtor == "worker" and not b.others
            if cat == "others":
                return b.debtor != "worker" and not b.others
            return True

        cands = [b for b in beats if fits(b)]
        self.rng.shuffle(cands)
        cands.sort(key=lambda b: -b.weight * self.rng.random())
        for b in cands[:4]:
            lp = self.loop_from_beat(day, proj, b, joint=cat == "joint", **kw)
            if lp is not None:
                return lp
        generic = [b for b in A.GENERIC if fits(b)]
        b = self.pick(generic, [g.weight for g in generic])
        return self.loop_from_beat(day, proj, b, joint=cat == "joint" and not b.others, **kw) if b else None

    def _unattached_loop(self, day: str) -> _Loop | None:
        b = self.pick(list(A.UNATTACHED), [x.weight for x in A.UNATTACHED])
        return self.loop_from_beat(day, None, b)

    # ============================================================ sealing a day
    def _seal_day(self, day: str) -> None:
        for _ in range(4):  # transitions scheduled for today after the agenda ran (same-day closures)
            items = self.agenda.pop(day, [])
            if not items:
                break
            for _prio, _s, kind, payload in sorted(items, key=lambda x: (x[0], x[1])):
                if kind == "loop":
                    self._transition(day, *payload)
        for m in [c for c in self.day_comms if c.kind == "meeting" and not c.acts]:
            if not self._fill_meeting(m, day):
                self._drop(m)
        self._volume(day)
        for c in self.day_comms:
            self._reveal_people(c)
            self._name_forms(c)
        self.day_comms = []

    def _drop(self, c: Communication) -> None:
        self.comms.remove(c)
        self.day_comms.remove(c)

    def _fill_meeting(self, m: Communication, day: str) -> bool:
        """An otherwise empty meeting goes over recent changes again (duplicate signals)."""
        if m.extra.get("fixed"):
            return True
        cands = [eid for d, eid in self.recent[-60:]
                 if d < day and self.ev[eid].get("project") == m.project and self.ev[eid]["t"] <= m.t
                 and self.ev[eid]["type"] != "fact.set"]
        if not cands or self.rng.random() < 0.35:
            return False
        for eid in self.rng.sample(cands, min(len(cands), self.rng.randint(1, 2))):
            self.reveal(m, eid, "direct")
        return True

    def _reveal_people(self, c: Communication) -> None:
        """A communication shows who sent it and who was on it."""
        for pid in c.people():
            if pid == self.W or pid not in self.ent_ev:
                continue
            eid = self.ent_ev[pid]
            k = self.known.get(eid)
            if (k is None or k > c.date) and self.ev[eid]["t"] <= c.t:
                self.reveal(c, eid, "direct", primary=False)

    def _name_forms(self, c: Communication) -> None:
        if c.noise:
            return
        forms = c.extra.setdefault("name_forms", {})
        subjects = set(c.people())
        for a in c.acts:
            e = self.ev[a.event]
            subjects.update(x for x in (e.get("debtor"), e.get("creditor")) if x)
        collision = {p for pair in self.plan["collisions"]["first_names"] for p in pair}
        for pid in sorted(subjects):
            if pid == self.W or pid not in self.people or pid in forms:
                continue
            p = self.people[pid]
            if pid in collision and self.rng.random() < 0.5:
                forms[pid] = p["first"]
            elif p.get("nickname") and self.rng.random() < 0.3:
                forms[pid] = p["nickname"]
            elif p.get("role_phrase") and self.rng.random() < 0.06:
                forms[pid] = p["role_phrase"]
        if not forms:
            c.extra.pop("name_forms")

    def _volume(self, day: str) -> None:
        wd = self.weekday(day)
        lo, hi = self.plan["setting"]["volume"]
        span = max(1, len(self.days) - 1)
        ramp = 0.94 + 0.12 * (self.days.index(day) / span)
        target = int(round(self.rng.randint(lo, hi) * WEEKDAY_VOLUME[wd] * ramp))
        delivered = lambda: sum(len(c.prefixes()) for c in self.comms if c.date == day)  # noqa: E731
        ev_email = sum(1 for c in self.comms if c.date == day and c.kind == "email" and not c.noise)
        n_noise = max(1 if wd == 5 else 2, int(round(ev_email * self.rng.uniform(0.85, 1.2))))
        cap = int(round(target * 1.1)) - delivered()
        n_noise = max(1, min(n_noise, cap))
        if wd == 5:
            n_noise = self.rng.randint(2, 3)
        for _ in range(n_noise):
            self._noise_email(day)
        guard = 0
        while delivered() < target and guard < 40:
            guard += 1
            r = self.rng.random()
            if r < 0.3:
                self._noise_chat(day)
            elif r < 0.62:
                if not self._fyi(day):
                    self._noise_email(day)
            elif r < 0.75 and wd < 5:
                self._calendar_filler(day)
            else:
                self._noise_email(day)

    # ------------------------------------------------------------ noise and filler
    def _noise_email(self, day: str) -> Communication:
        sender = self.rng.choice(self.minors)
        p = self.people[sender]
        kind = p.get("minor_kind", "newsletter")
        d = parse_date(day)
        subjects = {
            "newsletter": [f"{p['role'].split(', ', 1)[-1]}: issue {d.isocalendar()[1]}", "This week in digital services",
                           "Five reads for the week"],
            "service_desk": [f"[INC-{self.rng.randint(40000, 89999)}] Ticket updated", "Scheduled maintenance this weekend",
                             f"[REQ-{self.rng.randint(10000, 39999)}] Request resolved"],
            "status": ["[Resolved] Elevated latency on file storage", "[Scheduled] Network maintenance window",
                       "[Investigating] Intermittent sign-in delays"],
            "comms": ["All-staff: building access changes", "Wellbeing week activities", "Parking lot resurfacing"],
            "events": ["Room booking confirmation", "Catering menu for next month", "Event space survey"],
            "conference": ["Call for proposals closes soon", "Early-bird registration ends Friday", "Speaker spotlight"],
            "benefits": ["Open enrollment reminder", "Your benefits statement is ready", "Wellness credit deadline"],
            "marketing": ["Webinar: getting more from your data", "Customer story: faster onboarding", "Product update roundup"],
        }.get(kind, ["Newsletter"])
        m = self.rand_minute(6 * 60 + 30, 19 * 60)
        c = self.new_comm(day, "email", m, sender, [self.W], subject=self.rng.choice(subjects), noise=True,
                          extra={"noise_kind": kind})
        return c

    def _noise_chat(self, day: str) -> Communication:
        # Social chatter comes from colleagues the worker already knows, so noise never introduces anyone.
        pool = [p for p in self.proj_people(None, day) if self.people[p].get("group") in ("central", "functional")
                and self.known.get(self.ent_ev[p], "9999") < day]
        sender = self.rng.choice(pool) if pool else self.collab
        channel = self.rng.choice(["#random", "#general", "#coffee"])
        m = self.rand_minute(8 * 60, 17 * 60 + 30)
        return self.new_comm(day, "chat_channel", m, sender, [], participants=[sender, self.W], subject=channel,
                             noise=True, extra={"noise_kind": "social"})

    def _fyi(self, day: str) -> bool:
        cands = [eid for d, eid in self.recent[-80:] if d >= add_days(day, -4) and self.ev[eid]["type"] != "fact.set"]
        if not cands:
            return False
        eid = self.rng.choice(cands)
        e = self.ev[eid]
        proj = self.projs.get(e.get("project") or "")
        sender = self.pick_cp(proj, day) or self.collab
        lo = self.minute(e["t"]) + 5 if e["t"][:10] == day else DAY_START
        r = self.message(day, sender, self.W, proj, lo=lo, reuse=0.0, subject="FYI")
        if r is None:
            return False
        c, _t = r
        self.reveal(c, eid, "second_hand", by=sender)
        return True

    def _calendar_filler(self, day: str) -> Communication:
        projs = self.live(day)
        proj = self.pick(projs, [p.weight for p in projs])
        org = self.pick_cp(proj, day) or self.collab
        when = self.bday(day, self.rng.randint(1, 4))
        title = f"{proj.p['short'][:1].upper() + proj.p['short'][1:]} sync" if proj else "Catch-up"
        kind = self.pick(["calendar_invite", "calendar_update", "calendar_cancel"], [0.7, 0.2, 0.1])
        c = self.new_comm(day, kind, self.rand_minute(), org, [self.W], project=proj.id if proj else None,
                          subject=("Invite: " if kind == "calendar_invite" else "Updated: " if kind == "calendar_update"
                                   else "Cancelled: ") + title,
                          extra={"meeting": {"title": title, "start": self.ts(when, 14 * 60), "end": self.ts(when, 14 * 60 + 30)}})
        if kind != "calendar_cancel":
            self._join_link(c)
        return c

    # ============================================================ planted challenges
    def _challenge(self, day: str, ch: dict, stage: str) -> None:
        fn = getattr(self, "_ch_" + ch["tag"])
        fn(day, ch, stage, self.sc.setdefault((ch["week"], ch["tag"]), {}))

    def _proj(self, pid: str | None, *, active: bool = True) -> _Proj:
        proj = self.projs.get(pid or "")
        if proj is None or (active and (not proj.active or proj.since >= self.today)):
            cands = [p for p in self.live(self.today) if p.p["size"] in ("flagship", "mid", "hub")]
            proj = self.pick(cands, [p.weight for p in cands]) or self.projs[self.flagship_id]
        return proj

    def live(self, day: str) -> list[_Proj]:
        """Projects that can carry activity today."""
        return [p for p in self.projs.values() if p.active and p.since < day]

    def _active_loops(self, pred=lambda lp: True) -> list[_Loop]:
        return [lp for cid, lp in sorted(self.loops.items())
                if lp.status in ACTIVE and lp.accepted and not lp.frozen and pred(lp)]

    def _known_by(self, lp: _Loop, day: str) -> bool:
        k = self.known.get(self.loop_ev[lp.id])
        return k is not None and k < day

    def _ch_worker_directive(self, day, ch, stage, st) -> None:
        proj = self._proj(ch.get("project"))
        c = self.new_comm(day, "note", self.rand_minute(7 * 60 + 15, 8 * 60 + 20), self.W, [], subject="Mon notes")
        c.extra["fixed"] = True
        k = self.rng.choice("ABC")
        noun = self.noun(proj)
        proj.nouns.add(noun)
        beat = A.D("dir", f"Use approach {k} for the {{proj.short}} {noun}",
                   f"Decided to use approach {k} for the {{proj.short}} {noun}", [f"approach {k.lower()}", noun],
                   by=("worker",))
        e = self.decide(day, proj, beat, comm=c, t=c.t)
        drop = self._active_loops(lambda lp: lp.project == proj.id and lp.debtor != self.W
                                  and self._known_by(lp, day) and lp.last_t < c.t)
        if drop:
            lp = self.rng.choice(drop)
            r = self._resolve(lp, c.t, "dropped", f"Dropped: {self.pov(lp.what)} (superseded by the approach {k} decision)")
            self.reveal(c, r["id"])
        if e is not None:
            c.tag("worker_directive")

    def _ch_noise(self, day, ch, stage, st) -> None:
        self._noise_email(day).tag("noise")

    def _ch_implied_commitment(self, day, ch, stage, st) -> None:
        proj = self._proj(ch.get("project"))
        m = self.meeting_for(day, proj, []) or self.new_meeting(
            day, f"{proj.p['short']} working session", 10 * 60 + 30, 45, proj.owner,
            [proj.owner, *self.proj_people(proj, day)[:3]], proj, coverage="transcript")
        raiser = self.pick([p for p in m.participants if p != self.W]) or proj.owner
        issue = self.rng.choice([i for i in ISSUES if i not in proj.nouns] or list(ISSUES))
        proj.nouns.add(issue)
        beat = A.L("implied", f"Look into the {{proj.short}} {issue}", f"I said I'd take a look at the {{proj.short}} {issue}",
                   [issue, "{proj.kw}"], creditor="cp", kind="task", n=99)
        lp = self.loop_from_beat(day, proj, beat, comm=m, t=self.in_meeting(m), how="implied", basis="reported",
                                 creditor=raiser if raiser != self.W else None, accepted=True)
        if lp is not None:
            m.tag("implied_commitment")

    def _ch_duplicate_signal(self, day, ch, stage, st) -> None:
        proj = self._proj(ch.get("project"))
        asker = self.pick_cp(proj, day) or self.collab
        r = self.message(day, asker, self.W, proj, lo=8 * 60, prefer="email", reuse=0.0)
        if r is None:
            return
        c1, t = r
        c1.extra["fixed"] = True
        noun = self.noun(proj)
        beat = A.L("dup", f"Send {{creditor.first}} the {{proj.short}} {noun}", f"{{creditor.first}} asked me for the {{proj.short}} {noun}",
                   [noun, "{proj.kw}"], creditor="cp", kind="ask", n=99)
        lp = self.loop_from_beat(day, proj, beat, comm=c1, t=t, basis="received", accepted=True, creditor=asker)
        if lp is None:
            return
        m = self.meeting_for(day, proj, [asker], self.minute(c1.t) + 5)
        if m is None:
            r2 = self.message(day, asker, self.W, proj, lo=self.minute(c1.t) + 30, prefer="chat", reuse=0.0)
            if r2 is None:
                return
            m = r2[0]
        self.reveal(m, self.loop_ev[lp.id], "direct", by=asker)
        m.tag("duplicate_signal")

    def _ch_privacy(self, day, ch, stage, st) -> None:
        proj = self._proj(None)
        org = proj.owner if proj.owner != self.W else self.collab
        when = self.bday(day, 1)
        title = f"{proj.p['short'][:1].upper() + proj.p['short'][1:]} review"
        c = self.new_comm(day, "calendar_invite", self.rand_minute(9 * 60, 16 * 60), org, [self.W], project=proj.id,
                          subject=f"Invite: {title}",
                          extra={"meeting": {"title": title, "start": self.ts(when, 15 * 60), "end": self.ts(when, 15 * 60 + 45)}})
        self._join_link(c)
        c.tag("privacy")
        # A vendor engineer emails a temporary password in plain text.
        vend = [x for x in self.live(day) if x.p.get("vendors") and x.p["cast"].get("se")]
        if vend:
            vp = self.rng.choice(vend)
            se = self.role(vp, "se", day)
            if se:
                pw = f"Tmp-{self.rng.choice(['Kelp', 'Moss', 'Flint', 'Reed', 'Birch'])}-{self.rng.randint(1000, 9999)}!"
                c2 = self.new_comm(day, "email", self.rand_minute(10 * 60, 17 * 60), se, [self.W], project=vp.id,
                                   subject=f"{self.orgs[self.people[se]['org']]['short']} sandbox credentials")
                c2.secrets.append(pw)
                c2.extra["temp_password"] = pw
                c2.tag("privacy")
                beat = A.L("creds", "Set up {vendor.short} sandbox access for {creditor.first}",
                           "{debtor.first} sent {vendor.short} sandbox credentials",
                           ["sandbox access", "{vendor.short}"], debtor="se", creditor="worker", kind="task", n=99)
                lp = self.loop_from_beat(day, vp, beat, comm=c2, t=c2.t, basis="received", lifecycle=False,
                                         accepted=True, debtor=se, creditor=self.W)
                if lp is not None:
                    e = self._resolve(lp, c2.t, "done", f"{self.first(se)} set up sandbox access for me")
                    self.reveal(c2, e["id"])

    def _ch_alias(self, day, ch, stage, st) -> None:
        pool = [p for p in self.proj_people(None, day) if self.people[p].get("nickname")]
        if not pool:
            return
        pid = self.pick(pool, [self.weight_of(p, None) for p in pool])
        projs = [p for p in self.live(day) if pid in self.proj_people(p, day)]
        proj = self.pick(projs, [p.weight for p in projs]) if projs else None
        r = self.message(day, pid, self.W, proj, prefer="chat", reuse=0.0)
        if r is None:
            return
        c, t = r
        c.extra["fixed"] = True
        if proj is not None:
            self.project_loop(day, proj, category="others", comm=c, t=t, debtor=pid, creditor=self.W, basis="received",
                              accepted=True)
        else:
            self.loop_from_beat(day, None, A.UNATTACHED[3], comm=c, t=t, debtor=pid, creditor=self.W, basis="received",
                                accepted=True)
        c.extra.setdefault("name_forms", {})[pid] = self.people[pid]["nickname"]
        c.tag("alias")

    def _ch_name_collision(self, day, ch, stage, st) -> None:
        pairs = [pair for pair in self.plan["collisions"]["first_names"] if all(self._ok(p, day) for p in pair)]
        if not pairs:
            return
        pair = self.rng.choice(pairs)
        for i, pid in enumerate(pair):
            projs = [p for p in self.live(day) if pid in self.proj_people(p, day)]
            proj = self.pick(projs, [p.weight for p in projs]) if projs else None
            r = self.message(day, pid, self.W, proj, lo=9 * 60 + i * 120, prefer="chat", reuse=0.0)
            if r is None:
                continue
            c, t = r
            c.extra["fixed"] = True
            if proj is not None and i == 0:
                self.project_loop(day, proj, category="others", comm=c, t=t, debtor=pid, creditor=self.W,
                                  basis="received", accepted=True)
            else:
                self.loop_from_beat(day, proj, A.GENERIC[2] if proj else A.UNATTACHED[3], comm=c, t=t, debtor=pid,
                                    creditor=self.W, basis="received", accepted=True)
            c.extra.setdefault("name_forms", {})[pid] = self.people[pid]["first"]
            c.tag("name_collision")

    def _ch_new_entity(self, day, ch, stage, st) -> None:
        pid = ch.get("person")
        p = self.people.get(pid or "")
        if p is None or pid in self.ent_ev:
            return
        proj = self._proj(ch.get("project"))
        m = self.rand_minute(8 * 60 + 30, 11 * 60)
        e = self._person_create(p, self.ts(day, m - 1), summary=f"{p['name']}, {p['role']} (new contact)")
        c = self.new_comm(day, "email", m, pid, [self.W], project=proj.id, subject=f"Introduction: {proj.p['short']}")
        c.extra["fixed"] = True
        self.reveal(c, e["id"])
        if pid not in proj.members:
            proj.members.append(pid)
        noun = {"Privacy Officer": "privacy review form", "Senior Account Executive": "renewal questionnaire"}.get(
            p["role"].split(",")[0], self.noun(proj))
        beat = A.L("intro", f"Send {{creditor.first}} the {{proj.short}} {noun}",
                   f"{{creditor.first}} (new) asked me for the {{proj.short}} {noun}", [noun, "{proj.kw}"],
                   creditor="cp", kind="ask", n=99)
        self.loop_from_beat(day, proj, beat, comm=c, t=c.t, basis="received", accepted=True, creditor=pid,
                            force_due=True)
        c.tag("new_entity")

    def _ch_supersession(self, day, ch, stage, st) -> None:
        proj = self._proj(ch.get("project"))
        if not proj.target:
            cands = [p for p in self.live(day) if p.target]
            if not cands:
                lps = self._active_loops(lambda lp: bool(lp.due) and self._known_by(lp, day))
                if lps:
                    self._transition(day, self.rng.choice(lps).id, "due", {})
                return
            proj = self.rng.choice(cands)
        beat = A.F("slip", "target_date", "+5..10", "{proj.short} target date moved to {date}")
        sender = proj.owner if proj.owner != self.W else proj.p["cast"].get("lead") or self.collab
        placed = self._place(day, mode=self.pick(["meeting", "message"], [0.5, 0.5]), sender=sender, recipient=self.W,
                             proj=proj, subject=f"{proj.p['name']}: new target date")
        if placed is None:
            return
        comm, t = placed
        evs = self.fact_beat(day, proj, beat, comm=comm, t=t)
        if evs:
            comm.tag("supersession")

    def _ch_unobservable(self, day, ch, stage, st) -> None:
        proj = self._proj(ch.get("project"))
        attr = ch.get("attribute", "budget")
        amount = self.rng.choice([60, 85, 120, 150, 240, 310]) * 1000
        value = {"budget": f"{amount} USD", "budget_ceiling": f"{amount} USD", "savings_target": f"{amount // 2} USD per year",
                 "discount": f"{self.rng.choice([8, 12, 15, 18])}%"}[attr]
        sender = proj.p["cast"]["fin"] if attr != "discount" else (proj.p["cast"]["proc"])
        m = self.rand_minute(9 * 60, 15 * 60)
        t = self.ts(day, m - 30)
        e = self._ev("fact.set", t, f"{proj.p['name']} {attr.replace('_', ' ')} set", subject=proj.id, attribute=attr,
                     value=value, project=proj.id)
        self.hide(e, "unobservable")
        r = self.message(day, sender, self.W, proj, lo=m, prefer="email", reuse=0.0,
                         subject=f"{proj.p['name']}: numbers")
        if r is None:
            return
        c, t2 = r
        c.extra["fixed"] = True
        c.extra["allusion"] = {"subject": proj.id, "attribute": attr}
        noun = self.noun(proj)
        beat = A.L("cost", f"Send {{creditor.first}} the {{proj.short}} {noun}", f"{{creditor.first}} asked me for the {{proj.short}} {noun}",
                   [noun, "{proj.kw}"], creditor="cp", kind="ask", n=99)
        self.loop_from_beat(day, proj, beat, comm=c, t=t2, basis="received", accepted=True, creditor=sender)
        c.tag("unobservable")

    def _ch_draft_vs_sent(self, day, ch, stage, st) -> None:
        if stage == "setup":
            proj = self._proj(None)
            cp = self.pick_cp(proj, day) or self.collab
            noun = self.noun(proj)
            beat = A.L("draftloop", f"Send {{creditor.first}} the {{proj.short}} {noun}", f"I promised {{creditor.first}} the {{proj.short}} {noun}",
                       [noun, "{proj.kw}"], creditor="cp", kind="task", n=99)
            lp = self.loop_from_beat(day, proj, beat, basis="sent", lifecycle=False, accepted=True, creditor=cp)
            if lp is not None:
                lp.frozen = True
                st["loop"] = lp.id
            return
        lp = self.loops.get(st.get("loop", ""))
        if lp is None:
            cands = self._active_loops(lambda x: x.debtor == self.W and self._known_by(x, day))
            if not cands:
                return
            lp = self.rng.choice(cands)
        c = self.new_comm(day, "email", self.rand_minute(21 * 60 + 30, 22 * 60 + 50), self.W, [lp.creditor],
                          project=lp.project, subject=f"DRAFT: {self.subject_of(lp.what)}", draft=True)
        c.extra.update({"draft_of": lp.id, "fixed": True})
        c.tag("draft_vs_sent")
        nxt = self.bday(day, 1)
        if nxt <= self.last_day and self.rng.random() < 0.6:
            lp.frozen = False
            self._schedule(nxt, 3, "loop", (lp.id, "done", {}))

    def _ch_batch_catchup(self, day, ch, stage, st) -> None:
        nxt = next((d for d in self.days if d > day), None)
        if nxt is None:
            return
        base = self.minute(self.ts(nxt, 7 * 60 + 38))
        projs = sorted(self.live(day), key=lambda p: -p.weight)[:3]
        kinds = ["chat_channel", "meeting", "email", "chat_dm"]
        for i, kind in enumerate(kinds[: self.rng.randint(3, 4)]):
            proj = projs[i % len(projs)]
            m = self.rand_minute(10 * 60 + i * 90, 10 * 60 + i * 90 + 60)
            received = self.ts(nxt, base + i)
            sender = proj.owner if proj.owner != self.W else self.collab
            if kind == "meeting":
                attendees = [sender, *self.proj_people(proj, day)[:3]]
                c = self.new_comm(day, "meeting", m + 30, sender, [], participants=[*dict.fromkeys(attendees)],
                                  project=proj.id, subject=f"{proj.p['short']} sync (worker away)", received=received,
                                  extra={"coverage": "transcript", "start": self.ts(day, m), "end": self.ts(day, m + 30)})
            elif kind == "chat_channel":
                c = self.new_comm(day, kind, m, sender, [], participants=self._channel_members(proj), project=proj.id,
                                  subject=self.chat_channel_name(proj), received=received)
            else:
                c = self.new_comm(day, kind, m, sender, [self.W], project=proj.id, received=received,
                                  subject=f"While you were out: {proj.p['short']}")
            c.extra.update({"fixed": True, "away": "offsite"})
            t = self.ts(day, m - 5) if kind != "meeting" else self.in_meeting(c)
            lp = self.project_loop(day, proj, comm=c, t=t, basis="reported" if kind == "meeting" else "received",
                                   accepted=True)
            olds = self._active_loops(lambda x, pid=proj.id, t=t: x.project == pid and self._known_by(x, day)
                                      and x.last_t < t)
            if olds and self.rng.random() < 0.7:
                old = self.rng.choice(olds)
                tt = max(t, self.ts(day, self.minute(old.last_t) + 5)) if old.last_t[:10] == day else t
                if tt <= c.t:
                    e = self._resolve(old, tt, "done", self.past(old.what, old.debtor))
                    self.reveal(c, e["id"], "direct" if kind != "chat_dm" else "second_hand")
            if lp is not None or c.acts:
                c.tag("batch_catchup")

    def _ch_transfer(self, day, ch, stage, st) -> None:
        cands = self._active_loops(lambda lp: lp.debtor != self.W and self._known_by(lp, day) and lp.project)
        self.rng.shuffle(cands)
        for lp in cands:
            proj = self.projs[lp.project]
            pool = [p for p in self.proj_people(proj, day) if p not in (lp.debtor, lp.creditor, *lp.others)]
            same_org = [p for p in pool if self.people[p].get("org") == self.people[lp.debtor].get("org")]
            if not pool:
                continue
            new = self.rng.choice(same_org or pool)
            r = self.message(day, lp.debtor, self.W, proj, lo=self._lo(lp, day), prefer="email", reuse=0.0,
                             cc=[new], subject=self._re(lp))
            if r is None:
                continue
            c, t = r
            c.extra["fixed"] = True
            old = lp.debtor
            e = self._update(lp, t, {"debtor": new}, f"{self.subject_of(lp.what)} handed from {self.first(old)} to {self.first(new)}")
            self.reveal(c, e["id"])
            c.tag("transfer")
            return

    def _ch_correction(self, day, ch, stage, st) -> None:
        if stage == "setup":
            proj = self._proj(None)
            st["variant"] = "reopen" if self.rng.random() < 0.6 else "due"
            if st["variant"] == "reopen":
                eng = proj.p["cast"].get("eng") if self._ok(proj.p["cast"].get("eng"), day) else self.pick_cp(proj, day)
                issue = self.rng.choice([i for i in ISSUES if i not in proj.nouns] or list(ISSUES))
                proj.nouns.add(issue)
                beat = A.L("fix", f"Fix the {{proj.short}} {issue}", f"{{debtor.first}} is fixing the {{proj.short}} {issue}",
                           [issue, "{proj.kw}"], debtor="cp", creditor="worker", kind="task", n=99)
                lp = self.loop_from_beat(day, proj, beat, basis="received", lifecycle=False, accepted=True, debtor=eng,
                                         creditor=self.W)
                if lp is None:
                    return
                lp.frozen = True
                st["loop"] = lp.id
                r = self.message(day, lp.debtor, self.W, proj, lo=self.minute(lp.last_t) + 60, prefer="chat", reuse=0.0)
                if r is None:
                    return
                e = self._resolve(lp, r[1], "done", f"{self.first(lp.debtor)} reported the {proj.p['short']} {issue} fixed")
                self.reveal(r[0], e["id"])
            else:
                lp = self.project_loop(day, proj, category="worker", lifecycle=False, accepted=True, force_due=True,
                                       basis="reported")
                if lp is not None:
                    lp.frozen = True
                    st["loop"] = lp.id
            return
        lp = self.loops.get(st.get("loop", ""))
        if lp is None:
            return
        proj = self.projs.get(lp.project or "")
        teller = self.pick_cp(proj, day, {lp.debtor, lp.creditor}) or self.collab
        placed = self._place(day, mode=self.pick(["meeting", "message"], [0.5, 0.5]), sender=teller, recipient=self.W,
                             proj=proj, after=lp.last_t)
        if placed is None:
            return
        c, t = placed
        if st["variant"] == "reopen":
            e = self._update(lp, t, {"status": "open"},
                             f"Correction: the {self.lower_first(self.subject_of(lp.what))} fix was rolled back; reopened")
            self.reveal(c, e["id"], "correction", by=teller)
            lp.frozen = False
            self._schedule(self.bday(day, self.rng.randint(1, 2)), 3, "loop", (lp.id, "done", {}))
        else:
            new_due = self.bday(lp.due or day, self.rng.choice([-1, -2])) if lp.due else self.bday(day, 2)
            if new_due <= day:
                new_due = self.bday(day, 1)
            if new_due == lp.due:
                new_due = self.bday(new_due, 1)
            e = self._update(lp, t, {"due": new_due},
                             f"Correction: {self.subject_of(lp.what)} is due {self.date_words(new_due)}", _supersedes=True)
            self.reveal(c, e["id"], "correction", by=teller)
            lp.frozen = False
        c.tag("correction")

    def _ch_weak_evidence(self, day, ch, stage, st) -> None:
        if stage == "setup":
            proj = self._proj(None)
            cp = self.pick_cp(proj, day) or self.collab
            noun = self.noun(proj)
            beat = A.L("walk", f"Walk {{creditor.first}} through the {{proj.short}} {noun}",
                       f"I offered to walk {{creditor.first}} through the {{proj.short}} {noun}", [noun, "{proj.kw}"],
                       creditor="cp", kind="task", n=99)
            lp = self.loop_from_beat(day, proj, beat, basis="sent", lifecycle=False, accepted=True, creditor=cp)
            if lp is None:
                return
            lp.frozen = True
            st["loop"] = lp.id
            meet = ch["day"]
            title = f"Walkthrough: {self.subject_of(lp.what).split(' through the ', 1)[-1]}"
            c = self.new_comm(day, "calendar_invite", self.rand_minute(self.minute(lp.last_t) + 10, DAY_END), self.W,
                              [cp], project=proj.id, subject=f"Invite: {title}",
                              extra={"meeting": {"title": title, "start": self.ts(meet, 14 * 60), "end": self.ts(meet, 14 * 60 + 30)}})
            self._join_link(c)
            c.tag("weak_evidence", "privacy")
            st["invite"] = c.id
            return
        lp = self.loops.get(st.get("loop", ""))
        if lp is None or lp.status not in ACTIVE:
            return
        e = self._resolve(lp, self.ts(day, 14 * 60 + 35), "done", self.past(lp.what, self.W))
        self.hide(e, "weak evidence: the walkthrough left no trace")

    def _ch_acceptance_vs_occurrence(self, day, ch, stage, st) -> None:
        projs = self.live(day)
        proj = self.pick(projs, [p.weight for p in projs])
        org = self.pick_cp(proj, day) or self.collab
        when = self.bday(day, 1) if self.bday(day, 1) <= self.last_day else day
        title = f"{proj.p['short'][:1].upper() + proj.p['short'][1:]} follow-up"
        c = self.new_comm(day, "calendar_reply", self.rand_minute(8 * 60, 12 * 60), self.W, [org], project=proj.id,
                          subject=f"Accepted: {title}",
                          extra={"meeting": {"title": title, "start": self.ts(when, 16 * 60), "end": self.ts(when, 16 * 60 + 30),
                                             "organizer": org}, "response": "accepted", "fixed": True})
        c.tag("acceptance_vs_occurrence")

    def _ch_restructuring(self, day, ch, stage, st) -> None:
        mode = ch.get("mode", "split")
        src = self.projs.get(ch.get("project") or "")
        if mode == "merge" and src is not None and not src.merged:
            into = self._proj(ch.get("into"))
            if into.id == src.id:
                return
            c = self.new_comm(day, "note", self.rand_minute(16 * 60, 18 * 60), self.W, [],
                              subject=f"{parse_date(day).strftime('%a')} notes")
            c.extra["fixed"] = True
            e = self._ev("project.merge", c.t, f"{src.p['name']} folded into {into.p['name']}", projects=[src.id],
                         into=into.id)
            src.merged = True
            src.status = "merged"
            for lp in self.loops.values():
                if lp.project == src.id:
                    lp.project = into.id
                    lp.frozen = False if lp.status in ACTIVE else lp.frozen
            self.reveal(c, e["id"])
            c.tag("restructuring", "worker_directive")
            return
        if src is None or not src.active:
            src = self.projs[self.flagship_id]
        unit = self.orgs.get(src.p.get("unit") or "")
        new_topic = src.p.get("topic")
        if src.arch.name == "pivoting_discovery":
            topic = new_topic = src.p.get("pivot") or "a new problem"
            titled = " ".join(w[:1].upper() + w[1:] for w in topic.split())
            name = f"{unit['short']} {titled} Discovery" if unit else f"{titled} Discovery"
            short, arch = f"{topic} discovery", "unit_discovery"
        else:
            subs = ["evaluation", "onboarding", "data access", "support model", "training", "reporting",
                    "integration", "rollout"]
            self.rng.shuffle(subs)
            sub = next((x for x in subs if self._pid(f"{src.p['short']} {x.title()} Workstream") not in self.projs),
                       None)
            if sub is None:
                return
            name = f"{src.p['short']} {sub.title()} Workstream"
            short, arch = f"{src.p['short']} {sub} workstream", "delegated_asks"
        pid = self._pid(name)
        if pid in self.projs:
            return
        sender = src.p["cast"].get("lead") or src.owner
        if sender == self.W:
            sender = self.collab
        c = self.new_comm(day, "email", self.rand_minute(10 * 60, 16 * 60), sender, [self.W], project=src.id,
                          subject=f"Splitting out {short}")
        c.extra["fixed"] = True
        lead = src.p["cast"].get("lead") or src.owner
        pp = dict(src.p)
        pp.update(id=pid, name=name, short=short, kw=short.lower(), code=None, surface_forms=[f"the {short}"], topic=new_topic,
                  archetype=arch, size="mid", phase=A.get(arch).start[0], status="active", target_date=None,
                  weight=max(3.0, src.weight * 0.3), owner=lead, members=[self.W, lead, *src.members[2:5]])
        pp["members"] = list(dict.fromkeys(pp["members"]))
        t = self.ts(day, self.minute(c.t) - 2)
        ce = self._project_create(pp, t, summary=f"{name} split out of {src.p['name']}")
        movable = self._active_loops(lambda lp: lp.project == src.id and self._known_by(lp, day))
        moves = {lp.id: pid for lp in self.rng.sample(movable, min(len(movable), self.rng.randint(1, 2)))}
        e = self._ev("project.split", c.t, f"{name} split out of {src.p['name']}", project=src.id, into=[pid],
                     moves=moves)
        for cid in moves:
            self.loops[cid].project = pid
        self.reveal(c, ce["id"])
        self.reveal(c, e["id"])
        c.tag("restructuring", "new_entity")

    @staticmethod
    def _pid(name: str) -> str:
        return "pr-" + "-".join(name.lower().replace("'", "").replace("/", " ").split())

    def _ch_version_mismatch(self, day, ch, stage, st) -> None:
        if stage == "setup":
            proj = self._proj(None)
            noun = self.rng.choice(["scorecard", "cost model", "options paper", "evaluation workbook", "rollout plan"])
            if noun in proj.nouns:
                noun = noun + " v2"
            proj.nouns.add(noun)
            beat = A.L("vm", f"Send {{creditor.first}} the {{proj.short}} {noun}", f"{{debtor.first}} will send the {{proj.short}} {noun}",
                       [noun, "{proj.kw}"], debtor="cp", creditor="worker", kind="task", n=99)
            lp = self.loop_from_beat(day, proj, beat, basis="reported", lifecycle=False, accepted=True)
            if lp is not None:
                lp.frozen = True
                st["loop"] = lp.id
            return
        lp = self.loops.get(st.get("loop", ""))
        if lp is None or lp.status not in ACTIVE:
            return
        proj = self.projs.get(lp.project or "")
        r = self.message(day, lp.debtor, lp.creditor, proj, lo=self._lo(lp, day), prefer="email", reuse=0.0,
                         subject=self.subject_of(lp.what))
        if r is None:
            return
        c, t = r
        k = self.rng.randint(1, 3)
        c.extra.update({"fixed": True, "version_mismatch": {"body": f"v{k}", "attachment": f"v{k + 1}"}})
        e = self._resolve(lp, t, "done", self.past(lp.what, lp.debtor))
        self.reveal(c, e["id"])
        doc = self.new_comm(day, "document", self.minute(c.t), lp.debtor, [], project=lp.project,
                            subject=f"{self.subject_of(lp.what)} v{k + 1}", parent=c.id,
                            extra={"format": self.rng.choice(["xlsx", "docx"]), "version": f"v{k + 1}", "fixed": True})
        doc.received_at = c.received_at
        self.reveal(doc, e["id"])
        c.tag("version_mismatch")
        doc.tag("version_mismatch")
        lp.frozen = False

    def _ch_silent_closure(self, day, ch, stage, st) -> None:
        if stage == "setup":
            proj = self._proj(None)
            access = self.rng.choice([a for a in ACCESS if a not in proj.nouns] or list(ACCESS))
            proj.nouns.add(access)
            beat = A.L("access", f"Set up {{proj.short}} {access} for {{creditor.first}}",
                       f"I asked {{debtor.first}} to set up {{proj.short}} {access} for me", [access, "{proj.kw}"],
                       debtor="cp", creditor="worker", kind="ask", n=99)
            eng = proj.p["cast"].get("eng") if self._ok(proj.p["cast"].get("eng"), day) else None
            lp = self.loop_from_beat(day, proj, beat, basis="sent", lifecycle=False, accepted=True, debtor=eng,
                                     creditor=self.W)
            if lp is not None:
                lp.frozen = True
                st["loop"] = lp.id
            return
        lp = self.loops.get(st.get("loop", ""))
        if lp is None or lp.status not in ACTIVE:
            return
        proj = self.projs.get(lp.project or "")
        to = self.pick_cp(proj, day, {lp.debtor}) or self.collab
        r = self.message(day, self.W, to, proj, lo=self._lo(lp, day), prefer="chat", reuse=0.0)
        if r is None:
            return
        c, t = r
        c.extra["fixed"] = True
        e = self._resolve(lp, t, "done", self.past(lp.what, lp.debtor))
        self.reveal(c, e["id"], "indirect")
        c.tag("silent_closure")

    def _ch_reversal(self, day, ch, stage, st) -> None:
        proj = self._proj(ch.get("project"))
        if stage == "setup":
            beats = [b for b in proj.arch.decisions if proj.uses[(b.key, "")] < 1]
            beat = beats[0] if beats else A.D("scope", "Limit the {proj.short} rollout to {n} {v.sites}",
                                              "Decided to limit the {proj.short} rollout to {n} {v.sites}",
                                              ["{n} {v.sites}", "rollout"])
            e = self.decide(day, proj, beat)
            if e is not None:
                st["decision"] = e["decision"]
            return
        did = st.get("decision")
        if did is None:
            cands = [d for d in self.dec.values() if not d["reversed"] and self.known.get(self.dec_ev[d["id"]], "9") < day]
            if not cands:
                return
            did = self.rng.choice(cands)["id"]
        d = self.dec[did]
        proj = self.projs[d["project"]]
        sender = proj.sponsor if proj.sponsor != self.W else proj.owner
        placed = self._place(day, mode=self.pick(["meeting", "message"], [0.5, 0.5]), sender=sender, recipient=self.W,
                             proj=proj, subject=f"Change of plan: {proj.p['name']}")
        if placed is None:
            return
        c, t = placed
        ctx = self._ctx(proj)
        reasons = proj.arch.reversal_reasons or ("{sponsor.first} asked for a different approach",)
        reason = self.fmt(self.rng.choice(reasons), ctx)
        e = self._ev("decision.reverse", t, f"Reversed: {self.lower_first(d['what'])} ({reason})", decision=did,
                     reason=reason, project=proj.id)
        d["reversed"] = True
        self.reveal(c, e["id"])
        n2 = NUMBER_WORDS.get(proj.p.get("n", 3) + 1, "more")
        what2 = f"Widen the {proj.p['short']} scope to {n2} {self.vocab.sites}"
        self.n_dec += 1
        did2 = f"d-x{self.n_dec:03d}"
        t2 = self.ts(day, self.minute(t) + 1) if self.minute(t) + 1 <= self.minute(c.t) else t
        e2 = self._ev("decision.make", t2, f"Decided to {self.lower_first(what2)}", decision=did2, what=what2,
                      by=[sender] if sender else [self.W], project=proj.id,
                      keywords=_clean_keywords([f"{n2} {self.vocab.sites}", proj.p["kw"]], what2))
        self.dec_ev[did2] = e2["id"]
        self.dec[did2] = {"id": did2, "project": proj.id, "what": what2, "reversed": False, "t": t2}
        self.reveal(c, e2["id"])
        c.tag("reversal")

    def _ch_endorsement(self, day, ch, stage, st) -> None:
        if stage == "setup":
            proj = self._proj(None)
            m = self.meeting_for(day, proj, [])
            if m is not None and m.extra.get("coverage") in ("recap", "transcript+recap"):
                lp = self.project_loop(day, proj, category="worker", comm=m, t=self.in_meeting(m), basis="inferred",
                                       how="implied", accepted=False, lifecycle=False)
            else:
                asker = self.pick_cp(proj, day) or self.collab
                r = self.message(day, asker, self.W, proj, prefer="email", reuse=0.0)
                lp = None
                if r is not None:
                    noun = self.noun(proj)
                    beat = A.L("sugg", f"Review {{creditor.first}}'s {{proj.short}} {noun}",
                               f"{{creditor.first}} asked me to review the {{proj.short}} {noun} (not yet agreed)",
                               [noun, "{proj.kw}"], creditor="cp", kind="ask", n=99)
                    lp = self.loop_from_beat(day, proj, beat, comm=r[0], t=r[1], basis="received", accepted=False,
                                             lifecycle=False, creditor=asker)
            if lp is not None:
                lp.frozen = True
                st["loop"] = lp.id
            return
        lp = self.loops.get(st.get("loop", ""))
        if lp is None or lp.accepted or lp.status not in ACTIVE:
            return
        kind = "voice_memo" if self.weekday(day) == 5 else "note"
        c = self.new_comm(day, kind, self.rand_minute(max(self._lo(lp, day), 16 * 60), 19 * 60), self.W, [],
                          subject=f"{parse_date(day).strftime('%a')} {'voice memo' if kind == 'voice_memo' else 'notes'}")
        c.extra["fixed"] = True
        due = self.bday(day, self.rng.randint(2, 4))
        e = self._update(lp, c.t, {"accepted": True, "due": due}, f"{self.endorse_summary(lp)} by {self.date_words(due)}")
        self.reveal(c, e["id"])
        c.tag("endorsement", "worker_directive")
        lp.frozen = False
        self._plan_lifecycle(lp, day)

    def _ch_scattered_evidence(self, day, ch, stage, st) -> None:
        if stage == "setup":
            proj = self._proj(None)
            m = self.meeting_for(day, proj, []) or self.new_meeting(
                day, f"{proj.p['short']} check-in", 14 * 60, 30, proj.owner, [proj.owner, *self.proj_people(proj, day)[:2]],
                proj, coverage="transcript")
            m.extra["fixed"] = True
            cp = self.pick([p for p in m.participants if p != self.W]) or proj.owner
            noun = self.noun(proj)
            beat = A.L("scatter", f"Send {{creditor.first}} the {{proj.short}} {noun}",
                       f"I said I could get {{creditor.first}} the {{proj.short}} {noun} sometime next week",
                       [noun, "{proj.kw}"], creditor="cp", kind="task", n=99)
            lp = self.loop_from_beat(day, proj, beat, comm=m, t=self.in_meeting(m), how="hedged", basis="reported",
                                     lifecycle=False, accepted=True, creditor=cp if cp != self.W else None)
            if lp is not None:
                lp.frozen = True
                st["loop"] = lp.id
                m.tag("scattered_evidence")
            return
        lp = self.loops.get(st.get("loop", ""))
        if lp is None:
            return
        proj = self.projs.get(lp.project or "")
        steps = ch.get("steps") or []
        if stage == "step0" and lp.status in ACTIVE:
            due = steps[-1] if steps else self.bday(day, 2)
            relay = self.collab if self.collab not in (lp.creditor,) else self.pick_cp(proj, day, {lp.creditor})
            r = self.message(day, relay, self.W, proj, lo=self._lo(lp, day), prefer="chat", reuse=0.0)
            if r is None:
                return
            e = self._update(lp, r[1], {"due": due}, f"{self.first(lp.creditor)} needs the {lp.keywords[0]} by {self.date_words(due)}")
            self.reveal(r[0], e["id"], "second_hand", by=relay)
            r[0].extra["fixed"] = True
            r[0].tag("scattered_evidence")
        elif stage == "step1" and lp.status in ACTIVE:
            r = self.message(day, self.W, lp.creditor, proj, lo=self._lo(lp, day), prefer="chat", reuse=0.0)
            if r is None:
                return
            e = self._resolve(lp, r[1], "done", self.past(lp.what, self.W))
            self.reveal(r[0], e["id"])
            r[0].extra["fixed"] = True
            r[0].tag("scattered_evidence")
            st["done"] = e["id"]
        elif stage == "step2" and st.get("done"):
            r = self.message(day, lp.creditor, self.W, proj, lo=self._lo(lp, day), prefer="email", reuse=0.0,
                             subject=self._re(lp))
            if r is None:
                return
            self.reveal(r[0], st["done"], "direct")
            r[0].extra["fixed"] = True
            r[0].tag("scattered_evidence", "duplicate_signal")

    # ============================================================ finalize
    def _finalize(self) -> Simulation:
        # Events in world order, numbered e-0001...
        order = sorted(self.events, key=lambda e: (e["t"], e["_seq"]))
        emap = {e["id"]: f"e-{i:04d}" for i, e in enumerate(order, 1)}
        cmap: dict[str, str] = {}
        dmap: dict[str, str] = {}
        for e in order:
            if e["type"] == "commitment.create":
                cmap[e["commitment"]] = f"c-{len(cmap) + 1:03d}"
            elif e["type"] == "decision.make":
                dmap[e["decision"]] = f"d-{len(dmap) + 1:03d}"
        flags: dict[str, set[str]] = defaultdict(set)
        events: list[dict] = []
        prev_due: dict[str, str | None] = {}
        for e in order:
            out = {k: v for k, v in e.items() if not k.startswith("_")}
            out["id"] = emap[e["id"]]
            if "commitment" in out:
                out["commitment"] = cmap[out["commitment"]]
            if "decision" in out:
                out["decision"] = dmap[out["decision"]]
            if out["type"] == "project.split":
                out["moves"] = {cmap[k]: v for k, v in sorted(out.get("moves", {}).items(), key=lambda kv: cmap[kv[0]])}
            if out["type"] == "commitment.create" and out.get("project") is None:
                out.pop("project", None)
            if e.get("_supersedes"):
                flags[out["id"]].add("supersession")
            et = out["type"]
            if et == "commitment.create":
                prev_due[out["commitment"]] = out.get("due")
            if et == "commitment.update":
                ch = out["changes"]
                if "debtor" in ch:
                    flags[out["id"]].add("transfer")
                if ch.get("accepted") is True:
                    flags[out["id"]].add("endorsement")
                if "due" in ch and prev_due.get(out["commitment"]):
                    flags[out["id"]].add("supersession")
                if "due" in ch:
                    prev_due[out["commitment"]] = ch["due"]
            if et == "decision.reverse":
                flags[out["id"]].add("reversal")
            if et in ("project.split", "project.merge"):
                flags[out["id"]].add("restructuring")
            events.append(out)
        by_new = {e["id"]: e for e in events}
        seed_start = self.cal["seed"]["start"]
        # Communications in delivery order, numbered cm-0001..., artifacts per prefix.
        comms = sorted(self.comms, key=lambda c: (c.received_at, c.t, c.extra.get("_seq", 0)))
        commap = {c.id: f"cm-{i:04d}" for i, c in enumerate(comms, 1)}
        counters: Counter = Counter()
        for c in comms:
            c.id = commap[c.id]
            if c.parent:
                c.parent = commap.get(c.parent, c.parent)
            dups = set(c.extra.pop("_dup", []))
            c.extra.pop("_seq", None)
            c.extra.pop("fixed", None)
            if "draft_of" in c.extra:
                c.extra["draft_of"] = cmap.get(c.extra["draft_of"], c.extra["draft_of"])
            for a in c.acts:
                old = a.event
                a.event = emap[old]
                e = by_new[a.event]
                if old in dups:
                    c.tag("duplicate_signal")
                for tag in sorted(flags.get(a.event, ())):
                    c.tag(tag)
                if a.how == "indirect" and e["type"] == "commitment.resolve":
                    c.tag("silent_closure")
                if a.how == "implied" and e["type"] == "commitment.create":
                    c.tag("implied_commitment")
                if a.how == "correction":
                    c.tag("correction")
                if e["type"] == "entity.create" and e["kind"] in ("person", "project") and e["t"][:10] > seed_start \
                        and e["t"][:10] >= add_days(c.date, -2):
                    c.tag("new_entity")
                if e["type"] == "commitment.create" and e.get("accepted") is False:
                    c.tag("endorsement")
            if c.kind in ("note", "voice_memo") and c.sender == self.W and any(
                    by_new[a.event]["type"] in ("decision.make", "commitment.resolve", "commitment.update", "project.merge")
                    for a in c.acts):
                c.tag("worker_directive")
            if c.noise:
                c.tag("noise")
            if c.secrets:
                c.tag("privacy")
            if c.date > c.t[:10]:
                c.tag("batch_catchup")
            forms = c.extra.get("name_forms") or {}
            collision = {p for pair in self.plan["collisions"]["first_names"] for p in pair}
            for pid, form in forms.items():
                if pid in collision and form == self.people[pid]["first"]:
                    c.tag("name_collision")
                elif form != self.people[pid]["name"]:
                    c.tag("alias")
            if c.kind == "email" and not c.subject:
                c.subject = self._default_subject(c, by_new)
            c.artifacts = []
            for prefix in c.prefixes():
                counters[prefix] += 1
                c.artifacts.append(f"{prefix}-{counters[prefix]:04d}")
        unrevealed = {emap[k]: v for k, v in self.unrevealed.items()}
        revealed = {a.event for c in comms for a in c.acts}
        worker_create = emap[self.ent_ev[self.W]]
        for e in events:
            if e["id"] not in revealed and e["id"] not in unrevealed and e["id"] != worker_create:
                # People and projects nobody ever mentions stay hidden; anything else is a bug.
                unrevealed[e["id"]] = "never appears" if e["type"] == "entity.create" else "never revealed"
        meta = self._meta()
        return Simulation(events=events, comms=comms, meta=meta, unrevealed=dict(sorted(unrevealed.items())))

    def _default_subject(self, c: Communication, by_new: dict[str, dict]) -> str:
        for a in c.acts:
            e = by_new[a.event]
            if e["type"] == "commitment.create":
                return self.subject_of(e["what"])
            if e["type"] in ("commitment.update", "commitment.resolve"):
                create = next((x for x in by_new.values() if x["type"] == "commitment.create"
                               and x["commitment"] == e["commitment"]), None)
                if create:
                    return "Re: " + self.subject_of(create["what"])
            if e["type"] == "decision.make":
                return self.subject_of(e["what"])
        proj = self.projs.get(c.project or "")
        return f"{proj.p['name']}: quick update" if proj else "Quick question"

    def _meta(self) -> dict:
        plan = self.plan
        umb = self.orgs[plan["setting"]["umbrella"]]
        cen = self.orgs[plan["setting"]["central"]]
        g = plan["generator"]
        return {
            "id": plan["world_id"],
            "title": f"Generated world: {cen['name']}, {umb['name']} ({plan['setting']['label']})",
            "version": 1,
            "split": "dev",
            "worker": self.W,
            "timezone": self.tz,
            "seed": {"start": self.cal["seed"]["start"], "end": self.cal["seed"]["end"]},
            "episode": {"days": list(self.episode_days)},
            "checkpoints": [dict(c) for c in self.cal["checkpoints"]],
            "generator": {"kind": "wcb-gen", "version": g["version"], "seed": g["seed"], "sim_seed": self.seed,
                          "size": g["size"], "weeks": g["weeks"], "setting": plan["setting"]["key"]},
        }


def _clean_keywords(keywords: list[str], what: str) -> list[str]:
    """Lowercase, deduplicated keywords that occur in `what`; at least two."""
    low = what.lower()
    out: list[str] = []
    for k in keywords:
        k = " ".join(k.lower().split())
        if k and k in low and k not in out:
            out.append(k)
    if len(out) < 2:
        words = [w.strip(".,;:'\"()") for w in low.split()]
        words = [w for w in words if len(w) > 4 and w not in out and not any(w in o for o in out)]
        words.sort(key=len, reverse=True)
        out += words[: 2 - len(out)]
    return out
