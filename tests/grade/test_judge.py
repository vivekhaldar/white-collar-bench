"""Heuristic and LLM judges: matching rules, rubric verdicts, parsing, voting and caching."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wcb.grade.judge import (
    DEFAULT_LLM_JUDGE,
    RUBRIC_PROMPT,
    SAME_ITEM_PROMPT,
    SYSTEM_PROMPT,
    HeuristicJudge,
    LLMJudge,
    load_cache,
    majority,
    make_judge,
    match_tokens,
    name_tokens,
    parse_verdict,
    parse_yes_no,
    rubric_prompt,
    same_item_prompt,
)

J = HeuristicJudge()

LOOPS = {
    "c-001": {
        "what": "Return the Tessellate security questionnaire",
        "keywords": ["security questionnaire", "questionnaire"],
    },
    "c-002": {
        "what": "Send Ada the January reconciliation report",
        "keywords": ["reconciliation report", "january"],
    },
    "c-003": {
        "what": "Review Sam Patel's ingestion design doc",
        "keywords": ["ingestion design", "design doc"],
    },
    "c-004": {
        "what": "Send Ada Tessellate volume pricing",
        "keywords": ["volume pricing", "pricing"],
    },
    "c-005": {
        "what": "Approve Ben's GL sandbox access request",
        "keywords": ["access request", "sandbox"],
    },
}

PARAPHRASES = [
    ("c-001", {"text": "Send Cora the completed security questionnaire"}),
    ("c-001", {"text": "Return Tessellate's security questionnaire"}),
    ("c-001", {"text": "Fill in the questionnaire from Tessellate"}),
    ("c-002", {"text": "January reconciliation report from Ben"}),
    ("c-002", {"text": "Reconciliation report"}),
    ("c-003", {"text": "Review Samir's ingestion doc"}),
    ("c-003", {"text": "Ingestion design doc review"}),
    ("c-003", {"text": "Look over the ingestion design document"}),
    ("c-004", {"text": "Volume pricing", "counterparty": "Cora Velez"}),
    ("c-004", {"text": "Cora to send volume pricing for Tessellate"}),
    ("c-005", {"text": "Approve Ben's sandbox access"}),
    ("c-005", {"text": "GL sandbox access request approval"}),
]

NEGATIVES = [
    ("c-002", {"text": "Send Ada the February forecast report"}),
    ("c-002", {"text": "Send the report"}),
    ("c-003", {"text": "Review the budget doc"}),
    ("c-005", {"text": "Approve Ben's holiday request"}),
    ("c-005", {"text": "Approve Ben's Holiday Request"}),
    ("c-001", {"text": "Send Cora the contract"}),
]


# ---------------------------------------------------------------- heuristic same_item
@pytest.mark.parametrize("loop, pred", PARAPHRASES)
def test_heuristic_paraphrases_match_only_their_loop(loop, pred):
    hits = [cid for cid, gold in LOOPS.items() if J.same_item(pred, gold, kind="loop")]
    assert hits == [loop]


@pytest.mark.parametrize("loop, pred", NEGATIVES)
def test_heuristic_rejects_lookalikes(loop, pred):
    assert not J.same_item(pred, LOOPS[loop], kind="loop")


def test_heuristic_change_items_use_summary():
    gold = {"summary": "Quillon decision target moved to 5 February", "keywords": []}
    assert J.same_item({"text": "Decision target moved to 5 Feb"}, gold, kind="change")
    assert not J.same_item({"text": "Quillon budget approved"}, gold, kind="change")


def test_keyword_route_needs_some_description_overlap():
    gold = LOOPS["c-004"]  # keyword 'pricing'
    assert not J.same_item({"text": "Pricing"}, gold, kind="loop")  # 1 of 5 tokens
    assert J.same_item({"text": "Tessellate pricing"}, gold, kind="loop")  # 2 of 5 tokens


def test_match_tokens():
    assert match_tokens("Review Sam Patel's reports") == {"review", "sam", "patel", "report"}
    assert match_tokens("Phase 2 of the plan") == {"phase", "2", "plan"}
    assert match_tokens("process") == {"process"}
    assert match_tokens(None) == set()


def test_name_tokens():
    assert name_tokens("Review Samir's ingestion doc") == {"samir"}
    assert name_tokens("APPROVE BEN'S HOLIDAY REQUEST") == set()
    assert name_tokens("") == set()


# ---------------------------------------------------------------- heuristic rubric
ITEM = {
    "id": "r1",
    "text": "Decision target is 5 February",
    "weight": 2,
    "keywords": [["2027-02-05"], ["decision", "target"]],
    "stale": [["2027-01-29"]],
}


@pytest.mark.parametrize(
    "text, verdict",
    [
        ("Decision now targeted for 5 Feb.", "covered"),
        ("Target date: February 5th", "covered"),
        ("target 2027-02-05", "covered"),
        ("target moved to 2/5", "covered"),
        ("Decision targeted for 29 January.", "contradicted"),  # stale present, new absent
        ("Target 2027-01-29", "contradicted"),
        ("Target moved from Jan 29 to Feb 5", "covered"),  # both: covered wins
        ("5 Feb", "missing"),  # second group absent
        ("Nothing relevant", "missing"),
    ],
)
def test_heuristic_rubric(text, verdict):
    assert J.rubric(text, ITEM, {}) == verdict


def test_rubric_contradiction_needs_every_stale_group():
    item = {
        "text": "Pilot is Reno and Sparks",
        "keywords": [["sparks"]],
        "stale": [["reno"], ["only"]],
    }
    assert J.rubric("Pilot at Reno", item, {}) == "missing"
    assert J.rubric("Pilot at Reno only", item, {}) == "contradicted"
    assert J.rubric("Pilot at Reno and Sparks; only two depots", item, {}) == "covered"


def test_rubric_whole_words_and_accents():
    item = {"text": "x", "keywords": [["cafe"]], "stale": []}
    assert J.rubric("Meet at the Café", item, {}) == "covered"
    assert J.rubric("cafeteria", item, {}) == "missing"


def test_rubric_without_keywords_falls_back_to_tokens():
    item = {"text": "Waiting on volume pricing from Cora", "keywords": [], "stale": []}
    assert J.rubric("Cora still owes volume pricing; waiting.", item, {}) == "covered"
    assert J.rubric("Pricing", item, {}) == "missing"
    assert J.rubric("Anything", {"text": "", "keywords": []}, {}) == "missing"


# ---------------------------------------------------------------- parsing and voting
@pytest.mark.parametrize(
    "text, expected",
    [
        ("YES", True),
        ("no", False),
        ("**Yes**", True),
        ("Answer: NO.", False),
        ("Yes, same commitment", True),
        ("", None),
        ("Maybe", None),
        ("nope", None),
    ],
)
def test_parse_yes_no(text, expected):
    assert parse_yes_no(text) is expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("COVERED", "covered"),
        ("missing", "missing"),
        ("**CONTRADICTED**", "contradicted"),
        ("Verdict: Covered.", "covered"),
        ("NOT COVERED", "missing"),
        ("The answer contradicts it", "contradicted"),
        ("", None),
        ("unclear", None),
    ],
)
def test_parse_verdict(text, expected):
    assert parse_verdict(text) == expected


def test_majority_and_ties():
    assert majority([True, True, False], (False, True)) is True
    assert majority([True, False, None], (False, True)) is False  # tie -> conservative
    assert majority([None, None], (False, True)) is False
    assert (
        majority(["covered", "contradicted", "missing"], ("missing", "covered", "contradicted"))
        == "missing"
    )
    assert (
        majority(["covered", "contradicted"], ("missing", "covered", "contradicted")) == "covered"
    )


# ---------------------------------------------------------------- prompts
def test_same_item_prompt_contents():
    gold = {
        "loop": "c-004",
        "what": "Send Ada Tessellate volume pricing",
        "counterparty": "p-cora-velez",
        "counterparty_name": "Cora Velez",
        "status": "open",
        "due": None,
        "keywords": ["pricing"],
        "support": ["em-0004"],
    }
    pred = {"text": "Volume pricing from Cora", "status": "open", "cites": ["em-0004"], "due": None}
    p = same_item_prompt(pred, gold, "loop")
    assert p.startswith("Do these two descriptions refer to the same commitment? Answer YES or NO.")
    assert "Send Ada Tessellate volume pricing" in p and "Cora Velez" in p
    assert "Volume pricing from Cora" in p
    assert "em-0004" not in p and "keywords" not in p and "null" not in p
    change = same_item_prompt(
        {"text": "x"}, {"summary": "Target moved", "date": "2027-01-11"}, "change"
    )
    assert "the same change?" in change and "2027-01-11" in change


def test_rubric_prompt_contents():
    p = rubric_prompt(
        "Target is 29 Jan.",
        {"text": "Decision target is 5 February"},
        {"target_date": "2027-02-05"},
    )
    assert "Decision target is 5 February" in p and '"target_date": "2027-02-05"' in p
    assert "Target is 29 Jan." in p
    assert "COVERED" in p and "MISSING" in p and "CONTRADICTED" in p


def test_prompts_are_documented_verbatim():
    doc = (Path(__file__).parents[2] / "docs" / "judge.md").read_text(encoding="utf-8")
    for text in (SYSTEM_PROMPT, SAME_ITEM_PROMPT, RUBRIC_PROMPT):
        assert text in doc


# ---------------------------------------------------------------- LLM judge
GOLD = {
    "loop": "c-004",
    "what": "Send Ada Tessellate volume pricing",
    "counterparty": "p-cora-velez",
}
PRED = {"text": "Volume pricing from Cora"}


def test_llm_same_item_single_sample(make_fake_client):
    client = make_fake_client(["YES"])
    judge = LLMJudge(client)
    assert judge.same_item(PRED, GOLD, kind="loop") is True
    call = client.calls[0]
    assert call["temperature"] == 0.0 and call["system"] == SYSTEM_PROMPT
    assert "Send Ada Tessellate volume pricing" in call["prompt"]
    assert judge.name == "llm:fake:fake-model"


def test_llm_majority_vote_over_samples(make_fake_client):
    client = make_fake_client(["NO", "Yes.", "**YES**"])
    judge = LLMJudge(client, samples=3)
    assert judge.same_item(PRED, GOLD, kind="loop") is True
    assert len(client.calls) == 3
    assert {c["temperature"] for c in client.calls} == {1.0}


def test_llm_rubric_votes_and_unparseable(make_fake_client):
    judge = LLMJudge(make_fake_client(["CONTRADICTED", "contradicted", "COVERED"]), samples=3)
    assert judge.rubric("Target is 29 Jan", {"text": "Target is 5 Feb"}, {}) == "contradicted"
    garbage = LLMJudge(make_fake_client(["I am not sure."]))
    assert garbage.rubric("x", {"text": "y"}, {}) == "missing"
    assert LLMJudge(make_fake_client(["hmm"])).same_item(PRED, GOLD, kind="loop") is False


def test_llm_in_memory_cache(make_fake_client):
    client = make_fake_client(["YES"])
    judge = LLMJudge(client)
    for _ in range(3):
        assert judge.same_item(PRED, GOLD, kind="loop")
    assert len(client.calls) == 1 and judge.calls == 1


def test_llm_cache_file_hit(tmp_path, make_fake_client):
    cache = tmp_path / "judge" / "cache.jsonl"
    first = make_fake_client(["NO"])
    assert LLMJudge(first, cache_path=cache).same_item(PRED, GOLD, kind="loop") is False
    assert LLMJudge(first, cache_path=cache).rubric("a", {"text": "b"}, {}) == "missing"
    rows = [json.loads(line) for line in cache.read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["same_item", "rubric"]
    assert rows[0]["outputs"] == ["NO"] and rows[0]["model"] == "fake:fake-model"

    # A fresh judge (new process) with the same cache makes no calls, even if the model
    # would now answer differently: re-grading is stable.
    second = make_fake_client(["YES"])
    judge = LLMJudge(second, cache_path=cache)
    assert judge.same_item(PRED, GOLD, kind="loop") is False
    assert second.calls == []
    assert load_cache(cache) == {rows[0]["key"]: False, rows[1]["key"]: "missing"}


def test_llm_cache_key_depends_on_model_and_samples(tmp_path, make_fake_client):
    cache = tmp_path / "cache.jsonl"
    LLMJudge(make_fake_client(["NO"], spec="a:m1"), cache_path=cache).same_item(
        PRED, GOLD, kind="loop"
    )
    other = make_fake_client(["YES"], spec="a:m2")
    assert LLMJudge(other, cache_path=cache).same_item(PRED, GOLD, kind="loop") is True
    assert len(other.calls) == 1
    voted = make_fake_client(["YES"], spec="a:m1")
    assert LLMJudge(voted, samples=3, cache_path=cache).same_item(PRED, GOLD, kind="loop") is True
    assert len(voted.calls) == 3


def test_load_cache_skips_bad_lines(tmp_path):
    p = tmp_path / "c.jsonl"
    p.write_text('{"key": "k1", "decision": true}\nnot json\n{"nokey": 1}\n', encoding="utf-8")
    assert load_cache(p) == {"k1": True}


def test_llm_judge_rejects_zero_samples(make_fake_client):
    with pytest.raises(ValueError):
        LLMJudge(make_fake_client(["YES"]), samples=0)


# ---------------------------------------------------------------- factory
def test_make_judge_heuristic():
    assert make_judge().name == "heuristic"
    assert make_judge("heuristic", model="ignored").name == "heuristic"


def test_make_judge_llm(monkeypatch, tmp_path):
    monkeypatch.delenv("WCB_JUDGE_SAMPLES", raising=False)
    monkeypatch.delenv("WCB_JUDGE_CACHE", raising=False)
    judge = make_judge("llm", "cmd:cat", cache_path=tmp_path / "c.jsonl")
    assert judge.name == "llm:cmd:cat" and judge.samples == 3
    assert judge.cache_path == tmp_path / "c.jsonl"
    default = make_judge("llm")
    assert default.name == f"llm:{DEFAULT_LLM_JUDGE}"
    monkeypatch.setenv("WCB_JUDGE_SAMPLES", "1")
    monkeypatch.setenv("WCB_JUDGE_CACHE", str(tmp_path / "env.jsonl"))
    env_judge = make_judge("llm", "openai:some-model")
    assert env_judge.samples == 1 and env_judge.cache_path == tmp_path / "env.jsonl"
    assert env_judge.name == "llm:openai:some-model"


def test_make_judge_llm_with_command_end_to_end(tmp_path):
    # A real subprocess judge that always answers YES; no network involved.
    judge = make_judge("llm", "cmd:cat >/dev/null; echo YES")
    assert judge.same_item(PRED, GOLD, kind="loop") is True


def test_make_judge_unknown_kind():
    with pytest.raises(ValueError):
        make_judge("oracle")
