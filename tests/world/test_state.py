from wcb.world.model import World
from wcb.world.state import state_at


def test_load_and_dates(mini_world_dir):
    w = World.load(mini_world_dir)
    assert w.id == "mini"
    assert w.worker == "p-ada-quist"
    assert w.episode_days() == ["2027-01-11", "2027-01-12"]
    assert w.seed_dates()[0] == "2027-01-04"
    assert len(w.artifacts) == 13
    assert "p-sam-reyes" in w.alias_table()["sam"] and "p-sam-patel" in w.alias_table()["sam"]


def test_knowability_and_supersession(mini_world_dir):
    w = World.load(mini_world_dir)
    seed = state_at(w, "2027-01-08")
    mon = state_at(w, "2027-01-11")
    tue = state_at(w, "2027-01-12")
    quillon = lambda s: s["entities"]["pr-quillon"]["attrs"]  # noqa: E731
    assert quillon(seed)["target_date"] == "2027-01-29"
    assert quillon(mon)["target_date"] == "2027-02-05"
    # Unobservable fact never becomes knowable.
    assert "budget" not in quillon(tue)
    assert "e-0016" in tue["unknowable"]


def test_endorsement_transfer_and_closure(mini_world_dir):
    w = World.load(mini_world_dir)
    seed, mon, tue = (state_at(w, d) for d in ("2027-01-08", "2027-01-11", "2027-01-12"))
    assert seed["loops"]["c-003"]["accepted"] is False
    assert mon["loops"]["c-003"]["accepted"] is True and mon["loops"]["c-003"]["due"] == "2027-01-13"
    assert seed["loops"]["c-004"]["debtor"] == "p-sam-reyes"
    assert mon["loops"]["c-004"]["debtor"] == "p-cora-velez"
    assert mon["loops"]["c-005"]["status"] == "done"  # silent closure via chat
    assert tue["loops"]["c-001"]["status"] == "done"
    # Resolution that no artifact reveals stays open in gold (weak evidence).
    assert tue["loops"]["c-002"]["status"] == "open"
    assert "e-0033" in tue["unknowable"]


def test_decision_reversal(mini_world_dir):
    w = World.load(mini_world_dir)
    tue = state_at(w, "2027-01-12")
    assert tue["decisions"]["d-001"]["status"] == "reversed"
    assert tue["decisions"]["d-001"]["reversed_on"] == "2027-01-12"
    assert tue["decisions"]["d-002"]["made_on"] == "2027-01-12"


def test_evidence_and_secrets(mini_world_dir):
    w = World.load(mini_world_dir)
    mon = state_at(w, "2027-01-11")
    assert mon["loops"]["c-004"]["evidence"] == ["mt-0001", "em-0004"]
    assert "514227" in mon["secrets"]
    assert "em-0005" not in mon["delivered"]


def test_transfer_touches_both_debtors(mini_world_dir):
    # e-0022 hands c-004 from Sam Reyes to Cora: both people are subjects of the hand-off.
    w = World.load(mini_world_dir)
    ev = next(e for e in state_at(w, "2027-01-11")["events"] if e["id"] == "e-0022")
    assert ev["subjects"] == ["c-004", "p-cora-velez", "p-ada-quist", "p-sam-reyes"]
