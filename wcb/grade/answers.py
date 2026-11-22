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
   | priority | must-include recall in the top k x (1 - share of top loop items that are distractors) |

5. **Citations.** `c` = valid cites / counted cites (0 when there are none). For list and
   change answers each predicted item's cites are checked against the support of the gold
   item it matched (the question's support when it matched none) and counted once per item;
   top-level cites are checked against the question's support. Other types pool all cites,
   count each source once and check it against the question's support. A cite is valid if it
   is an artifact ID in that support, or (Track A) names an existing record other than
   `people/me` in the store the answers were produced from whose text cites one of those
   artifacts (`citation_precision`). Final score = `q x (0.75 + 0.25 x c)`. When the
   question's `support` is empty (an answerable empty list, nothing due tomorrow) there is
   nothing to cite: `c` is None and the score is `q`.

A valid answer that makes a grader raise a value error scores 0 with a `grader_error` detail
instead of stopping the run; errors raised by the judge itself still propagate.

Entity names are resolved with `ScoreContext.resolve_entities`: whole-phrase, case- and
accent-insensitive lookups in the world's alias table, where an alias shared by several
entities (two people called "Sam") resolves to nothing. Point answers also look at how a
value is framed (`wcb.util.text.framing`): a value after "from", "was", "not", "previously"
and similar words is history, not the answer.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from wcb.contract.answers import check_answer
from wcb.grade.citation_evidence import additional_sources
from wcb.grade.judge import VERDICTS, Judge, match_tokens, padding_penalty
from wcb.grade.matching import assign, confirmed_edges, distinct_edges, match_items
from wcb.questions.rubric import LOOP_STATUS_WORDS, STATUS_SYNONYMS
from wcb.util.dates import (
    business_days_between,
    date_mentions,
    date_of,
    leading_date,
    normalize_date_text,
)
from wcb.util.text import (
    CLAUSE_BREAKS,
    CURRENT_MARKERS,
    HISTORY_MARKERS,
    framing,
    marked_tokens,
    negated,
    normalize,
    normalize_marked,
    phrase_spans,
)

ACTIVE = frozenset({"open", "waiting", "blocked"})

#: Artifact IDs look like `em-0193` (docs/formats.md, conventions).
ARTIFACT_RE = re.compile(r"^[a-z]{2}-[A-Za-z0-9-]+$")
#: Store records live in these directories (contract/CONTRACT.md §1).
RECORD_DIRS = ("people", "orgs", "projects", "loops", "logs")
#: The worker's own record (contract/CONTRACT.md §2.1).
WORKER_RECORD = "people/me"
#: Pronouns that mean the worker. Inside a longer answer, one that follows a preposition
#: ("took it over from you", "owes it to me") is context, not the answer.
WORKER_PRONOUNS = ("me", "myself", "you", "yourself")
#: Extra surface forms that always mean the worker.
WORKER_ALIASES = (*WORKER_PRONOUNS, "people/me")
PREPOSITIONS = frozenset({"to", "from", "with", "by", "for", "of", "about", "over"})
#: Words that make a free-text point answer a hedge, unless the gold value has them too.
HEDGE_WORDS = frozenset("or either maybe perhaps possibly probably unclear unsure".split())
#: A text point answer may add at most this many unsupported content words per word of the
#: gold value (see `text_matches`), and at least `TEXT_MIN_EXTRA` in all.
TEXT_EXTRA_RATIO = 0.5
TEXT_MIN_EXTRA = 1
#: Words that say where a fact is kept rather than state one ("the store records her as ...").
PROVENANCE_WORDS = frozenset("alias aliases aka record records recorded store stored listed".split())
#: Pronouns that stand for a person subject.
PERSON_PRONOUNS = frozenset("he him his she her hers they them their".split())
#: Words naming the fields of a subject's record, by kind ("target date 16 August"), and the
#: kinds of entity it links to ("she leads Saltmarren's side of the scheduling project").
FIELD_LABELS = {
    "person": frozenset("role title organization org relationship project".split()),
    "project": frozenset(
        "project phase stage status target date owner owned sponsor sponsored blocker next step "
        "organization org".split()
    ),
}
#: Project phases that mean the project is over; the `done` status synonyms also name them.
TERMINAL_PHASES = frozenset({"closed", "done"})
#: Artifact-ID-like tokens in a store record's text.
ARTIFACT_IN_TEXT = re.compile(r"(?<![A-Za-z0-9-])[a-z]{2}-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
#: Errors a grader may raise on an odd but valid answer; they score the question 0.
GRADER_ERRORS = (ValueError, TypeError, ArithmeticError)

_WORD = re.compile(r"[a-z0-9]+")


def _phrase(s: str) -> tuple[str, ...]:
    return tuple(_WORD.findall(normalize(s)))


def framed_words(text: str | None) -> tuple[list[str], list[str]]:
    """The words of `text` (as `_phrase` splits them) and the framing in force at each word.

    The framing is 'history' after a `HISTORY_MARKERS` word ("from", "was", "not", ...),
    'current' after a `CURRENT_MARKERS` word ("to", "now", "->"), and '' otherwise; it resets
    at clause punctuation. Marker words are kept in the word list (they can be part of a name)
    and get the framing in force before them.
    """
    words: list[str] = []
    roles: list[str] = []
    role = ""
    for tok, _, _ in marked_tokens(normalize_marked(text)):
        if tok in CLAUSE_BREAKS:
            role = ""
            continue
        if _WORD.fullmatch(tok):
            words.append(tok)
            roles.append(role)
        if tok in HISTORY_MARKERS:
            role = "history"
        elif tok in CURRENT_MARKERS:
            role = "current"
    return words, roles


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
    #: Delivered artifact ID -> entities, loops and decisions its knowable events are about.
    about: dict[str, set[str]] = field(default_factory=dict)
    track: str = "A"
    world: Any = field(default=None, repr=False, compare=False)
    _index: dict[tuple[str, ...], set[str]] | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _records: dict[str, set[str] | None] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    @classmethod
    def from_state(cls, world: Any, state: dict, *, store_root: Path | None = None, track: str = "A") -> ScoreContext:
        """Build a context from a `wcb.world.model.World` and its gold state at the checkpoint."""
        return cls(
            alias_table=world.alias_table(),
            entities=state["entities"],
            worker=state["worker"],
            date=state["date"],
            delivered=set(state.get("delivered") or []),
            store_root=Path(store_root) if store_root else None,
            about=artifact_subjects(state),
            track=track, world=world,
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

    def mentions(self, words: list[str]) -> list[tuple[int, int, set[str]]]:
        """Alias occurrences in a word sequence: (start, end, entity IDs), in text order.

        Every alias occurrence is found as a whole phrase. Longer occurrences win over the
        shorter ones they contain ("Sam Patel" over "Sam"). An occurrence of an alias shared by
        several entities is kept with all their IDs.
        """
        index = self._alias_index()
        longest = max((len(k) for k in index), default=0)
        hits = []
        for start in range(len(words)):
            for n in range(min(longest, len(words) - start), 0, -1):
                ids = index.get(tuple(words[start : start + n]))
                if ids:
                    hits.append((n, start, ids))
        taken: set[int] = set()
        out = []
        for n, start, ids in sorted(hits, key=lambda h: (-h[0], h[1])):
            span = set(range(start, start + n))
            if span & taken:
                continue
            taken |= span
            out.append((start, start + n, ids))
        return sorted(out, key=lambda m: m[0])

    def resolve_entities(self, text: str | None) -> set[str]:
        """Entity IDs unambiguously named in `text`.

        See `mentions`. An occurrence whose alias belongs to several entities resolves to
        nothing, so a bare shared first name names no one.
        """
        if not text:
            return set()
        out: set[str] = set()
        for _, _, ids in self.mentions(list(_phrase(str(text)))):
            if len(ids) == 1:
                out |= ids
        return out

    def answer_entities(self, text: str | None) -> set[str]:
        """Entities a point answer gives as its value.

        Like `resolve_entities`, but a mention framed as history ("from Sam Reyes", "not
        Cora", "previously Ben") is skipped, and so is a worker pronoun after a preposition
        ("took it over from you", "owes it to me"), which is context rather than a name.
        """
        words, roles = framed_words(text)
        out: set[str] = set()
        for start, end, ids in self.mentions(words):
            if len(ids) != 1 or roles[start] == "history":
                continue
            phrase = " ".join(words[start:end])
            if phrase in WORKER_PRONOUNS and start > 0 and words[start - 1] in PREPOSITIONS:
                continue
            out |= ids
        return out

    def names_exactly(self, text: str | None, want: str) -> bool:
        """True if `text` gives entity `want` and no rival for it as its value.

        Among entities of `want`'s kind, `answer_entities` must be exactly {`want`}, and no
        alias shared by several such entities may occur unless `want` is one of them: "Cora
        Velez or Sam" hedges between Cora and a Sam even though "Sam" alone names no one.
        Mentions framed as history ("from Sam Reyes") do not count.
        """
        kind = self.entity_kind(want)
        if {e for e in self.answer_entities(text) if self.entity_kind(e) == kind} != {want}:
            return False
        words, roles = framed_words(text)
        for start, _, ids in self.mentions(words):
            same_kind = {e for e in ids if self.entity_kind(e) == kind}
            if len(same_kind) > 1 and want not in same_kind and roles[start] != "history":
                return False
        return True

    def record_refs(self, rid: str) -> set[str] | None:
        """Artifact-ID-like tokens in store record `rid`'s text; None if it does not exist."""
        if rid not in self._records:
            refs: set[str] | None = None
            if self.store_root is not None:
                path = Path(self.store_root) / f"{rid}.md"
                try:
                    refs = set(ARTIFACT_IN_TEXT.findall(path.read_text(encoding="utf-8")))
                except (OSError, UnicodeDecodeError, ValueError):
                    refs = None
            self._records[rid] = refs
        return self._records[rid]

    def entity_kind(self, eid: str) -> str:
        """'person', 'org' or 'project' for an entity ID (from gold state, else its prefix)."""
        kind = (self.entities.get(eid) or {}).get("kind")
        if kind:
            return kind
        if eid.startswith("pr-"):
            return "project"
        return {"p": "person", "o": "org"}.get(eid.split("-", 1)[0], "")


def artifact_subjects(state: dict) -> dict[str, set[str]]:
    """Artifact ID -> what its knowable events are about: their `subjects` (entities, loops,
    decisions) and `project`, from the gold state's event list."""
    out: dict[str, set[str]] = {}
    for ev in state.get("events") or []:
        about = {str(x) for x in ev.get("subjects") or []}
        if ev.get("project"):
            about.add(str(ev["project"]))
        for a in ev.get("artifacts") or []:
            out.setdefault(a, set()).update(about)
    return out


def question_subjects(q: dict) -> set[str]:
    """The objects a question is about (`params`: project, person, commitment, decision)."""
    params = q.get("params") or {}
    return {
        str(params[k]) for k in ("project", "person", "commitment", "decision") if params.get(k)
    }


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
    citation: float | None  # c, or None when not applicable (abstentions, invalid answers,
    # questions with empty support, grader errors)
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
    if abstained and q.get("gold", {}).get("uncertain"):
        return result(valid=True, abstained=True, base=1.0, citation=None, score=1.0,
                      details={"note": "source evidence is inconclusive"})
    if abstained:
        return result(
            valid=True,
            abstained=True,
            base=0.0,
            citation=None,
            score=0.0,
            details={"note": "abstained on an answerable question"},
        )

    watched = _WatchedJudge(judge)
    try:
        base, details = GRADERS[qtype](q, answer, watched, ctx)
        c, cite_details = citation_precision(
            answer,
            q.get("support") or [],
            ctx,
            item_support=matched_item_support(q, details),
            subjects=question_subjects(q),
            extra=additional_sources(q, answer, details, ctx),
        )
    except GRADER_ERRORS as e:
        if watched.raised:
            raise
        return result(
            valid=True,
            abstained=False,
            base=0.0,
            citation=None,
            score=0.0,
            details={"grader_error": f"{type(e).__name__}: {e}"},
        )
    details["citations"] = cite_details
    return result(
        valid=True,
        abstained=False,
        base=base,
        citation=c,
        score=base if c is None else base * (0.75 + 0.25 * c),
        details=details,
    )


class _WatchedJudge:
    """Passes calls through to a judge and remembers whether one raised.

    `score_question` scores a question 0 when its grader raises on an odd answer, but a
    failing judge (an unreachable model, say) must still stop the run.
    """

    def __init__(self, judge: Judge):
        self._judge = judge
        self.name = getattr(judge, "name", "")
        self.raised = False

    def same_item(self, pred: dict, gold: dict, *, kind: str) -> bool:
        try:
            return self._judge.same_item(pred, gold, kind=kind)
        except BaseException:
            self.raised = True
            raise

    def rubric(self, answer_text: str, item: dict, facts: dict) -> str:
        try:
            return self._judge.rubric(answer_text, item, facts)
        except BaseException:
            self.raised = True
            raise

    def __getattr__(self, name: str) -> Any:
        """Optional judge methods (`point`), watched the same way."""
        fn = getattr(self._judge, name)

        def call(*a: Any, **k: Any) -> Any:
            try:
                return fn(*a, **k)
            except BaseException:
                self.raised = True
                raise

        return call


# ---------------------------------------------------------------- point
def grade_point(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """1 if the value matches the gold value for its kind, else 0.

    * entity: among entities of the gold one's kind, the answer names exactly the gold entity
      (`ScoreContext.names_exactly`). "Cora Velez (Tessellate)" and "Cora Velez (took it
      over from Sam Reyes)" are fine for a person; "Sam", "Cora or Ben", "Cora or Sam" are
      not.
    * date: the value comes first. A value that leads with a date (`leading_date`:
      "2027-02-05 (moved from 29 Jan on 12 Jan)") gives that date, unless it has a hedge
      word; otherwise `normalize_date_text` (the one current date in the text). A year-less
      date takes the year that puts it from three months before to nine months after the
      checkpoint. The date must equal the gold date.
    * number: `parse_number` (the one current number; labels such as Q3 or FY2027 and values
      framed as history are skipped) equals the gold number.
    * text, project `status` (`project_attr` with `attribute: status`): the answer names
      exactly the gold status among the statuses' synonyms, not counting ones framed as
      history ("active, not paused"); hedge words fail.
    * other text: see `text_matches`; the answer must also not state a rival value of the
      attribute (`stated_rival`: another entity's value, or the subject's earlier one). A
      project's phase that means it is over (`TERMINAL_PHASES`) also accepts the synonyms of
      the `done` status ("complete", "finished") when the project's status is done.

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
    if gold.get("uncertain") and q.get("template") == "person_attr":
        accept += ["unknown", "not specified", "not stated", "unknown from the inputs"]
    if kind == "entity":
        accept = [a for a in accept if len(ctx.alias_ids(a)) <= 1]
    if kind == "text" and is_terminal_phase(q, ctx):
        accept += [s for s in STATUS_SYNONYMS["done"] if s not in accept]
    ok = any(normalize(text) == normalize(a) for a in accept)
    if not ok and kind == "entity" and gold.get("entity"):
        want = gold["entity"]
        kind_of = ctx.entity_kind(want)
        resolved = {e for e in ctx.answer_entities(text) if ctx.entity_kind(e) == kind_of}
        details["resolved"] = sorted(resolved)
        ok = ctx.names_exactly(text, want)
    elif not ok and kind == "date":
        lead = None if hedge_words(text) else leading_date(text, today=ctx.date)
        got = lead or normalize_date_text(text, today=ctx.date)
        details["normalized"] = got
        if lead is not None:
            details["leading"] = True
        ok = got is not None and got == date_of(str(gold.get("value")))
    elif not ok and kind == "number":
        got, want_n = parse_number(raw), parse_number(gold.get("value"))
        details["normalized"] = got
        ok = (
            got is not None
            and want_n is not None
            and math.isclose(got, want_n, rel_tol=1e-9, abs_tol=1e-9)
        )
    elif not ok and is_status_question(q) and normalize(str(gold.get("value"))) in STATUS_SYNONYMS:
        named = statuses_named(text)
        details["statuses"] = sorted(named)
        ok = named == {normalize(str(gold.get("value")))} and not hedge_words(text)
    elif not ok and kind in ("text", "entity"):
        support = point_support(q, ctx)
        ok = any(text_matches(text, a, q, ctx, support=support) for a in accept)
        rival = stated_rival(text, accept, q, ctx, support=support) if ok and kind == "text" else None
        if rival is not None:
            details["rival"] = rival
            ok = False
    if not ok and q.get("template") == "person_attr" and q.get("params", {}).get("attribute") == "relationship":
        ok = relationship_matches(text, str(gold.get("value")))
    if not ok and kind == "text" and text.strip() and hasattr(judge, "point"):
        ok = bool(
            judge.point(str(q.get("text") or ""), str(gold.get("value")), text, point_facts(q, ctx))
        )
        details["judge"] = ok
    return (1.0 if ok else 0.0), details


# Descriptions used by people answering without the store's taxonomy. Match complete
# descriptions; leave more complex prose and ambiguous reporting lines to the panel.
RELATIONSHIP_DESCRIPTIONS = {
    "peer": r"(?:a )?(?:teammate|team[- ]mate|fellow team member|colleague (?:in|on|from) "
            r"(?:my|our|the) (?:own |same )?(?:org(?:anization)?|team|department)|"
            r"same[- ]team colleague|cross-portfolio colleague and collaborator)",
    "stakeholder": r"(?:an? )?(?:cross[- ]department(?:al)? (?:collaborator|counterpart)|"
                   r"departmental counterpart|client counterpart|external project stakeholder)",
    "manager": r"(?:my |the worker.s )(?:manager|direct supervisor|line manager|boss)",
    "report": r"(?:my direct report|reports (?:directly )?to me)",
    "executive": r"(?:an? )?(?:senior executive|executive sponsor|member of (?:the )?executive leadership)",
    "vendor": r"(?:an? )?(?:vendor representative|supplier representative|external supplier)",
}


def relationship_matches(text: str, value: str) -> bool:
    pattern = RELATIONSHIP_DESCRIPTIONS.get(value)
    if not pattern or hedge_words(text):
        return False
    # A trailing qualification may identify the colleague's role or organization.
    head, _, tail = re.split(r"(:| \(| at )", normalize(text).rstrip(". "), maxsplit=1) if re.search(
        r":| \(| at ", normalize(text)) else (normalize(text).rstrip(". "), "", "")
    if re.search(r"\b(?:or|instead|actually|but|not|my manager|my boss|my direct report)\b", tail):
        return False
    return re.fullmatch(pattern, head.strip()) is not None


def point_facts(q: dict, ctx: ScoreContext) -> dict:
    """What an LLM judge sees about a point question's subject: its current attributes (entity
    IDs as names) and earlier values of the asked attribute, which are wrong answers."""
    params = q.get("params") or {}
    subject = params.get("project") or params.get("person")
    ent = ctx.entities.get(str(subject)) or {}

    def show(v: Any) -> Any:
        if isinstance(v, list):
            return [show(x) for x in v]
        if isinstance(v, str) and v in ctx.entities:
            return ctx.entities[v].get("name", v)
        return v

    attrs = {k: show(v) for k, v in (ent.get("attrs") or {}).items() if not str(k).startswith("_")}
    attr = params.get("attribute")
    hist = ((ent.get("attr_history") or {}).get(attr) or []) if attr else []
    earlier = [show(h.get("value")) for h in hist[:-1] if isinstance(h, dict)]
    out: dict[str, Any] = {"subject": ent.get("name", subject), "attributes": attrs}
    if earlier:
        out["earlier_values"] = earlier
    return out


def is_status_question(q: dict) -> bool:
    """True for a `project_attr` question about the project's `status`."""
    params = q.get("params") or {}
    return q.get("template") == "project_attr" and params.get("attribute") == "status"


def is_terminal_phase(q: dict, ctx: ScoreContext) -> bool:
    """True for a project's phase that means it is over, when its status is `done`.

    The phase label of a finished project depends on its kind ("closed" for an event, "done"
    for a review), while the sources just say the work is complete.
    """
    params = q.get("params") or {}
    if q.get("template") != "project_attr" or params.get("attribute") != "phase":
        return False
    value = normalize(str((q.get("gold") or {}).get("value") or ""))
    attrs = (ctx.entities.get(str(params.get("project"))) or {}).get("attrs") or {}
    return value in TERMINAL_PHASES and attrs.get("status") == "done"


def statuses_named(text: str) -> set[str]:
    """Project statuses whose name or a synonym occurs in `text`, not framed as history."""
    norm = normalize_marked(text)
    out = set()
    for status, synonyms in STATUS_SYNONYMS.items():
        for form in {status, *synonyms}:
            if any(framing(norm, a) != "history" for a, _ in phrase_spans(norm, form)):
                out.add(status)
    return out


def hedge_words(text: str, *, allowed: str = "") -> set[str]:
    """`HEDGE_WORDS` in `text` ("or", "maybe", ...) that `allowed` does not contain."""
    return (set(_phrase(text)) & HEDGE_WORDS) - set(_phrase(allowed))


def _content(
    text: str, ctx: ScoreContext, *, framed: bool, keep_names: bool = False
) -> tuple[set[str], set[str]]:
    """(content tokens, entity IDs) of a text value, with entity names taken out.

    Names (any alias, even an ambiguous one) are left out of the tokens, unless `keep_names`;
    unambiguous ones are returned as entity IDs. With `framed`, marker words and everything
    framed as history are left out too.
    """
    words, roles = framed_words(text)
    named: set[str] = set()
    skip: set[int] = set()
    for start, end, ids in ctx.mentions(words):
        if not keep_names:
            skip |= set(range(start, end))
        if len(ids) == 1 and not (framed and roles[start] == "history"):
            named |= ids
    toks: set[str] = set()
    for i, w in enumerate(words):
        if i in skip:
            continue
        if framed and (roles[i] == "history" or w in HISTORY_MARKERS or w in CURRENT_MARKERS):
            continue
        toks |= match_tokens(w)
    return toks, named


@dataclass(frozen=True)
class PointSupport:
    """What a text point answer may mention besides the value without it being an extra.

    Attributes:
        tokens: content tokens (`match_tokens`) taken from the subject's record.
        ids: entity IDs from the subject's record.
        org_bound: the subject is a person with a recorded org, so naming another org (not
            framed as history) is wrong, as with "Registrar at Kestrow".
    """

    tokens: frozenset[str] = frozenset()
    ids: frozenset[str] = frozenset()
    org_bound: bool = False


def _org_family(org: Any, ctx: ScoreContext) -> set[str]:
    """An org and the orgs with the same email domain ("SLIO" and "Drayhurst University")."""
    ent = ctx.entities.get(org) if isinstance(org, str) else None
    if ent is None:
        return set()
    domain = (ent.get("attrs") or {}).get("domain")
    return {org} | {
        eid
        for eid, e in ctx.entities.items()
        if domain and e.get("kind") == "org" and (e.get("attrs") or {}).get("domain") == domain
    }


def point_support(q: dict, ctx: ScoreContext) -> PointSupport:
    """The subject's current record in gold state, as context a text answer may add.

    For a `person_attr` or `project_attr` question (empty otherwise), the subject's names and
    aliases plus, by the subject's kind:

    * person: personal pronouns, role and relationship; their org, the orgs with its email
      domain, and all their names; the worker (the other side of the relationship, as in
      "her relationship to me"); the projects the person owns, sponsors or works on, and
      their names;
    * project: phase; owner, sponsor and the project's orgs, and their names.

    The words of the record's field names ("role", "organization", "phase", "target date")
    are included too. Entities named inside a role or phase ("Principal, Integration
    Platform") count as the record's.
    """
    params = q.get("params") or {}
    subject = params.get("person") or params.get("project")
    if q.get("template") not in ("person_attr", "project_attr") or not isinstance(subject, str):
        return PointSupport()
    ent = ctx.entities.get(subject)
    if not ent:
        return PointSupport()
    kind = ent.get("kind") or ctx.entity_kind(subject)
    attrs = ent.get("attrs") or {}
    tokens = set(FIELD_LABELS.get(kind, frozenset()))
    ids = {subject}
    values: list[Any] = []
    org_bound = False
    if kind == "person":
        tokens |= PERSON_PRONOUNS
        values += [attrs.get("role"), attrs.get("relationship")]
        org_bound = bool(_org_family(attrs.get("org"), ctx))
        ids |= _org_family(attrs.get("org"), ctx) | {ctx.worker}
        for pid, p in ctx.entities.items():
            pa = p.get("attrs") or {}
            if p.get("kind") == "project" and (
                subject in (pa.get("owner"), pa.get("sponsor")) or subject in (pa.get("members") or [])
            ):
                ids.add(pid)
    elif kind == "project":
        values.append(attrs.get("phase"))
        ids |= {attrs.get(k) for k in ("owner", "sponsor") if isinstance(attrs.get(k), str)}
        ids |= {o for o in attrs.get("orgs") or [] if isinstance(o, str)}
    for value in values:
        if isinstance(value, str):
            tokens |= match_tokens(value)
            ids |= _content(value, ctx, framed=False)[1]
    for eid in ids:
        e = ctx.entities.get(eid) or {}
        for name in [e.get("name"), *(e.get("surface_forms") or [])]:
            if isinstance(name, str):
                tokens |= match_tokens(name)
    tokens = {t for word in tokens for t in match_tokens(word)}
    return PointSupport(frozenset(tokens), frozenset(ids), org_bound)


_PROVENANCE_TOKENS = frozenset(match_tokens(" ".join(PROVENANCE_WORDS)))
_YEAR_TOKEN = re.compile(r"(19|20)\d{2}")
_WEEKDAY_TOKENS = frozenset(
    match_tokens(
        "monday tuesday wednesday thursday friday saturday sunday "
        "mon tue tues wed weds thu thur thurs fri sat sun"
    )
)


def _date_tokens(text: str) -> set[str]:
    """Tokens of the dates in `text` (`date_mentions`), weekdays and years."""
    norm = normalize_marked(text)
    out = {t for a, b, *_ in date_mentions(norm) for t in match_tokens(norm[a:b])}
    out |= {t for t in match_tokens(norm) if _YEAR_TOKEN.fullmatch(t)}
    return out | _WEEKDAY_TOKENS


def text_matches(
    text: str, value: str, q: dict, ctx: ScoreContext, *, support: PointSupport | None = None
) -> bool:
    """Whether a free-text answer states the text `value` and little that is unsupported.

    Names of people, orgs and projects are compared as entities, not words, so "Registrar"
    and "Registrar at Saltmarren" both state "Registrar, TU Saltmarren". The answer must:

    * contain every content word of the value (`match_tokens`, names aside; when the value is
      only a name, such as an email address, its words);
    * not name, instead of an entity in the value, another entity of the same kind
      ("Registrar at Kestrow"); for a person subject with a recorded org, naming an org
      outside the subject's record is wrong the same way ("Privacy Officer at Larchmont"
      when she is at Kestrow);
    * add at most `TEXT_EXTRA_RATIO` (0.5) unsupported content words or entities per content
      word of the value, and at least `TEXT_MIN_EXTRA` (1);
    * contain no hedge word (`HEDGE_WORDS`: "or", "maybe", ...) the value lacks.

    Supported words cost nothing: words and entities of the question text, of the subject's
    current record (`point_support`: names, org, role, relationship, phase, owner, sponsor,
    ...), dates, weekdays and years, and words saying where a fact is kept
    (`PROVENANCE_WORDS`: "alias", "recorded", "store").

    Words framed as history ("not a solutions engineer", "previously deputy registrar") do not
    count either way, unless the value itself contains marker words.
    """
    support = point_support(q, ctx) if support is None else support
    framed = not (set(_phrase(value)) & (HISTORY_MARKERS | CURRENT_MARKERS))
    want, want_ids = _content(value, ctx, framed=False)
    have, have_ids = _content(text, ctx, framed=framed)
    if not want:  # the value is all names
        want, want_ids = match_tokens(value), set()
        have, _ = _content(text, ctx, framed=framed, keep_names=True)
    if not want or hedge_words(text, allowed=value) or not want <= have:
        return False
    question = str(q.get("text") or "")
    other_ids = have_ids - want_ids - ctx.resolve_entities(question) - support.ids
    anchor_kinds = {ctx.entity_kind(e) for e in want_ids} | ({"org"} if support.org_bound else set())
    if any(ctx.entity_kind(e) in anchor_kinds for e in other_ids):
        return False  # "Registrar at Kestrow" for "Registrar, TU Saltmarren"
    free = match_tokens(question) | support.tokens | _PROVENANCE_TOKENS | _date_tokens(text)
    extra = len(have - want - free) + len(other_ids)
    return extra <= max(TEXT_MIN_EXTRA, TEXT_EXTRA_RATIO * len(want))


def rival_values(q: dict, ctx: ScoreContext) -> list[str]:
    """Other values the asked attribute takes: the rivals a hedging answer would add.

    For a `project_attr` or `person_attr` question, the same attribute of every other entity
    of the subject's kind ("Data engineer" when asking for Sam Reyes's role, which is how a
    name collision is hedged) and the subject's earlier values of it (a superseded phase).
    Empty for other questions.
    """
    params = q.get("params") or {}
    attr = params.get("attribute")
    subject = params.get("project") or params.get("person")
    if q.get("template") not in ("project_attr", "person_attr") or not attr or not subject:
        return []
    kind = ctx.entity_kind(str(subject))
    out = [
        v
        for eid, ent in ctx.entities.items()
        if eid != subject and ctx.entity_kind(eid) == kind
        for v in [(ent.get("attrs") or {}).get(attr)]
        if isinstance(v, str)
    ]
    history = ((ctx.entities.get(subject) or {}).get("attr_history") or {}).get(attr) or []
    out += [h["value"] for h in history if isinstance(h, dict) and isinstance(h.get("value"), str)]
    return out


def stated_rival(
    text: str,
    accept: list[str],
    q: dict,
    ctx: ScoreContext,
    *,
    support: PointSupport | None = None,
) -> str | None:
    """The first rival value (`rival_values`) a text answer also states, or None.

    A rival is stated when every content word it does not share with the gold value, the
    question or the subject's record (`point_support`) occurs in the answer, not framed as
    history: "Solutions engineer / Data engineer" states the rival "Data engineer";
    "Solutions engineer, not a data engineer" does not, and neither does "Stakeholder; she
    is the Account Manager at Galix" state the relationship "manager" when her role is
    Account Manager.
    """
    support = point_support(q, ctx) if support is None else support
    gold = {normalize(a) for a in accept}
    framed = not (set(_phrase(" ".join(accept))) & (HISTORY_MARKERS | CURRENT_MARKERS))
    have, _ = _content(text, ctx, framed=framed)
    known = match_tokens(str(q.get("text") or "")) | support.tokens
    for a in accept:
        known |= _content(a, ctx, framed=False)[0]
    for value in rival_values(q, ctx):
        if normalize(value) in gold:
            continue
        own = _content(value, ctx, framed=False)[0] - known
        if own and own <= have:
            return value
    return None


_NUMBER = re.compile(r"(?<![a-z0-9.])(-?\d+(?:\.\d+)?)\s*(thousand|million|billion|mm|bn|k|m|b)?\b")
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
_CURRENCY_AFTER = re.compile(r"\s*(usd|eur|gbp|dollars?|euros?)\b")
_CURRENCY_BEFORE = re.compile(r"(\$|\b(usd|eur|gbp))\s*$")
_YEARLIKE = re.compile(r"(19|20)\d{2}")


def parse_number(value: Any) -> float | None:
    """The one number a value states, with currency symbols and thousands separators ignored.

    `'$180k'`, `'180,000 USD'` and `180000` all give 180000.0; `'1.2m'` gives 1200000.0.

    In text, dates are skipped, and so are labels glued to letters (`Q3`, `FY2027`, `v2`)
    and numbers framed as history (`'$180k (up from $150k)'`). A bare year (`2027`) is
    skipped when another number remains. If several different numbers remain, the one
    framed as current (`'$150k, now $180k'`) wins, else the one marked as money or with a
    `k`/`m` suffix (`'$180k for 3 campuses'`); otherwise the value is ambiguous (None).
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    norm = re.sub(r"(?<=\d),(?=\d)", "", normalize_marked(str(value)))
    for a, b, *_ in date_mentions(norm):
        norm = norm[:a] + " " * (b - a) + norm[b:]
    found = []  # (value, framing, money, yearlike)
    for m in _NUMBER.finditer(norm):
        mult = m.group(2) or ""
        money = bool(
            mult
            or _CURRENCY_BEFORE.search(norm[: m.start()])
            or _CURRENCY_AFTER.match(norm, m.end())
        )
        yearlike = not money and bool(_YEARLIKE.fullmatch(m.group(1)))
        role = framing(norm, m.start())
        found.append((float(m.group(1)) * _MULT.get(mult, 1.0), role, money, yearlike))
    found = [f for f in found if f[1] != "history"]
    if any(not f[3] for f in found):
        found = [f for f in found if not f[3]]
    for keep in (lambda f: True, lambda f: f[1] == "current", lambda f: f[2]):
        values = {f[0] for f in found if keep(f)}
        if len(values) == 1:
            return values.pop()
    return None


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
    """1 if the predicted name names exactly the gold counterparty; None if gold has none.

    See `ScoreContext.names_exactly`: "Cora Velez" and "Cora (Tessellate)" earn the credit for
    Cora; "Sam", "Cora Velez, Ben Okoro" and a list of everyone do not.
    """
    if not gold:
        return None
    return 1.0 if isinstance(pred, str) and ctx.names_exactly(pred, gold) else 0.0


def attribute_credit(pred: dict, gold: dict, ctx: ScoreContext) -> tuple[float, dict]:
    """Mean of status, due and counterparty credit (counterparty skipped when gold has none)."""
    parts = {
        "status": (1.0 if pred.get("status") in gold.get("accept_status", [])
                   else status_credit(pred.get("status"), gold.get("status"))),
        "due": due_credit(pred.get("due"), gold.get("due")),
        "counterparty": counterparty_credit(
            pred.get("counterparty"), gold.get("counterparty"), ctx
        ),
    }
    graded = [v for v in parts.values() if v is not None]
    return sum(graded) / len(graded), parts


def f1(p: float, r: float) -> float:
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def _counted(pred: list, gold: list, pairs: list[tuple[int, int]]) -> tuple[int, int]:
    """Predictions and gold items that count in precision and recall.

    An optional gold item (a suggested loop, or an ask the worker has not answered) is
    neither required nor wrong: it leaves recall's denominator, and a prediction matched to it
    leaves precision's."""
    to_optional = sum(1 for _, j in pairs if gold[j].get("optional"))
    required = sum(1 for g in gold if not g.get("optional"))
    return len(pred) - to_optional, required


def _empty_case(n_pred: int, n_gold: int) -> float | None:
    """Score when either side is empty: 1 if both are, 0 if only one is, None otherwise."""
    if n_pred == 0 and n_gold == 0:
        return 1.0
    if n_pred == 0 or n_gold == 0:
        return 0.0
    return None


def grade_list(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """Soft F1: P = sum(a) / predicted, R = sum(a) / gold, a = attribute credit per match.

    A predicted item that repeats an earlier one (`wcb.grade.matching.item_key`) cannot match,
    but still counts as predicted.
    """
    pred, gold = list(answer.get("items") or []), list((q.get("gold") or {}).get("items") or [])
    if not pred or not (gold or (q.get("gold") or {}).get("suggested")):
        early = _empty_case(len(pred), sum(1 for g in gold if not g.get("optional")))
        return early, {"n_pred": len(pred), "n_gold": len(gold), "matches": []}
    pairs = match_items(pred, gold, judge, kind="loop", ctx=ctx, distinct=True)
    matches, total = [], 0.0
    for i, j in pairs:
        a, parts = attribute_credit(pred[i], gold[j], ctx)
        if not gold[j].get("optional"):
            total += a
        matches.append({"pred": i, "gold": gold[j].get("loop", j), "credit": a, **parts})
    n_pred, n_gold = _counted(pred, gold, pairs)
    matched_pred, matched_gold = {i for i, _ in pairs}, {j for _, j in pairs}
    suggested = list((q.get("gold") or {}).get("suggested") or [])
    rest = [i for i in range(len(pred)) if i not in matched_pred]
    if suggested and rest:
        extra = match_items([pred[i] for i in rest], suggested, judge, kind="loop", ctx=ctx)
        n_pred -= len(extra)
    early = _empty_case(n_pred, n_gold)
    p = total / n_pred if n_pred else 0.0
    r = total / n_gold if n_gold else 0.0
    return (f1(p, r) if early is None else early), {
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
    """max(0, (sum w*covered - sum w*contradicted) / sum w - padding) over the checklist.

    `padding` is `judge.padding_penalty`: up to 0.25 for an answer that is mostly not about
    the question's facts, so stuffing a status or brief with everything costs something."""
    gold = q.get("gold") or {}
    items, facts = gold.get("rubric") or [], gold.get("facts") or {}
    text = answer_text(answer)
    verdicts, total, net = [], 0.0, 0.0
    raw = [judge.rubric(text, item, facts) for item in items]
    raw = [v if v in VERDICTS else "missing" for v in raw]
    raw = [_status_by_default(q, item, v, raw, text) for item, v in zip(items, raw, strict=True)]
    for item, v in zip(items, raw, strict=True):
        w = float(item.get("weight", 1))
        if item.get("optional") and v == "missing":
            verdicts.append({"item": item.get("id"), "weight": 0.0, "verdict": "optional"})
            continue
        total += w
        net += w if v == "covered" else (-w if v == "contradicted" else 0.0)
        verdicts.append({"item": item.get("id"), "weight": w, "verdict": v})
    penalty = padding_penalty(text, facts) if total else 0.0
    score = 1.0 if total == 0 else max(0.0, net / total - penalty)
    return score, {"verdicts": verdicts, "padding_penalty": penalty}


def _status_by_default(q: dict, item: dict, verdict: str, verdicts: list[str], text: str) -> str:
    """An `active` project-status item is covered by an answer that gives no other status.

    Answers describe a running project by what it is doing (\"in build\", \"in security review
    and blocked\") rather than by the word \"active\". Such an answer covers the item when it
    names no other status (paused, dormant, done, cancelled, merged; `statuses_named`) and
    covers at least one other item, so an empty or off-topic answer still earns nothing."""
    if verdict != "missing" or q.get("type") != "status" or item.get("aspect") != "status":
        return verdict
    if "active" not in (item.get("keywords") or [[]])[0]:
        return verdict
    if statuses_named(text) - {"active"}:
        return verdict
    return "covered" if "covered" in verdicts else verdict


# ---------------------------------------------------------------- change
def _reported_outcome(pred: dict, item: dict) -> tuple[bool, bool]:
    """An asserted outcome, and whether its clause names the specific deliverable."""
    words = list(LOOP_STATUS_WORDS.get(item.get("outcome"), []))
    if item.get("outcome") == "done":
        words.extend(["handed", "handed off", "transferred"])
    keywords = item.get("keywords") or []
    asserted = False
    for clause in re.split(r"[;.!?\n]", pred.get("text", "")):
        text = normalize_marked(clause)
        for word in words:
            for start, _ in phrase_spans(text, word):
                if negated(text, start) or re.search(r"\b(?:will|might|could|to be|to)\s+(?:be\s+)?$", text[:start]):
                    continue
                asserted = True
                if keywords and len(keywords[0].split()) > 1 and phrase_spans(text, keywords[0]):
                    return True, True
    return asserted, False


def grade_change(q: dict, answer: dict, judge: Judge, ctx: ScoreContext) -> tuple[float, dict]:
    """F1 over distinct predictions and events, allowing a confirmed same-thread bundle."""
    pred, gold = list(answer.get("items") or []), list((q.get("gold") or {}).get("items") or [])
    if not pred or not gold:
        early = _empty_case(len(pred), sum(1 for g in gold if not g.get("optional")))
        return early, {"n_pred": len(pred), "n_gold": len(gold), "matches": []}
    edges = distinct_edges(pred, confirmed_edges(pred, gold, judge, kind="change", ctx=ctx))
    pairs = assign(edges)
    confirmed = {(i, j) for _, i, j in edges}
    by_event = {item.get("event"): j for j, item in enumerate(gold)}
    matched = {j: i for i, j in pairs}
    for end, item in enumerate(gold):
        start = by_event.get(item.get("paired_event")) if item.get("paired_event") else None
        if start is None or (start in matched) == (end in matched):
            continue
        i = matched[end] if end in matched else matched[start]
        asserted, explicit = _reported_outcome(pred[i], item)
        if not asserted or ((i, end) not in confirmed and not explicit):
            continue
        # Completion entails creation on the same loop. A decision must be stated too.
        if gold[start].get("type") == "decision.make" and (i, start) not in confirmed:
            continue
        extra = start if end in matched else end
        pairs.append((i, extra))
        matched[extra] = i
    required_preds = {i for i, j in pairs if not gold[j].get("optional")}
    optional_preds = {i for i, j in pairs if gold[j].get("optional")} - required_preds
    hits = sum(not gold[j].get("optional") for _, j in pairs)
    n_pred = len(pred) - len(optional_preds)
    n_gold = sum(not item.get("optional") for item in gold)
    early = _empty_case(n_pred, n_gold)
    p = len(required_preds) / n_pred if n_pred else 0.0
    r = hits / n_gold if n_gold else 0.0
    matched_gold = {j for _, j in pairs}
    return (f1(p, r) if early is None else early), {
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
    try:
        off = abs(business_days_between(date_of(want), date_of(got)))
    except ValueError:  # matches the schema's pattern but is no calendar date (2027-02-30)
        details["problem"] = "not a calendar date"
        return 0.0, details
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
    """recall(must_include in top k) x (1 - distractor items / loop items in the top k).

    The top items are first matched one-to-one against the worker's loops (must-include and
    other worker-active ones); an item that repeats an earlier one cannot match. A top item
    counts as a distractor when the judge confirms it describes a distractor loop (closed, or
    owed by someone else) and no worker loop, so an item that describes an open worker loop is
    never penalized, even when it is a duplicate or also resembles a closed loop. Several
    items describing distractors each count. *Loop items* are the top items the judge
    confirms against some gold loop, worker's or distractor; an item that describes no loop
    ("Catch up on email") counts neither way, so filler cannot dilute the penalty.
    """
    gold = q.get("gold") or {}
    k = int(gold.get("k") or 10)
    top = list(answer.get("items") or [])[:k]
    combined, roles = priority_gold(gold)
    worker = [j for j, r in enumerate(roles) if r != "distractor"]
    distractors = [j for j, r in enumerate(roles) if r == "distractor"]
    n_must = roles.count("must")
    pairs: list[tuple[int, int]] = []
    worker_edges: list[tuple[float, int, int]] = []
    if top and worker:
        worker_edges = confirmed_edges(
            top, [combined[j] for j in worker], judge, kind="loop", ctx=ctx
        )
        pairs = [(i, worker[j]) for i, j in assign(distinct_edges(top, worker_edges))]
    with_worker_edge = {i for _, i, _ in worker_edges}
    rest = [i for i in range(len(top)) if i not in with_worker_edge]
    distractor_hits: dict[int, int] = {}
    if rest and distractors:
        edges = confirmed_edges(
            [top[i] for i in rest], [combined[j] for j in distractors], judge, kind="loop", ctx=ctx
        )
        for _, i, j in sorted(edges, key=lambda e: (-e[0], e[1], e[2])):
            distractor_hits.setdefault(rest[i], distractors[j])
    hit_must = sum(1 for _, j in pairs if roles[j] == "must")
    recall = 1.0 if n_must == 0 else hit_must / n_must
    loop_items = with_worker_edge | set(distractor_hits)
    penalty = len(distractor_hits) / len(loop_items) if loop_items else 0.0
    matched = {j for _, j in pairs}
    matches = sorted([*pairs, *distractor_hits.items()])
    return recall * (1 - penalty), {
        "k": k,
        "n_top": len(top),
        "n_loop_items": len(loop_items),
        "recall": recall,
        "penalty": penalty,
        "matches": [
            {"pred": i, "gold": combined[j].get("loop", j), "role": roles[j]} for i, j in matches
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
#: Question types whose items are checked against the support of the gold item they matched,
#: with the gold item key `grade_list` and `grade_change` report in `details["matches"]`.
ITEM_SCOPED = {"list": "loop", "change": "event"}


def cite_groups(answer: dict) -> list[tuple[str, list[str]]]:
    """Cites by where they appear: `("cites", ...)` for the top-level list, then
    `("items[i]", ...)` and `("claims[i]", ...)`, in answer order. Non-strings are dropped."""
    out = [("cites", [c for c in answer.get("cites") or [] if isinstance(c, str)])]
    for key in ("items", "claims"):
        for i, part in enumerate(answer.get(key) or []):
            if isinstance(part, dict):
                out.append(
                    (f"{key}[{i}]", [c for c in part.get("cites") or [] if isinstance(c, str)])
                )
    return out


def collect_cites(answer: dict) -> list[str]:
    """Every cite in an answer: top-level `cites`, then `items[].cites`, then `claims[].cites`."""
    return [c for _, cites in cite_groups(answer) for c in cites]


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


def workspace_reference(cite: str, root: Path | None) -> bool:
    """A Track B reference to its own existing notes is ancillary to source citations."""
    relative = Path(cite.removeprefix("[[").removesuffix("]]").partition("#")[0])
    if root is None or relative.is_absolute() or ".." in relative.parts or not relative.suffix:
        return False
    try:
        path = root / relative
        return path.resolve().is_relative_to(root.resolve()) and path.is_file()
    except (OSError, RuntimeError, ValueError):
        return False


def cite_key(cite: str) -> str:
    """What makes two cites the same source: the artifact ID, or the normalized record ID."""
    return cite if ARTIFACT_RE.match(cite) else (store_record_id(cite) or cite)


def _support_status(cite: str, support: set[str], ctx: ScoreContext) -> str:
    if ARTIFACT_RE.match(cite):
        if cite in support:
            return "valid"
        return "not_in_support" if cite in ctx.delivered else "not_delivered"
    rid = store_record_id(cite)
    if rid is None or ctx.store_root is None:
        return "unrecognized"
    if rid == WORKER_RECORD:
        return "worker_record"
    refs = ctx.record_refs(rid)
    if refs is None:
        return "no_such_record"
    return "valid" if refs & support else "record_unsupported"


def cite_status(
    cite: str, support: set[str], ctx: ScoreContext, *, question: set[str] | None = None
) -> str:
    """'valid', or why not: 'not_in_support', 'not_delivered', 'no_such_record',
    'worker_record', 'record_unsupported', 'wrong_item' or 'unrecognized'.

    `support` is the scope the cite is checked against: the support of the gold item a
    predicted item matched, or the question's support. An artifact ID is valid when it is in
    it. A store path (Track A) is valid when the record exists in the store the answers were
    produced from and its text cites at least one artifact of that support (in its evidence,
    a `[src: ...]` note or a log line), so the record carries evidence for the item; an
    unrelated record is 'record_unsupported'. The worker's own record, `people/me`, is never
    valid: every answer relates to the worker, so it is not specific evidence for any one of
    them. With `question` (the question's support, when `support` is an item's), a cite that
    fails the item but would pass the question is 'wrong_item': evidence for another item.
    """
    status = _support_status(cite, support, ctx)
    if (
        question is not None
        and status in ("not_in_support", "record_unsupported")
        and _support_status(cite, question, ctx) == "valid"
    ):
        return "wrong_item"
    return status


def matched_item_support(q: dict, details: dict) -> dict[int, list[str]] | None:
    """For list and change questions, predicted item index -> support of the gold item it was
    matched to (from the grader's `details["matches"]`); None for other types, whose
    citations are checked against the question's support. A gold item without support (older
    gold files) is left out, so its match is checked against the question's support."""
    key = ITEM_SCOPED.get(q.get("type", ""))
    if key is None:
        return None
    gold = list((q.get("gold") or {}).get("items") or [])
    by_id = {g.get(key, j): g for j, g in enumerate(gold) if isinstance(g, dict)}
    out: dict[int, list[str]] = {}
    for m in details.get("matches") or []:
        sup = (by_id.get(m.get("gold")) or {}).get("support")
        if sup:
            index = int(m["pred"])
            out[index] = list(dict.fromkeys([*out.get(index, []), *sup]))
    return out


def citation_precision(
    answer: dict,
    support: list[str],
    ctx: ScoreContext,
    *,
    item_support: dict[int, list[str]] | None = None,
    subjects: set[str] | None = None,
    extra: dict[int, set[str]] | None = None,
) -> tuple[float | None, dict]:
    """c = valid cites / counted cites, 0 when there are none; plus per-cite diagnostics.

    Without `item_support` (point, status, brief, temporal and priority questions) all of an
    answer's cites are pooled and checked against the question's `support`; a source cited
    more than once counts once (`loops/x` and `./loops/x.md` are the same record).

    With `item_support` (list and change questions; see `matched_item_support`) each
    predicted item is its own unit: its distinct cites are checked against the support of the
    gold item it matched, or against the question's support when it matched none. Top-level
    and claim cites form one more unit, checked against the question's support. A source
    counts once per unit, so one cited on two items counts twice and must support both.

    With `subjects` (`question_subjects`), a cite checked against the question's support
    (not a list or change item's) is also valid when it is a delivered artifact revealing an
    event about one of them (`ScoreContext.about`): gold support lists the evidence for each
    fact, while a status, brief or point answer may fairly cite other inputs about the same
    project or person. Item cites stay strict, so evidence for another loop of the same
    person is still `not_in_support` or `wrong_item`.

    With an empty `support` there is nothing a citation could point to, so `c` is None (not
    applicable) and the question score is its base score.
    """
    sup = set(support)
    extra = extra or {}
    pooled_extra = set().union(*extra.values()) if item_support is None else set()
    units: list[tuple[int | None, set[str], list[str]]] = []
    if item_support is None:
        units.append((None, sup, collect_cites(answer)))
    else:
        loose: list[str] = []
        for where, cites in cite_groups(answer):
            if where.startswith("items["):
                i = int(where[6:-1])
                units.append((i, set(item_support[i]) if i in item_support else sup, cites))
            else:
                loose += cites
        units.insert(0, (None, sup, loose))
    total = valid = 0
    invalid: list[dict[str, Any]] = []
    for item, scope, cites in units:
        distinct: dict[str, str] = {}
        for cite in cites:
            distinct.setdefault(cite_key(cite), cite)
        wider = sup if scope is not sup else None
        for cite in distinct.values():
            if ctx.track == "B" and workspace_reference(cite, ctx.store_root):
                continue
            total += 1
            why = cite_status(cite, scope, ctx, question=wider)
            if (
                why == "not_in_support"
                and item is None
                and subjects
                and ctx.about.get(cite, set()) & subjects
            ):
                why = "valid"
            if why == "not_in_support" and cite in (
                pooled_extra if item is None else extra.get(item, set())
            ):
                why = "valid"
            if why == "valid":
                valid += 1
            else:
                invalid.append(
                    {"cite": cite, "why": why, **({} if item is None else {"item": item})}
                )
    details: dict[str, Any] = {
        "scope": "question" if item_support is None else "item",
        "total": total,
        "valid": valid,
        "invalid": invalid,
    }
    if not sup:
        details["note"] = "no supporting artifacts: citations not scored"
        return None, details
    return (valid / total if total else 0.0), details
