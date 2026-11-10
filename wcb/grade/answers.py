"""Per-question answer grading (docs/scoring.md, "Query scoring" and "Citations").

`score_question` grades one answer against one gold question (docs/formats.md §3.2) and
returns a `QuestionScore`. The steps are the same for every type:

1. **Missing or invalid.** A missing answer, or one that fails
   `wcb.contract.answers.check_answer`, scores 0.
2. **Unanswerable gold** (`answerable: false`). Abstaining scores 1; anything else scores 0.
3. **Abstaining on an answerable question** scores 0.
4. **Base score** `q` in [0, 1], by type (see the `grade_*` functions):

   | Type | Base score |
   |---|---|
   | point | 1 if the value resolves to the gold entity / date / number / text, else 0 |
   | list | soft F1: matched items earn attribute credit for status, due date and counterparty |
   | status, brief | weighted checklist: (covered - contradicted) / total weight, floored at 0 |
   | change | F1 over one-to-one matched items |
   | temporal | 1 exact date, 0.5 within one business day, else 0 |
   | priority | must-include recall in the top k x (1 - share of top items that are distractors) |

5. **Citations.** `c` = valid cites / all cites (0 when there are none). A cite is valid if it
   is an artifact ID in the question's `support`, or (Track A) names an existing record in the
   store the answers were produced from. Final score = `q x (0.75 + 0.25 x c)`.

Entity names are resolved with `ScoreContext.resolve_entities`: whole-phrase, case- and
accent-insensitive lookups in the world's alias table, where an alias shared by several
entities (two people called "Sam") resolves to nothing.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from wcb.contract.answers import check_answer
from wcb.grade.judge import VERDICTS, Judge, match_tokens
from wcb.grade.matching import match_items
from wcb.util.dates import business_days_between, date_of, normalize_date_text
from wcb.util.text import normalize

ACTIVE = frozenset({"open", "waiting", "blocked"})

#: Artifact IDs look like `em-0193` (docs/formats.md, conventions).
ARTIFACT_RE = re.compile(r"^[a-z]{2}-[A-Za-z0-9-]+$")
#: Store records live in these directories (contract/CONTRACT.md §1).
RECORD_DIRS = ("people", "orgs", "projects", "loops", "logs")
#: Extra surface forms that always mean the worker.
WORKER_ALIASES = ("me", "myself", "you", "yourself", "people/me")

_WORD = re.compile(r"[a-z0-9]+")


def _phrase(s: str) -> tuple[str, ...]:
    return tuple(_WORD.findall(normalize(s)))


# ---------------------------------------------------------------- context
@dataclass
class ScoreContext:
    """Everything about the world a grader needs besides the question itself.

    Attributes:
        alias_table: normalized surface form -> entity IDs (`World.alias_table()`).
        entities: the gold state's `entities` at the checkpoint (names, kinds, attributes).
        worker: the worker's entity ID.
        date: the checkpoint date, `YYYY-MM-DD` (gives the default year for dates in answers).
        delivered: artifact IDs delivered by the checkpoint.
        store_root: the store the answers were produced from, for store-path citations.
    """

    alias_table: dict[str, set[str]]
    entities: dict
    worker: str
    date: str
    delivered: set[str]
    store_root: Path | None = None
    _index: dict[tuple[str, ...], set[str]] | None = field(
        default=None, init=False, repr=False, compare=False
    )

    @classmethod
    def from_state(cls, world: Any, state: dict, *, store_root: Path | None = None) -> ScoreContext:
        """Build a context from a `wcb.world.model.World` and its gold state at the checkpoint."""
        return cls(
            alias_table=world.alias_table(),
            entities=state["entities"],
            worker=state["worker"],
            date=state["date"],
            delivered=set(state.get("delivered") or []),
            store_root=Path(store_root) if store_root else None,
        )

    @property
    def year(self) -> int:
        return int(str(self.date)[:4])

    def _alias_index(self) -> dict[tuple[str, ...], set[str]]:
        """Alias phrases as token tuples -> entity IDs (built once)."""
        if self._index is None:
            index: dict[tuple[str, ...], set[str]] = {}
            forms = [(k, ids) for k, ids in self.alias_table.items()]
            forms += [(a, {self.worker}) for a in WORKER_ALIASES]
            for form, ids in forms:
                ph = _phrase(form)
                variants = [ph] + ([ph[1:]] if len(ph) > 1 and ph[0] == "the" else [])
                for v in variants:
                    if v:
                        index.setdefault(v, set()).update(ids)
            self._index = index
        return self._index

    def alias_ids(self, text: str | None) -> set[str]:
        """Entity IDs whose alias is exactly `text` (as a whole phrase); empty if none."""
        return set(self._alias_index().get(_phrase(str(text or "")), set()))

    def resolve_entities(self, text: str | None) -> set[str]:
        """Entity IDs unambiguously named in `text`.

        Every alias occurrence is found as a whole phrase. Longer occurrences win over the
        shorter ones they contain ("Sam Patel" over "Sam"). An occurrence whose alias belongs to
        several entities resolves to nothing, so a bare shared first name names no one.
        """
        if not text:
            return set()
        index = self._alias_index()
        toks = _phrase(str(text))
        longest = max((len(k) for k in index), default=0)
        hits = []
        for start in range(len(toks)):
            for n in range(min(longest, len(toks) - start), 0, -1):
                ids = index.get(tuple(toks[start : start + n]))
                if ids:
                    hits.append((n, start, ids))
        taken: set[int] = set()
        out: set[str] = set()
        for n, start, ids in sorted(hits, key=lambda h: (-h[0], h[1])):
            span = set(range(start, start + n))
            if span & taken:
                continue
            taken |= span
            if len(ids) == 1:
                out |= ids
        return out

    def entity_kind(self, eid: str) -> str:
        """'person', 'org' or 'project' for an entity ID (from gold state, else its prefix)."""
        kind = (self.entities.get(eid) or {}).get("kind")
        if kind:
            return kind
        if eid.startswith("pr-"):
            return "project"
        return {"p": "person", "o": "org"}.get(eid.split("-", 1)[0], "")


# ---------------------------------------------------------------- result
@dataclass
class QuestionScore:
    """The grade of one answer. `details` holds per-type diagnostics for reports."""

    id: str
    type: str
    template: str
    answerable: bool
    challenges: list[str]
    valid: bool
    abstained: bool
    base: float  # q in [0, 1] before citations
    citation: float | None  # c, or None when not applicable (abstentions, invalid answers)
    score: float  # final
    details: dict

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- entry points
def score_answers(
    gold_doc: dict, answers: dict, judge: Judge, ctx: ScoreContext
) -> list[QuestionScore]:
    """Grade every question of a gold checkpoint document (`gold/questions/<cp>.json`)."""
    answers = answers if isinstance(answers, dict) else {}
    return [
        score_question(q, answers.get(q["id"]), judge, ctx) for q in gold_doc.get("questions", [])
    ]


def score_question(q: dict, answer: dict | None, judge: Judge, ctx: ScoreContext) -> QuestionScore:
    """Grade one answer (None when missing) against one gold question."""
    qtype = q["type"]
    answerable = bool(q.get("answerable", True))

    def result(
        *,
        valid: bool,
        abstained: bool,
        base: float,
        citation: float | None,
        score: float,
        details: dict,
    ):
        return QuestionScore(
            id=q["id"],
            type=qtype,
            template=q.get("template", ""),
            answerable=answerable,
            challenges=list(q.get("challenges") or []),
            valid=valid,
            abstained=abstained,
            base=base,
            citation=citation,
            score=score,
            details=details,
        )

    if answer is None:
        return result(
            valid=False,
            abstained=False,
            base=0.0,
            citation=None,
            score=0.0,
            details={"problems": ["missing answer"]},
        )
    problems = check_answer(answer, qtype)
    if problems:
        return result(
            valid=False,
            abstained=False,
            base=0.0,
            citation=None,
            score=0.0,
            details={"problems": problems},
        )
    abstained = bool(answer.get("abstain"))
    if not answerable:
        s = 1.0 if abstained else 0.0
        note = "correct abstention" if abstained else "answered an unanswerable question"
        return result(
            valid=True, abstained=abstained, base=s, citation=None, score=s, details={"note": note}
        )
    if abstained:
        return result(
            valid=True,
            abstained=True,
            base=0.0,
            citation=None,
            score=0.0,
            details={"note": "abstained on an answerable question"},
        )

    base, details = GRADERS[qtype](q, answer, judge, ctx)
    c, cite_details = citation_precision(answer, q.get("support") or [], ctx)
    details["citations"] = cite_details
    return result(
        valid=True,
        abstained=False,
        base=base,
        citation=c,
        score=base * (0.75 + 0.25 * c),
        details=details,
    )


# ---------------------------------------------------------------- point
def grade_point(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """1 if the value matches the gold value for its kind, else 0.

    * entity: the value names exactly the gold entity among entities of the same kind (so
      "Cora Velez (Tessellate)" is fine for a person, "Sam" or "Cora or Ben" is not);
    * date: `normalize_date_text` with the checkpoint year as default equals the gold date;
    * number: numeric equality after stripping currency and commas (`k`/`m` suffixes allowed);
    * text: normalized equality, or every content token of the gold value is in the answer.

    For every kind, normalized equality with the gold value or an `accept` string also counts,
    except that an accept string that is an alias of several entities (a shared first name)
    never counts for an entity question.
    """
    gold = q.get("gold") or {}
    kind = gold.get("kind", "text")
    raw = answer.get("value")
    text = "" if raw is None else str(raw)
    accept = [str(a) for a in [gold.get("value"), *(gold.get("accept") or [])] if a is not None]
    details: dict[str, Any] = {"kind": kind, "value": raw, "gold": gold.get("value")}
    if kind == "entity":
        accept = [a for a in accept if len(ctx.alias_ids(a)) <= 1]
    ok = any(normalize(text) == normalize(a) for a in accept)
    if not ok and kind == "entity" and gold.get("entity"):
        want = gold["entity"]
        kind_of = ctx.entity_kind(want)
        resolved = {e for e in ctx.resolve_entities(text) if ctx.entity_kind(e) == kind_of}
        details["resolved"] = sorted(resolved)
        ok = resolved == {want}
    elif not ok and kind == "date":
        got = normalize_date_text(text, default_year=ctx.year)
        details["normalized"] = got
        ok = got is not None and got == date_of(str(gold.get("value")))
    elif not ok and kind == "number":
        got, want_n = parse_number(raw), parse_number(gold.get("value"))
        details["normalized"] = got
        ok = (
            got is not None
            and want_n is not None
            and math.isclose(got, want_n, rel_tol=1e-9, abs_tol=1e-9)
        )
    elif not ok and kind in ("text", "entity"):
        have = match_tokens(text)
        ok = any(match_tokens(a) and match_tokens(a) <= have for a in accept)
    return (1.0 if ok else 0.0), details


_NUMBER = re.compile(r"(-?\d+(?:\.\d+)?)\s*(thousand|million|billion|mm|bn|k|m|b)?\b")
_MULT = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mm": 1e6,
    "million": 1e6,
    "b": 1e9,
    "bn": 1e9,
    "billion": 1e9,
}


def parse_number(value: Any) -> float | None:
    """First number in a value, with currency symbols and thousands separators ignored.

    `'$180k'`, `'180,000 USD'` and `180000` all give 180000.0; `'1.2m'` gives 1200000.0.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = re.sub(r"(?<=\d),(?=\d)", "", str(value).lower())
    m = _NUMBER.search(s)
    if not m:
        return None
    return float(m.group(1)) * _MULT.get(m.group(2) or "", 1.0)


