"""Planner, names and archetype library (docs/generator.md "Planner", "Archetypes")."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import pytest
import yaml

from wcb.util.dates import parse_date
from wcb.util.io import dump_yaml
from wcb.world import archetypes as A
from wcb.world import names as N
from wcb.world.planner import CHALLENGE_TAGS, SETTINGS, SIZES, make_plan

PILOT = Path(__file__).resolve().parents[2] / "worlds" / "pilot" / "world.jsonl"


# ---------------------------------------------------------------- determinism and calendar
def test_plan_is_deterministic():
    a = make_plan(11, weeks=2, size="standard")
    b = make_plan(11, weeks=2, size="standard")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert json.dumps(make_plan(12), sort_keys=True) != json.dumps(make_plan(11), sort_keys=True)


def test_plan_round_trips_through_yaml():
    plan = make_plan(5, weeks=2)
    assert yaml.safe_load(dump_yaml(plan)) == json.loads(json.dumps(plan))


def test_start_must_be_a_monday():
    with pytest.raises(ValueError):
        make_plan(1, start="2027-04-06")
    with pytest.raises(ValueError):
        make_plan(1, size="huge")


@pytest.mark.parametrize("weeks", [1, 2, 3])
def test_calendar_shape(weeks):
    plan = make_plan(7, weeks=weeks, start="2027-04-05")
    cal = plan["calendar"]
    assert cal["seed"]["start"] == "2027-03-22"  # two weeks before the episode, a Monday
    seed_days = cal["seed"]["days"]
    assert [d for d in seed_days if parse_date(d).weekday() < 5] == [
        "2027-03-22", "2027-03-23", "2027-03-24", "2027-03-25", "2027-03-26",
        "2027-03-29", "2027-03-30", "2027-03-31", "2027-04-01", "2027-04-02",
    ]
    assert all(parse_date(d).weekday() <= 5 for d in seed_days)
    assert cal["seed"]["end"] == seed_days[-1] < cal["episode"]["days"][0] == "2027-04-05"
    assert len(cal["episode"]["weeks"]) == weeks
    for days in cal["episode"]["weeks"]:
        assert [parse_date(d).weekday() for d in days][:5] == [0, 1, 2, 3, 4]
        assert len(days) in (5, 6)  # optional light Saturday
    cps = cal["checkpoints"]
    assert len(cps) == 3 * weeks
    for w, days in enumerate(cal["episode"]["weeks"]):
        assert [c["date"] for c in cps[3 * w: 3 * w + 3]] == [days[1], days[3], days[-1]]


# ---------------------------------------------------------------- sizes, settings and cast
@pytest.mark.parametrize("size", ["small", "standard", "large"])
def test_plan_sizes(size):
    lo, hi = SIZES[size]["projects"]
    for seed in range(6):
        plan = make_plan(seed, size=size)
        projects = plan["projects"]
        assert lo <= len(projects) <= hi, (seed, len(projects))
        sizes = Counter(p["size"] for p in projects)
        assert sizes["flagship"] == 1 and sizes["hub"] == 1
        assert sizes["placeholder"] >= 1 and sizes["dormant"] >= 1
        units = [o for o in plan["orgs"] if o["role"] == "unit"]
        vendors = [o for o in plan["orgs"] if o["role"] == "vendor"]
        assert 3 <= len(units) <= 5 and 2 <= len(vendors) <= 3
        assert any(o["role"] == "partner" for o in plan["orgs"])
        core = [p for p in plan["people"] if p["tier"] == "core"]
        minor = [p for p in plan["people"] if p["tier"] == "minor"]
        assert len(minor) >= 5
        if size == "standard":
            assert 35 <= len(plan["people"]) <= 55
            assert 10 <= len(projects) <= 14
        assert len(core) >= 25
        ids = [p["id"] for p in projects] + [p["id"] for p in plan["people"]] + [o["id"] for o in plan["orgs"]]
        assert len(ids) == len(set(ids))
        # Heavy tail: the flagship carries the largest weight, then the hub.
        weights = sorted(projects, key=lambda p: -p["weight"])
        assert weights[0]["size"] == "flagship" and weights[1]["size"] == "hub"


@pytest.mark.parametrize("setting", sorted(SETTINGS))
def test_every_setting_plans(setting):
    plan = make_plan(3, setting=setting)
    assert plan["setting"]["key"] == setting
    tz = plan["setting"]["timezone"]
    assert len(tz) == 6 and tz[0] in "+-" and tz[3] == ":"
    assert {o["role"] for o in plan["orgs"]} >= {"umbrella", "central", "unit", "vendor", "partner"}
    for o in plan["orgs"]:
        assert o["domain"].endswith(".example")
    for p in plan["people"]:
        assert p["email"].endswith(".example")


def test_at_least_four_settings_and_twelve_archetypes():
    assert len(SETTINGS) >= 4
    assert len(A.ARCHETYPES) >= 12
    assert A.check_library() == []


def test_worker_is_senior_ic_without_reports():
    for seed in range(5):
        plan = make_plan(seed)
        people = {p["id"]: p for p in plan["people"]}
        worker = people[plan["worker"]]
        central = next(o for o in plan["orgs"] if o["role"] == "central")
        assert worker["org"] == central["id"]
        assert not any(p.get("relationship") == "report" for p in plan["people"])
        assert sum(1 for p in plan["people"] if p.get("relationship") == "manager") == 1


def test_surface_forms_and_handles():
    plan = make_plan(4)
    for p in plan["people"]:
        if p["tier"] != "core" or p["group"] == "mailbox":
            continue
        forms = p["surface_forms"]
        assert 3 <= len(forms) <= 6, (p["id"], forms)
        assert p["name"] not in forms
        assert p["first"] in forms and p["email"] in forms and p["handle"] in forms
        if p["nickname"]:
            assert p["nickname"] in forms
    handles = [p["handle"] for p in plan["people"] if p.get("handle")]
    assert len(handles) == len(set(handles))
    assert any(p["nickname"] for p in plan["people"])


def test_deliberate_name_collisions_and_homophones():
    for seed in range(8):
        plan = make_plan(seed)
        people = {p["id"]: p for p in plan["people"]}
        groups = plan["collisions"]["first_names"]
        assert len(groups) >= 2
        for group in groups:
            assert len(group) >= 2
            firsts = {people[p]["first"] for p in group}
            assert len(firsts) == 1
            assert len({people[p]["org"] for p in group}) == len(group)  # different organizations
        a, b = (people[p] for p in plan["collisions"]["homophones"])
        assert a["first"] != b["first"] and a["org"] != b["org"]
        assert (a["first"], b["first"]) in N.HOMOPHONE_PAIRS or (b["first"], a["first"]) in N.HOMOPHONE_PAIRS
        firsts = Counter(p["first"] for p in plan["people"] if p["tier"] == "core" and p["group"] != "mailbox")
        assert sum(1 for n in firsts.values() if n > 1) >= 2


# ---------------------------------------------------------------- names and denylists
def test_name_pools_are_large_and_clean():
    assert len(N.FIRST_NAMES) >= 250
    assert len(N.SURNAMES) >= 250
    for name in N.FIRST_NAMES + N.SURNAMES:
        assert not N.is_denied(name), name
    assert all(n in N.FIRST_NAMES for n in N.NICKNAMES)


def test_denylist_is_case_insensitive_and_substring():
    for bad in ("Teague", "THISTLEDOWN Labs", "the quillon project", "Selvafield", "Orrisfield", "quorne",
                "Brenwick", "Wexmoor"):
        assert N.is_denied(bad), bad
    assert N.is_denied("Mara Ilves")  # pilot cast, as a whole token
    assert not N.is_denied("Selvora Labs")


def test_coined_names_are_fresh_and_clean():
    gen = N.NameGen(random.Random(3))
    words = [gen.coin(2) for _ in range(60)] + [gen.place() for _ in range(40)] + [gen.code_word() for _ in range(30)]
    assert len({w.lower() for w in words}) == len(words)
    for w in words:
        assert not N.is_denied(w) and w[:1].isupper()


def _pilot_tokens() -> set[str]:
    if not PILOT.exists():
        return set()
    toks: set[str] = set()
    for line in PILOT.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("type") == "entity.create" and e.get("kind") in ("person", "org", "project"):
            for t in N._fold(e["name"]).split():
                if len(t) > 3 and t.replace("-", "").isalpha():
                    toks.add(t)
    generic = {"university", "office", "digital", "strategy", "system", "learning", "research", "institute",
               "service", "status", "notifications", "mailbox", "team", "selection", "model", "discovery",
               "hire", "tool", "feedback", "writing", "teaching", "faculty", "workshop", "library",
               "assistant", "community", "practice", "advising", "scheduling", "transfer", "evaluation",
               "engineer", "staff", "helper", "citation", "placeholder", "valley", "desk", "services", "with"}
    return toks - generic


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_plans_avoid_denylist_and_pilot_names(seed):
    plan = make_plan(seed, weeks=2)
    blob = json.dumps(plan).lower()
    for bad in N.HARD_DENYLIST:
        assert bad not in blob, bad
    pilot = _pilot_tokens()
    for x in plan["people"] + plan["orgs"] + plan["projects"]:
        for tok in N._fold(x["name"]).split():
            assert tok not in pilot, (x["name"], tok)


# ---------------------------------------------------------------- portfolio and challenges
def test_projects_are_well_formed():
    plan = make_plan(9, weeks=2)
    people = {p["id"] for p in plan["people"]}
    orgs = {o["id"] for o in plan["orgs"]}
    for p in plan["projects"]:
        assert p["archetype"] in A.ARCHETYPES
        assert p["phase"] in {ph.name for ph in A.get(p["archetype"]).phases}
        assert p["owner"] in people and p["sponsor"] in people
        assert set(p["members"]) <= people and 2 <= len(p["members"]) <= 15
        assert set(p["orgs"]) <= orgs
        assert p["kw"] and p["kw"] in p["short"].lower()
        for role, val in p["cast"].items():
            for v in val if isinstance(val, list) else [val]:
                assert v in people, (p["id"], role, v)
    assert plan["worker"] in plan["projects"][0]["members"]


@pytest.mark.parametrize("weeks", [1, 2, 4])
def test_every_challenge_tag_is_scheduled_every_week(weeks):
    for seed in range(4):
        plan = make_plan(seed, weeks=weeks)
        cal = plan["calendar"]
        delivery = set(cal["seed"]["days"]) | set(cal["episode"]["days"])
        for w, days in enumerate(cal["episode"]["weeks"], 1):
            entries = [c for c in plan["challenges"] if c["week"] == w]
            assert {c["tag"] for c in entries} == set(CHALLENGE_TAGS)
            for c in entries:
                assert c["day"] in days, c
                if c.get("setup"):
                    assert c["setup"] in delivery and c["setup"] <= c["day"], c
                for s in c.get("steps") or []:
                    assert s in days
        newcomers = [p for p in plan["people"] if p["group"] == "newcomer"]
        assert len(newcomers) == weeks
        assert all(p["appears"] in cal["episode"]["days"] for p in newcomers)
