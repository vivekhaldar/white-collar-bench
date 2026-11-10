"""Perfect answers built from gold: a test helper and an upper-bound sanity check.

`perfect_answers` turns a gold questions document (`gold/questions/<cp>.json`, docs/formats.md
§3.2) into an answers object (§4) that should score about 1.0 on every question with the
heuristic judge. Tests use it to check that grading gives full marks to correct answers, and
that a run built from it scores near 100 end to end. It reads gold, so it is never a baseline.

What each answer contains:

| Type | Answer |
|---|---|
| point | the gold value |
| list | one item per gold item: `what`, counterparty name, direction, status, due date |
| status, brief | a summary of every rubric item's text plus the first alternative of every keyword group, and one claim per rubric item |
| change | one item per gold change: its summary and keywords, with the date |
| temporal | the gold date |
| priority | the must-include loops, then the other worker-owned active loops (no distractors) |
| unanswerable | abstain |

Every answer cites the gold `support` artifacts (restricted to the question's support, so all
citations are valid). With `store_ids` (world object ID -> store record ID, e.g. from
`wcb.store.oracle.record_ids`), list and priority items also cite the loop's store record.
"""

from __future__ import annotations

from typing import Any


def perfect_answers(
    gold_doc: dict,
    store_ids: dict[str, str] | None = None,
    *,
    entity_names: dict[str, str] | None = None,
) -> dict:
    """Answers that should score about 1.0 on every question of `gold_doc`.

    Counterparty names come from `entity_names` (entity ID -> display name) when given;
    otherwise from `store_ids` (`people/cora-velez` -> "cora velez", `people/me` -> "me");
    otherwise from the entity ID itself (`p-cora-velez` -> "cora velez"). The grader resolves
    names through the alias table, so these all work when IDs are slugs of canonical names.
    """
    names = _Names(entity_names or {}, store_ids or {})
    out: dict[str, Any] = {}
    for q in gold_doc.get("questions", []):
        out[q["id"]] = perfect_answer(q, names, store_ids or {})
    return out


def perfect_answer(q: dict, names: _Names, store_ids: dict[str, str]) -> dict:
    """The perfect answer for one gold question (see the module docstring)."""
    qtype = q["type"]
    if not q.get("answerable", True):
        return {"type": qtype, "abstain": True}
    gold = q.get("gold") or {}
    support = list(q.get("support") or [])
    cite = _Citer(support, store_ids)
    if qtype == "point":
        return {"type": qtype, "abstain": False, "value": str(gold.get("value")), "cites": support}
    if qtype == "list":
        items = [_loop_item(it, names, cite) for it in gold.get("items") or []]
        return {"type": qtype, "abstain": False, "items": items}
    if qtype in ("status", "brief"):
        return _rubric_answer(qtype, gold, cite)
    if qtype == "change":
        items = [
            {
                "text": _join([it.get("summary", ""), *_strs(it.get("keywords"))]),
                "date": it.get("date"),
                "cites": cite(it.get("support")),
            }
            for it in gold.get("items") or []
        ]
        return {"type": qtype, "abstain": False, "items": items}
    if qtype == "temporal":
        date = gold.get("date")
        return {"type": qtype, "abstain": False, "date": date, "text": str(date), "cites": support}
    if qtype == "priority":
        seen, items = set(), []
        for it in [*(gold.get("must_include") or []), *(gold.get("worker_active") or [])]:
            if it.get("loop") in seen:
                continue
            seen.add(it.get("loop"))
            items.append(
                {
                    "text": it.get("what", ""),
                    "due": it.get("due"),
                    "why": f"due {it['due']}" if it.get("due") else "open commitment",
                    "cites": cite(it.get("support"), it.get("loop")),
                }
            )
        return {"type": qtype, "abstain": False, "items": items[: int(gold.get("k") or 10)]}
    raise ValueError(f"question {q.get('id')}: unknown type {qtype!r}")


# ---------------------------------------------------------------- helpers
class _Names:
    """Entity ID -> a name the grader's alias table resolves back to that entity."""

    def __init__(self, names: dict[str, str], store_ids: dict[str, str]):
        self.names = names
        self.store_ids = store_ids

    def __call__(self, eid: Any) -> str | None:
        if not isinstance(eid, str) or not eid:
            return None
        if eid in self.names:
            return self.names[eid]
        rid = self.store_ids.get(eid)
        if rid:
            slug = rid.rsplit("/", 1)[-1]
            return "me" if rid == "people/me" else slug.replace("-", " ")
        return eid.split("-", 1)[-1].replace("-", " ")


class _Citer:
    """Builds cite lists: gold support restricted to the question's support, plus store IDs."""

    def __init__(self, support: list[str], store_ids: dict[str, str]):
        self.support = support
        self.store_ids = store_ids

    def __call__(self, item_support: Any, world_id: Any = None) -> list[str]:
        allowed = set(self.support)
        cites = [s for s in _strs(item_support) if not allowed or s in allowed]
        rid = self.store_ids.get(world_id) if isinstance(world_id, str) else None
        return cites + ([rid] if rid else [])


def _loop_item(it: dict, names: _Names, cite: _Citer) -> dict:
    return {
        "text": it.get("what", ""),
        "counterparty": names(it.get("counterparty")),
        "direction": it.get("direction"),
        "status": it.get("status"),
        "due": it.get("due"),
        "cites": cite(it.get("support"), it.get("loop")),
    }


def _rubric_answer(qtype: str, gold: dict, cite: _Citer) -> dict:
    """A summary covering every rubric item: its text plus each keyword group's first form."""
    rubric = gold.get("rubric") or []
    sentences, claims = [], []
    for item in rubric:
        firsts = [_first(g) for g in item.get("keywords") or []]
        text = _join([item.get("text", ""), *[f for f in firsts if f]])
        sentences.append(text)
        claims.append({"text": text, "cites": cite(item.get("support"))})
    summary = " ".join(sentences) or "No change."
    return {"type": qtype, "abstain": False, "summary": summary, "claims": claims}


def _first(group: Any) -> str | None:
    if isinstance(group, str):
        return group
    if isinstance(group, (list, tuple)) and group:
        return str(group[0])
    return None


def _strs(value: Any) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, (list, tuple)) else []


def _join(parts: list[str]) -> str:
    """'Main text (kw1; kw2).' from a main text and keyword phrases."""
    main, extra = (parts[0] if parts else "").strip(), [p for p in parts[1:] if p]
    text = f"{main} ({'; '.join(extra)})" if extra else main
    return text if text.endswith(".") else text + "."
