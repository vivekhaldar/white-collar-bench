"""Project summaries track current state (issue #8, docs/generator.md "Summaries track current state").

A project's summary is regenerated from its archetype description whenever the project changes.
Values in that description that a decision can change (scope count, hosting, shortlist, build or
buy) must come from the project's current state, so that a later unrelated update (a phase move,
a date slip) cannot resurrect a value an accepted decision replaced, and an earlier checkpoint
never shows the later value.
"""

from __future__ import annotations

import functools
import re
from pathlib import Path

import pytest

from wcb.world import archetypes as A
from wcb.world.check import stale_count_summaries, superseded_counts
from wcb.world.model import World
from wcb.world.planner import make_plan
from wcb.world.simulator import FALLBACK_SCOPE, NUMBER_WORDS, _Sim
from wcb.world.state import state_at

ROOT = Path(__file__).resolve().parents[2]
DEV_WORLDS = sorted(p for p in (ROOT / "worlds" / "dev").iterdir() if (p / "world.jsonl").is_file())
# Freshly generated worlds besides the committed dev worlds: (seed, size, weeks).
EXTRA_SIMS = [(11, "standard", 2), (12, "small", 2), (13, "standard", 4), (14, "large", 1)]


# ---------------------------------------------------------------- driving the simulator
def _summaries(sim: _Sim, pid: str) -> list[str]:
    return [e["value"] for e in sim.events
            if e["type"] == "fact.set" and e.get("attribute") == "summary" and e["subject"] == pid]


def _current_summary(sim: _Sim, pid: str) -> str:
    return (_summaries(sim, pid) or [sim.projs[pid].summary])[-1]


def _note(sim: _Sim, day: str, minute: int):
    return sim.new_comm(day, "note", minute, sim.W, [], subject="notes")


def _reverse(sim: _Sim, did: str, days: list[str]) -> None:
    """Fire the reversal challenge on `did` until it is placed (placement can miss a day)."""
    for day in days:
        sim._ch_reversal(day, {"project": sim.dec[did]["project"]}, "step0", {"decision": did})
        if sim.dec[did]["reversed"]:
            return
    raise AssertionError(f"could not place a reversal of {did}")


@functools.cache
def _flagship_seed() -> int:
    """A seed whose flagship starts in a phase with a successor, so a phase move is possible."""
    for seed in range(40):
        plan = make_plan(seed, weeks=2)
        pp = next(p for p in plan["projects"] if p["archetype"] == "flagship_pilot")
        if A.get("flagship_pilot").phase(pp["phase"]).next:
            return seed
    raise AssertionError("no seed")


def _flagship_sim() -> tuple[_Sim, object]:
    seed = _flagship_seed()
    sim = _Sim(make_plan(seed, weeks=2), seed)
    sim._init_entities()
    return sim, sim.projs[sim.flagship_id]


def _beat(key: str) -> A.Beat:
    return next(b for b in A.get("flagship_pilot").decisions if b.key == key)


