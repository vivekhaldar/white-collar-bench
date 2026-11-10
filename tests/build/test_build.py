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


# ---------------------------------------------------------------- freshness stamp
def test_build_writes_a_stamp_and_reports_staleness(world_copy):
    from wcb.world.build import BUILD_STAMP, GOLD_VERSION, ensure_built, gold_status

    stamp = world_copy / "gold" / BUILD_STAMP
    stamp.unlink(missing_ok=True)
    assert gold_status(world_copy) == "gold not built"
    assert build_world(world_copy).ok
    assert read_json(stamp)["gold_version"] == GOLD_VERSION
    assert gold_status(world_copy) is None
    assert ensure_built(world_copy) is None  # current: nothing to do

    artifact = next(p for p in (world_copy / "inbox").rglob("*.md"))
    artifact.write_text(artifact.read_text() + "\nEdited.\n")
    assert gold_status(world_copy) == "world sources changed since the last build"
    (world_copy / "inbox" / artifact.parent.name / "manifest.json").write_text("{}")
    assert gold_status(world_copy) == "world sources changed since the last build"  # manifests ignored

    seen = []
    res = ensure_built(world_copy, echo=seen.append)
    assert res is not None and res.ok and gold_status(world_copy) is None
    assert seen and "sources changed" in seen[0]

    data = read_json(stamp)
    data["gold_version"] = GOLD_VERSION - 1
    stamp.write_text(json.dumps(data))
    assert "gold version" in gold_status(world_copy)


def test_ensure_built_raises_when_the_build_fails(world_copy):
    import pytest

    from wcb.world.build import ensure_built, gold_status

    assert build_world(world_copy).ok
    (world_copy / "world.jsonl").write_text('{"id": "e-bad", "t": "not a time"}\n')
    assert gold_status(world_copy) == "world sources changed since the last build"
    with pytest.raises(ValueError, match="failed to build"):
        ensure_built(world_copy)
    assert gold_status(world_copy) is not None  # still stale, so the next run tries again


def test_committed_fixture_gold_is_current():
    """tests/fixtures/mini-world is committed with its gold; rebuild it when this fails."""
    from wcb.paths import repo_root
    from wcb.world.build import gold_status

    assert gold_status(repo_root() / "tests" / "fixtures" / "mini-world") is None
