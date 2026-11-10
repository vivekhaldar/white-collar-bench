"""Simulator: determinism, world consistency, knowability, planted challenges and calibration.

The simulator's output is checked with the repository's own tools: the world-check functions
(`wcb.world.check`), gold state (`wcb.world.state.state_at`) and calibration statistics
(`wcb.world.stats.compute_stats`), applied to an in-memory world built from the simulation's
preview `artifact.emit` events.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict

import pytest

from wcb.util.dates import add_days, parse_date
from wcb.world import check as C
from wcb.world.comms import (
    CHANNEL_OF_KIND,
    COVERAGE_PREFIXES,
    HOWS,
    KINDS,
    Act,
    Communication,
    artifact_prefixes,
)
from wcb.world.names import HARD_DENYLIST
from wcb.world.planner import CHALLENGE_TAGS, make_plan
from wcb.world.simulator import simulate
from wcb.world.state import state_at
from wcb.world.stats import compute_stats

CALIBRATION_SEEDS = (0, 1, 2, 3, 4, 5)
WORLDS = [(0, "standard", 1), (1, "standard", 1), (2, "small", 1), (3, "large", 1), (4, "standard", 2)]


def _check_issues(sim):
    """World-check issues for the simulation (everything that does not need artifact files)."""
    world = sim.world()
    issues: list = []
    C._check_meta(world.meta, issues)
    C._check_event_fields(list(world.events), world.meta, issues)
    ix = C._Index.build(world)
    C._check_ids(world, ix, issues)
    C._check_references(world, ix, issues)
    for a in world.artifacts.values():
        C._check_reveals(a, ix, a.id, issues)
    C._check_project_summaries(world, ix, issues)
    return world, issues


# ---------------------------------------------------------------- determinism and serialization
def test_simulation_is_deterministic():
    a = simulate(make_plan(21, weeks=2), 21)
    b = simulate(make_plan(21, weeks=2), 21)
    assert json.dumps(a.to_dict(), sort_keys=True) == json.dumps(b.to_dict(), sort_keys=True)
    c = simulate(make_plan(21, weeks=2), 22)
    assert json.dumps(a.to_dict(), sort_keys=True) != json.dumps(c.to_dict(), sort_keys=True)


def test_communication_round_trip(sim_of):
    sim = sim_of(0)
    for c in sim.comms:
        d = c.to_dict()
        assert Communication.from_dict(d).to_dict() == d
        assert json.loads(json.dumps(d)) == d
    a = Act("e-0001", "hedged", "p-x")
    assert Act.from_dict(a.to_dict()) == a and Act.from_dict({"event": "e-1"}).how == "direct"


def test_meta_is_a_valid_world_yaml(sim_of):
    sim = sim_of(4, "standard", 2)
    meta = sim.meta
    plan = make_plan(4, weeks=2)
    assert meta["worker"] == plan["worker"]
    assert meta["episode"]["days"] == plan["calendar"]["episode"]["days"]
    assert meta["seed"] == {"start": plan["calendar"]["seed"]["start"], "end": plan["calendar"]["seed"]["end"]}
    assert [c["id"] for c in meta["checkpoints"]] == [f"cp{i}" for i in range(1, 7)]
    assert meta["generator"]["kind"] == "wcb-gen"
    issues: list = []
    C._check_meta(meta, issues)
    assert issues == []


# ---------------------------------------------------------------- world consistency
@pytest.mark.parametrize("seed,size,weeks", WORLDS)
def test_world_check_is_clean(sim_of, seed, size, weeks):
    _world, issues = _check_issues(sim_of(seed, size, weeks))
    assert [i.format() for i in issues] == []


@pytest.mark.parametrize("seed,size,weeks", WORLDS)
def test_events_reference_existing_ids(sim_of, seed, size, weeks):
    sim = sim_of(seed, size, weeks)
    entities = {e["entity"]: e["kind"] for e in sim.events if e["type"] == "entity.create"}
    created: dict[str, str] = {}
    ids = [e["id"] for e in sim.events]
    assert ids == [f"e-{i:04d}" for i in range(1, len(ids) + 1)]
    assert [e["t"] for e in sim.events] == sorted(e["t"] for e in sim.events)
    for e in sim.events:
        et = e["type"]
        if et == "commitment.create":
            assert e["commitment"] not in created
            created[e["commitment"]] = e["t"]
            for k in ("debtor", "creditor"):
                assert entities[e[k]] == "person"
            assert all(entities[o] == "person" for o in e["others"])
            assert e.get("project") is None or entities[e["project"]] == "project"
        elif et in ("commitment.update", "commitment.resolve"):
            assert e["commitment"] in created and created[e["commitment"]] <= e["t"]
            for k in ("debtor", "creditor"):
                if k in (e.get("changes") or {}):
                    assert entities[e["changes"][k]] == "person"
        elif et == "fact.set":
            assert e["subject"] in entities
        elif et == "decision.make":
            assert all(entities[p] == "person" for p in e["by"])
        elif et == "project.split":
            assert entities[e["project"]] == "project" and all(entities[p] == "project" for p in e["into"])
            assert all(c in created for c in e["moves"])
        elif et == "project.merge":
            assert entities[e["into"]] == "project" and all(entities[p] == "project" for p in e["projects"])
    commitments = sorted(created)
    assert commitments == [f"c-{i:03d}" for i in range(1, len(commitments) + 1)]


@pytest.mark.parametrize("seed,size,weeks", WORLDS)
def test_state_at_every_day_without_unknown_object_updates(sim_of, seed, size, weeks):
    sim = sim_of(seed, size, weeks)
    world = sim.world()
    known_on = world.known_on()
    for date in world.all_dates():
        st = state_at(world, date)
        applied = {e["id"] for e in st["events"]}
        knowable = {eid for eid, d in known_on.items() if d <= date}
        # Every knowable event is applied: no update is revealed before the object it changes.
        assert knowable <= applied, sorted(knowable - applied)[:5]
        for lp in st["loops"].values():
            for k in ("debtor", "creditor"):
                assert lp[k] in st["entities"] or lp[k] == sim.meta["worker"]
            assert lp["project"] is None or lp["project"] in st["entities"]


@pytest.mark.parametrize("seed,size,weeks", WORLDS)
def test_reveals_and_delivery(sim_of, seed, size, weeks):
    sim = sim_of(seed, size, weeks)
    ev = {e["id"]: e for e in sim.events}
    cal = make_plan(seed, size=size, weeks=weeks)["calendar"]
    seed_start, seed_end = cal["seed"]["start"], cal["seed"]["end"]
    episode = set(cal["episode"]["days"])
    revealed: set[str] = set()
    for c in sim.comms:
        assert c.kind in KINDS and c.channel == CHANNEL_OF_KIND[c.kind]
        assert c.t <= c.received_at
        assert (seed_start <= c.date <= seed_end) or c.date in episode
        for a in c.acts:
            assert a.how in HOWS
            assert ev[a.event]["t"] <= c.t, (c.id, a.event)
            revealed.add(a.event)
        for tag in c.challenges:
            assert tag in C.CHALLENGE_TAGS
    hidden = set(sim.unrevealed)
    assert not hidden & revealed
    assert hidden | revealed | {sim.events[0]["id"]} == set(ev)
    reasons = Counter(sim.unrevealed.values())
    assert reasons["unobservable"] >= weeks
    assert "never revealed" not in reasons
    for eid, why in sim.unrevealed.items():
        if why == "never appears":
            assert ev[eid]["type"] == "entity.create"


def test_artifact_ids_in_delivery_order(sim_of):
    sim = sim_of(4, "standard", 2)
    seen: dict[str, int] = defaultdict(int)
    order = [(c.received_at, c.id) for c in sim.comms]
    assert order == sorted(order)
    assert [c.id for c in sim.comms] == [f"cm-{i:04d}" for i in range(1, len(sim.comms) + 1)]
    for c in sim.comms:
        assert [a[:2] for a in c.artifacts] == artifact_prefixes(c.kind, c.extra.get("coverage"))
        for aid in c.artifacts:
            prefix, num = aid.split("-")
            seen[prefix] += 1
            assert int(num) == seen[prefix], aid
        if c.kind == "meeting":
            assert c.extra["coverage"] in COVERAGE_PREFIXES
        if c.parent:
            parent = next(x for x in sim.comms if x.id == c.parent)
            assert parent.received_at == c.received_at


def test_keywords_and_summaries(sim_of):
    sim = sim_of(1)
    for e in sim.events:
        assert e["summary"].strip(), e
        if e["type"] in ("commitment.create", "decision.make"):
            assert len(e["keywords"]) >= 2, e
            for kw in e["keywords"]:
                assert kw == kw.lower() and kw in e["what"].lower(), (kw, e["what"])
    # A summary is rewritten at the same instant as each status/phase/target/blocker change.
    summary_at = {(e["subject"], e["t"]) for e in sim.events if e["type"] == "fact.set" and e["attribute"] == "summary"}
    for e in sim.events:
        if e["type"] == "fact.set" and e["attribute"] in ("status", "phase", "target_date", "blocker"):
            assert (e["subject"], e["t"]) in summary_at, e


def test_no_denylisted_strings(sim_of):
    for key in WORLDS[:3]:
        blob = json.dumps(sim_of(*key).to_dict()).lower()
        for bad in HARD_DENYLIST:
            assert bad not in blob, bad


# ---------------------------------------------------------------- planted challenges
@pytest.mark.parametrize("seed,size,weeks", WORLDS + [(5, "standard", 3), (6, "small", 2)])
def test_every_challenge_tag_appears_every_episode_week(sim_of, seed, size, weeks):
    sim = sim_of(seed, size, weeks)
    plan = make_plan(seed, size=size, weeks=weeks)
    for w, days in enumerate(plan["calendar"]["episode"]["weeks"], 1):
        tags = {t for c in sim.comms if days[0] <= c.date <= days[-1] for t in c.challenges}
        assert set(CHALLENGE_TAGS) <= tags, (w, sorted(set(CHALLENGE_TAGS) - tags))


def test_challenge_mechanics(sim_of):
    sim = sim_of(4, "standard", 2)
    ev = {e["id"]: e for e in sim.events}
    by_tag = defaultdict(list)
    for c in sim.comms:
        for t in c.challenges:
            by_tag[t].append(c)
    # batch catch-up: written on one day, delivered early the next delivery day
    for c in by_tag["batch_catchup"]:
        assert c.date > c.t[:10] and c.received_at[11:13] == "07"
    # privacy: planted secrets (join links, passcodes, temporary passwords)
    secrets = [s for c in by_tag["privacy"] for s in c.secrets]
    assert any(s.startswith("https://") for s in secrets) and any(s.isdigit() for s in secrets)
    assert any(s.startswith("Tmp-") for s in secrets)
    # draft vs sent: a draft that reveals nothing
    drafts = [c for c in sim.comms if c.draft]
    assert drafts and all(not c.acts and c.kind == "email" for c in drafts)
    # acceptance vs occurrence: an acceptance that reveals nothing
    assert all(c.kind == "calendar_reply" and not c.acts for c in by_tag["acceptance_vs_occurrence"])
    # weak evidence: a resolution that no communication reveals
    weak = [eid for eid, why in sim.unrevealed.items() if why.startswith("weak evidence")]
    assert len(weak) >= 2 and all(ev[e]["type"] == "commitment.resolve" for e in weak)
    # endorsement: a suggested loop accepted later through a worker note
    suggested = {e["commitment"] for e in sim.events if e["type"] == "commitment.create" and not e["accepted"]}
    endorsed = [c for c in by_tag["endorsement"] if c.kind in ("note", "voice_memo")
                and any(ev[a.event]["type"] == "commitment.update"
                        and ev[a.event]["changes"].get("accepted") is True
                        and ev[a.event]["commitment"] in suggested for a in c.acts)]
    assert endorsed
    # version mismatch: an email and its attachment with different version labels
    vm = [c for c in by_tag["version_mismatch"] if c.kind == "email"]
    assert vm and all(c.extra["version_mismatch"]["body"] != c.extra["version_mismatch"]["attachment"] for c in vm)
    assert any(c.kind == "document" and c.parent for c in by_tag["version_mismatch"])
    # restructuring: a split or a merge
    assert any(ev[a.event]["type"] in ("project.split", "project.merge") for c in by_tag["restructuring"] for a in c.acts)
    # reversal, transfer, silent closure, correction, implied commitments
    assert any(ev[a.event]["type"] == "decision.reverse" for c in by_tag["reversal"] for a in c.acts)
    assert any("debtor" in ev[a.event].get("changes", {}) for c in by_tag["transfer"] for a in c.acts)
    assert any(a.how == "indirect" for c in by_tag["silent_closure"] for a in c.acts)
    assert any(a.how == "correction" for c in by_tag["correction"] for a in c.acts)
    assert any(a.how == "implied" for c in by_tag["implied_commitment"] for a in c.acts)
    # unobservable: the allusion comm names a fact that is never revealed
    for c in by_tag["unobservable"]:
        allusion = c.extra["allusion"]
        hidden = [e for e in sim.events if e["type"] == "fact.set" and e["subject"] == allusion["subject"]
                  and e["attribute"] == allusion["attribute"]]
        assert hidden and all(e["id"] in sim.unrevealed for e in hidden)
    # name collisions and aliases are expressed as name forms for the renderers
    plan = make_plan(4, weeks=2)
    people = {p["id"]: p for p in plan["people"]}
    for c in by_tag["name_collision"]:
        assert any(people[p]["first"] == f for p, f in c.extra["name_forms"].items())
    assert all(c.extra.get("name_forms") for c in by_tag["alias"])
    # scattered evidence spans several channels and days
    sc = by_tag["scattered_evidence"]
    assert len({c.channel for c in sc}) >= 2 and len({c.date for c in sc}) >= 3


# ---------------------------------------------------------------- calibration
@pytest.fixture(scope="module")
def calibration(sim_of):
    rows = []
    for seed in CALIBRATION_SEEDS:
        sim = sim_of(seed)
        world = sim.world()
        final = state_at(world, world.all_dates()[-1])
        stats = compute_stats(world, final, None)
        rows.append((sim, stats))
    return rows


def _mean(xs):
    return statistics.mean(xs)


def test_calibration_loops(calibration):
    loops = [s["loops"] for _, s in calibration]
    per_day = _mean(s["commitments"]["created_per_workday_mean"] for _, s in calibration)
    assert 5.0 <= per_day <= 9.0, per_day

    def share(section, key):
        return _mean(lp[section]["shares"].get(key, 0.0) for lp in loops)

    assert 0.35 <= share("owner", "worker") <= 0.58
    assert 0.35 <= share("owner", "others") <= 0.60
    assert 0.02 <= share("owner", "joint") <= 0.14
    assert 0.30 <= share("final_status", "done") <= 0.55
    assert 0.15 <= share("final_status", "waiting") <= 0.38
    assert 0.15 <= share("final_status", "open") <= 0.40
    assert share("final_status", "dropped") <= 0.12
    assert share("final_status", "blocked") <= 0.05
    assert 0.45 <= share("kind", "task") <= 0.65 and 0.3 <= share("kind", "ask") <= 0.5
    assert 0.01 <= share("kind", "decision") <= 0.10
    assert 0.30 <= share("basis", "reported") <= 0.60
    accepted = _mean(lp["accepted_share"] for lp in loops)
    assert 0.80 <= accepted <= 0.96, accepted
    due = _mean(lp["hard_due_share"] for lp in loops)
    assert 0.03 <= due <= 0.18, due
    assert _mean(lp["lifetime_business_days"]["median"] for lp in loops) <= 2.5
    assert 0.35 <= _mean(lp["top2_project_share"] for lp in loops) <= 0.7


def test_calibration_volume_and_channels(calibration):
    weekday: dict[int, list[int]] = defaultdict(list)
    email_noise, evidence = [], Counter()
    for sim, stats in calibration:
        for d, day in stats["artifacts"]["per_day"].items():
            weekday[parse_date(d).weekday()].append(day["total"])
        emails = [c for c in sim.comms if c.kind == "email"]
        email_noise.append(sum(c.noise for c in emails) / len(emails))
        for c in sim.comms:
            if not c.noise:
                evidence[c.channel] += len(c.artifacts)
    weekdays = [n for wd in range(5) for n in weekday[wd]]
    assert 15 <= _mean(weekdays) <= 20, _mean(weekdays)
    assert min(weekdays) >= 10 and max(weekdays) <= 30
    # Monday and Tuesday are the heaviest days; Saturday is about a third of a weekday.
    assert _mean(weekday[0] + weekday[1]) >= _mean(weekday[3] + weekday[4])
    if weekday[5]:
        assert 0.2 <= _mean(weekday[5]) / _mean(weekdays) <= 0.5
    assert not weekday[6]
    assert 0.4 <= _mean(email_noise) <= 0.65
    total = sum(evidence.values())
    mix = {k: v / total for k, v in evidence.items()}
    assert mix["chat"] > mix["email"] > mix["meeting"] > mix.get("document", 0)
    assert 0.32 <= mix["chat"] <= 0.55 and 0.2 <= mix["email"] <= 0.4 and 0.08 <= mix["meeting"] <= 0.25


def test_meeting_coverage_mix(calibration):
    cov = Counter(c.extra["coverage"] for sim, _ in calibration for c in sim.comms if c.kind == "meeting")
    n = sum(cov.values())
    with_transcript = (cov["transcript"] + cov["transcript+recap"]) / n
    assert 0.4 <= with_transcript <= 0.75
    assert 0.12 <= cov["recap"] / n <= 0.4
    assert 0.05 <= (cov["debrief"] + cov["voice_debrief"]) / n <= 0.3
    meetings_per_day = n / sum(1 for sim, s in calibration for d in s["artifacts"]["per_day"] if parse_date(d).weekday() < 5)
    assert 1.5 <= meetings_per_day <= 5


def test_cast_concentration(calibration):
    # One collaborator is on a large share of loops; most of the cast is on few.
    for sim, _ in calibration:
        loops = [e for e in sim.events if e["type"] == "commitment.create"]
        worker = sim.meta["worker"]
        on = Counter(p for e in loops for p in {e["debtor"], e["creditor"], *e["others"]} if p != worker)
        top = on.most_common(1)[0][1] / len(loops)
        assert 0.12 <= top <= 0.6, top


def test_saturday_and_seed_days_have_deliveries(sim_of):
    sim = sim_of(4, "standard", 2)
    plan = make_plan(4, weeks=2)
    dates = {c.date for c in sim.comms}
    for d in plan["calendar"]["seed"]["days"] + plan["calendar"]["episode"]["days"]:
        assert d in dates, d
    assert all(parse_date(d).weekday() < 6 for d in dates)
    assert add_days(plan["calendar"]["episode"]["days"][-1], 1) not in dates
