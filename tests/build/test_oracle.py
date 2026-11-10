"""Tests for the oracle-store renderer (wcb/store/oracle.py)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from wcb.paths import contract_dir
from wcb.store.oracle import oracle_records, record_ids, render_oracle_store
from wcb.util import frontmatter
from wcb.util.io import read_json
from wcb.world.model import World
from wcb.world.state import state_at

LINK_FIELDS = ("org", "owner", "counterparty", "project", "parent", "merged_into")
LIST_LINK_FIELDS = ("people", "orgs", "others", "split_into")


@pytest.fixture
def world(mini_world_dir) -> World:
    return World.load(mini_world_dir)


def _store(world: World, date: str, tmp_path: Path) -> Path:
    out = tmp_path / date
    render_oracle_store(world, state_at(world, date), out)
    return out


def _records(store: Path) -> dict[str, tuple[dict, str]]:
    out = {}
    for f in sorted(store.rglob("*.md")):
        meta, body = frontmatter.parse(f.read_text(encoding="utf-8"))
        out[f.relative_to(store).with_suffix("").as_posix()] = (meta, body)
    return out


# ---------------------------------------------------------------- record IDs
def test_record_ids_are_stable_slugs(world):
    ids = record_ids(world)
    assert ids["p-ada-quist"] == "people/me"
    assert ids["p-sam-patel"] == "people/sam-patel" and ids["p-sam-reyes"] == "people/sam-reyes"
    assert ids["o-tessellate"] == "orgs/tessellate-analytics"
    assert ids["pr-quillon"] == "projects/quillon"
    # Loops are named after the create event's `what`, even after a transfer.
    assert ids["c-004"] == "loops/send-ada-tessellate-volume-pricing"
    assert ids["d-001"] == "loops/limit-the-quillon-pilot-to-the-reno-depot"
    assert len(set(ids.values())) == len(ids)


def test_record_id_collisions_get_numbered_suffixes(world):
    events = [dict(e) for e in world.events]
    clone = next(
        e for e in events if e.get("commitment") == "c-001" and e["type"] == "commitment.create"
    )
    events.append(
        {**clone, "id": "e-0999", "commitment": "c-099", "t": "2027-01-12T17:00:00-08:00"}
    )
    events.append(
        {**clone, "id": "e-1000", "commitment": "c-100", "t": "2027-01-12T18:00:00-08:00"}
    )
    w2 = World(
        dir=world.dir, meta=world.meta, events=events, artifacts=world.artifacts, by_id=world.by_id
    )
    ids = record_ids(w2)
    base = "loops/return-the-tessellate-security-questionnaire"
    assert (ids["c-001"], ids["c-099"], ids["c-100"]) == (base, base + "-2", base + "-3")


# ---------------------------------------------------------------- content on the last day
def test_last_day_store_records(world, tmp_path):
    recs = _records(_store(world, "2027-01-12", tmp_path))
    ids = record_ids(world)
    loop = lambda cid: recs[ids[cid]][0]  # noqa: E731
    # Transfer: Cora now owes the volume pricing.
    assert loop("c-004")["owner"] == "people/cora-velez"
    assert loop("c-004")["counterparty"] == "people/me"
    assert [e["source"] for e in loop("c-004")["evidence"]] == ["mt-0001", "em-0004"]
    assert loop("c-004")["evidence"][0]["basis"] == "reported"
    # Weak evidence: the resolution of c-002 is never revealed, so it stays open.
    assert loop("c-002")["status"] == "open"
    assert loop("c-001")["status"] == "done"
    # Endorsement: c-003 accepted with a due date after the worker's note.
    assert loop("c-003")["accepted"] is True and loop("c-003")["due"] == "2027-01-13"
    # Decisions: d-001 reversed, d-002 made.
    d1, d2 = loop("d-001"), loop("d-002")
    assert (
        d1["kind"] == "decision"
        and d1["status"] == "reversed"
        and d1["reversed_on"] == "2027-01-12"
    )
    assert d1["counterparty"] is None and d1["owner"] == "people/me"
    assert (
        d2["status"] == "done"
        and d2["decided_on"] == "2027-01-12"
        and d2["outcome"].startswith("Run the Quillon pilot")
    )
    assert d2["others"] == ["people/ben-okoro"]
    # Project: superseded target date replaced; budget never revealed.
    quillon_meta, quillon_body = recs["projects/quillon"]
    assert quillon_meta["target_date"] == "2027-02-05"
    assert "people/ben-okoro" in quillon_meta["people"]
    assert re.search(r"## Current state\n\nAs of 2027-01-12: Pilot scope widened", quillon_body)
    assert "Phase: pilot planning." in quillon_body


def test_minor_people_and_hidden_attrs_are_not_rendered(world, tmp_path):
    store = _store(world, "2027-01-12", tmp_path)
    recs = _records(store)
    assert "people/nina-hart" not in recs
    all_text = "\n".join(p.read_text(encoding="utf-8") for p in store.rglob("*.md"))
    assert (
        "Nina" not in all_text
        and "_archetype" not in all_text
        and "competitive_vendor" not in all_text
    )
    assert "180000" not in all_text  # unobservable budget
    assert "- em-0003 (email): FreightWire weekly: no change" in recs["logs/2027-01-08"][1]


def test_ambiguous_first_name_is_not_an_alias(world, tmp_path):
    recs = _records(_store(world, "2027-01-12", tmp_path))
    assert "Sam" not in recs["people/sam-patel"][0]["aliases"]
    assert "Samir" in recs["people/sam-patel"][0]["aliases"]
    assert "Sam" not in recs["people/sam-reyes"][0]["aliases"]


def test_seed_store_reflects_seed_state(world, tmp_path):
    recs = _records(_store(world, "2027-01-08", tmp_path))
    ids = record_ids(world)
    assert recs[ids["c-003"]][0]["accepted"] is False
    assert recs[ids["c-004"]][0]["owner"] == "people/sam-reyes"
    assert recs[ids["d-001"]][0]["status"] == "done"
    assert recs["projects/quillon"][0]["target_date"] == "2027-01-29"
    assert sorted(r for r in recs if r.startswith("logs/")) == [
        f"logs/2027-01-0{d}" for d in range(4, 9)
    ]


def test_daily_logs_have_one_bullet_per_artifact(world, tmp_path):
    recs = _records(_store(world, "2027-01-12", tmp_path))
    meta, body = recs["logs/2027-01-11"]
    assert meta == {"id": "logs/2027-01-11", "type": "log", "date": "2027-01-11"}
    bullets = [line for line in body.splitlines() if line.startswith("- ")]
    assert [b.split()[1] for b in bullets] == ["nt-0002", "em-0004", "ch-0002", "ca-0001"]
    assert bullets[-1] == "- ca-0001 (calendar): Invite: Reconciliation review: no change"
    assert "[[loops/send-ada-tessellate-volume-pricing]]" in bullets[1]


def test_logs_are_identical_across_dates(world, tmp_path):
    early = _records(_store(world, "2027-01-11", tmp_path))
    late = _records(_store(world, "2027-01-12", tmp_path))
    for rid in early:
        if rid.startswith("logs/"):
            assert early[rid] == late[rid]


def test_unknowable_person_gets_a_stub(world):
    state = state_at(world, "2027-01-12")
    del state["entities"]["p-cora-velez"]
    records = oracle_records(world, state)
    meta, body = frontmatter.parse(records["people/cora-velez"])
    assert meta["name"] == "Cora Velez" and meta["aliases"] == []
    assert "no details are known yet" in body


def test_secrets_never_reach_the_store(world, tmp_path):
    store = _store(world, "2027-01-12", tmp_path)
    text = "\n".join(p.read_text(encoding="utf-8") for p in store.rglob("*.md"))
    for secret in state_at(world, "2027-01-12")["secrets"]:
        assert secret not in text


# ---------------------------------------------------------------- contract validity
@pytest.mark.parametrize("date", ["2027-01-08", "2027-01-11", "2027-01-12"])
def test_store_matches_contract_schemas(world, tmp_path, date):
    jsonschema = pytest.importorskip("jsonschema")
    schemas = {
        t: jsonschema.Draft202012Validator(
            read_json(contract_dir() / "schemas" / f"{t}.schema.json")
        )
        for t in ("person", "org", "project", "loop", "log")
    }
    recs = _records(_store(world, date, tmp_path))
    assert "people/me" in recs
    for rid, (meta, body) in recs.items():
        assert meta["id"] == rid
        errors = [e.message for e in schemas[meta["type"]].iter_errors(meta)]
        assert errors == [], (rid, errors)
        for f in LINK_FIELDS:
            if meta.get(f):
                assert meta[f] in recs, (rid, f, meta[f])
        for f in LIST_LINK_FIELDS:
            for target in meta.get(f) or []:
                assert target in recs, (rid, f, target)
        for target in re.findall(r"\[\[([^\]]+)\]\]", body):
            assert target in recs, (rid, target)
        if meta["type"] == "project":
            current = body.split("## Current state\n\n", 1)[1].split("\n\n## ", 1)[0]
            assert current.startswith("As of ") and "\n" not in current.strip()


@pytest.mark.parametrize("date", ["2027-01-08", "2027-01-12"])
def test_store_passes_contract_validator(world, tmp_path, date):
    validate = pytest.importorskip("wcb.contract.validate")
    state = state_at(world, date)
    store = _store(world, date, tmp_path)
    issues = validate.validate_store(
        store, secrets=state["secrets"], delivered=set(state["delivered"])
    )
    assert [i.format() for i in issues if i.code != "contract.missing"] == []
