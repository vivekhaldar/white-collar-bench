"""Tests for wcb.contract.validate.validate_answers."""

import json

import pytest

from wcb.cli import main
from wcb.contract.validate import CODES, validate_answers
from wcb.paths import contract_dir

EXAMPLE = contract_dir() / "answers" / "example.answers.json"
EXAMPLE_TYPES = {"q-001": "point", "q-002": "list", "q-003": "status", "q-004": "temporal", "q-005": "point"}


def write_json(path, data):
    path.write_text(json.dumps(data))
    return path


@pytest.fixture
def visible_questions(tmp_path):
    """Agent-visible .wcb/questions.json format."""
    qs = [{"id": k, "type": t, "text": "..."} for k, t in EXAMPLE_TYPES.items()]
    return write_json(tmp_path / "questions.json", {"date": "2027-03-02", "questions": qs})


def test_example_answers_pass():
    assert validate_answers(EXAMPLE) == []


def test_example_answers_pass_with_visible_questions(visible_questions):
    assert validate_answers(EXAMPLE, visible_questions) == []


def test_gold_questions_format(tmp_path):
    qs = [{"id": k, "type": t, "template": "x", "params": {}, "text": "...", "gold": {}} for k, t in EXAMPLE_TYPES.items()]
    gold = write_json(tmp_path / "cp1.json", {"world": "w", "checkpoint": "cp1", "date": "2027-03-02", "questions": qs})
    assert validate_answers(EXAMPLE, gold) == []


def test_missing_and_unknown_answers(tmp_path, visible_questions):
    answers = json.loads(EXAMPLE.read_text())
    del answers["q-003"]
    answers["q-999"] = {"type": "point", "abstain": True}
    issues = validate_answers(write_json(tmp_path / "answers.json", answers), visible_questions)
    got = sorted((i.path, i.code, i.severity) for i in issues)
    assert got == [("q-003", "answers.missing", "error"), ("q-999", "answers.unknown", "warning")]


def test_type_mismatch_and_schema_errors(tmp_path, visible_questions):
    answers = json.loads(EXAMPLE.read_text())
    answers["q-001"] = {"type": "list", "abstain": False, "items": []}  # question is a point
    answers["q-004"] = {"type": "temporal", "abstain": False, "date": "24 Feb"}  # not YYYY-MM-DD
    issues = validate_answers(write_json(tmp_path / "answers.json", answers), visible_questions)
    assert {i.path for i in issues} == {"q-001", "q-004"}
    assert {i.code for i in issues} == {"answers.schema"}
    assert any("does not match question type" in i.message for i in issues if i.path == "q-001")


def test_without_questions_checks_declared_types(tmp_path):
    answers = {"q-1": {"abstain": True}, "q-2": {"type": "point", "abstain": False}}
    issues = validate_answers(write_json(tmp_path / "a.json", answers))
    assert {(i.path, i.code) for i in issues} == {("q-1", "answers.schema"), ("q-2", "answers.schema")}


def test_invalid_json_and_wrong_root(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert [i.code for i in validate_answers(bad)] == ["answers.json"]
    root = write_json(tmp_path / "list.json", [1, 2])
    issues = validate_answers(root)
    assert [(i.code, i.path) for i in issues] == [("answers.schema", str(root))]


def test_malformed_questions_file_raises(tmp_path):
    q = write_json(tmp_path / "q.json", {"questions": [{"id": "q-001"}]})
    with pytest.raises(ValueError):
        validate_answers(EXAMPLE, q)


def test_answer_codes_are_documented(tmp_path, visible_questions):
    answers = {"q-001": {"type": "list", "abstain": False}, "q-x": {"type": "point", "abstain": True}}
    issues = validate_answers(write_json(tmp_path / "a.json", answers), visible_questions)
    assert issues and {i.code for i in issues} <= set(CODES)


def test_cli_validate_answers(tmp_path, visible_questions, capsys):
    assert main(["validate", "answers", str(EXAMPLE), "--questions", str(visible_questions)]) == 0
    assert "0 error(s)" in capsys.readouterr().out
    bad = write_json(tmp_path / "a.json", {"q-001": {"type": "point"}})
    assert main(["validate", "answers", str(bad), "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out[0]["code"] == "answers.schema" and out[0]["path"] == "q-001"
