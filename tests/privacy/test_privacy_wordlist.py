"""Tests for the scanner's built-in vocabulary (wcb.privacy.wordlist) and how it is applied."""

from __future__ import annotations

import pytest

from wcb.privacy import wordlist
from wcb.privacy.scan import _Vocab

ALL_SETS = {
    "COMMON_WORDS": wordlist.COMMON_WORDS,
    "MONTHS": wordlist.MONTHS,
    "WEEKDAYS": wordlist.WEEKDAYS,
    "CALENDAR_WORDS": wordlist.CALENDAR_WORDS,
    "PLACES": wordlist.PLACES,
    "TECH_TERMS": wordlist.TECH_TERMS,
    "FIRST_NAMES": wordlist.FIRST_NAMES,
    "SURNAMES": wordlist.SURNAMES,
}


@pytest.mark.parametrize("name", sorted(ALL_SETS))
def test_sets_are_lowercase_single_tokens(name):
    words = ALL_SETS[name]
    assert words, name
    bad = sorted(w for w in words if w != w.lower() or not w or any(c.isspace() for c in w))
    assert not bad, f"{name}: {bad[:10]}"


def test_sets_are_reasonably_sized():
    assert len(wordlist.COMMON_WORDS) > 3000
    assert len(wordlist.FIRST_NAMES) > 400
    assert len(wordlist.SURNAMES) > 400


def test_calendar_words_are_never_reported():
    for w in ("monday", "friday", "january", "sept", "q3", "christmas"):
        assert w in wordlist.NEVER_REPORTED


def test_names_are_separate_from_never_reported():
    # Names that are not also ordinary words must stay reportable (as low severity).
    for name in ("michael", "priya", "nguyen", "patel"):
        assert name in wordlist.COMMON_NAMES
        assert name not in wordlist.NEVER_REPORTED


@pytest.fixture(scope="module")
def vocab() -> _Vocab:
    return _Vocab()


@pytest.mark.parametrize(
    "word",
    [
        "planning",
        "planned",
        "scheduled",
        "reviews",
        "payments",
        "cities",
        "summarization",
        "stability",
        "aggregation",
        "unclear",
        "rework",
        "follow-up",
        "don't",
        "team's",
        "urls",
        "yyyy-mm-dd",
        "valueerror",
        "slack",
        "london",
        "q",
    ],
)
def test_common_words_and_inflections(vocab, word):
    assert vocab.is_common(word)


@pytest.mark.parametrize(
    "word", ["quillon", "zephyrine", "vexmoor", "tessellate", "walker", "banks", "michael"]
)
def test_invented_words_and_names_are_not_common(vocab, word):
    assert not vocab.is_common(word)


def test_names(vocab):
    assert vocab.is_name("michael")
    assert vocab.is_name("smith-jones")
    assert not vocab.is_name("quillon")


def test_allowlist_words_extend_common():
    v = _Vocab(["zephyrine"])
    assert v.is_common("zephyrine")
    assert v.is_common("zephyrine's")


def test_frozen_vocab_does_not_retain_new_words():
    v = _Vocab()
    assert v.is_common("planning")
    v.freeze()
    assert not v.is_common("quorvane")
    assert "quorvane" not in v._cache
    v.forget_scratch()
    assert "quorvane" not in v._scratch
    assert "planning" in v._cache
