"""Privacy leak scanner: find terms from a private repository that appear in benchmark content.

white-collar-bench is synthetic, but its authors (people and models) may have seen a real,
private knowledge-work repository. `scan` checks that no identifying detail from such a
repository has crept into the benchmark corpus (worlds, docs, contract). See docs/privacy.md for
the policy, the workflow and how to triage findings.

What counts as a term:

- **email**: an email address, compared in full.
- **domain**: an email domain or a bare domain name such as ``<org>.com`` in prose.
- **url_host**: the host of an ``http(s)://`` or ``www.`` URL.
- **proper_noun**: a capitalized word (medium, or low for very common personal names) or a run of
  2-4 capitalized words such as a full name or an organization name (high).
- **phrase**: a run of 6 or more words in which every 6-word window has at least two different
  words that are not common English (high). This catches copied sentences.

Hosts are compared by registrable domain, so ``mail.<org>.com`` in one place matches
``<org>.com`` in the other. Reserved documentation TLDs (``.example``, ``.test``, ``.invalid``,
``.localhost``) and well-known public hosts (``github.com``, ``arxiv.org``, ...) are ignored.

How a scan runs:

1. Walk the corpus and index candidate terms (6-grams are kept as hashes).
2. Walk the private repository. For each file, keep only the candidate terms that are already in
   the corpus index and count how many private files contain each.
3. Walk the corpus again and report each overlapping term with the corpus file(s) it is in.

Privacy properties:

- The private repository is read at run time only. Nothing derived from it is written to disk.
- Across the scan, memory holds only terms that already occur in the benchmark corpus, plus
  counts. Each private file's text and terms are discarded as soon as it has been processed.
- A `Finding` names the benchmark-side term, the corpus file and the *number* of private files
  containing the term. It never contains a private path or private context.

Suppressing false positives: besides the built-in lists in `wcb.privacy.wordlist`, a file named
``.privacy-allow.txt`` (one term per line, ``#`` comments) is read from each corpus path and its
parent directories up to the enclosing repository root (a directory with ``.git`` or
``pyproject.toml``).
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import unicodedata
import zipfile
import zlib
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

from wcb.privacy import wordlist

__all__ = [
    "ALLOWLIST_FILENAME",
    "Finding",
    "extract_terms",
    "scan",
]

# ------------------------------------------------------------------------------ configuration

#: Plain-text suffixes read on both sides.
TEXT_SUFFIXES = frozenset(
    """.md .markdown .txt .rst .org .json .jsonl .yaml .yml .toml .vtt .eml .csv .tsv .ics .html
    .htm .py .ts .tsx .js .jsx .mjs .cjs""".split()
)
#: Binary document formats whose text is extracted on the corpus side only.
DOCUMENT_SUFFIXES = frozenset({".docx", ".xlsx", ".pptx", ".pdf"})
#: Directory names never descended into. Directories containing ``pyvenv.cfg`` are skipped too.
SKIP_DIRS = frozenset(
    """.git .hg .svn node_modules __pycache__ .venv venv .tox .nox .mypy_cache .pytest_cache
    .ruff_cache site-packages .ipynb_checkpoints""".split()
)
#: Private files larger than this are skipped (they are almost always exports or data dumps).
MAX_PRIVATE_FILE_BYTES = 2 * 1024 * 1024
#: Corpus files larger than this are skipped. Generous, because world event logs can be large.
MAX_CORPUS_FILE_BYTES = 64 * 1024 * 1024
#: Cap on decompressed data per zip member or PDF stream (guards against compression bombs).
MAX_INFLATED_BYTES = 32 * 1024 * 1024

#: Allowlist file name, looked up next to the corpus (see module docstring and docs/privacy.md).
ALLOWLIST_FILENAME = ".privacy-allow.txt"

PHRASE_WORDS = 6
MIN_PHRASE_DISTINCTIVE = 2  # distinct non-common words required in each 6-word window
MIN_PHRASE_CHARS = 20  # minimum letters in a 6-word window (drops code like "k: v for k")
MAX_RUN_WORDS = 4

#: Top-level domains reserved for documentation and testing (RFC 2606, RFC 6761).
RESERVED_TLDS = frozenset({"example", "test", "invalid", "localhost"})

#: Public hosts whose appearance on both sides reveals nothing. Matched on the registrable domain.
GENERIC_HOSTS = frozenset(
    """example.com example.org example.net github.com githubusercontent.com github.blog
    gitlab.com bitbucket.org schema.org json-schema.org w3.org whatwg.org ietf.org
    rfc-editor.org iana.org arxiv.org doi.org acm.org ieee.org semanticscholar.org
    aclanthology.org openreview.net neurips.cc anthropic.com claude.ai claude.com openai.com
    chatgpt.com huggingface.co google.com googleapis.com gstatic.com youtube.com youtu.be
    microsoft.com office.com live.com outlook.com hotmail.com msn.com bing.com apple.com
    icloud.com me.com mac.com amazon.com amazonaws.com aws.amazon.com yahoo.com gmail.com
    googlemail.com proton.me protonmail.com wikipedia.org wikimedia.org python.org pypi.org
    readthedocs.org npmjs.com npmjs.org nodejs.org mozilla.org stackoverflow.com
    stackexchange.com linkedin.com twitter.com x.com facebook.com instagram.com reddit.com
    medium.com shields.io creativecommons.org opensource.org apache.org gnu.org
    openxmlformats.org purl.org xmlsoap.org adobe.com ns.adobe.com docker.com docker.io
    kubernetes.io golang.org go.dev rust-lang.org crates.io rubygems.org mit.edu
    slack.com zoom.us notion.so figma.com dropbox.com atlassian.com atlassian.net
    yaml.org toml.io jsonlines.org commonmark.org unicode.org iso.org semver.org spdx.org
    keepachangelog.com pypa.io
    """.split()
)

#: Multi-tenant platforms: the label left of the suffix names the tenant (``<org>.slack.com``),
#: so hosts on these suffixes are compared on ``<tenant>.<suffix>`` instead of the base domain.
TENANT_HOST_SUFFIXES = (
    "github.io",
    "gitlab.io",
    "herokuapp.com",
    "vercel.app",
    "netlify.app",
    "pages.dev",
    "web.app",
    "firebaseapp.com",
    "azurewebsites.net",
    "cloudfront.net",
    "sharepoint.com",
    "atlassian.net",
    "slack.com",
    "zoom.us",
    "webex.com",
    "okta.com",
    "zendesk.com",
    "my.salesforce.com",
    "lightning.force.com",
    "notion.site",
    "substack.com",
    "blogspot.com",
    "wordpress.com",
    "myshopify.com",
    "readthedocs.io",
)

#: Subdomain labels that name a platform function, not a tenant (``app.slack.com``).
GENERIC_HOST_LABELS = frozenset(
    """www www2 app apps api docs doc mail email login auth accounts account support help status
    blog community developer developers dev cdn static assets files media meet join events
    us eu uk au ca""".split()
)
_REGIONAL_LABEL = re.compile(r"[a-z]{2}\d{1,3}(?:web)?")  # e.g. Zoom's "us02web"

#: Second-level labels under country-code TLDs that are not registrable on their own (co.uk).
_SECOND_LEVEL = frozenset(
    {"co", "com", "org", "net", "ac", "gov", "edu", "ne", "or", "go", "ltd", "plc"}
)

#: TLDs recognised for bare domain names in prose ("see <org>.com"). URLs and email
#: addresses accept any TLD; bare names need a known TLD to avoid matching "notes.md".
_BARE_TLDS = (
    "com net org io co ai dev app edu gov mil int info biz tech cloud xyz us uk eu de fr nl be ch "
    "at se dk fi ca au nz jp cn kr sg hk tw br mx es pt it pl cz ie il za ru example"
).split()

#: Shared role mailboxes. Two copies of ``noreply@github.com`` are not a leak.
_ROLE_MAILBOXES = frozenset(
    """noreply no-reply donotreply do-not-reply support info admin hello contact help team
    security privacy sales billing webmaster postmaster abuse notifications notification
    mailer-daemon calendar-notification""".split()
)

#: Lowercase words allowed inside a capitalized run ("University of Lisbon", "Ludwig van Beethoven").
_RUN_CONNECTORS = frozenset(
    {"of", "de", "da", "di", "du", "del", "della", "der", "den", "van", "von", "la", "le", "&"}
)

SEVERITIES = ("high", "medium", "low")
KINDS = ("email", "domain", "url_host", "proper_noun", "phrase")
_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}
_KIND_RANK = {k: i for i, k in enumerate(KINDS)}


# ------------------------------------------------------------------------------ findings


@dataclass
class Finding:
    """One term that occurs both in the private repository and in the benchmark corpus.

    Attributes:
        kind: ``email``, ``domain``, ``url_host``, ``proper_noun`` or ``phrase``.
        severity: ``high``, ``medium`` or ``low``.
        term: the overlapping term as it appears in the benchmark corpus (first occurrence).
        corpus_file: the first corpus file (in sorted order) that contains the term.
        count_private: how many private files contain the term. For a merged phrase, the largest
            count among its 6-word windows.
        other_files: further corpus files that contain the term, sorted.
    """

    kind: str
    severity: str
    term: str
    corpus_file: str
    count_private: int
    other_files: tuple[str, ...] = ()

    def sort_key(self) -> tuple:
        return (
            _SEVERITY_RANK.get(self.severity, 99),
            _KIND_RANK.get(self.kind, 99),
            self.term.casefold(),
            self.term,
            self.corpus_file,
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["other_files"] = list(self.other_files)
        return d

    def format(self) -> str:
        """One line: severity, kind, term, where it is in the corpus, and the private file count."""
        term = " ".join(self.term.split())
        if len(term) > 140:
            term = term[:137] + "..."
        more = f" (+{len(self.other_files)} more corpus files)" if self.other_files else ""
        n = self.count_private
        return (
            f'{self.severity.upper():6} {self.kind:11} "{term}" in {self.corpus_file}{more}; '
            f"in {n} private file{'s' if n != 1 else ''}"
        )


# ------------------------------------------------------------------------------ text helpers


def _fold(s: str) -> str:
    """Case- and accent-insensitive key for a word or term."""
    s = s.replace("’", "'")
    if s.isascii():
        return s.lower()
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def _norm_term(s: str) -> str:
    return " ".join(_fold(s).split())


# Suffix rules used to match inflected forms against COMMON_WORDS: (suffix, replacements).
_SUFFIX_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("iest", ("y",)),
    ("ies", ("y",)),
    ("ied", ("y",)),
    ("ier", ("y",)),
    ("ily", ("y",)),
    ("izations", ("ize",)),
    ("ization", ("ize",)),
    ("isations", ("ise",)),
    ("isation", ("ise",)),
    ("ations", ("e", "", "ate")),
    ("ation", ("e", "", "ate")),
    ("ions", ("", "e")),
    ("ion", ("", "e")),
    ("ility", ("le",)),
    ("ities", ("", "e")),
    ("ity", ("", "e")),
    ("izes", ("", "e", "y")),
    ("ized", ("", "e", "y")),
    ("ize", ("", "e", "y")),
    ("ises", ("", "e", "y")),
    ("ised", ("", "e", "y")),
    ("ise", ("", "e", "y")),
    ("ally", ("", "al")),
    ("al", ("", "e")),
    ("ive", ("", "e")),
    ("ments", ("",)),
    ("ment", ("",)),
    ("ness", ("",)),
    ("less", ("",)),
    ("ful", ("",)),
    ("able", ("", "e")),
    ("ings", ("", "e")),
    ("ing", ("", "e")),
    ("ers", ("", "e")),
    ("er", ("", "e")),
    ("est", ("", "e")),
    ("ed", ("", "e")),
    ("es", ("", "e")),
    ("ly", ("",)),
    ("s", ("",)),
)


#: Prefixes stripped when matching against COMMON_WORDS (only if 5+ letters remain).
_PREFIXES = ("multi", "inter", "under", "over", "self", "non", "pre", "sub", "un", "re", "co")


def _variants(word: str) -> list[str]:
    """Candidate base forms of an inflected English word ("planning" -> "plann", "plan", ...)."""
    out: list[str] = []
    for suffix, replacements in _SUFFIX_RULES:
        if not word.endswith(suffix) or len(word) - len(suffix) < 3:
            continue
        if suffix == "s" and word.endswith(("ss", "us", "is")):
            continue
        stem = word[: -len(suffix)]
        for rep in replacements:
            out.append(stem + rep)
        if len(stem) >= 4 and stem[-1] == stem[-2] and stem[-1] not in "aeiouls":
            out.append(stem[:-1])  # undouble: "planned" -> "plann" -> "plan"
    return out


class _Vocab:
    """Common-word and name lookups, extended by single-word allowlist entries."""

    def __init__(self, extra_common: Iterable[str] = ()):
        self.english = wordlist.COMMON_WORDS
        letters = frozenset("abcdefghijklmnopqrstuvwxyz")
        self.never = wordlist.NEVER_REPORTED | letters | frozenset(extra_common)
        self.names = wordlist.COMMON_NAMES
        self.first_names = wordlist.FIRST_NAMES
        self._cache: dict[str, bool] = {}
        self._scratch: dict[str, bool] = {}  # per-file cache once frozen (see freeze())
        self._frozen = False

    def is_common(self, key: str) -> bool:
        """True if `key` (a folded word) is ordinary vocabulary that must not be reported."""
        hit = self._cache.get(key)
        if hit is None:
            hit = self._scratch.get(key)
            if hit is None:
                hit = self._compute_common(key)
                (self._scratch if self._frozen else self._cache)[key] = hit
        return hit

    def freeze(self) -> None:
        """Stop adding words to the long-lived cache.

        Called after the corpus pass, so that words seen only in the private repository live in
        the scratch cache, which `forget_scratch` empties after every private file.
        """
        self._frozen = True

    def forget_scratch(self) -> None:
        self._scratch = {}

    def _compute_common(self, key: str) -> bool:
        if key in self.never:
            return True
        if "-" in key:
            parts = [p for p in key.split("-") if p]
            return bool(parts) and all(self.is_common(p) for p in parts)
        if "'" in key:
            base, _, suffix = key.partition("'")
            return suffix in ("s", "d", "ll", "re", "ve", "m", "t") and self.is_common(base)
        if not key.isalpha() or key in self.names:
            return False  # a known name is never "common" by inflection ("Walker", "Banks")
        for v in _variants(key):
            if v in self.never:
                return True
            if any(v2 in self.english for v2 in _variants(v)):
                return True
        for prefix in _PREFIXES:
            rest = key[len(prefix) :]
            if key.startswith(prefix) and len(rest) >= 5 and self.is_common(rest):
                return True  # "unclear", "rework", "multiregion"
        return False

    def is_name(self, key: str) -> bool:
        parts = [p for p in key.replace(" ", "-").split("-") if p]
        return bool(parts) and all(p.partition("'")[0] in self.names for p in parts)


# ------------------------------------------------------------------------------ term extraction

_EMAIL = re.compile(
    r"(?<![\w.%+-])([A-Za-z0-9][A-Za-z0-9._%+-]{0,63})@"
    r"((?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63})(?![\w-])"
)
_URL = re.compile(
    r"(?:\b(?:https?|ftps?)://|(?<![\w.@/-])(?=www\.))([^\s/?#<>\"'`)\]|\\,;]+)", re.IGNORECASE
)
_URL_FULL = re.compile(r"\b(?:https?|ftps?)://\S+|(?<![\w.@/-])www\.\S+", re.IGNORECASE)
_BARE_DOMAIN = re.compile(
    r"(?<![\w.@/-])((?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+(?:"
    + "|".join(_BARE_TLDS)
    + r"))(?![\w-]|\.[A-Za-z0-9])",
    re.IGNORECASE,
)
_HOSTNAME = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{1,62}")

# Characters that end a "piece" of text for proper-noun scanning: line breaks, structural
# separators in calendar/CSV/table/markup syntax, escaped newlines, and "key:value" colons.
_PIECE_SPLIT = re.compile(r"\\[nNrt,;]|[\r\n;=|\t<>/\\\[\]{}]+|:(?=\S)")
_STRIP_LEAD = "\"'“”‘’«»([{*_~`¿¡#"
_STRIP_TRAIL = "\"'“”‘’«»)]}*_~`.,;:!?…"
_SENTENCE_END = frozenset(".!?:…")
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*(?:-[^\W\d_]+(?:['’][^\W\d_]+)*)*")
_PHRASE_TOKEN = re.compile(r"[^\W_]+(?:['’][^\W_]+)*")


def _clean_host(raw: str) -> str | None:
    """Normalize a host string; None if it is not a plausible public DNS name."""
    host = raw.rsplit("@", 1)[-1].split(":", 1)[0].strip(".").lower()
    if host.startswith("www."):
        host = host[4:]
    if not _HOSTNAME.fullmatch(host):
        return None
    return host


def _host_key(host: str) -> str | None:
    """Comparison key for a normalized host, or None if the host should be ignored."""
    labels = host.split(".")
    if len(labels) < 2 or labels[-1] in RESERVED_TLDS or all(p.isdigit() for p in labels):
        return None
    for suffix in TENANT_HOST_SUFFIXES:
        if host == suffix:
            return None
        if host.endswith("." + suffix):
            tenant = host[: -len(suffix) - 1].rsplit(".", 1)[-1]
            if tenant in GENERIC_HOST_LABELS or _REGIONAL_LABEL.fullmatch(tenant):
                return None
            return f"{tenant}.{suffix}"
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _SECOND_LEVEL:
        base = ".".join(labels[-3:])
    else:
        base = ".".join(labels[-2:])
    if base in GENERIC_HOSTS or host in GENERIC_HOSTS:
        return None
    return base


def _email_key(local: str, domain: str) -> str | None:
    host = _clean_host(domain)
    if host is None:
        return None
    labels = host.split(".")
    if labels[-1] in RESERVED_TLDS or ".".join(labels[-2:]) in (
        "example.com",
        "example.org",
        "example.net",
    ):
        return None
    local = local.lower()
    if local in _ROLE_MAILBOXES and _host_key(host) is None:
        return None
    return f"{local}@{host}"


@dataclass
class _Token:
    surface: str
    key: str
    connector: bool = False
    common: bool = True  # ordinary vocabulary ("Next", "Mark")
    name: bool = False  # a known personal name ("Mark", "Patel")
    first_name: bool = False  # a known first name


@dataclass
class _Terms:
    """Everything extracted from one text. Never persisted."""

    emails: dict[str, str] = field(default_factory=dict)  # key -> surface
    hosts: dict[tuple[str, str], str] = field(default_factory=dict)  # (kind, host) -> surface
    bare_hosts: set[str] = field(default_factory=set)  # hosts written as bare names in prose
    words: dict[str, str] = field(default_factory=dict)  # folded word -> surface
    word_mid: Counter = field(default_factory=Counter)  # capitalized, not sentence-initial
    word_initial: Counter = field(default_factory=Counter)  # capitalized, sentence-initial
    lower: Counter = field(default_factory=Counter)  # all-lowercase standalone words
    runs: dict[str, tuple[str, str]] = field(default_factory=dict)  # key -> (surface, first word)
    clean: str = ""  # text with URLs and emails removed, used for phrases
    # Phrase tokens of `clean`: (start offset, end offset, folded word, is distinctive).
    tokens: list[tuple[int, int, str, bool]] = field(default_factory=list)


CODE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"})


def _is_code(path: Path) -> bool:
    """Source code shares idioms with any other code base, so phrase matching skips it.

    Names, emails, domains and hosts in code are still compared.
    """
    return Path(path).suffix.lower() in CODE_SUFFIXES


def _analyze(text: str, vocab: _Vocab, *, phrases: bool = True) -> _Terms:
    t = _Terms()
    for m in _URL.finditer(text):
        raw = m.group(1)
        host = _clean_host(raw)
        if host is not None:
            surface = raw.rsplit("@", 1)[-1].split(":", 1)[0].strip(".")
            t.hosts.setdefault(("url_host", host), surface)
    clean = _URL_FULL.sub("\n", text)

    for m in _EMAIL.finditer(clean):
        key = _email_key(m.group(1), m.group(2))
        if key is not None:
            t.emails.setdefault(key, m.group(0))
        host = _clean_host(m.group(2))
        if host is not None:
            t.hosts.setdefault(("domain", host), m.group(2))
    clean = _EMAIL.sub("\n", clean)

    for m in _BARE_DOMAIN.finditer(clean):
        host = _clean_host(m.group(1))
        if host is not None:
            t.hosts.setdefault(("domain", host), m.group(1))
            t.bare_hosts.add(host)
    clean = _BARE_DOMAIN.sub(" ", clean)

    _scan_capitals(clean, vocab, t)
    if phrases:
        t.clean = clean
        for m in _PHRASE_TOKEN.finditer(clean):
            key = _fold(m.group())
            distinctive = (
                len(key) >= 3 and not any(c.isdigit() for c in key) and not vocab.is_common(key)
            )
            t.tokens.append((m.start(), m.end(), key, distinctive))
    return t


def _scan_capitals(text: str, vocab: _Vocab, t: _Terms) -> None:
    """Collect capitalized words, runs of capitalized words, and lowercase word counts."""
    for piece in _PIECE_SPLIT.split(text):
        run: list[_Token] = []
        initial = True
        for chunk in piece.split():
            core = chunk.lstrip(_STRIP_LEAD)
            if len(core) != len(chunk):
                _flush_run(run, t)
            stripped = core.rstrip(_STRIP_TRAIL)
            trail = core[len(stripped) :]
            core = stripped

            # Middle initial inside a name: "Imogen K. Tran".
            if run and len(core) == 1 and core.isupper() and trail == "." and not run[-1].connector:
                run.append(_Token(core + ".", _fold(core) + ".", connector=True))
                continue
            if chunk == "&" and run:
                run.append(_Token("&", "&", connector=True))
                continue

            if core and _WORD.fullmatch(core):
                word = core
                if word[-2:] in ("'s", "’s") and len(word) > 3:
                    word = word[:-2]
                if word[0].isupper():
                    parts = word.split("-")
                    if len(parts) > 1 and not all(p[:1].isupper() for p in parts):
                        word = parts[0]  # "Imogen-led" -> "Imogen"; the rest is not a name
                        trail = trail or "-"
                    key = _fold(word)
                    common = vocab.is_common(key)
                    if not common:
                        t.words.setdefault(key, word)
                        (t.word_initial if initial else t.word_mid)[key] += 1
                    run.append(
                        _Token(
                            word,
                            key,
                            common=common,
                            name=vocab.is_name(key),
                            first_name=key in vocab.first_names,
                        )
                    )
                else:
                    key = _fold(word)
                    if run and key in _RUN_CONNECTORS:
                        run.append(_Token(word, key, connector=True))
                    else:
                        _flush_run(run, t)
                        t.lower[key] += 1
                if trail:
                    _flush_run(run, t)
                    initial = any(c in _SENTENCE_END for c in trail)
                else:
                    initial = False
            else:
                # Numbers, identifiers, list markers, punctuation: end the run. A list marker at
                # the start of a piece keeps the next word sentence-initial.
                _flush_run(run, t)
                if not initial:
                    initial = bool(chunk) and chunk[-1] in _SENTENCE_END
        _flush_run(run, t)


def _flush_run(run: list[_Token], t: _Terms) -> None:
    """Record every window of 2-4 capitalized words that could be a name.

    A window must start with a non-common word ("Quillon Marbeck", "Tessellate Analytics"), or
    with a first name that is also a common word, followed by another name or non-common word
    ("Mark Quellby", "Grant Vexley", but not "Grant Proposal").
    """
    while run and run[-1].connector:
        run.pop()
    caps = [i for i, tok in enumerate(run) if not tok.connector]
    for a_pos, a in enumerate(caps):
        first = run[a]
        if first.common and not first.first_name:
            continue
        for b_pos in range(a_pos + 1, min(a_pos + MAX_RUN_WORDS, len(caps))):
            b = caps[b_pos]
            toks = run[a : b + 1]
            if first.common and not any(
                tok.name or not tok.common for tok in toks[1:] if not tok.connector
            ):
                continue
            key = " ".join(tok.key for tok in toks)
            if key not in t.runs:
                t.runs[key] = (" ".join(tok.surface for tok in toks), run[a].key)
    run.clear()


def _grams(t: _Terms) -> Iterator[tuple[int, int]]:
    """(start token index, hash) for each 6-word window that is distinctive enough to report.

    A window qualifies if it has at least two different non-common words and enough letters.
    Hashes are Python's per-process string hashes: comparable within one scan, never stored.
    """
    toks = t.tokens
    n = len(toks)
    if n < PHRASE_WORDS:
        return
    flags = [1 if tok[3] else 0 for tok in toks]
    window = sum(flags[:PHRASE_WORDS])
    for i in range(n - PHRASE_WORDS + 1):
        if i:
            window += flags[i + PHRASE_WORDS - 1] - flags[i - 1]
        if window < MIN_PHRASE_DISTINCTIVE:
            continue
        keys = [tok[2] for tok in toks[i : i + PHRASE_WORDS]]
        if sum(map(len, keys)) < MIN_PHRASE_CHARS:
            continue
        distinct = {k for k, tok in zip(keys, toks[i : i + PHRASE_WORDS], strict=True) if tok[3]}
        if len(distinct) >= MIN_PHRASE_DISTINCTIVE:
            yield i, hash("\x1f".join(keys))


def _is_proper(mid: int, initial: int, lower: int) -> bool:
    """A word counts as a proper noun if it is capitalized at least as often as it is lowercase.

    This drops ordinary words missing from the built-in list, which are capitalized only at
    sentence starts and in headings ("Telemetry is live" vs "the telemetry"), while keeping names
    that quick notes sometimes write in lowercase ("review samir's doc"). Lowercase slugs such as
    ``quillon-marbeck`` are not counted as lowercase uses. `mid` and `initial` are counted
    separately so the rule can be tightened without changing the extraction.
    """
    capitalized = mid + initial
    return capitalized > 0 and capitalized >= lower


def extract_terms(texts: Iterable[str], *, min_len: int = 4) -> dict[str, set[str]]:
    """Extract candidate identifying terms from texts, keyed by kind.

    Returns a dict with keys ``email``, ``domain``, ``url_host``, ``proper_noun`` and
    ``phrase``. Emails and hosts are lowercased and exclude reserved and generic domains;
    proper nouns keep the surface form of their first occurrence (single words of at least
    `min_len` letters, and runs of 2-4 capitalized words); phrases are lowercased 6-word windows
    with at least two non-common words. This is the extraction `scan` applies to both sides; it
    is exposed for testing and for checking a single text by hand.
    """
    vocab = _Vocab()
    out: dict[str, set[str]] = {k: set() for k in KINDS}
    words: dict[str, str] = {}
    runs: dict[str, tuple[str, str]] = {}
    mid: Counter = Counter()
    init: Counter = Counter()
    lower: Counter = Counter()
    for text in texts:
        t = _analyze(text, vocab)
        out["email"].update(t.emails)
        for (kind, host), _surface in t.hosts.items():
            if _host_key(host) is not None:
                out[kind].add(host)
        for k, v in t.words.items():
            words.setdefault(k, v)
        for k, v in t.runs.items():
            runs.setdefault(k, v)
        mid.update(t.word_mid)
        init.update(t.word_initial)
        lower.update(t.lower)
        toks = t.tokens
        for i, _h in _grams(t):
            out["phrase"].add(" ".join(tok[2] for tok in toks[i : i + PHRASE_WORDS]))
    for k, surface in words.items():
        if len(k) >= min_len and _is_proper(mid[k], init[k], lower[k]):
            out["proper_noun"].add(surface)
    for k, (surface, first) in runs.items():
        if len(k) >= min_len and (
            vocab.is_common(first) or _is_proper(mid[first], init[first], lower[first])
        ):
            out["proper_noun"].add(surface)
    return out


# ------------------------------------------------------------------------------ file reading


def _is_within(path: Path, roots: Iterable[Path]) -> bool:
    return any(path == r or r in path.parents for r in roots)


def _iter_files(root: Path, suffixes: frozenset[str], exclude: list[Path]) -> Iterator[Path]:
    """Files under `root` with a wanted suffix, in sorted order, skipping junk and `exclude`."""
    if root.is_file():
        if root.suffix.lower() in suffixes and root.name != ALLOWLIST_FILENAME:
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        keep = []
        for name in sorted(dirnames):
            sub = d / name
            if name in SKIP_DIRS or (sub / "pyvenv.cfg").exists():
                continue
            if exclude and _is_within(sub.resolve(), exclude):
                continue
            keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            p = d / name
            if name == ALLOWLIST_FILENAME or p.suffix.lower() not in suffixes:
                continue
            if exclude and _is_within(p.resolve(), exclude):
                continue
            yield p


def _read_text(path: Path, *, max_bytes: int, documents: bool) -> str | None:
    """Extracted text of a file, or None if it is too large, binary or unreadable."""
    try:
        if not path.is_file() or path.stat().st_size > max_bytes:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    suffix = path.suffix.lower()
    if suffix in DOCUMENT_SUFFIXES:
        if not documents:
            return None
        return _pdf_text(data) if suffix == ".pdf" else _office_text(data)
    if b"\x00" in data[:8192]:
        return None
    text = data.decode("utf-8", errors="replace").lstrip("\ufeff")
    if suffix == ".json":
        return _json_text(text)
    if suffix == ".jsonl":
        return "\n".join(_json_text(line) for line in text.splitlines())
    if suffix in (".html", ".htm"):
        return _html_text(text)
    if suffix == ".eml":
        return _eml_text(text)
    return text


def _json_text(text: str) -> str:
    """All string keys and values of a JSON document in document order, one per line.

    Returns the raw text if it is not valid JSON. Iterative, so deep nesting cannot overflow.
    """
    try:
        stack: list = [json.loads(text)]
    except ValueError:
        return text
    out: list[str] = []
    while stack:
        v = stack.pop()
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            items: list = []
            for k, item in v.items():
                items += [str(k), item]
            stack.extend(reversed(items))
        elif isinstance(v, list):
            stack.extend(reversed(v))
    return "\n".join(out)


_HTML_DROP = re.compile(r"<(script|style)\b.*?</\1\s*>", re.IGNORECASE | re.DOTALL)
_HTML_BLOCK = re.compile(
    r"<(?:br|/?(?:p|div|li|ul|ol|h[1-6]|tr|td|th|table|section|article|header|footer|blockquote|pre))\b[^>]*>",
    re.IGNORECASE,
)
_HTML_TAG = re.compile(r"<[^>]+>")
_HTML_LINK = re.compile(r"""\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def _html_text(text: str) -> str:
    links = _HTML_LINK.findall(text)
    body = _HTML_DROP.sub(" ", text)
    body = _HTML_BLOCK.sub("\n", body)
    body = html.unescape(_HTML_TAG.sub(" ", body))
    return body + "\n" + "\n".join(html.unescape(u).replace("mailto:", "") for u in links)


