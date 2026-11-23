import gzip
import json
from types import SimpleNamespace

from scripts import lite_regression as regression
from wcb.grade.judge import DEFAULT_PANEL


def test_live_panel_fills_conditional_votes_then_scores_offline(tmp_path, monkeypatch):
    models = DEFAULT_PANEL.split(",")
    calls = []

    class Client:
        def __init__(self, spec):
            self.spec = spec

        def complete(self, prompt, **kwargs):
            calls.append(self.spec)
            return "YES" if self.spec == models[0] or "longer excerpt" in prompt else "NO"

    monkeypatch.setattr(regression, "make_client", Client)
    monkeypatch.setattr(regression, "CACHES", tmp_path)
    monkeypatch.setattr(regression, "PANEL_CACHE", tmp_path / "panel.jsonl")
    (tmp_path / "judge-cache-opus-track-a.jsonl.gz").write_bytes(gzip.compress(b""))
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    monkeypatch.setattr(regression, "load_run_meta", lambda run: {"worlds": []})
    monkeypatch.setattr(regression.RunPlan, "from_meta", lambda *a, **kw: SimpleNamespace(world_entries=[{}]))

    def score_world(plan, entry, judge, acc):
        if judge.citation("question", "claim", "brief excerpt") is None:
            judge.review_citation("question", "claim", "longer excerpt")

    monkeypatch.setattr(regression, "score_world", score_world)
    assert regression.rescore(tmp_path, "opus", "a", False) == ({}, 2)
    assert not calls
    assert regression.rescore(tmp_path, "opus", "a", True) == ({}, 0)
    assert calls == models * 2
    rows = [json.loads(line) for line in regression.PANEL_CACHE.read_text().splitlines()]
    assert {(row["model"], row["kind"]) for row in rows} == {
        (model, kind) for model in models for kind in ("citation", "citation_review")
    }
    calls.clear()
    assert regression.rescore(tmp_path, "opus", "a", False) == ({}, 0)
    assert not calls