# ---------------------------------------------------------------- list
def status_credit(pred: Any, gold: Any) -> float:
    """1 for the same status; 0.5 if both are active (open/waiting/blocked); else 0."""
    if pred == gold and pred is not None:
        return 1.0
    if pred in ACTIVE and gold in ACTIVE:
        return 0.5
    return 0.0


def due_credit(pred: Any, gold: Any) -> float:
    """1 if both due dates are absent or they are the same date; else 0."""
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    return 1.0 if date_of(str(pred)) == date_of(str(gold)) else 0.0


def counterparty_credit(pred: Any, gold: Any, ctx: ScoreContext) -> float | None:
    """1 if the predicted name resolves to the gold counterparty; None if gold has none."""
    if not gold:
        return None
    return 1.0 if isinstance(pred, str) and gold in ctx.resolve_entities(pred) else 0.0


def attribute_credit(pred: dict, gold: dict, ctx: ScoreContext) -> tuple[float, dict]:
    """Mean of status, due and counterparty credit (counterparty skipped when gold has none)."""
    parts = {
        "status": status_credit(pred.get("status"), gold.get("status")),
        "due": due_credit(pred.get("due"), gold.get("due")),
        "counterparty": counterparty_credit(
            pred.get("counterparty"), gold.get("counterparty"), ctx
        ),
    }
    graded = [v for v in parts.values() if v is not None]
    return sum(graded) / len(graded), parts