def test_scope_reversal_survives_later_phase_and_date_updates():
    sim, proj = _flagship_sim()
    days = sim.episode_days
    n0 = proj.n
    old, new = f"{NUMBER_WORDS[n0]} {sim.vocab.sites}", f"{NUMBER_WORDS[n0 + 1]} {sim.vocab.sites}"
    assert old in proj.summary and new not in proj.summary

    # Initial scope: the decision restates the plan's count; the summary does not change.
    c = _note(sim, days[0], 8 * 60)
    did = sim.decide(days[0], proj, _beat("d_scope"), comm=c, t=c.t)["decision"]
    assert old in sim.dec[did]["what"]
    assert old in _current_summary(sim, proj.id)

    # Reversal and replacement: the summary is rewritten with the new scope at once.
    _reverse(sim, did, days[1:])
    replacement = sim.dec[f"d-x{sim.n_dec:03d}"]
    assert new in replacement["what"]
    rewritten = _current_summary(sim, proj.id)
    assert new in rewritten and old not in rewritten
    rev_t = sim.ev[sim.dec_ev[replacement["id"]]]["t"]
    summary_ev = [e for e in sim.events if e["type"] == "fact.set" and e.get("attribute") == "summary"
                  and e["subject"] == proj.id][-1]
    assert summary_ev["t"] == rev_t

    # A later, unrelated phase move and date slip rewrite the summary again: still the new scope.
    later = days[-1]
    nxt = proj.arch.phase(proj.phase).next[0][0]
    c2 = _note(sim, later, 9 * 60)
    sim.set_facts(proj, c2.t, {"phase": nxt}, f"{proj.p['name']} moved to {nxt}", c2)
    if proj.target:
        sim.fact_beat(later, proj, A.SLIP, comm=c2, t=c2.t)
    final = _current_summary(sim, proj.id)
    assert final != rewritten
    assert new in final and old not in final


def test_hosting_replacement_survives_later_updates():
    sim, proj = _flagship_sim()
    days = sim.episode_days
    hub = sim.plan_projects[sim.hub_id]["short"]
    assert f"hosted on {hub}" in proj.summary
    c = _note(sim, days[0], 8 * 60)
    did = sim.decide(days[0], proj, _beat("d_host"), comm=c, t=c.t)["decision"]
    _reverse(sim, did, days[1:])
    assert f"hosted on a dedicated tenant outside {hub}" in _current_summary(sim, proj.id)
    c2 = _note(sim, days[-1], 9 * 60)
    sim.set_facts(proj, c2.t, {"blocker": "a test blocker"}, "blocked", c2)
    final = _current_summary(sim, proj.id)
    assert "a test blocker" in final
    assert f"hosted on a dedicated tenant outside {hub}" in final
    assert f"hosted on {hub}." not in final


def test_reversing_the_replacement_restores_the_scope():
    sim, proj = _flagship_sim()
    days = sim.episode_days
    n0 = proj.n
    c = _note(sim, days[0], 8 * 60)
    did = sim.decide(days[0], proj, _beat("d_scope"), comm=c, t=c.t)["decision"]
    _reverse(sim, did, days[1:])
    assert proj.n == n0 + 1
    replacement = f"d-x{sim.n_dec:03d}"
    _reverse(sim, replacement, days[3:])
    assert proj.n == n0
    assert f"{NUMBER_WORDS[n0]} {sim.vocab.sites}" in _current_summary(sim, proj.id)


def test_every_description_effect_is_reachable_and_changes_the_description():
    """Each decision effect names state that the description shows, and applying it changes
    the text: an effect that the description ignores would be a no-op."""
    assert A.check_library() == []
    sim, _ = _flagship_sim()
    effects = [(arch, b) for arch in A.ARCHETYPES.values() for b in arch.decisions if b.effect]
    assert {arch.name for arch, _ in effects} == {"flagship_pilot", "vendor_pair_evaluation", "internal_incubation"}
    for arch, b in effects + [(A.get("flagship_pilot"), FALLBACK_SCOPE)]:
        pp = next((p for p in sim.plan["projects"] if p["archetype"] == arch.name), None)
        if pp is None:
            continue
        proj = sim.projs[pp["id"]]
        before = sim._desc(proj)
        undo = sim.apply_effect(proj, b.effect)
        assert sim._desc(proj) != before, (arch.name, b.key)
        sim.undo_effect(proj, undo)
        assert sim._desc(proj) == before


