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
