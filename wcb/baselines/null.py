"""Null baseline: an agent that does nothing and abstains on every question.

It sets the score floor (docs/plan.md section 7): it earns credit only on unanswerable questions,
where abstaining is correct. It also doubles as the smallest working example of the agent side
of the adapter protocol. Run it with ``python -m wcb.baselines.null`` from an adapter
(``adapters/examples/null.yaml``); it reads the session from environment variables:

- ``WCB_PHASE``: ``ingest`` or ``query``.
- ``WCB_WORKSPACE``: the workspace directory (default: the current directory).

Ingest sessions leave the store untouched. Query sessions read ``.wcb/questions.json`` and write
``.wcb/answers.json`` with ``{"type": <question type>, "abstain": true}`` for every question.
Both phases report zero usage in ``.wcb/usage.json``, the self-reported usage format from
docs/formats.md section 5.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ZERO_USAGE = {
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
    "tool_calls": 0,
    "model": "none",
}


def abstain_all(questions: dict) -> dict:
    """Answers that abstain on every question in a ``.wcb/questions.json`` object."""
    return {q["id"]: {"type": q["type"], "abstain": True} for q in questions.get("questions", [])}


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    phase = os.environ.get("WCB_PHASE", "")
    workspace = Path(os.environ.get("WCB_WORKSPACE") or ".")
    wcb_dir = workspace / ".wcb"
    if phase == "ingest":
        _write_json(wcb_dir / "usage.json", ZERO_USAGE)
        print(f"null baseline: {os.environ.get('WCB_DATE', '?')} ingest, nothing to do")
        return 0
    if phase == "query":
        questions_file = wcb_dir / "questions.json"
        try:
            questions = json.loads(questions_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"null baseline: cannot read {questions_file}: {e}", file=sys.stderr)
            return 1
        answers = abstain_all(questions)
        _write_json(wcb_dir / "answers.json", answers)
        _write_json(wcb_dir / "usage.json", ZERO_USAGE)
        print(f"null baseline: abstained on {len(answers)} question(s)")
        return 0
    print(
        f"null baseline: WCB_PHASE must be 'ingest' or 'query', got {phase!r}; "
        "run it through 'wcb run --adapter adapters/examples/null.yaml'",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