# ---------------------------------------------------------------- the dev world from issue #8
def test_issue_8_garnet_scope_by_checkpoint():
    w = World.load(ROOT / "worlds" / "dev" / "gen-s7-w2")
    summary = {d: state_at(w, d)["entities"]["pr-garnet"]["attrs"]["summary"] for d in ("2027-07-07", "2027-07-08", "2027-07-17")}
    assert "three courses" in summary["2027-07-07"] and "four courses" not in summary["2027-07-07"]
    for d in ("2027-07-08", "2027-07-17"):
        assert "four courses" in summary[d] and "three courses" not in summary[d]
    decisions = state_at(w, "2027-07-17")["decisions"]
    whats = {d["what"]: d["status"] for d in decisions.values() if d["project"] == "pr-garnet"}
    assert whats["Limit the Garnet pilot to three courses"] == "reversed"
    assert whats["Widen the Garnet pilot to four courses"] == "made"


# ---------------------------------------------------------------- sweep over generated worlds
def _pattern(template: str) -> re.Pattern:
    """A regex for text rendered from a beat template: slots become wildcards."""
    parts = re.split(r"\{[a-z_0-9.]+\}", template)
    return re.compile("^" + ".+?".join(re.escape(p) for p in parts) + "$")


# Templates of replacement decisions that change a description, per archetype.
EFFECT_COUNTERS = {
    arch.name: [_pattern(b.counter[0]) for b in arch.decisions if b.effect]
    + ([_pattern(FALLBACK_SCOPE.counter[0])] if arch.name == "flagship_pilot" else [])
    for arch in A.ARCHETYPES.values()
}


def _desc_at_creation(w: World) -> dict[str, str]:
    """Each project's description as first created: the entity.create summary is 'Name: desc'."""
    out = {}
    for e in w.events:
        if e.get("type") == "entity.create" and e.get("kind") == "project":
            prefix = f"{e['name']}: "
            if e["summary"].startswith(prefix):
                out[e["entity"]] = e["summary"][len(prefix):]
    return out


def _sweep(w: World) -> list[str]:
    """Problems with current summaries at every checkpoint of `w`."""
    problems = [f"{pid}: summary still says {old!r} at the end of {day} after {did}"
                for pid, did, old, day in stale_count_summaries(w)]
    created = _desc_at_creation(w)
    for cp in sorted({c["date"] for c in w.checkpoints()} | {w.seed_end}):
        st = state_at(w, cp)
        for pid, ent in st["entities"].items():
            if ent["kind"] != "project" or pid not in created:
                continue
            arch = ent["attrs"].get("_archetype")
            summary = str(ent["attrs"].get("summary") or "")
            changed = [did for did, d in st["decisions"].items()
                       if d["project"] == pid and d["status"] == "made"
                       and any(p.match(d["what"]) for p in EFFECT_COUNTERS.get(arch, []))]
            # Superseded counts the generic check can see, at this checkpoint's knowledge.
            for d in st["decisions"].values():
                if d["project"] == pid and d["status"] == "reversed":
                    for rid in changed:
                        for old, new in superseded_counts(d["what"], st["decisions"][rid]["what"]):
                            if old in summary.lower() and new not in summary.lower():
                                problems.append(f"{cp} {pid}: summary says {old!r} after {rid}")
            if changed and summary.startswith(created[pid]):
                problems.append(f"{cp} {pid}: summary still has the creation-time description after {changed}")
            if not changed and not summary.startswith(created[pid]) and ent["attrs"].get("status") != "merged":
                # No replacement known yet: the description must not show a later value.
                problems.append(f"{cp} {pid}: description changed before any known replacement: {summary!r}")
    return problems


@pytest.mark.parametrize("world_dir", DEV_WORLDS, ids=lambda p: p.name)
def test_dev_world_summaries_never_show_superseded_values(world_dir):
    assert _sweep(World.load(world_dir)) == []


def test_dev_worlds_exercise_replacements():
    """The sweep is not vacuous: the dev worlds replace scope, the shortlist and build-vs-buy."""
    kinds = set()
    for d in DEV_WORLDS:
        for e in World.load(d).events:
            if e.get("type") == "decision.make":
                for arch, pats in EFFECT_COUNTERS.items():
                    if any(p.match(e["what"]) for p in pats):
                        kinds.add(arch)
    assert {"flagship_pilot", "vendor_pair_evaluation", "internal_incubation"} <= kinds


