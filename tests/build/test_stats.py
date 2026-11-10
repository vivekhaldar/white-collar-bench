"""Tests for calibration statistics (wcb/world/stats.py)."""

from __future__ import annotations

from wcb.world.stats import world_stats


def test_stats_on_mini_world(world_copy):
    s = world_stats(world_copy)
    assert s["world"] == "mini"
    assert s["entities"]["people"] == {"total": 6, "non_minor": 5, "minor": 1, "in_loops": 4}
    assert (s["entities"]["orgs"], s["entities"]["projects"]) == (2, 2)
    art = s["artifacts"]
    assert art["total"] == 13 and art["seed"] == 6 and art["episode"] == 7
    assert art["noise_share"] == round(1 / 13, 3)
    assert art["per_day"]["2027-01-11"]["by_channel"] == {
        "calendar": 1,
        "chat": 1,
        "email": 1,
        "note": 1,
    }
    assert s["commitments"]["created_per_day"] == {
        "2027-01-04": 1,
        "2027-01-05": 2,
        "2027-01-06": 1,
        "2027-01-07": 1,
    }
    loops = s["loops"]
    assert loops["kind"]["counts"] == {"ask": 3, "decision": 2, "task": 2}
    assert loops["owner"]["counts"] == {"others": 2, "worker": 3}
    assert loops["final_status"]["counts"] == {"done": 2, "open": 3}
    assert loops["decision_status"] == {"made": 1, "reversed": 1}
    assert loops["suggested_at_create_share"] == 0.2
    assert loops["hard_due_share"] == 0.4
    # c-005: 5 Jan -> 11 Jan is 4 business days; c-001: 4 Jan -> 12 Jan is 6.
    assert loops["lifetime_business_days"] == {"n": 2, "median": 5.0, "p75": 5.5, "p90": 5.8}
    assert s["events_by_type"]["artifact.emit"] == 13
    assert s["challenges"]["transfer"] == 1
    assert s["questions"] is None  # not built yet


def test_stats_include_questions_once_built(world_copy):
    from wcb.util.io import write_json

    write_json(
        world_copy / "gold/questions/cp1.json",
        {
            "world": "mini",
            "checkpoint": "cp1",
            "date": "2027-01-11",
            "questions": [
                {
                    "id": "q-1",
                    "type": "list",
                    "template": "i_owe",
                    "answerable": True,
                    "challenges": ["alias"],
                },
                {"id": "q-2", "type": "point", "template": "project_attr", "answerable": False},
            ],
        },
    )
    q = world_stats(world_copy)["questions"]
    assert q["total"] == 2 and q["unanswerable"] == 1 and q["unanswerable_share"] == 0.5
    assert q["by_template"] == {"i_owe": 1, "project_attr": 1}
    assert q["by_checkpoint"] == {"cp1": 2}
