"""Generate `questions.yaml` for a generated world (docs/generator.md, "Question generator").

`generate_questions(world, states, seed=...)` returns question specs (docs/formats.md §3.1) for
every checkpoint. Gold answers are not computed here: `wcb world build` derives them from the
gold state, exactly as for a hand-authored world. Selection uses the gold state at each
checkpoint so that questions meant to be answerable are, and the others are not.

Every checkpoint gets:

- a prioritization question (`focus_tomorrow`);
- the flagship project's status (`project_status`);
- what changed on a busy project since the previous checkpoint (`project_changes`; for the
  first checkpoint, since the end of the seed window);
- per-person ledgers: what I owe someone and what someone owes me (`i_owe`, `owed_to_me`);
- a rotation of point, list, brief and temporal questions (`loop_owner`, `loop_due`,
  `project_attr`, `person_attr`, `project_loops`, `person_brief`, `decision_date`,
  `event_date`), so the world as a whole covers every template;
- about 10% unanswerable questions, mostly about facts no input reveals (an unobservable
  budget, a closure nobody reported, a person nobody mentions).

Entities touched by planted challenges are preferred. About 30% of entity mentions use an
alias (`name_form`): a nickname, initial and surname, role phrase or project code name that
an input delivered by the checkpoint actually uses, and that names exactly one entity.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

from wcb.questions.templates import TEMPLATES, lower_first
from wcb.util.dates import parse_date
from wcb.util.text import normalize
from wcb.world.model import ACTIVE_STATUSES, World
from wcb.world.state import state_at

PER_CHECKPOINT = {"small": 11, "standard": 15, "large": 18}
UNANSWERABLE_SHARE = 0.10
ALIAS_SHARE = 0.30
RELEVANT_TAGS = frozenset(
    """supersession reversal alias name_collision new_entity duplicate_signal implied_commitment
    weak_evidence transfer silent_closure unobservable draft_vs_sent acceptance_vs_occurrence
    correction restructuring endorsement worker_directive version_mismatch batch_catchup
    scattered_evidence""".split()
)
HIDDEN_ATTRS = ("budget", "budget_ceiling", "savings_target", "discount")
HIDDEN_ATTR_TEXT = {
    "budget": "What is the budget for {P}?",
    "budget_ceiling": "What is the budget ceiling for {P}?",
    "savings_target": "What is the savings target for {P}?",
    "discount": "What discount did we negotiate on {P}?",
}
OPTIONAL = ("loop_owner", "loop_due", "project_attr", "person_attr", "project_loops", "person_brief",
            "decision_date", "event_date")


def generate_questions(world: World, states: dict[str, dict], *, seed: int) -> list[dict]:
    """Question specs for every checkpoint of `world`, in checkpoint order."""
    return _QGen(world, states, seed).run()


class _QGen:
    def __init__(self, world: World, states: dict[str, dict], seed: int):
        self.w = world
        self.states = states
        self.rng = random.Random(f"wcb-questions:{seed}:{world.id}")
        gen = world.meta.get("generator") or {}
        self.per_cp = PER_CHECKPOINT.get(str(gen.get("size", "standard")), 15)
        self.worker = world.worker
        self.creates = world.entity_events()
        self.alias = world.alias_table()
        self.revealers = world.revealing_artifacts()
        self.art_tags = {a.id: set(a.challenges) & RELEVANT_TAGS for a in world.artifacts.values()}
        self.flagship = next((e for e, ev in self.creates.items() if ev["kind"] == "project"
                              and (ev.get("attrs") or {}).get("_archetype") == "flagship_pilot"), None)
        self.hidden_facts = [e for e in world.events if e.get("type") == "fact.set"
                             and e.get("attribute") in HIDDEN_ATTRS and not self.revealers.get(e["id"])]
        self.hidden_closures = [e for e in world.events if e.get("type") == "commitment.resolve"
                                and not self.revealers.get(e["id"])]
        self.collision = {e for e, ev in self.creates.items() if ev["kind"] == "person"
                          and len(self.alias.get(normalize(ev["name"].split()[0]), set())) > 1}
        self.texts: dict[str, str] = {}
        self.specs: list[dict] = []
        self.asked: Counter = Counter()
        self.mentions = 0
        self.aliased = 0

    # ------------------------------------------------------------ driver
    def run(self) -> list[dict]:
        cps = self.w.checkpoints()
        total = self.per_cp * len(cps)
        un_done = 0
        prev = self.w.seed_end
        for i, cp in enumerate(cps):
            state = self.states.get(cp["date"]) or state_at(self.w, cp["date"])
            self.state, self.cp, self.since = state, cp, prev
            self.tags = self._entity_tags(state)
            target_un = int(UNANSWERABLE_SHARE * total * (i + 1) / len(cps) + 0.5)
            n_un = max(0, target_un - un_done)
            before = len(self.specs)
            self._mandatory()
            rot = list(OPTIONAL)
            k = i % len(rot)
            rot = rot[k:] + rot[:k]
            budget = self.per_cp - n_un - (len(self.specs) - before)
            j = 0
            tries = 0
            while budget > 0 and tries < 3 * len(rot):
                if getattr(self, "_q_" + rot[j % len(rot)])():
                    budget -= 1
                j += 1
                tries += 1
            un_done += self._unanswerable(n_un)
            prev = cp["date"]
        for n, s in enumerate(self.specs, 1):
            s["id"] = f"q-{n:03d}"
        return [{"id": s["id"], **{k: v for k, v in s.items() if k != "id"}} for s in self.specs]

    # ------------------------------------------------------------ helpers
    def _entity_tags(self, state: dict) -> dict[str, set[str]]:
        out: dict[str, set[str]] = {}
        for ev in state["events"]:
            tags: set[str] = set()
            for a in ev.get("artifacts") or []:
                tags |= self.art_tags.get(a, set())
            for s in ev.get("subjects") or []:
                out.setdefault(s, set()).update(tags)
        return out

    def _weight(self, eid: str) -> float:
        return 1.0 + 2.0 * len(self.tags.get(eid, ()))

    def _pick(self, cands: list[str], key: str, *, repeat: bool = False) -> str | None:
        """A candidate weighted by challenge tags, avoiding ones already asked with `key`.

        With `repeat`, an already-asked candidate is allowed when nothing else is left."""
        fresh = [c for c in cands if not self.asked[(key, c)]]
        if not fresh and repeat:
            fresh = list(cands)
        if not fresh:
            return None
        return self.rng.choices(fresh, weights=[self._weight(c) for c in fresh])[0]

    def _gold(self, template: str, params: dict) -> tuple[bool, dict, list[str]]:
        return TEMPLATES[template].gold(params, self.w, self.state)

    def _text_upto(self, date: str) -> str:
        if date not in self.texts:
            from wcb.world.check import artifact_text

            parts = []
            for a in self.w.artifacts_through(date):
                t = artifact_text(self.w.dir / a.path) if (self.w.dir / a.path).exists() else None
                if t:
                    parts.append(t)
            self.texts[date] = normalize("\n".join(parts))
        return self.texts[date]

    def _alias_for(self, eid: str) -> str | None:
        ev = self.creates.get(eid)
        if ev is None:
            return None
        forms = [f for f in ev.get("surface_forms") or [] if "@" not in f and f != ev["name"]]
        corpus = self._text_upto(self.cp["date"])
        ok = [f for f in forms if self.alias.get(normalize(f).lstrip("@"), set()) == {eid}
              and len(normalize(f)) >= 3 and normalize(f) in corpus]
        return self.rng.choice(ok) if ok else None

    def _add(self, template: str, params: dict, *, entity: str | None = None, key: str | None = None,
             tags: set[str] | None = None, text: str | None = None, answerable: bool = True,
             obj: str | None = None) -> bool:
        params = dict(params)
        ok, _gold, support = self._gold(template, params)
        if ok != answerable:
            return False
        qtags = set(tags or ())
        for a in support:
            qtags |= self.art_tags.get(a, set()) - {"alias", "name_collision"}
        target = params.get("person") or params.get("project")
        if target in self.collision:
            qtags.add("name_collision")
        if entity is not None:
            self.mentions += 1
            behind = self.aliased < ALIAS_SHARE * self.mentions - 1
            if behind or self.rng.random() < ALIAS_SHARE:
                form = self._alias_for(entity)
                if form:
                    params["name_form"] = form
                    self.aliased += 1
                    qtags.add("alias")
        spec: dict[str, Any] = {"id": "", "checkpoint": self.cp["id"], "template": template, "params": params}
        if text:
            spec["text"] = text
        spec["challenges"] = sorted(qtags & RELEVANT_TAGS)
        self.specs.append(spec)
        self.asked[(key or template, obj or entity or str(sorted(params.items())))] += 1
        return True

    def _people(self) -> list[str]:
        return sorted(p for p, ent in self.state["entities"].items()
                      if ent["kind"] == "person" and p != self.worker and not ent["attrs"].get("_minor"))

    def _projects(self, *, live: bool = False) -> list[str]:
        out = []
        for p, ent in sorted(self.state["entities"].items()):
            if ent["kind"] != "project":
                continue
            if live and ent["attrs"].get("status") in ("done", "cancelled", "merged"):
                continue
            out.append(p)
        return out

    def _accepted_active(self) -> dict[str, dict]:
        return {c: lp for c, lp in self.state["loops"].items()
                if lp.get("accepted") and lp.get("status") in ACTIVE_STATUSES}

    def _unique_what(self, cid: str) -> bool:
        what = normalize(self.state["loops"][cid]["what"])
        return sum(1 for lp in self.state["loops"].values() if normalize(lp["what"]) == what) == 1

    # ------------------------------------------------------------ every checkpoint
    def _mandatory(self) -> None:
        self._add("focus_tomorrow", {})
        flag = self.flagship if self.flagship in self.state["entities"] else None
        if flag is None:
            projs = self._projects(live=True)
            flag = projs[0] if projs else None
        if flag:
            self._add("project_status", {"project": flag}, entity=flag)
        self._q_changes()
        self._q_ledger("i_owe")
        self._q_ledger("owed_to_me")

    def _q_changes(self) -> bool:
        from wcb.questions.templates import project_change_events

        counts = []
        for p in self._projects():
            n = len(project_change_events(self.w, self.state, p, self.since))
            if n:
                counts.append((n + (3 if p == self.flagship else 0), p))
        if not counts:
            return False
        counts.sort(key=lambda x: (-x[0], x[1]))
        top = [p for _, p in counts[:4]]
        p = self._pick(top, "changes", repeat=True)
        return self._add("project_changes", {"project": p, "since": self.since}, entity=p, key="changes")

    def _q_ledger(self, template: str) -> bool:
        active = self._accepted_active()
        people: Counter = Counter()
        for lp in active.values():
            if template == "i_owe" and lp["debtor"] == self.worker:
                for p in [lp["creditor"], *lp.get("others", [])]:
                    if p != self.worker:
                        people[p] += 1
            elif template == "owed_to_me" and lp["creditor"] == self.worker and lp["debtor"] != self.worker:
                people[lp["debtor"]] += 1
        cands = sorted(p for p in people if p in self.state["entities"]
                       and not self.state["entities"][p]["attrs"].get("_minor"))
        p = self._pick(cands, template, repeat=True)
        if p is None:
            return False
        return self._add(template, {"person": p}, entity=p)

    # ------------------------------------------------------------ rotation
    def _q_loop_owner(self) -> bool:
        loops = self.state["loops"]
        transferred = [c for c, lp in loops.items() if any("debtor" in h["changes"] for h in lp["history"][1:])
                       and self._unique_what(c)]
        others = [c for c, lp in self._accepted_active().items() if lp["debtor"] != self.worker and self._unique_what(c)]
        cands = sorted(transferred) or sorted(others)
        c = self._pick(cands, "loop_owner")
        return bool(c) and self._add("loop_owner", {"commitment": c}, key="loop_owner", obj=c)

    def _q_loop_due(self) -> bool:
        loops = self.state["loops"]
        moved = [c for c, lp in loops.items() if lp.get("due") and any("due" in h["changes"] for h in lp["history"][1:])
                 and self._unique_what(c)]
        dated = [c for c, lp in loops.items() if lp.get("due") and lp.get("status") in ACTIVE_STATUSES and self._unique_what(c)]
        c = self._pick(sorted(moved) or sorted(dated), "loop_due")
        return bool(c) and self._add("loop_due", {"commitment": c}, key="loop_due", obj=c)

    def _q_project_attr(self) -> bool:
        opts = []
        for p in self._projects():
            attrs = self.state["entities"][p]["attrs"]
            hist = self.state["entities"][p].get("attr_history") or {}
            if attrs.get("target_date") and len(hist.get("target_date") or []) > 1:
                opts.append((p, "target_date", 3))
            for a, w in (("owner", 1), ("phase", 1), ("next_step", 1), ("blocker", 2), ("sponsor", 1),
                         ("target_date", 1)):
                if attrs.get(a):
                    opts.append((p, a, w))
        opts = [o for o in opts if not self.asked[("project_attr", f"{o[0]}:{o[1]}")]]
        if not opts:
            return False
        p, a, _ = self.rng.choices(opts, weights=[o[2] * self._weight(o[0]) for o in opts])[0]
        ok = self._add("project_attr", {"project": p, "attribute": a}, entity=p, key="project_attr")
        if ok:
            self.asked[("project_attr", f"{p}:{a}")] += 1
        return ok

    def _q_person_attr(self) -> bool:
        people = self._people()
        newcomers = [p for p in people if "new_entity" in self.tags.get(p, set())]
        p = self._pick(newcomers or people, "person_attr")
        if p is None:
            return False
        attrs = self.state["entities"][p]["attrs"]
        choices = [a for a in ("role", "org", "relationship") if attrs.get(a)]
        if not choices:
            return False
        return self._add("person_attr", {"person": p, "attribute": self.rng.choice(choices)}, entity=p)

    def _q_project_loops(self) -> bool:
        active = self._accepted_active()
        per = Counter(lp["project"] for lp in active.values() if lp.get("project"))
        cands = sorted(p for p, n in per.items() if 2 <= n <= 9 and p in self.state["entities"])
        p = self._pick(cands, "project_loops")
        return bool(p) and self._add("project_loops", {"project": p}, entity=p)

    def _q_person_brief(self) -> bool:
        active = self._accepted_active()
        per: Counter = Counter()
        for lp in active.values():
            for x in (lp["debtor"], lp["creditor"]):
                if x != self.worker:
                    per[x] += 1
        cands = sorted(p for p in per if p in self.state["entities"]
                       and not self.state["entities"][p]["attrs"].get("_minor"))
        p = self._pick(cands, "person_brief")
        return bool(p) and self._add("person_brief", {"person": p}, entity=p)

    def _q_decision_date(self) -> bool:
        decs = self.state["decisions"]
        reversed_ = sorted(d for d, x in decs.items() if x["status"] == "reversed")
        d = self._pick(reversed_ or sorted(decs), "decision_date")
        return bool(d) and self._add("decision_date", {"decision": d}, key="decision_date", obj=d)

    def _q_event_date(self) -> bool:
        opts = []
        for ev in self.state["events"]:
            text = self._event_text(ev)
            if text and not self.asked[("event_date", ev["id"])]:
                opts.append((ev, text))
        if not opts:
            return False
        weights = [1 + 2 * len(set().union(*(self.art_tags.get(a, set()) for a in ev["artifacts"])) if ev["artifacts"] else 0)
                   for ev, _ in opts]
        ev, text = self.rng.choices(opts, weights=weights)[0]
        ok = self._add("event_date", {"event": ev["id"]}, key="event_date", text=text)
        if ok:
            self.asked[("event_date", ev["id"])] += 1
        return ok

    def _event_text(self, ev: dict) -> str | None:
        """Question text for an event, or None if the event type is not asked about."""
        raw = self.w.by_id.get(ev["id"], {})
        et = raw.get("type")
        name = self._name
        if et == "commitment.update" and "debtor" in (raw.get("changes") or {}):
            lp = self.state["loops"].get(raw["commitment"])
            if lp and self._unique_what(raw["commitment"]):
                return f'When was "{lp["what"]}" handed over to {name(raw["changes"]["debtor"])}?'
        if et == "decision.reverse":
            d = self.state["decisions"].get(raw["decision"])
            if d:
                return f"When did we reverse the decision to {lower_first(d['what'])}?"
        if et == "project.split":
            into = [name(p) for p in raw.get("into") or []]
            return f"When was {' and '.join(into)} split out of {name(raw['project'])}?"
        if et == "project.merge":
            return f"When was {' and '.join(name(p) for p in raw.get('projects') or [])} folded into {name(raw['into'])}?"
        if et == "fact.set" and raw.get("attribute") == "target_date" and raw.get("value"):
            d = parse_date(raw["value"])
            return f"When did the target date for {name(raw['subject'])} move to {d.day} {d.strftime('%B')}?"
        if et == "commitment.resolve" and raw.get("status") == "done":
            lp = self.state["loops"].get(raw["commitment"])
            if lp and self._unique_what(raw["commitment"]):
                return f'When was "{lp["what"]}" completed?'
        return None

    def _name(self, eid: str) -> str:
        ent = self.state["entities"].get(eid) or self.creates.get(eid)
        return str(ent["name"]) if ent else eid

    # ------------------------------------------------------------ unanswerable
    def _unanswerable(self, n: int) -> int:
        """Unanswerable questions about entities the inputs do show: a hidden figure, a closure no
        input reports, a detail never given. A person no input mentions is only a last resort
        (the missing name gives it away)."""
        made = 0
        kinds = ["hidden_fact", "hidden_closure", "seen_person_detail", "hidden_fact", "any_budget"]
        self.rng.shuffle(kinds)
        for kind in kinds * 2:
            if made >= n:
                break
            if getattr(self, "_u_" + kind)():
                made += 1
        while made < n and (self._u_any_budget() or self._u_seen_person_detail() or self._u_unknown_person()):
            made += 1
        return made

    def _u_hidden_fact(self) -> bool:
        cands = [e for e in self.hidden_facts if e["subject"] in self.state["entities"]
                 and not self.asked[("u_fact", e["subject"] + e["attribute"])]]
        if not cands:
            return False
        e = self.rng.choice(cands)
        P = self._name(e["subject"])
        ok = self._add("project_attr", {"project": e["subject"], "attribute": e["attribute"]}, answerable=False,
                       tags={"unobservable"}, text=HIDDEN_ATTR_TEXT[e["attribute"]].format(P=P))
        if ok:
            self.asked[("u_fact", e["subject"] + e["attribute"])] += 1
        return ok

    def _u_hidden_closure(self) -> bool:
        cands = [e for e in self.hidden_closures if e["t"][:10] <= self.cp["date"]
                 and e["commitment"] in self.state["loops"] and not self.asked[("u_close", e["id"])]
                 and self._unique_what(e["commitment"])]
        if not cands:
            return False
        e = self.rng.choice(cands)
        what = self.state["loops"][e["commitment"]]["what"]
        ok = self._add("event_date", {"event": e["id"]}, answerable=False, tags={"weak_evidence", "unobservable"},
                       text=f'When was "{what}" completed?')
        if ok:
            self.asked[("u_close", e["id"])] += 1
        return ok

    def _u_seen_person_detail(self) -> bool:
        """A detail about someone the inputs mention that no input ever gives (their direct line,
        their office), asked about a person the worker deals with."""
        active = self._accepted_active()
        people = sorted({x for lp in active.values() for x in (lp["debtor"], lp["creditor"]) if x != self.worker
                         and x in self.state["entities"] and not self.state["entities"][x]["attrs"].get("_minor")})
        attr = self.rng.choice(["phone", "office"])
        cands = [p for p in people if not self.state["entities"][p]["attrs"].get(attr)
                 and not self.asked[("u_detail", p)]]
        if not cands:
            return False
        p = self.rng.choice(cands)
        ok = self._add("person_attr", {"person": p, "attribute": attr}, answerable=False, tags={"unobservable"},
                       entity=p)
        if ok:
            self.asked[("u_detail", p)] += 1
        return ok

    def _u_unknown_person(self) -> bool:
        cands = sorted(p for p, ev in self.creates.items() if ev["kind"] == "person" and p not in self.state["entities"]
                       and not self.revealers.get(ev["id"]) and p != self.worker
                       and not (ev.get("attrs") or {}).get("_minor") and not self.asked[("u_person", p)]
                       and len(self.alias.get(normalize(ev["name"]), set())) == 1)
        if not cands:
            return False
        p = self.rng.choice(cands)
        ok = self._add("person_attr", {"person": p, "attribute": "role"}, answerable=False, tags={"unobservable"})
        if ok:
            self.asked[("u_person", p)] += 1
        return ok

    def _u_any_budget(self) -> bool:
        projs = self._projects(live=True)
        self.rng.shuffle(projs)
        for p in projs:
            if not self.asked[("u_budget", p)] and "budget" not in self.state["entities"][p]["attrs"]:
                ok = self._add("project_attr", {"project": p, "attribute": "budget"}, answerable=False,
                               tags={"unobservable"}, entity=p)
                self.asked[("u_budget", p)] += 1
                if ok:
                    return True
        return False
