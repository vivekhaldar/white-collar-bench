"""Tests for `wcb world build` (wcb/world/build.py)."""

from __future__ import annotations

import json
from pathlib import Path

from wcb.util.io import read_json
from wcb.world.build import build_world, oracle_dates
from wcb.world.model import World
from wcb.world.state import state_at


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_build_writes_manifests_state_and_oracle_stores(world_copy):
    res = build_world(world_copy)
    assert res.ok, res.format()
    world = World.load(world_copy)
    # Manifests: one per delivery date, artifacts ordered by received_at then id.
    m = read_json(world_copy / "inbox/2027-01-11/manifest.json")
    assert m["date"] == "2027-01-11"
    assert [a["id"] for a in m["artifacts"]] == ["nt-0002", "em-0004", "ch-0002", "ca-0001"]
    assert m["artifacts"][1] == {
        "id": "em-0004",
        "channel": "email",
        "received_at": "2027-01-11T09:30:00-08:00",
        "path": "em-0004.eml",
        "title": "Re: volume pricing",
    }
    assert "inbox/2027-01-04/manifest.json" in res.written
    # Gold state for every date, identical to the engine's output.
    states = sorted(p.stem for p in (world_copy / "gold/state").glob("*.json"))
    assert states == world.all_dates()
    assert read_json(world_copy / "gold/state/2027-01-12.json") == json.loads(
        json.dumps(state_at(world, "2027-01-12"))
    )
    # Oracle stores for the end of the seed window and every episode day.
    stores = sorted(p.name for p in (world_copy / "gold/oracle-store").iterdir())
    assert stores == oracle_dates(world) == ["2027-01-08", "2027-01-11", "2027-01-12"]
    assert (world_copy / "gold/oracle-store/2027-01-12/people/me.md").is_file()
    assert not (world_copy / "gold/oracle-store/2027-01-12/CONTRACT.md").exists()
    # Calibration.
    cal = read_json(world_copy / "gold/calibration.json")
    assert cal["world"] == "mini" and cal["artifacts"]["total"] == 13
    assert "oracle store(s)" in res.format()


def test_build_is_deterministic(world_copy):
    assert build_world(world_copy).ok
    first = _snapshot(world_copy)
    assert build_world(world_copy).ok
    assert _snapshot(world_copy) == first


def test_build_removes_stale_derived_files(world_copy):
    stale_state = world_copy / "gold/state/2026-12-31.json"
    stale_store = world_copy / "gold/oracle-store/2026-12-31/people/me.md"
    stale_manifest = world_copy / "inbox/2027-01-09/manifest.json"
    for f in (stale_state, stale_store, stale_manifest):
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{}", encoding="utf-8")
    extra_record = world_copy / "gold/oracle-store/2027-01-12/people/ghost.md"
    extra_record.parent.mkdir(parents=True, exist_ok=True)
    extra_record.write_text("stale", encoding="utf-8")
    assert build_world(world_copy).ok
    assert not stale_state.exists() and not stale_store.parent.parent.exists()
    assert not stale_manifest.exists() and not extra_record.exists()


def test_build_aborts_on_check_errors(world_copy):
    (world_copy / "inbox/2027-01-11/stray.txt").write_text("x", encoding="utf-8")
    res = build_world(world_copy)
    assert not res.ok and res.written == []
    assert not (world_copy / "gold").exists()
    assert "build aborted" in res.format() and "inbox.undeclared" in res.format()


def test_build_without_question_module_warns(world_copy):
    res = build_world(world_copy)
    try:
        import wcb.questions.build  # noqa: F401
    except ImportError:
        assert any(i.code == "questions.skipped" for i in res.issues)
    else:
        assert (world_copy / "gold/questions/cp1.json").is_file()
        assert (world_copy / "gold/questions/cp2.json").is_file()
