#!/usr/bin/env python3
"""Template: plug your own agent into white-collar-bench.

Copy this file and ``custom-script.yaml`` next to each other, rename them, and fill in the places
marked ``YOUR AGENT``. As shipped it is a complete, working (but trivial) agent:

- **ingest sessions** write one daily-log bullet per input and change nothing else;
- **query sessions** abstain on every question;
- **both** write ``.wcb/usage.json``.

It uses only the Python standard library, so it runs anywhere ``python`` does.

How a session works (docs/adapters.md has the full reference):

1. The runner starts this script in a fresh process, with the workspace as the working directory
   and stdin empty. Nothing survives between sessions except the files in the workspace.
2. Everything about the session is in environment variables (read below) and in the workspace:

   - ingest: ``inbox/<date>/manifest.json`` plus the input files (``.eml``, ``.json`` chat,
     ``.vtt`` transcripts, ``.md`` notes, ``.ics`` invites, ``.docx``/``.xlsx``/``.pdf``
     documents). Track A also has the store and ``CONTRACT.md``; Track B has ``GOALS.md``.
   - query: ``.wcb/questions.json`` and ``.wcb/answer-schema.json``. The store is read-only;
     write only ``.wcb/answers.json`` (and ``.wcb/usage.json``).

3. Exit 0 when done. A non-zero exit, or running past the adapter's ``timeout_s``, makes the
   runner throw away this session's store changes (ingest) or record empty answers (query).

Rules: the prompt and any system prompt you add must be generic (no knowledge about particular
worlds, people or questions); read nothing outside the workspace; keep no memory outside it.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ============================================================================ 1. the session
# The runner always sets these. Defaults let you run the script by hand for debugging:
#   WCB_PHASE=query WCB_WORKSPACE=/path/to/copy python custom_agent_template.py
PHASE = os.environ.get("WCB_PHASE", "")  # "ingest" or "query"
DATE = os.environ.get("WCB_DATE", "")  # simulated "today", YYYY-MM-DD
TRACK = os.environ.get("WCB_TRACK", "A")  # "A" (store contract) or "B" (open representation)
WORKSPACE = Path(os.environ.get("WCB_WORKSPACE") or ".").resolve()
PROMPT_FILE = os.environ.get("WCB_PROMPT_FILE")  # the fixed benchmark prompt for this session
SESSION_DIR = os.environ.get("WCB_SESSION_DIR")  # log directory outside the workspace (optional)

# Your adapter's `env:` and `env_passthrough:` values arrive here too, for example:
API_KEY = os.environ.get("MY_PROVIDER_API_KEY")
MODEL = "none"  # YOUR AGENT: the model you call, e.g. "vendor/model-name"; reported in usage.json


# ============================================================================ 2. usage
class Usage:
    """Count what your agent spends; written to .wcb/usage.json at the end of the session."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd: float | None = None
        self.tool_calls = 0

    def to_dict(self) -> dict:
        # The runner reads these keys (docs/formats.md section 5). Extra keys are kept as-is.
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "tool_calls": self.tool_calls,
            "model": MODEL,
        }


def call_model(prompt: str, usage: Usage) -> str:
    """YOUR AGENT: call your model or agent framework here and return its text.

    Add the tokens it reports to ``usage``, for example::

        reply = my_client.generate(prompt)
        usage.input_tokens += reply.input_tokens
        usage.output_tokens += reply.output_tokens
        return reply.text

    Only model endpoints may be contacted over the network.
    """
    raise NotImplementedError("plug your model in here")


# ============================================================================ 3. ingestion
def ingest(usage: Usage) -> None:
    """Incorporate today's inputs into the store (Track A) or your own files (Track B)."""
    inbox_root = WORKSPACE / "inbox"
    if not inbox_root.is_dir():
        print("no inbox/ directory in the workspace: nothing to ingest", file=sys.stderr)
        return
    # Normally there is one directory, inbox/<WCB_DATE>/. The Track B seed session delivers every
    # seed date at once (inbox/<d1>/, inbox/<d2>/, ...), so handle all of them, oldest first.
    for day_dir in sorted(p for p in inbox_root.iterdir() if p.is_dir()):
        manifest = json.loads((day_dir / "manifest.json").read_text(encoding="utf-8"))
        bullets = []
        for entry in manifest["artifacts"]:
            # entry: {"id": "em-0031", "channel": "email", "received_at": "...", "path": "em-0031.eml",
            #         "title": "...", "parent": "em-0030" (attachments only)}
            text = read_artifact(day_dir / entry["path"])
            print(f"read {entry['id']} ({entry['channel']}): {len(text)} characters")

            # YOUR AGENT: decide what this input changes and update the store, e.g. ask your
            # model with the input text plus the relevant existing records, then write records
            # with write_record(). In Track A follow CONTRACT.md (people/, orgs/, projects/,
            # loops/, logs/); in Track B organize files however you like (see GOALS.md).
            # Never copy passwords, passcodes or meeting join links into the workspace.

            bullets.append(f"- {entry['id']} ({entry['channel']}): {entry.get('title', '')}")
        write_daily_log(day_dir.name, bullets)


