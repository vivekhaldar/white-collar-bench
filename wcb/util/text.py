"""Text normalization, tokenization and slugs."""

from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset(
    """a an and are as at be by for from has have i in is it its me my of on or our that the their
    them they this to was we were will with you your re fw fwd about into over per via up out
    """.split()
)

_WORD = re.compile(r"[a-z0-9]+")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.lower()).strip()


def tokens(s: str, *, drop_stopwords: bool = True) -> list[str]:
    toks = _WORD.findall(normalize(s))
    if drop_stopwords:
        toks = [t for t in toks if t not in STOPWORDS]
    return toks


def token_set(s: str) -> set[str]:
    return set(tokens(s))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def containment(needle: set[str], hay: set[str]) -> float:
    """Fraction of `needle` tokens present in `hay`."""
    if not needle:
        return 0.0
    return len(needle & hay) / len(needle)


def slugify(s: str, *, max_len: int = 60) -> str:
    s = normalize(s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rsplit("-", 1)[0] or s[:max_len]
    return s or "untitled"


def contains_phrase(text: str, phrase: str) -> bool:
    """Whole-word, case/accent-insensitive phrase containment."""
    t = " " + " ".join(_WORD.findall(normalize(text))) + " "
    p = " ".join(_WORD.findall(normalize(phrase)))
    return bool(p) and f" {p} " in t


# ---------------------------------------------------------------- framing of values in answers
# Graders read free-text answers that often mention an old value next to the current one
# ("5 Feb (moved from 29 Jan)", "Cora Velez, took it over from Sam Reyes"). These markers let
# them tell a value framed as past or rejected from one stated as current. See
# docs/scoring.md, "Implementation notes".

#: A value after one of these words, in the same clause, is framed as past or rejected.
HISTORY_MARKERS = frozenset(
    """from was were previously formerly former originally earlier old instead rather not no
    never nor neither isn wasn aren ex""".split()
)
#: A value after one of these words is framed as the current one ("moved to 5 Feb").
CURRENT_MARKERS = frozenset({"to", "now", "currently", "new", "->", "=>"})
#: A value followed closely by one of these words is framed as finished ("evaluation is done").
FINISHED_MARKERS = frozenset(
    "finished done complete completed over ended closed behind superseded obsolete".split()
)
#: Punctuation that ends a clause, and so the reach of a marker.
CLAUSE_BREAKS = frozenset(".,;:()[]!?")
#: How many words after a value a finished marker may come.
FINISHED_WINDOW = 3

_MARK_TOKEN = re.compile(r"[a-z0-9]+|->|=>|[.,;:()\[\]!?]")


def normalize_marked(text: str | None) -> str:
    """`normalize`, keeping arrows (`→` becomes `->`) so they can act as markers."""
    s = str(text or "")
    for arrow in ("→", "⟶", "➔", "⇒"):
        s = s.replace(arrow, " -> ")
    return normalize(s)


def marked_tokens(norm: str) -> list[tuple[str, int, int]]:
    """Words, arrows and clause punctuation of normalized text, with character spans."""
    return [(m.group(), m.start(), m.end()) for m in _MARK_TOKEN.finditer(norm)]


def framing(norm: str, start: int, end: int | None = None, *, finished: bool = False) -> str:
    """How the mention `norm[start:end]` is framed: 'history', 'current' or ''.

    The nearest marker before the mention in its clause decides: a `HISTORY_MARKERS` word
    gives 'history' and a `CURRENT_MARKERS` word 'current'. With `finished`, a mention without
    such a marker is also 'history' when a `FINISHED_MARKERS` word follows it within
    `FINISHED_WINDOW` words in the same clause. `norm` must come from `normalize_marked`.
    """
    for tok, _, _ in reversed(marked_tokens(norm[:start])):
        if tok in CLAUSE_BREAKS:
            break
        if tok in HISTORY_MARKERS:
            return "history"
        if tok in CURRENT_MARKERS:
            return "current"
    if finished and end is not None:
        for i, (tok, _, _) in enumerate(marked_tokens(norm[end:])):
            if tok in CLAUSE_BREAKS or i >= FINISHED_WINDOW:
                break
            if tok in FINISHED_MARKERS:
                return "history"
    return ""


# ---------------------------------------------------------------- superseded values
# Rubric grading asks a narrower question about a superseded value: is this mention of it
# labelled as history anywhere around it, not only by the word before it? Answers write
# "the 78/74 in the 4 March email were v1 totals", "1 Nov -> 12 Nov -> 7 Dec",
# "29 Jan (original date)" or "moved from 1 Nov to 12 Nov, then 24 Nov, then 7 Dec".

#: Before a superseded value, in its clause, these words label it as history too
#: ("the original 29 Jan date", "replacing 29 Jan"), besides `HISTORY_MARKERS`.
HISTORY_LABELS = frozenset(
    """previous prior original initial initially outdated stale superseded superseding
    replaced replacing obsolete""".split()
)
#: After a superseded value, the first of these in its clause decides: a past-tense verb
#: makes it history ("78/74 in the email were v1 totals"), a present one does not
#: ("78/74 are the totals").
PAST_VERBS = frozenset("was were had".split())
PRESENT_VERBS = frozenset("is are remains remain stays stay will has have now".split())
#: Words that end the reach of a verb after a value ("Target 29 Jan and the kickoff was ...").
COORDINATORS = frozenset(
    "and but or while whereas because although though so if when until unless".split()
)
#: A parenthesis right after a value that opens with one of these labels it as history:
#: "29 Jan (original date)", "78/74 (superseded)", "29 Jan (now 5 Feb)".
PAREN_HISTORY_LABELS = HISTORY_LABELS | frozenset(
    "old earlier former now since".split()
)
#: Verbs of a move. "Moved from 1 Nov to 12 Nov, then 24 Nov, then 7 Dec": in a sentence
#: with one, a value followed by "then" was replaced by what follows.
MOVE_WORDS = frozenset(
    """moved move moves slipped slip slips pushed push changed change shifted shift
    rescheduled postponed delayed went revised""".split()
)
#: "29 Jan (moved to 5 Feb)": these, followed by `to`, inside a parenthesis right after a value.
MOVE_TO_WORDS = MOVE_WORDS | frozenset("replaced updated corrected".split())
#: A short phrase starting with one of these may sit between a moved value and `then`, saying
#: when the move happened: "moved from 15 Dec to 22 Dec on 8 Nov, then to 31 Dec".
WHEN_WORDS = frozenset("on in at by during".split())
WHEN_PHRASE_MAX = 5
#: "it was 15 Dec, then 22 Dec": the most tokens one link of such a chain may have.
CHAIN_LINK_MAX = 4
_SENTENCE_BREAKS = frozenset(".!?")


def stale_history(norm: str, start: int, end: int) -> bool:
    """True when the mention `norm[start:end]` of a superseded value is labelled as history.

    Any of these holds (`norm` comes from `normalize_marked`):

    * `framing(..., finished=True)` says 'history': a `HISTORY_MARKERS` word before it in its
      clause, or a `FINISHED_MARKERS` word within `FINISHED_WINDOW` words after it;
    * a `HISTORY_LABELS` word comes before it in its clause, with no `CURRENT_MARKERS` word
      between them ("the original 29 Jan date");
    * after it, in its clause and before any `COORDINATORS` word, the first verb is a past one
      (`PAST_VERBS`, not `PRESENT_VERBS`): "the 78/74 in the 4 March email were v1 totals";
    * an arrow follows it, possibly after a short parenthesis: "1 Nov -> 12 Nov -> 7 Dec",
      "1 Nov -> 12 Nov (13 Sep) -> 24 Nov";
    * it follows `then` (or `then to`) in a sentence whose chain starts with a
      `HISTORY_MARKERS` word: "it was 15 Dec, then 22 Dec" (`_then_after_history`);
    * a parenthesis follows it and opens with a `PAREN_HISTORY_LABELS` word, or with a
      `MOVE_TO_WORDS` word and then `to`: "29 Jan (original)", "29 Jan (moved to 5 Feb)";
    * `then` follows it (after an optional comma, and an optional short `WHEN_WORDS` phrase
      such as "on 8 Nov") in a sentence with a `MOVE_WORDS` word before it: "moved from
      1 Nov to 12 Nov, then 24 Nov, then 7 Dec", "moved to 22 Dec on 8 Nov, then to 31 Dec".
    """
    if framing(norm, start, end, finished=True) == "history":
        return True
    before = marked_tokens(norm[:start])
    for tok, _, _ in reversed(before):
        if tok in CLAUSE_BREAKS or tok in CURRENT_MARKERS:
            break
        if tok in HISTORY_LABELS:
            return True
    after = [t for t, _, _ in marked_tokens(norm[end:])]
    if after and after[0] in ("->", "=>"):
        return True
    if after[:1] == ["("] and ")" in after[1:WHEN_PHRASE_MAX + 2]:  # "12 Nov (13 Sep) -> 24 Nov"
        close = after.index(")")
        if after[close + 1:close + 2] in (["->"], ["=>"]):
            return True
    if _then_after_history(before):
        return True
    if after and after[0] == "(":
        inside = after[1:4]
        if inside and inside[0] in PAREN_HISTORY_LABELS:
            return True
        if len(inside) >= 2 and inside[0] in MOVE_TO_WORDS and inside[1] == "to":
            return True
    for tok in after:
        if tok in CLAUSE_BREAKS or tok in COORDINATORS:
            break
        if tok in PAST_VERBS:
            return True
        if tok in PRESENT_VERBS or tok in CURRENT_MARKERS:
            break
    rest = after
    if rest[:1] and rest[0] in WHEN_WORDS:  # "to 22 Dec on 8 Nov, then 31 Dec"
        stop = next((i for i, t in enumerate(rest) if t == "then" or t in CLAUSE_BREAKS), len(rest))
        if stop <= WHEN_PHRASE_MAX:
            rest = rest[stop:]
    rest = rest[1:] if rest[:1] == [","] else rest
    if rest[:1] == ["then"]:
        for tok, _, _ in reversed(before):
            if tok in _SENTENCE_BREAKS:
                break
            if tok in MOVE_WORDS:
                return True
    return False


def _then_after_history(before: list[tuple[str, int, int]]) -> bool:
    """True when the value follows `then` (or `then to`) in a chain whose start is framed as
    history: "it was 15 Dec, then 22 Dec", "It was 14 Oct, then 1 Nov, then 15 Nov". Each link
    of the chain back to the `HISTORY_MARKERS` word must be a short dated value (at most
    `CHAIN_LINK_MAX` tokens, a comma included, one of them a number), so "Kickoff was last
    week, then 29 Jan is the target" is not a chain."""
    toks = [t for t, _, _ in before]
    while True:
        if toks[-1:] == ["to"]:
            toks = toks[:-1]
        if toks[-1:] != ["then"]:
            return False
        toks = toks[:-1]
        link: list[str] = []
        while toks and toks[-1] != "then" and toks[-1] not in HISTORY_MARKERS:
            if toks[-1] in _SENTENCE_BREAKS or toks[-1] in CURRENT_MARKERS or toks[-1] == "(":
                return False
            link.append(toks.pop())
        if not toks or len(link) > CHAIN_LINK_MAX or not any(t.isdigit() for t in link):
            return False
        if toks[-1] in HISTORY_MARKERS:
            return True


#: A value after one of these words in its clause is negated ("not 76", "no longer active").
NEGATORS = frozenset("not no never nor neither isn aren wasn weren without".split())


def negated(norm: str, start: int) -> bool:
    """True when a `NEGATORS` word comes before `norm[start:]` in its clause, with no
    `CURRENT_MARKERS` word between them: "the totals are not 76 and 71", "not active".
    `norm` comes from `normalize_marked`."""
    for tok, _, _ in reversed(marked_tokens(norm[:start])):
        if tok in CLAUSE_BREAKS or tok in CURRENT_MARKERS:
            return False
        if tok in NEGATORS:
            return True
    return False


def phrase_spans(norm: str, phrase: str) -> list[tuple[int, int]]:
    """Character spans of whole-word occurrences of `phrase` in normalized text `norm`.

    Matches the same occurrences as `contains_phrase`: words in order, separated by anything
    that is not a letter or digit.
    """
    words = _WORD.findall(normalize(phrase))
    if not words:
        return []
    pat = r"(?<![a-z0-9])" + r"[^a-z0-9]+".join(map(re.escape, words)) + r"(?![a-z0-9])"
    return [m.span() for m in re.finditer(pat, norm)]