def _eml_text(text: str) -> str:
    """Raw message plus decoded headers and decoded base64/quoted-printable text parts."""
    import email
    from email import policy

    extra: list[str] = []
    try:
        msg = email.message_from_string(text, policy=policy.default)
        if "=?" in text:
            for h in ("From", "To", "Cc", "Reply-To", "Subject"):
                if msg[h]:
                    extra.append(str(msg[h]))
        for part in msg.walk():
            if part.is_multipart() or part.get_content_maintype() != "text":
                continue
            if (part.get("Content-Transfer-Encoding") or "").lower() in (
                "base64",
                "quoted-printable",
            ):
                content = part.get_content()
                if part.get_content_subtype() == "html":
                    content = _html_text(content)
                extra.append(content)
    except Exception:  # noqa: BLE001 - malformed mail: fall back to the raw text
        pass
    return "\n".join([text, *extra])


_XML_BREAK = re.compile(
    r"</(?:\w+:)?(?:p|tr|row|si|txBody|h|list-item|comment)>|<(?:\w+:)?(?:br|cr)\b[^>]*>",
    re.IGNORECASE,
)
_XML_TAB = re.compile(r"</(?:\w+:)?(?:tc|c|is)>|<(?:\w+:)?tab\b[^>]*/>", re.IGNORECASE)
_XML_TAG = re.compile(r"<[^>]*>")
_XML_AUTHOR_ATTR = re.compile(r"\b(?:\w+:)?author=\"([^\"]*)\"")
_XML_TARGET = re.compile(r"\bTarget=\"([^\"]*)\"")


