"""Validate an answers object against contract/answers/answers.schema.json.

Shared by `wcb validate answers` and the grader: an answer that fails validation scores 0.
"""

from __future__ import annotations

import functools
from typing import Any

import jsonschema

from wcb.paths import contract_dir
from wcb.util.io import read_json

ANSWER_TYPES = ("point", "list", "status", "brief", "change", "temporal", "priority")


@functools.lru_cache(maxsize=1)
def answers_schema() -> dict[str, Any]:
    return read_json(contract_dir() / "answers" / "answers.schema.json")


@functools.lru_cache(maxsize=None)
def _validator(qtype: str) -> jsonschema.Draft202012Validator:
    schema = answers_schema()
    sub = {"$defs": schema["$defs"], **schema["$defs"][qtype]}
    return jsonschema.Draft202012Validator(sub)


def check_answer(answer: Any, qtype: str) -> list[str]:
    """Problems with one answer for a question of type `qtype` (empty list = valid)."""
    if qtype not in ANSWER_TYPES:
        return [f"unknown question type {qtype!r}"]
    if not isinstance(answer, dict):
        return ["answer must be a JSON object"]
    problems = []
    if answer.get("type") != qtype:
        problems.append(f"answer type {answer.get('type')!r} does not match question type {qtype!r}")
    for err in sorted(_validator(qtype).iter_errors(answer), key=lambda e: list(e.path)):
        loc = "/".join(str(p) for p in err.path)
        problems.append(f"{loc or '<root>'}: {err.message}")
    return problems


def check_answers(answers: Any, questions: list[dict] | None = None) -> dict[str, list[str]]:
    """Validate a whole answers object.

    Returns a mapping from question ID to its problems. With `questions`, every question gets
    an entry (missing answers are reported) and answer types are checked against question types.
    Without `questions`, each answer is checked against the type it declares.
    """
    if not isinstance(answers, dict):
        return {"<root>": ["answers file must be a JSON object mapping question IDs to answers"]}
    out: dict[str, list[str]] = {}
    if questions is None:
        for qid, ans in answers.items():
            qtype = ans.get("type") if isinstance(ans, dict) else None
            out[qid] = check_answer(ans, qtype) if qtype else ["answer has no 'type'"]
        return out
    for q in questions:
        qid = q["id"]
        if qid not in answers:
            out[qid] = ["missing answer"]
        else:
            out[qid] = check_answer(answers[qid], q["type"])
    known = {q["id"] for q in questions}
    for qid in answers:
        if qid not in known:
            out[qid] = ["answer for unknown question ID"]
    return out
