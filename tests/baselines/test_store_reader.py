import json

from wcb.baselines.store_reader import Reader
from wcb.store.parse import load_store


def _visible(mini_world_dir, cp):
    return json.loads((mini_world_dir / "gold" / "questions" / f"{cp}.json").read_text())


def test_reader_answers_oracle_store(mini_world_dir):
    store = load_store(mini_world_dir / "gold" / "oracle-store" / "2027-01-12")
    reader = Reader(store, "2027-01-12")
    gold = _visible(mini_world_dir, "cp2")
    answers = {q["id"]: reader.answer(q) for q in gold["questions"]}
    assert answers["q-009"]["date"] == "2027-01-12"
    assert answers["q-012"]["value"] == "Cora Velez"
    assert answers["q-013"]["value"] == "Solutions engineer"
    owed = answers["q-011"]["items"]
    assert [i["text"] for i in owed] == ["Send Ada the January reconciliation report"]
    focus = [i["text"] for i in answers["q-010"]["items"]]
    assert "Review Sam Patel's ingestion design doc" in focus


def test_reader_abstains_on_unknown_phrasing(mini_world_dir):
    store = load_store(mini_world_dir / "gold" / "oracle-store" / "2027-01-11")
    reader = Reader(store, "2027-01-11")
    assert reader.answer({"id": "x", "type": "point", "text": "Tell me something"}) == {
        "type": "point",
        "abstain": True,
    }
    assert (
        reader.answer({"id": "q-004", "type": "point", "text": "What is the budget for Quillon?"})[
            "abstain"
        ]
        is True
    )
