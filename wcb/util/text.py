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