@pytest.mark.parametrize("seed,size,weeks", EXTRA_SIMS)
def test_generated_world_summaries_never_show_superseded_values(tmp_path, seed, size, weeks):
    from wcb.world.generate import generate_world

    out = generate_world(seed=seed, weeks=weeks, size=size, out_dir=tmp_path / "w", build=False)
    assert _sweep(World.load(out)) == []


# ---------------------------------------------------------------- the mechanical check
def test_superseded_counts():
    assert superseded_counts("Limit the Garnet pilot to three courses", "Widen the Garnet pilot to four courses") == [
        ("three courses", "four courses")]
    assert superseded_counts("Adopt a three-tier risk model", "Adopt a two-tier risk model") == [
        ("three-tier", "two-tier")]
    assert superseded_counts("Shortlist Toria and Ithic", "Add a third bidder to the shortlist") == []


class _Events:
    def __init__(self, events):
        self.events = events


def _ev(i, day, etype, **kw):
    return {"id": f"e-{i:04d}", "t": f"{day}T10:{i:02d}:00-08:00", "type": etype, "summary": "", **kw}


def _scope_events(rewrite: str | None) -> list[dict]:
    """Initial scope -> reversal and replacement (with or without a summary rewrite) -> a later
    unrelated update that regenerates the summary."""
    evs = [
        _ev(1, "2027-01-04", "entity.create", entity="pr-x", kind="project", name="X",
            attrs={"summary": "Pilot for three courses. In build."}),
        _ev(2, "2027-01-05", "decision.make", decision="d-1", project="pr-x", what="Limit the X pilot to three courses"),
        _ev(3, "2027-01-06", "decision.reverse", decision="d-1", project="pr-x"),
        _ev(4, "2027-01-06", "decision.make", decision="d-2", project="pr-x", what="Widen the X pilot to four courses"),
    ]
    if rewrite is not None:
        evs.append(_ev(5, "2027-01-06", "fact.set", subject="pr-x", attribute="summary", value=rewrite))
    evs.append(_ev(6, "2027-01-08", "fact.set", subject="pr-x", attribute="summary",
                   value=(rewrite or "Pilot for three courses. In build.").replace("In build", "In testing")))
    return evs


def test_stale_count_summaries_flags_resurrected_scope():
    assert stale_count_summaries(_Events(_scope_events(None))) == [("pr-x", "d-2", "three courses", "2027-01-06")]
    assert stale_count_summaries(_Events(_scope_events("Pilot for four courses. In build."))) == []
    # History that names both counts is not stale.
    assert stale_count_summaries(_Events(_scope_events("Widened from three courses to four courses."))) == []


def test_stale_count_summaries_respects_a_reversed_replacement():
    evs = _scope_events("Pilot for four courses. In build.")
    evs += [_ev(7, "2027-01-09", "decision.reverse", decision="d-2", project="pr-x"),
            _ev(8, "2027-01-09", "fact.set", subject="pr-x", attribute="summary", value="Pilot for three courses.")]
    assert stale_count_summaries(_Events(evs)) == []


def test_pilot_summaries_are_current():
    """The hand-authored pilot rewrites Tinderbox's summary the day its scope widens."""
    w = World.load(ROOT / "worlds" / "pilot")
    assert stale_count_summaries(w) == []
    summary = {d: state_at(w, d)["entities"]["pr-tinderbox"]["attrs"]["summary"] for d in ("2027-03-04", "2027-03-06")}
    assert "three courses" in state_at(w, "2027-02-17")["entities"]["pr-tinderbox"]["attrs"]["summary"]
    assert "four courses" not in summary["2027-03-04"]
    assert "four courses" in summary["2027-03-06"] and "three courses" not in summary["2027-03-06"]