def _office_text(data: bytes) -> str | None:
    """Text of a .docx/.xlsx/.pptx: body text, comments, metadata, author attributes, link targets."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, OSError, ValueError):
        return None
    out: list[str] = []
    with zf:
        for info in sorted(zf.infolist(), key=lambda i: i.filename):
            name = info.filename
            if not name.endswith((".xml", ".rels")) or info.file_size > MAX_INFLATED_BYTES:
                continue
            try:
                xml = zf.read(info).decode("utf-8", errors="replace")
            except (zipfile.BadZipFile, OSError, ValueError, NotImplementedError, RuntimeError):
                continue
            if name.endswith(".rels"):
                out.extend(html.unescape(u) for u in _XML_TARGET.findall(xml) if ":" in u)
                continue
            out.extend(html.unescape(v) for v in _XML_AUTHOR_ATTR.findall(xml) if v.strip())
            if name.startswith(("docProps/", "customXml/")):
                body = _XML_TAG.sub("\n", xml)
            else:
                body = _XML_TAB.sub("\t", _XML_BREAK.sub("\n", xml))
                body = _XML_TAG.sub("", body)
            out.append(html.unescape(body))
    return "\n".join(out)


def _pdf_text(data: bytes) -> str:
    """Best-effort PDF text: pypdf if installed, else a small built-in content-stream reader."""
    try:
        import pypdf  # optional dependency
    except ImportError:
        pypdf = None
    if pypdf is not None:
        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            parts = [page.extract_text() or "" for page in reader.pages]
            meta = reader.metadata or {}
            parts.extend(str(v) for v in meta.values() if v)
            parts.append(_pdf_text_builtin(data, metadata_only=True))
            return "\n".join(parts)
        except Exception:  # noqa: BLE001 - fall back to the built-in reader
            pass
    return _pdf_text_builtin(data)


_PDF_STREAM = re.compile(rb"(?<!end)stream\r?\n")
_PDF_LITERAL = rb"\((?:\\.|[^\\()]|\((?:\\.|[^\\()])*\))*\)"
_PDF_INFO = re.compile(
    rb"/(?:Author|Title|Subject|Keywords|Creator|URI)\s*(" + _PDF_LITERAL + rb"|<[0-9A-Fa-f\s]*>)",
    re.DOTALL,
)
_PDF_TOKEN = re.compile(
    _PDF_LITERAL
    + rb"|<<|>>|<[0-9A-Fa-f\s]*>|\[|\]|[-+]?(?:\d+\.?\d*|\.\d+)|/[^\s/\[\]()<>{}%]*|%[^\r\n]*"
    rb"|[^\s/\[\]()<>{}%]+",
    re.DOTALL,
)
_PDF_ESCAPE = re.compile(rb"\\([nrtbf()\\]|[0-7]{1,3}|\r\n|\r|\n)")
_PDF_ESCAPES = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\b",
    b"f": b"\f",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}


def _pdf_decode(raw: bytes) -> str:
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    return raw.decode("cp1252", errors="replace")


def _pdf_string(tok: bytes) -> str:
    if tok.startswith(b"("):

        def repl(m: re.Match) -> bytes:
            s = m.group(1)
            if s in _PDF_ESCAPES:
                return _PDF_ESCAPES[s]
            if s[:1].isdigit():
                return bytes([int(s, 8) & 0xFF])
            return b""  # escaped line break: continuation

        return _pdf_decode(_PDF_ESCAPE.sub(repl, tok[1:-1]))
    hexdigits = re.sub(rb"\s+", b"", tok[1:-1])
    if len(hexdigits) % 2:
        hexdigits += b"0"
    try:
        raw = bytes.fromhex(hexdigits.decode("ascii"))
    except ValueError:
        return ""
    if raw.startswith(b"\xfe\xff"):
        return _pdf_decode(raw)
    # Hex strings in content streams are often glyph IDs; keep only printable text.
    return _pdf_decode(raw) if all(32 <= b < 127 or b in (9, 10, 13) for b in raw) else ""


def _pdf_inflate(raw: bytes) -> bytes:
    try:
        return zlib.decompressobj().decompress(raw, MAX_INFLATED_BYTES)
    except zlib.error:
        return raw


def _pdf_content_text(content: bytes) -> str:
    out: list[str] = []
    pending: list[str] = []
    numbers: list[float] = []
    in_array = False
    for m in _PDF_TOKEN.finditer(content):
        tok = m.group()
        c = tok[:1]
        if c == b"(" or (c == b"<" and tok != b"<<" and tok != b">>"):
            pending.append(_pdf_string(tok))
        elif c in b"+-.0123456789" and c:
            try:
                value = float(tok)
            except ValueError:
                continue
            if in_array and value < -180:
                pending.append(" ")  # large negative kerning inside TJ: a word gap
            numbers.append(value)
        elif tok == b"[":
            in_array = True
        elif tok == b"]":
            in_array = False
        elif tok in (b"Tj", b"TJ"):
            out.append("".join(pending) + " ")
            pending, numbers = [], []
        elif tok in (b"'", b'"'):
            out.append("\n" + "".join(pending) + " ")
            pending, numbers = [], []
        elif tok in (b"Td", b"TD"):
            out.append("\n" if len(numbers) >= 2 and numbers[-1] != 0 else " ")
            pending, numbers = [], []
        elif tok in (b"T*", b"Tm", b"ET", b"BT"):
            out.append("\n")
            pending, numbers = [], []
        elif c in (b"/", b"%"):
            continue
        else:
            pending, numbers = [], []
    return "".join(out)


def _pdf_text_builtin(data: bytes, *, metadata_only: bool = False) -> str:
    out: list[str] = []

    def info(blob: bytes) -> None:
        out.extend(_pdf_string(m.group(1)) for m in _PDF_INFO.finditer(blob))

    info(data)
    pos = 0
    while True:
        m = _PDF_STREAM.search(data, pos)
        if m is None:
            break
        end = data.find(b"endstream", m.end())
        if end < 0:
            break
        content = _pdf_inflate(data[m.end() : end])
        pos = end + len(b"endstream")
        if not metadata_only and b"BT" in content and (b"Tj" in content or b"TJ" in content):
            out.append(_pdf_content_text(content))
        else:
            info(content)  # object streams can hold /Author and /URI entries
    return "\n".join(out)


# ------------------------------------------------------------------------------ allowlist


@dataclass
class _Allowlist:
    terms: set[str] = field(default_factory=set)
    words: set[str] = field(default_factory=set)
    hosts: set[str] = field(default_factory=set)
    files: list[Path] = field(default_factory=list)

    @classmethod
    def load(cls, corpus: list[Path]) -> _Allowlist:
        allow = cls()
        for path in _allowlist_files(corpus):
            allow.files.append(path)
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                entry = line.split(" #", 1)[0].strip()
                if not entry or entry.startswith("#"):
                    continue
                norm = _norm_term(entry)
                allow.terms.add(norm)
                if " " not in norm and "@" not in norm:
                    if "." in norm:
                        allow.hosts.add(norm.removeprefix("www."))
                    else:
                        allow.words.add(norm)
        return allow

    def allows(self, kind: str, term: str) -> bool:
        norm = _norm_term(term)
        if norm in self.terms:
            return True
        if kind in ("domain", "url_host"):
            return any(norm == h or norm.endswith("." + h) for h in self.hosts)
        return False


def _allowlist_files(corpus: list[Path]) -> list[Path]:
    """Allowlist files in each corpus directory and its parents up to the repository root."""
    found: list[Path] = []
    for p in corpus:
        start = p.resolve()
        if not start.is_dir():
            start = start.parent
        chain: list[Path] = []
        root_found = False
        for d in (start, *start.parents):
            chain.append(d)
            if (d / ".git").exists() or (d / "pyproject.toml").exists():
                root_found = True
                break
        for d in chain if root_found else [start]:
            f = d / ALLOWLIST_FILENAME
            if f.is_file() and f not in found:
                found.append(f)
    return found


# ------------------------------------------------------------------------------ scan


@dataclass
class _CorpusIndex:
    emails: set[str] = field(default_factory=set)
    host_keys: set[str] = field(default_factory=set)
    words: set[str] = field(default_factory=set)
    word_mid: Counter = field(default_factory=Counter)
    word_initial: Counter = field(default_factory=Counter)
    lower: Counter = field(default_factory=Counter)
    runs: dict[str, str] = field(default_factory=dict)  # run key -> first word key
    grams: set[int] = field(default_factory=set)

    def add(self, t: _Terms) -> None:
        self.emails.update(t.emails)
        for _kind, host in t.hosts:
            key = _host_key(host)
            if key is not None:
                self.host_keys.add(key)
        self.words.update(t.words)
        self.word_mid.update(t.word_mid)
        self.word_initial.update(t.word_initial)
        self.lower.update(t.lower)
        for key, (_surface, first) in t.runs.items():
            self.runs.setdefault(key, first)
        self.grams.update(h for _i, h in _grams(t))

    def is_proper(self, key: str) -> bool:
        return _is_proper(self.word_mid[key], self.word_initial[key], self.lower[key])


@dataclass
class _PrivateMatches:
    """Per-term private file counts, restricted to terms that occur in the corpus."""

    index: _CorpusIndex
    files: int = 0
    emails: Counter = field(default_factory=Counter)
    host_keys: Counter = field(default_factory=Counter)
    words: Counter = field(default_factory=Counter)
    runs: Counter = field(default_factory=Counter)
    grams: Counter = field(default_factory=Counter)
    word_mid: Counter = field(default_factory=Counter)
    word_initial: Counter = field(default_factory=Counter)
    lower: Counter = field(default_factory=Counter)
    tracked: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.tracked = self.index.words | set(self.index.runs.values())

    def add(self, t: _Terms) -> None:
        idx = self.index
        self.files += 1
        self.emails.update(k for k in t.emails if k in idx.emails)
        keys = {_host_key(host) for (_kind, host) in t.hosts}
        self.host_keys.update(k for k in keys if k is not None and k in idx.host_keys)
        self.words.update(k for k in t.words if k in idx.words)
        self.runs.update(k for k in t.runs if k in idx.runs)
        self.grams.update({h for _i, h in _grams(t) if h in idx.grams})
        for counter, source in (
            (self.word_mid, t.word_mid),
            (self.word_initial, t.word_initial),
            (self.lower, t.lower),
        ):
            for k, n in source.items():
                if k in self.tracked:
                    counter[k] += n

    def is_proper(self, key: str) -> bool:
        return _is_proper(self.word_mid[key], self.word_initial[key], self.lower[key])


@dataclass
class _Group:
    kind: str
    key: str
    surface: str
    count: int
    files: set[str] = field(default_factory=set)


def scan(
    private_repo: Path,
    corpus: list[Path],
    *,
    min_len: int = 4,
    stats: dict | None = None,
) -> list[Finding]:
    """Report terms from `private_repo` that also appear in the benchmark `corpus`.

    Args:
        private_repo: root of a local checkout of the private repository. Read only, at run time.
        corpus: benchmark files or directories to check, e.g. ``worlds/``, ``docs/``, ``contract/``.
        min_len: minimum length in characters of a single-word proper noun (and of a run).
        stats: if given, filled with counts of scanned files and the allowlist files used.

    Returns:
        Findings sorted by severity, kind and term. An empty list means no overlap was found.

    Raises:
        FileNotFoundError: a path does not exist.
        ValueError: bad arguments, or nothing scannable on one side (an empty scan proves nothing).
    """
    if min_len < 1:
        raise ValueError(f"min_len must be at least 1, got {min_len}")
    private_repo = Path(private_repo)
    corpus = [Path(p) for p in corpus]
    if not private_repo.exists():
        raise FileNotFoundError(
            f"private repository not found: {private_repo} (pass the root of a local checkout to --private-repo)"
        )
    if not corpus:
        raise ValueError(
            "no corpus paths given; pass the benchmark paths to check, e.g. worlds/ docs/ contract/"
        )
    for p in corpus:
        if not p.exists():
            raise FileNotFoundError(f"corpus path not found: {p}")
    private_root = private_repo.resolve()
    corpus_roots = [p.resolve() for p in corpus]
    for p, r in zip(corpus, corpus_roots, strict=True):
        if r == private_root:
            raise ValueError(
                f"corpus path {p} is the private repository itself; pass benchmark paths only"
            )

    allow = _Allowlist.load(corpus)
    vocab = _Vocab(allow.words)
    sources = _corpus_sources(corpus, private_root)

    # Pass 1: index the corpus.
    index = _CorpusIndex()
    scanned: list[tuple[str, Path, str]] = []  # (display path, path, path words)
    for display, path, rel in sources:
        text = _read_text(path, max_bytes=MAX_CORPUS_FILE_BYTES, documents=True)
        if text is None:
            continue
        words_of_path = _path_words(rel)
        index.add(_analyze(text + "\n\n" + words_of_path, vocab, phrases=not _is_code(path)))
        scanned.append((display, path, words_of_path))
    if not scanned:
        raise ValueError(
            "no readable files found in the corpus paths "
            f"({', '.join(str(p) for p in corpus)}); supported: {', '.join(sorted(TEXT_SUFFIXES | DOCUMENT_SUFFIXES))}"
        )

    # Pass 2: stream the private repository, keeping only corpus terms. Skip the corpus itself
    # and any benchmark checkout nested inside the private repository.
    vocab.freeze()
    private = _PrivateMatches(index)
    skipped = 0
    nested = corpus_roots + _repo_roots(corpus)
    exclude = [r for r in nested if private_root in r.parents]
    for path in _iter_files(private_repo, TEXT_SUFFIXES, exclude=exclude):
        text = _read_text(path, max_bytes=MAX_PRIVATE_FILE_BYTES, documents=False)
        if text is None:
            skipped += 1
            continue
        rel = path.relative_to(private_repo) if private_repo.is_dir() else Path(path.name)
        private.add(_analyze(text + "\n\n" + _path_words(rel), vocab, phrases=not _is_code(path)))
        vocab.forget_scratch()  # keep nothing from this file except corpus-term counts
    if private.files == 0:
        raise ValueError(
            "no readable text files found in the private repository; check --private-repo "
            f"(supported: {', '.join(sorted(TEXT_SUFFIXES))}; files over {MAX_PRIVATE_FILE_BYTES // (1024 * 1024)} MB are skipped)"
        )

    words = {
        k
        for k in private.words
        if index.is_proper(k) and private.is_proper(k) and len(k) >= min_len
    }
    runs = {
        k
        for k in private.runs
        if len(k) >= min_len and _run_start_ok(index.runs[k], vocab, index, private)
    }

    # Pass 3: locate overlapping terms in the corpus.
    groups: dict[tuple[str, str], _Group] = {}

    def hit(kind: str, key: str, surface: str, count: int, display: str) -> None:
        g = groups.get((kind, key))
        if g is None:
            g = groups[(kind, key)] = _Group(kind, key, surface, count)
        g.count = max(g.count, count)
        g.files.add(display)

    for display, path, words_of_path in scanned:
        text = _read_text(path, max_bytes=MAX_CORPUS_FILE_BYTES, documents=True)
        if text is None:  # pragma: no cover - file changed between passes
            continue
        t = _analyze(text + "\n\n" + words_of_path, vocab, phrases=not _is_code(path))
        for key, surface in t.emails.items():
            if private.emails[key]:
                hit("email", key, surface, private.emails[key], display)
        for (kind, host), surface in t.hosts.items():
            hkey = _host_key(host)
            if hkey is None or not private.host_keys[hkey]:
                continue
            if kind == "domain" and host not in t.bare_hosts:
                # Only inside email addresses: skip if every such address is reported in full.
                addresses = [k for k in t.emails if k.rsplit("@", 1)[1] == host]
                if addresses and all(private.emails[a] for a in addresses):
                    continue
            hit(kind, host, surface, private.host_keys[hkey], display)
        for key, surface in t.words.items():
            if key in words:
                hit("proper_noun", key, surface, private.words[key], display)
        for key, (surface, _first) in t.runs.items():
            if key in runs:
                hit("proper_noun", key, surface, private.runs[key], display)
        for key, surface, count in _phrase_spans(t, private.grams):
            hit("phrase", key, surface, count, display)

    findings = []
    for g in _drop_subsumed(list(groups.values())):
        if allow.allows(g.kind, g.surface) or allow.allows(g.kind, g.key):
            continue
        files = sorted(g.files)
        findings.append(
            Finding(
                kind=g.kind,
                severity=_severity(g, vocab),
                term=g.surface,
                corpus_file=files[0],
                count_private=g.count,
                other_files=tuple(files[1:]),
            )
        )
    findings.sort(key=Finding.sort_key)

    if stats is not None:
        stats.update(
            corpus_files=len(scanned),
            private_files=private.files,
            private_files_skipped=skipped,
            allowlist_files=[str(p) for p in allow.files],
        )
    return findings


def _run_start_ok(first: str, vocab: _Vocab, index: _CorpusIndex, private: _PrivateMatches) -> bool:
    """A run counts if its first word is used as a proper noun on both sides.

    First names that are also common words ("Mark") are not tracked as proper nouns; a run
    starting with one was already required to contain another name or uncommon word.
    """
    return vocab.is_common(first) or (index.is_proper(first) and private.is_proper(first))


def _corpus_sources(corpus: list[Path], private_root: Path) -> list[tuple[str, Path, Path]]:
    """(display path, path, path relative to its corpus argument) for every corpus file.

    Files reachable from several overlapping arguments are listed once. A private repository
    nested inside a corpus directory is skipped.
    """
    seen: set[Path] = set()
    out: list[tuple[str, Path, Path]] = []
    for root in corpus:
        exclude = [private_root] if root.resolve() in private_root.parents else []
        for path in _iter_files(root, TEXT_SUFFIXES | DOCUMENT_SUFFIXES, exclude):
            real = path.resolve()
            if real in seen:
                continue
            seen.add(real)
            rel = path.relative_to(root) if root.is_dir() else Path(path.name)
            out.append((path.as_posix(), path, rel))
    return out


def _repo_roots(corpus: list[Path]) -> list[Path]:
    """Repository roots (directories with ``.git`` or ``pyproject.toml``) enclosing corpus paths."""
    roots: list[Path] = []
    for p in corpus:
        start = p.resolve()
        for d in (start, *start.parents):
            if (d / ".git").exists() or (d / "pyproject.toml").exists():
                if d not in roots:
                    roots.append(d)
                break
    return roots


def _path_words(path: Path) -> str:
    """Directory and file names as text, so names like "people/Ottoline Vray.md" are scanned too."""
    parts = [*path.parts[:-1], path.stem]
    return "\n".join(p for p in parts if p not in ("/", "\\", ".", ".."))


def _phrase_spans(t: _Terms, matched: Counter) -> Iterator[tuple[str, str, int]]:
    """Merge matching 6-grams into maximal spans: (key, surface, max private count)."""
    if not matched:
        return
    hits = [(i, matched[h]) for i, h in _grams(t) if h in matched]
    if not hits:
        return
    toks = t.tokens
    spans: list[list[int]] = []  # [start, end, count]
    for i, count in hits:
        if spans and i <= spans[-1][1]:
            spans[-1][1] = i + PHRASE_WORDS
            spans[-1][2] = max(spans[-1][2], count)
        else:
            spans.append([i, i + PHRASE_WORDS, count])
    for start, end, count in spans:
        surface = " ".join(t.clean[toks[start][0] : toks[end - 1][1]].split())
        key = " ".join(tok[2] for tok in toks[start:end])
        yield key, surface, count


def _drop_subsumed(groups: list[_Group]) -> list[_Group]:
    """Drop proper nouns fully explained by a longer reported run.

    A single word or a shorter run inside a reported run ("Imogen" inside "Imogen Tran") is
    dropped when every corpus file that contains it is already reported for a longer run.
    """
    runs = [g for g in groups if g.kind == "proper_noun" and " " in g.key]
    keep = []
    for g in groups:
        if g.kind == "proper_noun":
            needle = f" {g.key} "
            covering: set[str] = set()
            for r in runs:
                if r is not g and len(r.key) > len(g.key) and needle in f" {r.key} ":
                    covering |= r.files
            if covering and g.files <= covering:
                continue
        keep.append(g)
    return keep


def _severity(g: _Group, vocab: _Vocab) -> str:
    if g.kind == "proper_noun" and " " not in g.key:
        return "low" if vocab.is_name(g.key) else "medium"
    return "high"
