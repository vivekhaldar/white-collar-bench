"""Build gold question documents from `questions.yaml` (docs/formats.md §3, docs/questions.md).

`build_questions` is called by `wcb world build` and writes nothing itself. For every checkpoint
in `world.yaml` it renders each question spec against the gold state at the checkpoint date:

1. the template (`wcb.questions.templates.TEMPLATES`) gives the default text, which the spec's
   own `text` replaces entirely when present;
2. the template gives `(answerable, gold, support)`; an unanswerable question gets gold `{}`
   and support `[]`, so the correct answer is to abstain;
3. a status or brief question may append hand-written rubric items with `extra_rubric`;
4. `wcb.questions.support.widen_support` adds the other delivered artifacts about the same
   commitments, decisions, facts and events to item and question support.

`visible_questions` strips a gold document down to what the agent sees (§3.4).
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from wcb.questions.person_evidence import attribute_sources, ground_person_gold
from wcb.questions.rubric import normalize_extra_item, number_items
from wcb.questions.support import widen_support
from wcb.questions.templates import TEMPLATES, attr_support, support_union
from wcb.questions.transcript_evidence import conflicting_blocker_sources
from wcb.util.io import read_yaml
from wcb.world.model import World
from wcb.world.state import state_at


def load_specs(world: World) -> list[dict[str, Any]]:
    """Question specs from ``questions.yaml`` (``[]`` if the file is missing or empty).

    YAML dates (``since: 2027-03-01``) are converted to ISO strings.
    """
    path = world.dir / "questions.yaml"
    if not path.is_file():
        return []
    specs = _plain(read_yaml(path)) or []
    if not isinstance(specs, list):
        raise ValueError(f"{path}: questions.yaml must be a list of question specs")
    return specs


def build_question(spec: dict[str, Any], world: World, state: dict) -> dict[str, Any]:
    """One gold question (docs/formats.md §3.2) from its spec and the checkpoint's gold state."""
    qid = str(spec.get("id", "?"))
    name = spec.get("template")
    template = TEMPLATES.get(name)
    if template is None:
        raise ValueError(f"question {qid}: unknown template {name!r}")
    params = dict(spec.get("params") or {})
    missing = [p for p in template.params if p not in params]
    if missing:
        raise ValueError(f"question {qid}: template {name} needs params {missing}")
    text = spec.get("text") or template.text(params, world, state)
    answerable, gold, support = template.gold(params, world, state)
    if answerable and spec.get("extra_rubric") and "rubric" in gold:
        gold, support = _with_extra_rubric(gold, spec["extra_rubric"], state, support)
    if answerable and name in {"person_attr", "person_brief"}:
        gold = ground_person_gold(gold, world, state, params, name)
        if name == "person_attr" and params["attribute"] in {"role", "org", "relationship"}:
            evidence = attribute_sources(world, state, params["person"], params["attribute"])
            support = support_union(state, support, evidence) if evidence else []
        elif name == "person_brief":
            support = support_union(state, *(r["support"] for r in gold["rubric"]))
    if answerable and (name == "project_status" or
                       (name == "project_attr" and params.get("attribute") == "blocker")):
        conflict = conflicting_blocker_sources(world, state, params["project"])
        if conflict and name == "project_attr":
            gold = {**gold, "uncertain": True, "accept": [*gold.get("accept", []),
                    "nothing", "none", "no blockers", "no current blockers", "no currently reported blockers"]}
            support = support_union(state, support, conflict)
        elif conflict:
            disputed = set(attr_support(world, state, params["project"], "blocker"))
            gold = {**gold, "rubric": [r for r in gold["rubric"] if r.get("aspect") != "blocker"
                    and not (r.get("aspect") == "latest_change" and disputed & set(r["support"])
                             and "block" in r["text"].lower())]}
    if answerable:
        gold, support = widen_support(template.qtype, gold, support, world, state)
    return {
        "id": qid,
        "type": template.qtype,
        "template": template.name,
        "params": params,
        "text": str(text),
        "answerable": bool(answerable),
        "challenges": list(spec.get("challenges") or []),
        "support": list(support) if answerable else [],
        "gold": gold if answerable else {},
    }


def build_questions(world: World, states: dict[str, dict]) -> dict[str, dict]:
    """Gold questions documents keyed by checkpoint ID, in checkpoint order.

    `states` maps dates to gold states (docs/formats.md §2); a checkpoint date that is missing
    is computed with `state_at`. Every checkpoint gets a document, even one with no questions.
    Questions keep their order from ``questions.yaml``.
    """
    specs = load_specs(world)
    docs: dict[str, dict] = {}
    for cp in world.checkpoints():
        date = cp["date"]
        state = states.get(date) or state_at(world, date)
        questions = [
            build_question(spec, world, state)
            for spec in specs
            if str(spec.get("checkpoint")) == cp["id"]
        ]
        docs[cp["id"]] = {
            "world": world.id,
            "checkpoint": cp["id"],
            "date": date,
            "questions": questions,
        }
    return docs


def visible_questions(gold_doc: dict) -> dict:
    """The agent-visible questions (docs/formats.md §3.4): only ``id``, ``type`` and ``text``.

    Unanswerable questions keep their template's type, so agents cannot tell them apart.
    """
    return {
        "date": gold_doc["date"],
        "questions": [
            {"id": q["id"], "type": q["type"], "text": q["text"]} for q in gold_doc["questions"]
        ],
    }


# ---------------------------------------------------------------- helpers
def _with_extra_rubric(
    gold: dict, extra: Any, state: dict, support: list[str]
) -> tuple[dict, list[str]]:
    """Append a spec's ``extra_rubric`` items, renumber, and widen the question's support."""
    if not isinstance(extra, list):
        extra = [extra]
    rubric = [*gold["rubric"], *(normalize_extra_item(e) for e in extra)]
    number_items(rubric)
    support = support_union(state, support, *(r["support"] for r in rubric))
    return {**gold, "rubric": rubric}, support


def _plain(obj: Any) -> Any:
    """YAML values with dates and datetimes as ISO strings."""
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    return obj