def read_artifact(path: Path) -> str:
    """Text of one input file. Office documents and PDFs need extraction."""
    if path.suffix.lower() in (".docx", ".xlsx", ".pptx", ".pdf"):
        try:
            # Available when wcb is installed in the agent's environment (it is when the adapter
            # runs "python" from the wcb virtual environment). Otherwise use your own extractor.
            from wcb.agents.docs_text import extract_text

            return extract_text(path)
        except ImportError:
            return f"[binary document {path.name}: no text extractor available]"
    return path.read_text(encoding="utf-8", errors="replace")


def write_record(record_id: str, meta: dict, body: str) -> Path:
    """Write a Track A record: Markdown with YAML front matter, at <record_id>.md.

    Values are written in JSON syntax, which is valid YAML, so no YAML library is needed.
    Example of a loop record (see CONTRACT.md section 2.4)::

        write_record("loops/send-marisol-vendor-scorecard", {
            "id": "loops/send-marisol-vendor-scorecard", "type": "loop", "kind": "task",
            "title": "Send Marisol the revised vendor scorecard",
            "owner": "people/me", "counterparty": "people/marisol-teague",
            "status": "open", "accepted": True, "due": "2027-03-05",
            "evidence": [{"source": "em-0193", "basis": "received", "date": "2027-03-01"}],
            "created": "2027-03-01", "updated": "2027-03-01",
        }, "Marisol asked for the revised scorecard. [src: em-0193]\\n\\n## Log\\n\\n"
           "- 2027-03-01: created [src: em-0193]\\n")
    """
    lines = ["---"] + [f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()]
    path = WORKSPACE / f"{record_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n---\n" + body, encoding="utf-8")
    return path


def write_daily_log(date: str, bullets: list[str]) -> None:
    """Track A requires logs/<date>.md with one bullet per input processed that day."""
    write_record(
        f"logs/{date}",
        {"id": f"logs/{date}", "type": "log", "date": date},
        "\n".join(bullets) + "\n",
    )


# ============================================================================ 4. questions
def query(usage: Usage) -> None:
    """Answer every question in .wcb/questions.json into .wcb/answers.json."""
    questions = json.loads((WORKSPACE / ".wcb" / "questions.json").read_text(encoding="utf-8"))
    # questions: {"date": "2027-03-02", "questions": [{"id": "q-001", "type": "list",
    #             "text": "What do I currently owe Immy?"}, ...]}
    answers = {q["id"]: answer_question(q, usage) for q in questions["questions"]}
    out = WORKSPACE / ".wcb" / "answers.json"
    out.write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")
    print(f"answered {len(answers)} question(s)")


def answer_question(q: dict, usage: Usage) -> dict:
    """YOUR AGENT: answer one question from the store. ``type`` must equal ``q["type"]``.

    Answer shapes (contract/answers/answers.schema.json; `cites` hold artifact IDs such as
    "em-0193" and, in Track A, store record IDs such as "loops/send-scorecard"):

    - point:    {"type": "point", "abstain": False, "value": "Marisol Teague", "cites": [...],
                 "note": "optional context, not graded"}
                 (value: the bare answer only, e.g. "Privacy Officer" or "2027-11-18")
    - list:     {"type": "list", "abstain": False, "items": [{"text": "...", "counterparty":
                 "Marisol Teague", "direction": "i_owe", "status": "open", "due": "2027-03-05",
                 "cites": [...]}]}         (direction: i_owe | owed_to_me | other)
    - status / brief: {"type": "status", "abstain": False, "summary": "...",
                 "claims": [{"text": "...", "cites": [...]}]}
    - change:   {"type": "change", "abstain": False, "items": [{"text": "...",
                 "date": "2027-03-03", "cites": [...]}]}
    - temporal: {"type": "temporal", "abstain": False, "date": "2027-02-24", "cites": [...]}
    - priority: {"type": "priority", "abstain": False, "items": [{"text": "...",
                 "due": "2027-03-03", "why": "...", "cites": [...]}]}   (most important first)

    Abstain ({"type": ..., "abstain": True}) when the store does not support an answer: it is
    the right answer to unanswerable questions, and scores 0 on answerable ones.
    """
    return {"type": q["type"], "abstain": True}


# ============================================================================ 5. main
def main() -> int:
    usage = Usage()
    started = time.time()
    try:
        if PHASE == "ingest":
            ingest(usage)
        elif PHASE == "query":
            query(usage)
        else:
            print(f"WCB_PHASE must be 'ingest' or 'query', got {PHASE!r}", file=sys.stderr)
            return 2
    finally:
        # Write usage even if the session fails. .wcb/ is writable in every session.
        (WORKSPACE / ".wcb").mkdir(exist_ok=True)
        (WORKSPACE / ".wcb" / "usage.json").write_text(
            json.dumps(usage.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
    print(f"{PHASE} {DATE} done in {time.time() - started:.1f}s")  # goes to stdout.log
    return 0


if __name__ == "__main__":
    sys.exit(main())
