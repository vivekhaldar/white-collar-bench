"""Judges: the two narrow decisions that free-text grading needs (docs/judge.md).

A judge answers exactly two questions:

* `same_item(pred, gold, kind=...)`: does a predicted list/change item describe the same
  commitment (kind `'loop'`) or the same change (kind `'change'`) as a gold item?
* `rubric(answer_text, item, facts)`: does a status/brief answer cover one checklist item?
  Returns `'covered'`, `'missing'` or `'contradicted'` (the answer presents a superseded or
  conflicting value as current).

Two implementations:

* `HeuristicJudge` (default): deterministic keyword and token-overlap rules. Free, fast and
  exactly reproducible; it under-credits loose paraphrases.
* `LLMJudge`: asks a pinned model the same narrow questions, takes a majority vote over
  `samples`, and caches every decision in a JSONL file so re-grading is stable and cheap.

All prompts and thresholds below are part of the benchmark release; change them only with a
version bump (docs/judge.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from wcb.util.dates import DATE_RE, text_variants
from wcb.util.text import STOPWORDS, containment, contains_phrase, jaccard, normalize

VERDICTS = ("covered", "missing", "contradicted")

# ---------------------------------------------------------------- heuristic thresholds
#: Keyword route: a gold keyword phrase is present AND at least this share of the gold
#: description's tokens appear in the prediction.
KEYWORD_CONTAINMENT = 0.3
#: Overlap route: token Jaccard between prediction text and gold description.
JACCARD_MATCH = 0.5
#: Terse route: every content token of the prediction, apart from capitalized names (which
#: may be aliases), occurs in the gold description, and at least this many are shared
#: ("Review Samir's ingestion doc" for "Review Sam Patel's ingestion design doc").
TERSE_MIN_SHARED = 3
#: Rubric items without keyword groups count as covered when this share of the item's own
#: tokens appear in the answer.
RUBRIC_FALLBACK_CONTAINMENT = 0.6

#: Prediction fields read as free text when matching (besides `text`).
PRED_TEXT_FIELDS = ("text", "counterparty", "why")

_WORD = re.compile(r"[a-z0-9]+")


class Judge(Protocol):
    """What graders need from a judge. See the module docstring."""

    name: str

    def same_item(self, pred: dict, gold: dict, *, kind: str) -> bool: ...

    def rubric(self, answer_text: str, item: dict, facts: dict) -> str: ...


# ---------------------------------------------------------------- text helpers (shared with matching)
def match_tokens(text: str | None) -> set[str]:
    """Content tokens for matching: lowercase ASCII words without stopwords.

    Single letters (the `s` of a possessive like "Patel's") are dropped, single digits are
    kept, and a plural `s` is stripped from words longer than three letters, so "reports"
    matches "report".
    """
    out = set()
    for t in _WORD.findall(normalize(text or "")):
        if (len(t) < 2 and not t.isdigit()) or t in STOPWORDS:
            continue
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.add(t)
    return out


def pred_text(pred: dict, *, full: bool = True) -> str:
    """The free text of a predicted item: `text`, plus `counterparty` and `why` when `full`."""
    fields = PRED_TEXT_FIELDS if full else ("text",)
    return " ".join(str(pred[f]) for f in fields if isinstance(pred.get(f), str) and pred.get(f))


def gold_text(gold: dict) -> str:
    """The description of a gold item: a loop's `what` or a change's `summary`."""
    return str(gold.get("what") or gold.get("summary") or gold.get("text") or "")


def phrase_variants(phrase: str) -> list[str]:
    """A keyword phrase plus, for an ISO date, the ways it is written in prose ("5 Feb", ...)."""
    phrase = str(phrase)
    if DATE_RE.match(phrase.strip()):
        return [phrase, *text_variants(phrase.strip())]
    return [phrase]


def group_matches(text: str, group: list[str] | str) -> bool:
    """True if any alternative of a keyword group (or its date variants) occurs in `text`."""
    alts = [group] if isinstance(group, str) else list(group or [])
    return any(contains_phrase(text, v) for alt in alts for v in phrase_variants(alt))


# ---------------------------------------------------------------- heuristic judge
class HeuristicJudge:
    """Deterministic judge built on keywords and token overlap.

    Tokens are content words (`match_tokens`: no stopwords, no single letters, plural `s`
    stripped). `same_item` matches when any of these holds:

    1. *keyword route*: some gold keyword phrase occurs in the prediction (whole words,
       case- and accent-insensitive) and at least `KEYWORD_CONTAINMENT` (30%) of the gold
       description's tokens occur in the prediction (`text` + `counterparty` + `why`);
    2. *overlap route*: the token Jaccard similarity between the prediction's `text` (or its
       full text, whichever is higher) and the gold description is at least `JACCARD_MATCH`
       (0.5);
    3. *terse route*: every token of the prediction's `text` occurs in the gold description,
       except capitalized words after the first (names, which may be aliases the judge cannot
       resolve), and at least `TERSE_MIN_SHARED` (3) tokens are shared.

    The thresholds were tuned on the mini fixture world so that paraphrases such as "Volume
    pricing from Cora", "Ingestion design doc review" or "Review Samir's ingestion doc" match
    their loops while items that merely share a verb and a name ("Send Ada the February
    forecast report" vs "Send Ada the January reconciliation report", or "Approve Ben's
    holiday request" vs "Approve Ben's GL sandbox access request") do not.

    `rubric` marks an item *covered* when every keyword group has at least one alternative in
    the answer (ISO dates also match their prose forms), *contradicted* when it is not covered
    and every stale group matches, and *missing* otherwise. An item without keyword groups is
    covered when `RUBRIC_FALLBACK_CONTAINMENT` (60%) of its own text's tokens are present.
    """

    name = "heuristic"

    def same_item(self, pred: dict, gold: dict, *, kind: str) -> bool:
        return heuristic_same_item(pred, gold)

    def rubric(self, answer_text: str, item: dict, facts: dict) -> str:
        return heuristic_rubric(answer_text, item)


def heuristic_same_item(pred: dict, gold: dict) -> bool:
    """The heuristic matching rule (see `HeuristicJudge`)."""
    full = pred_text(pred, full=True)
    g = match_tokens(gold_text(gold))
    p_full, p_core = match_tokens(full), match_tokens(pred_text(pred, full=False))
    keywords = [k for k in gold.get("keywords") or [] if isinstance(k, str) and k.strip()]
    if (
        any(contains_phrase(full, k) for k in keywords)
        and containment(g, p_full) >= KEYWORD_CONTAINMENT
    ):
        return True
    if max(jaccard(g, p_core), jaccard(g, p_full)) >= JACCARD_MATCH:
        return True
    core = pred_text(pred, full=False)
    rest = p_core - g - name_tokens(core)
    return not rest and len(g & p_core) >= TERSE_MIN_SHARED


def name_tokens(text: str) -> set[str]:
    """Tokens of capitalized words after the first, e.g. {'samir'} in "Review Samir's doc".

    Returns nothing for Title Case or ALL CAPS text, where capitals do not mark names.
    """
    words = re.findall(r"[^\W_]+", text or "")[1:]
    caps = [w for w in words if w[:1].isupper()]
    if 2 * len(caps) > len(words):
        return set()
    return match_tokens(" ".join(caps))


def heuristic_rubric(answer_text: str, item: dict) -> str:
    """The heuristic rubric rule (see `HeuristicJudge`)."""
    groups = [g for g in item.get("keywords") or [] if g]
    if groups:
        covered = all(group_matches(answer_text, g) for g in groups)
    else:
        need = match_tokens(item.get("text", ""))
        covered = (
            bool(need)
            and containment(need, match_tokens(answer_text)) >= RUBRIC_FALLBACK_CONTAINMENT
        )
    if covered:
        return "covered"
    stale = [g for g in item.get("stale") or [] if g]
    if stale and all(group_matches(answer_text, g) for g in stale):
        return "contradicted"
    return "missing"


# ---------------------------------------------------------------- LLM judge
SYSTEM_PROMPT = (
    "You are a careful, strict grader for a benchmark about tracking a knowledge worker's "
    "commitments, projects and decisions. Follow the output format exactly."
)

SAME_ITEM_PROMPT = """Do these two descriptions refer to the same {noun}? Answer YES or NO.

Reference {noun}:
{gold}

Predicted item:
{pred}

Wording, level of detail and field values (status, dates, names) may differ. Answer YES only if both describe the same underlying {noun}; otherwise answer NO. Reply with the single word YES or NO."""

RUBRIC_PROMPT = """Grade the answer against one checklist item.

Checklist item:
{item}

Ground-truth facts (JSON):
{facts}

Answer:
<<<
{answer}
>>>

Reply with exactly one word:
COVERED - the answer states the checklist item (paraphrase is fine).
MISSING - the answer does not state it.
CONTRADICTED - the answer presents a superseded or conflicting value as current."""

#: Gold fields shown to the LLM for `same_item`, by kind.
GOLD_FIELDS = {
    "loop": ("what", "counterparty_name", "counterparty", "direction", "status", "due"),
    "change": ("summary", "date", "type"),
}
NOUNS = {"loop": "commitment", "change": "change"}

#: Token budget for one judge completion. Generous because some models think before
#: answering and thinking tokens count against it; a decision itself is one word.
JUDGE_MAX_TOKENS = 2048

_YES_NO = re.compile(r"\b(yes|no)\b")
_VERDICT = re.compile(
    r"\b(not covered|uncovered|covered|missing|contradicted|contradicts|contradiction)\b"
)
_VERDICT_MAP = {
    "covered": "covered",
    "not covered": "missing",
    "uncovered": "missing",
    "missing": "missing",
    "contradicted": "contradicted",
    "contradicts": "contradicted",
    "contradiction": "contradicted",
}


def _dumps(obj: Any) -> str:
    """Stable JSON for prompts (sorted keys) so identical inputs give identical cache keys."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def same_item_prompt(pred: dict, gold: dict, kind: str) -> str:
    """The exact user prompt for one `same_item` decision."""
    fields = GOLD_FIELDS.get(kind, GOLD_FIELDS["loop"])
    g = {k: gold[k] for k in fields if gold.get(k) not in (None, "", [])}
    p = {k: v for k, v in pred.items() if k != "cites" and v not in (None, "", [])}
    return SAME_ITEM_PROMPT.format(noun=NOUNS.get(kind, "item"), gold=_dumps(g), pred=_dumps(p))


def rubric_prompt(answer_text: str, item: dict, facts: dict) -> str:
    """The exact user prompt for one `rubric` decision."""
    return RUBRIC_PROMPT.format(
        item=item.get("text", ""), facts=_dumps(facts or {}), answer=answer_text
    )


def parse_yes_no(text: str) -> bool | None:
    """First YES/NO word in a completion (markdown and punctuation tolerated); None if absent."""
    m = _YES_NO.search(normalize(text or ""))
    return None if m is None else m.group(1) == "yes"


def parse_verdict(text: str) -> str | None:
    """First COVERED/MISSING/CONTRADICTED word in a completion; 'NOT COVERED' means missing."""
    m = _VERDICT.search(normalize(text or ""))
    return None if m is None else _VERDICT_MAP[m.group(1)]


def majority(values: list[Any], tie_order: tuple[Any, ...]) -> Any:
    """Most common non-None value; ties (and all-None) resolve by `tie_order` (first wins)."""
    counts = Counter(v for v in values if v is not None)
    if not counts:
        return tie_order[0]
    best = max(counts.values())
    return next(v for v in tie_order if counts.get(v) == best)


class LLMJudge:
    """Judge that asks a model the two narrow questions and caches the answers.

    * `client` is any object with a `model` attribute and
      `complete(prompt, *, system, temperature, max_tokens) -> str` (see `wcb.llm.client`).
    * Each decision is the majority over `samples` completions, made at temperature 0 when
      `samples == 1` and at temperature 1.0 otherwise. Unparseable completions are ignored;
      ties and all-unparseable votes resolve conservatively: NO for `same_item`, and
      missing > covered > contradicted for `rubric`.
    * Decisions are cached in memory and, when `cache_path` is given, appended to a JSONL file
      keyed by the sha256 of (model spec, sample count, system prompt, user prompt). Lines hold
      the raw completions for audit. Delete the file to force re-judging.
    """

    def __init__(self, client: Any, *, samples: int = 1, cache_path: Path | None = None):
        if samples < 1:
            raise ValueError("samples must be >= 1")
        self.client = client
        self.samples = samples
        self.model_spec = str(getattr(client, "spec", "") or getattr(client, "model", "unknown"))
        self.name = f"llm:{self.model_spec}"
        self.cache_path = Path(cache_path) if cache_path else None
        self.calls = 0  # model calls actually made (cache misses x samples)
        self._cache: dict[str, Any] = {}
        if self.cache_path and self.cache_path.exists():
            self._cache.update(load_cache(self.cache_path))

    @property
    def temperature(self) -> float:
        return 0.0 if self.samples == 1 else 1.0

    def same_item(self, pred: dict, gold: dict, *, kind: str) -> bool:
        prompt = same_item_prompt(pred, gold, kind)
        return bool(self._decide("same_item", prompt, parse_yes_no, (False, True)))

    def rubric(self, answer_text: str, item: dict, facts: dict) -> str:
        prompt = rubric_prompt(answer_text, item, facts)
        return str(
            self._decide("rubric", prompt, parse_verdict, ("missing", "covered", "contradicted"))
        )

    def cache_key(self, prompt: str) -> str:
        raw = _dumps([self.model_spec, self.samples, SYSTEM_PROMPT, prompt])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _decide(self, what: str, prompt: str, parse, tie_order: tuple[Any, ...]) -> Any:
        key = self.cache_key(prompt)
        if key in self._cache:
            return self._cache[key]
        outputs = []
        for _ in range(self.samples):
            self.calls += 1
            outputs.append(
                self.client.complete(
                    prompt,
                    system=SYSTEM_PROMPT,
                    temperature=self.temperature,
                    max_tokens=JUDGE_MAX_TOKENS,
                )
            )
        decision = majority([parse(o) for o in outputs], tie_order)
        self._cache[key] = decision
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "key": key,
                "model": self.model_spec,
                "kind": what,
                "samples": self.samples,
                "decision": decision,
                "outputs": outputs,
            }
            with open(self.cache_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return decision


def load_cache(path: Path) -> dict[str, Any]:
    """Read a judge cache file into {key: decision}; malformed lines are skipped."""
    out: dict[str, Any] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
                out[row["key"]] = row["decision"]
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
    return out


# ---------------------------------------------------------------- factory
#: Judge model used when `--judge llm` is given without `--judge-model`. Pinned per release.
DEFAULT_LLM_JUDGE = "anthropic:claude-opus-5-5"
#: Votes per decision for `make_judge` (docs/scoring.md: majority of 3 samples).
DEFAULT_SAMPLES = 3


def make_judge(
    kind: str = "heuristic", model: str | None = None, cache_path: Path | None = None
) -> Judge:
    """Build a judge for `wcb score --judge {heuristic,llm} [--judge-model SPEC]`.

    `model` is an LLM spec (`anthropic:<model>`, `openai:<model>` or `cmd:<command>`, see
    `wcb.llm.client.make_client`); it defaults to `DEFAULT_LLM_JUDGE`. The number of samples
    per decision comes from `WCB_JUDGE_SAMPLES` (default 3, as in docs/scoring.md). `cache_path` (or
    `WCB_JUDGE_CACHE` when it is None) is the JSONL decision cache.
    """
    if kind == "heuristic":
        return HeuristicJudge()
    if kind != "llm":
        raise ValueError(f"unknown judge kind {kind!r} (expected 'heuristic' or 'llm')")
    from wcb.llm.client import make_client

    samples = int(os.environ.get("WCB_JUDGE_SAMPLES", "") or DEFAULT_SAMPLES)
    if cache_path is None and os.environ.get("WCB_JUDGE_CACHE"):
        cache_path = Path(os.environ["WCB_JUDGE_CACHE"])
    return LLMJudge(make_client(model or DEFAULT_LLM_JUDGE), samples=samples, cache_path=cache_path)
