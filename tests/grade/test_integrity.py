"""Store integrity (SIS): the oracle store is perfect and each corruption lowers its metric."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from wcb.grade.integrity import (
    METRICS,
    alias_key,
    build_alias_index,
    map_record,
    store_integrity,
    superseded_loop_values,
)
from wcb.grade.judge import HeuristicJudge
from wcb.paths import contract_dir
from wcb.store.oracle import render_oracle_store
from wcb.store.parse import parse_record
from wcb.world.model import World
from wcb.world.state import state_at

J = HeuristicJudge()
LAST_DAY = "2027-01-12"
PRICING = "loops/send-ada-tessellate-volume-pricing.md"


@pytest.fixture(scope="module")
def world() -> World:
    return World.load(Path(__file__).parents[1] / "fixtures" / "mini-world")


@pytest.fixture(scope="module")
def last_state(world: World) -> dict:
    return state_at(world, LAST_DAY)


def oracle_copy(world: World, state: dict, dest: Path) -> Path:
    """Render the oracle store for `state` into `dest`, with CONTRACT.md as the runner adds it."""
    render_oracle_store(world, state, dest)
    shutil.copyfile(contract_dir() / "CONTRACT.md", dest / "CONTRACT.md")
    return dest


@pytest.fixture
def store(world: World, last_state: dict, tmp_path: Path) -> Path:
    return oracle_copy(world, last_state, tmp_path / "store")


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {path}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def replace_everywhere(root: Path, old: str, new: str) -> None:
    for f in root.rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        if old in text:
            f.write_text(text.replace(old, new), encoding="utf-8")


def unchanged(result: dict, *metrics: str) -> None:
    for m in metrics:
        assert result[m] == 1.0, (m, result["details"])


# ---------------------------------------------------------------- the oracle store is perfect
def test_oracle_store_last_day_is_perfect(world, last_state, store):
    r = store_integrity(store, last_state, world, J)
    for m in METRICS:
        assert r[m] >= 0.95, (m, r["details"])
    assert r["sis"] == pytest.approx(100.0 * sum(r[m] for m in METRICS) / 6)
    assert r["sis"] >= 95
    d = r["details"]
    assert d["entities"]["records"]["people/me"] == {"status": "mapped", "entity": "p-ada-quist"}
    assert d["loops"]["matches"][PRICING[:-3]] == "c-004"
    assert d["date"] == LAST_DAY


@pytest.mark.parametrize("date", ["2027-01-08", "2027-01-11"])
def test_oracle_store_earlier_days_are_perfect(world, tmp_path, date):
    state = state_at(world, date)
    r = store_integrity(oracle_copy(world, state, tmp_path / date), state, world, J)
    assert all(r[m] >= 0.95 for m in METRICS), r["details"]


def test_built_fixture_oracle_store_if_present(world, last_state, mini_world_dir):
    built = mini_world_dir / "gold" / "oracle-store" / LAST_DAY
    if not built.is_dir():
        pytest.skip("the mini world's gold/ has not been built")
    r = store_integrity(built, last_state, world, J)
    assert all(r[m] >= 0.95 for m in METRICS), r["details"]


# ---------------------------------------------------------------- corruptions
def test_duplicate_person_lowers_entity_f1_only(world, last_state, store):
    text = (store / "people/cora-velez.md").read_text(encoding="utf-8")
    (store / "people/cora.md").write_text(
        text.replace("id: people/cora-velez", "id: people/cora"), encoding="utf-8"
    )
    r = store_integrity(store, last_state, world, J)
    ents = r["details"]["entities"]
    assert r["entity_f1"] < 1.0
    assert ents["recall"] == 1.0 and ents["fp"] == 1
    statuses = {ents["records"][r]["status"] for r in ("people/cora", "people/cora-velez")}
    assert statuses == {"mapped", "duplicate"}
    assert len(ents["false_positives"]) == 1
    unchanged(r, "loop_f1", "field_accuracy", "freshness", "groundedness", "validity")


def test_wrongly_merged_sam_record(world, last_state, store):
    """Both Sams folded into one 'Sam' record: one entity is found, the other absorbed."""
    patel = (store / "people/sam-patel.md").read_text(encoding="utf-8")
    merged = re.sub(r"(?s)^---\n.*?\n---\n", "", patel, count=1)
    (store / "people/sam.md").write_text(
        "---\nid: people/sam\ntype: person\nname: Sam\n"
        "aliases: [Sam, Samir, sam.patel@larchmont.example, sam.reyes@tessellate.example]\n"
        "updated: 2027-01-12\n---\n" + merged,
        encoding="utf-8",
    )
    (store / "people/sam-patel.md").unlink()
    (store / "people/sam-reyes.md").unlink()
    replace_everywhere(store, "people/sam-patel", "people/sam")
    replace_everywhere(store, "people/sam-reyes", "people/sam")
    r = store_integrity(store, last_state, world, J)
    ents = r["details"]["entities"]
    assert ents["wrong_merges"] == [
        {"record": "people/sam", "entity": "p-sam-patel", "absorbed": ["p-sam-reyes"]}
    ]
    assert ents["missing"] == ["p-sam-reyes"]
    assert ents["precision"] == 1.0 and ents["recall"] < 1.0
    assert r["entity_f1"] < 1.0
    # c-003's counterparty link now points at the merged record, which maps to Sam Patel.
    unchanged(r, "loop_f1", "field_accuracy", "freshness", "groundedness")


def test_stale_owner_after_transfer(world, last_state, store):
    """c-004 was handed from Sam Reyes to Cora; a store still naming Sam Reyes is stale."""
    edit(store / PRICING, "owner: people/cora-velez", "owner: people/sam-reyes")
    r = store_integrity(store, last_state, world, J)
    assert r["freshness"] < 1.0
    assert r["details"]["freshness"]["stale"] == [
        {"record": PRICING[:-3], "gold": "c-004", "fields": ["owner"]}
    ]
    assert r["field_accuracy"] < 1.0
    assert r["details"]["fields"]["per_loop"][PRICING[:-3]]["owner"] == 0.0
    unchanged(r, "entity_f1", "loop_f1", "groundedness", "validity")


def test_dropped_loop_lowers_loop_f1(world, last_state, store):
    (store / "loops/review-sam-patel-s-ingestion-design-doc.md").unlink()
    r = store_integrity(store, last_state, world, J)
    loops = r["details"]["loops"]
    assert loops["missing"] == ["c-003"]
    assert loops["precision"] == 1.0 and loops["recall"] < 1.0
    assert r["loop_f1"] < 1.0
    unchanged(r, "entity_f1", "field_accuracy", "freshness", "groundedness", "validity")


def test_leaked_passcode_lowers_validity(world, last_state, store):
    notes = store / "notes" / "meetings.md"
    notes.parent.mkdir()
    notes.write_text("Reconciliation review: dial in with code 514227\n", encoding="utf-8")
    r = store_integrity(store, last_state, world, J)
    assert r["validity"] < 1.0
    assert r["details"]["validity"]["by_code"].get("privacy.secret", 0) >= 1
    unchanged(r, "entity_f1", "loop_f1", "field_accuracy", "freshness", "groundedness")


def test_stale_project_target_date(world, last_state, store):
    edit(store / "projects/quillon.md", "target_date: '2027-02-05'", "target_date: '2027-01-29'")
    r = store_integrity(store, last_state, world, J)
    assert {"record": "projects/quillon", "gold": "pr-quillon", "fields": ["target_date"]} in r[
        "details"
    ]["freshness"]["stale"]
    assert r["freshness"] < 1.0


def test_reversed_decision_still_done_is_stale(world, last_state, store):
    rec = store / "loops/limit-the-quillon-pilot-to-the-reno-depot.md"
    edit(rec, "status: reversed", "status: done")
    r = store_integrity(store, last_state, world, J)
    assert r["freshness"] < 1.0 and r["field_accuracy"] < 1.0
    per = r["details"]["fields"]["per_loop"]["loops/limit-the-quillon-pilot-to-the-reno-depot"]
    assert per == {"gold": "d-001", "credit": 0.0, "status": 0.0}


def test_reopened_status_is_stale_and_wrong(world, last_state, store):
    """c-005 is done; a record still 'open' shows the superseded status."""
    edit(store / "loops/approve-ben-s-gl-sandbox-access-request.md", "status: done", "status: open")
    r = store_integrity(store, last_state, world, J)
    stale = r["details"]["freshness"]["stale"]
    assert {
        "record": "loops/approve-ben-s-gl-sandbox-access-request",
        "gold": "c-005",
        "fields": ["status"],
    } in stale
    assert (
        r["details"]["fields"]["per_loop"]["loops/approve-ben-s-gl-sandbox-access-request"][
            "status"
        ]
        == 0.0
    )


def test_undelivered_evidence_is_ungrounded(world, last_state, store):
    rec = store / "loops/send-ada-the-january-reconciliation-report.md"
    edit(rec, "source: ch-0001", "source: ch-0099")
    r = store_integrity(store, last_state, world, J)
    assert r["details"]["groundedness"]["ungrounded"] == [
        "loops/send-ada-the-january-reconciliation-report"
    ]
    assert r["groundedness"] == pytest.approx(1 - 1 / 7)


def test_spurious_person_is_false_positive(world, last_state, store):
    (store / "people/zed-quill.md").write_text(
        "---\nid: people/zed-quill\ntype: person\nname: Zed Quill\naliases: []\nupdated: 2027-01-12\n---\n",
        encoding="utf-8",
    )
    r = store_integrity(store, last_state, world, J)
    assert r["details"]["entities"]["records"]["people/zed-quill"]["status"] == "unmatched"
    assert r["entity_f1"] < 1.0


def test_minor_person_record_is_ignored(world, last_state, store):
    """Nina Hart is a minor entity (a newsletter author): neither required nor penalized."""
    (store / "people/nina-hart.md").write_text(
        "---\nid: people/nina-hart\ntype: person\nname: Nina Hart\n"
        "aliases: [nina@freightwire.example]\nupdated: 2027-01-12\n---\n",
        encoding="utf-8",
    )
    r = store_integrity(store, last_state, world, J)
    assert r["details"]["entities"]["records"]["people/nina-hart"]["status"] == "minor"
    assert r["entity_f1"] == 1.0


def test_empty_store_scores_low_but_defined(world, last_state, tmp_path):
    (tmp_path / "empty").mkdir()
    r = store_integrity(tmp_path / "empty", last_state, world, J)
    assert r["entity_f1"] == 0.0 and r["loop_f1"] == 0.0 and r["field_accuracy"] == 0.0
    assert r["freshness"] == 1.0 and r["groundedness"] == 1.0  # nothing to check
    assert r["validity"] == 0.0  # people/me.md is missing
    assert r["sis"] == pytest.approx(100 * 2 / 6)


def test_missing_store_raises(world, last_state, tmp_path):
    with pytest.raises(FileNotFoundError):
        store_integrity(tmp_path / "nope", last_state, world, J)


# ---------------------------------------------------------------- mapping rules
def person(text_meta: str, rid: str = "people/x"):
    return parse_record(f"---\nid: {rid}\ntype: person\n{text_meta}\n---\n", f"{rid}.md")


def test_alias_key_normalizes_forms():
    assert alias_key("Dana  Teague") == alias_key("@marisol-teague") == "dana teague"
    assert alias_key("Ada.Quist@Larchmont.example") == "ada quist larchmont example"


def test_shared_first_name_is_unresolved(world, last_state):
    index = build_alias_index(last_state)["person"]
    m = map_record(person("name: Sam\naliases: [Sam]"), "person", index, last_state)
    assert m.status == "unresolved" and m.entity is None


def test_first_name_resolves_before_the_second_sam_is_knowable(world):
    """On 6 January only Sam Patel is knowable, so 'Sam' identifies him."""
    state = state_at(world, "2027-01-06")
    index = build_alias_index(state)["person"]
    m = map_record(person("name: Sam\naliases: []"), "person", index, state)
    assert (m.status, m.entity) == ("mapped", "p-sam-patel")


def test_record_maps_by_alias_and_email(world, last_state):
    index = build_alias_index(last_state)["person"]
    m = map_record(
        person("name: Samir\naliases: [Sam]\nemail: sam.patel@larchmont.example"),
        "person",
        index,
        last_state,
    )
    assert (m.status, m.entity) == ("mapped", "p-sam-patel")


def test_kind_restricts_mapping(world, last_state):
    """A person record named like a project does not map to the project."""
    index = build_alias_index(last_state)["person"]
    m = map_record(person("name: Quillon\naliases: []"), "person", index, last_state)
    assert m.status == "unmatched"


def test_superseded_loop_values(last_state):
    old = superseded_loop_values(last_state["loops"]["c-004"])
    assert old["debtor"] == {"p-sam-reyes"}
    assert old["status"] == set() and old["due"] == set()
    # c-003 gained a due date; having none before is an omission, not a stale value.
    assert superseded_loop_values(last_state["loops"]["c-003"])["due"] == set()