def f1(p: float, r: float) -> float:
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def _empty_case(n_pred: int, n_gold: int) -> float | None:
    """Score when either side is empty: 1 if both are, 0 if only one is, None otherwise."""
    if n_pred == 0 and n_gold == 0:
        return 1.0
    if n_pred == 0 or n_gold == 0:
        return 0.0
    return None


def grade_list(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """Soft F1: P = sum(a) / predicted, R = sum(a) / gold, a = attribute credit per match."""
    pred, gold = list(answer.get("items") or []), list((q.get("gold") or {}).get("items") or [])
    early = _empty_case(len(pred), len(gold))
    if early is not None:
        return early, {"n_pred": len(pred), "n_gold": len(gold), "matches": []}
    pairs = match_items(pred, gold, judge, kind="loop", ctx=ctx)
    matches, total = [], 0.0
    for i, j in pairs:
        a, parts = attribute_credit(pred[i], gold[j], ctx)
        total += a
        matches.append({"pred": i, "gold": gold[j].get("loop", j), "credit": a, **parts})
    p, r = total / len(pred), total / len(gold)
    matched_pred, matched_gold = {i for i, _ in pairs}, {j for _, j in pairs}
    return f1(p, r), {
        "n_pred": len(pred),
        "n_gold": len(gold),
        "precision": p,
        "recall": r,
        "matches": matches,
        "unmatched_pred": [i for i in range(len(pred)) if i not in matched_pred],
        "unmatched_gold": [g.get("loop", j) for j, g in enumerate(gold) if j not in matched_gold],
    }


# ---------------------------------------------------------------- status / brief
def answer_text(answer: dict) -> str:
    """The text a rubric is checked against: the summary followed by every claim's text."""
    parts = [answer.get("summary") or ""]
    parts += [c.get("text", "") for c in answer.get("claims") or [] if isinstance(c, dict)]
    return "\n".join(p for p in parts if p)


def grade_rubric(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """max(0, (sum w*covered - sum w*contradicted) / sum w) over the checklist."""
    gold = q.get("gold") or {}
    items, facts = gold.get("rubric") or [], gold.get("facts") or {}
    text = answer_text(answer)
    verdicts, total, net = [], 0.0, 0.0
    for item in items:
        w = float(item.get("weight", 1))
        v = judge.rubric(text, item, facts)
        v = v if v in VERDICTS else "missing"
        total += w
        net += w if v == "covered" else (-w if v == "contradicted" else 0.0)
        verdicts.append({"item": item.get("id"), "weight": w, "verdict": v})
    score = 1.0 if total == 0 else max(0.0, net / total)
    return score, {"verdicts": verdicts}


# ---------------------------------------------------------------- change
def grade_change(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """F1 over one-to-one matched change items."""
    pred, gold = list(answer.get("items") or []), list((q.get("gold") or {}).get("items") or [])
    early = _empty_case(len(pred), len(gold))
    if early is not None:
        return early, {"n_pred": len(pred), "n_gold": len(gold), "matches": []}
    pairs = match_items(pred, gold, judge, kind="change", ctx=ctx)
    p, r = len(pairs) / len(pred), len(pairs) / len(gold)
    matched_gold = {j for _, j in pairs}
    return f1(p, r), {
        "n_pred": len(pred),
        "n_gold": len(gold),
        "precision": p,
        "recall": r,
        "matches": [{"pred": i, "gold": gold[j].get("event", j)} for i, j in pairs],
        "unmatched_gold": [g.get("event", j) for j, g in enumerate(gold) if j not in matched_gold],
    }


# ---------------------------------------------------------------- temporal
def grade_temporal(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """1 for the exact date, 0.5 within one business day, else 0."""
    want = (q.get("gold") or {}).get("date")
    got = answer.get("date")
    details = {"date": got, "gold": want}
    if not want or not got:
        return 0.0, details
    if date_of(got) == date_of(want):
        return 1.0, details
    off = abs(business_days_between(date_of(want), date_of(got)))
    details["business_days_off"] = off
    return (0.5 if off <= 1 else 0.0), details


# ---------------------------------------------------------------- priority
def priority_gold(gold: dict) -> tuple[list[dict], list[str]]:
    """One combined gold list (must_include, then worker_active, then distractors) and roles.

    A loop listed twice (every must-include loop is also worker-active) is kept once, in its
    first and most important role. Roles are 'must', 'active' or 'distractor'.
    """
    items, roles, seen = [], [], set()
    for role, key in (
        ("must", "must_include"),
        ("active", "worker_active"),
        ("distractor", "distractors"),
    ):
        for it in gold.get(key) or []:
            ident = it.get("loop") or id(it)
            if ident in seen:
                continue
            seen.add(ident)
            items.append(it)
            roles.append(role)
    return items, roles


def grade_priority(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """recall(must_include in top k) x (1 - share of top items that match a distractor)."""
    gold = q.get("gold") or {}
    k = int(gold.get("k") or 10)
    top = list(answer.get("items") or [])[:k]
    combined, roles = priority_gold(gold)
    n_must = roles.count("must")
    pairs = match_items(top, combined, judge, kind="loop", ctx=ctx) if top and combined else []
    hit_must = sum(1 for _, j in pairs if roles[j] == "must")
    hit_distractor = sum(1 for _, j in pairs if roles[j] == "distractor")
    recall = 1.0 if n_must == 0 else hit_must / n_must
    penalty = 0.0 if not top else hit_distractor / len(top)
    matched = {j for _, j in pairs}
    return recall * (1 - penalty), {
        "k": k,
        "n_top": len(top),
        "recall": recall,
        "penalty": penalty,
        "matches": [
            {"pred": i, "gold": combined[j].get("loop", j), "role": roles[j]} for i, j in pairs
        ],
        "missed_must": [
            it.get("loop", j)
            for j, it in enumerate(combined)
            if roles[j] == "must" and j not in matched
        ],
    }


GRADERS = {
    "point": grade_point,
    "list": grade_list,
    "status": grade_rubric,
    "brief": grade_rubric,
    "change": grade_change,
    "temporal": grade_temporal,
    "priority": grade_priority,
}


# ---------------------------------------------------------------- citations
def collect_cites(answer: dict) -> list[str]:
    """Every cite in an answer: top-level `cites`, then `items[].cites`, then `claims[].cites`."""
    out = [c for c in answer.get("cites") or [] if isinstance(c, str)]
    for key in ("items", "claims"):
        for part in answer.get(key) or []:
            if isinstance(part, dict):
                out += [c for c in part.get("cites") or [] if isinstance(c, str)]
    return out


def store_record_id(cite: str) -> str | None:
    """Normalize a store-path cite to a record ID, e.g. './loops/x.md' -> 'loops/x'.

    Accepts `loops/x`, `loops/x.md`, `./loops/x.md`, `[[loops/x]]` and `loops/x#Log`. Returns
    None when the cite cannot name a record (wrong top directory, `..`, empty parts).
    """
    s = cite.strip()
    if s.startswith("[[") and s.endswith("]]"):
        s = s[2:-2]
    s = s.split("#", 1)[0].strip()
    while s.startswith("./"):
        s = s[2:]
    s = s.lstrip("/")
    if s.endswith(".md"):
        s = s[:-3]
    parts = s.split("/")
    if len(parts) < 2 or parts[0] not in RECORD_DIRS or any(p in ("", ".", "..") for p in parts):
        return None
    return s


def cite_status(cite: str, support: set[str], ctx: ScoreContext) -> str:
    """'valid', or why not: 'not_in_support', 'not_delivered', 'no_such_record', 'unrecognized'."""
    if ARTIFACT_RE.match(cite):
        if cite in support:
            return "valid"
        return "not_in_support" if cite in ctx.delivered else "not_delivered"
    rid = store_record_id(cite)
    if rid is None or ctx.store_root is None:
        return "unrecognized"
    return "valid" if (Path(ctx.store_root) / f"{rid}.md").is_file() else "no_such_record"


def citation_precision(answer: dict, support: list[str], ctx: ScoreContext) -> tuple[float, dict]:
    """c = valid cites / all cites, 0 when there are none; plus per-cite diagnostics."""
    cites = collect_cites(answer)
    sup = set(support)
    statuses = [(c, cite_status(c, sup, ctx)) for c in cites]
    valid = sum(1 for _, s in statuses if s == "valid")
    c = valid / len(cites) if cites else 0.0
    return c, {
        "total": len(cites),
        "valid": valid,
        "invalid": [{"cite": c_, "why": s} for c_, s in statuses if s != "valid"],
    }
