"""Track A contract validator: `wcb validate store <dir>` and `wcb validate answers <file>`.

`validate_store` checks a store directory against contract/CONTRACT.md and the JSON Schemas in
contract/schemas/. It returns a list of `Issue`s; each has a severity (`error` or `warning`), a
short dotted code, a message and the file it concerns. `CODES` below lists every code.

Errors count against the store's Validity metric (docs/scoring.md, "Store integrity"):
`Validity = 1 - min(1, errors / records)`. Warnings are advice and do not affect the score.

The checks, in the order they run:

1. Layout: `people/me.md` exists; `CONTRACT.md` is present and unedited; record directories
   hold only `.md` files directly inside them, named with lowercase slugs (`YYYY-MM-DD` for logs).
2. Per record: front matter parses; `type` matches the directory; `id` equals the path without
   `.md`; the front matter validates against `contract/schemas/<type>.schema.json`; dates are
   real calendar dates; link fields point to existing records of the right kind; body
   `[[...]]` links and `[src: ...]` citations resolve.
3. Per record type: a project's `## Current state` is exactly one paragraph beginning
   `As of YYYY-MM-DD`; `## Log` bullets read `- YYYY-MM-DD: ...`, oldest first; loop evidence
   cites artifact IDs (delivered ones, when the delivered set is known); a daily log's `date`
   equals its file name and its bullets start with an artifact ID.
4. Privacy, over every text file in the store: planted secrets (when given), meeting join
   links, passcodes and passwords, dial-in numbers and API-key-like tokens. `[redacted]` is fine.
5. Duplicate entities: people sharing an email or a full name; projects or orgs sharing a name.

Unknown extra front-matter fields are allowed everywhere.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from wcb.contract.answers import check_answers
from wcb.paths import contract_dir
from wcb.store.parse import RECORD_DIRS, Record, Store, load_store, normalize_ref
from wcb.util.io import read_json
from wcb.util.issues import Issue, error, warning
from wcb.util.text import normalize
from wcb.world.model import CHANNEL_PREFIX

#: Every issue code the validator emits: code -> (severity, meaning).
CODES: dict[str, tuple[str, str]] = {
    # layout
    "me.missing": ("error", "people/me.md (the worker's own record) does not exist"),
    "name.slug": (
        "error",
        "record file name is not a lowercase slug ([a-z0-9][a-z0-9-]*; logs: YYYY-MM-DD)",
    ),
    "path.nested": ("error", "record file is in a subdirectory of a record directory"),
    "file.unexpected": ("warning", "non-Markdown file inside a record directory"),
    "contract.missing": ("warning", "CONTRACT.md is missing from the store root"),
    "contract.modified": ("warning", "CONTRACT.md differs from the benchmark's contract"),
    # records
    "frontmatter": ("error", "front matter is missing or is not valid YAML"),
    "type.mismatch": (
        "error",
        "front matter 'type' is missing or does not match the record's directory",
    ),
    "id.mismatch": ("error", "front matter 'id' is missing or does not equal the path without .md"),
    "schema": ("error", "front matter fails the JSON Schema for its record type"),
    "date.invalid": ("error", "a YYYY-MM-DD value is not a real calendar date"),
    "date.order": ("warning", "'created' is later than 'updated'"),
    "link.missing": ("error", "a front-matter link points to a record that does not exist"),
    "link.unresolved": ("warning", "a body [[...]] link does not resolve to a record or file"),
    "citation.format": ("warning", "a [src: ...] citation is not an artifact ID"),
    "citation.undelivered": (
        "warning",
        "a [src: ...] citation names an artifact that was never delivered",
    ),
    # projects, loops and logs
    "project.current-state": (
        "error",
        "'## Current state' is missing, or is not one paragraph beginning 'As of YYYY-MM-DD'",
    ),
    "project.section": (
        "warning",
        "a project lacks '## Knowledge' or '## Log', or its sections are out of order",
    ),
    "log.bullet": ("warning", "a '## Log' bullet does not start with a date ('- YYYY-MM-DD: ...')"),
    "log.order": ("warning", "'## Log' bullets are not in date order (newest last)"),
    "evidence.source": ("warning", "a loop evidence source has an unknown artifact prefix"),
    "evidence.undelivered": (
        "warning",
        "a loop evidence source names an artifact that was never delivered",
    ),
    "log.date": ("error", "a daily log's 'date' does not equal its file name"),
    "log.entry": ("warning", "a daily-log bullet does not start with an artifact ID"),
    # privacy
    "privacy.secret": ("error", "a planted secret from the inputs appears in the store"),
    "privacy.join-link": ("error", "a video-meeting join link or meeting ID appears in the store"),
    "privacy.passcode": ("error", "a password, passcode, PIN or access code appears in the store"),
    "privacy.dial-in": ("error", "a dial-in number appears in the store"),
    "privacy.api-key": ("error", "an API key or other credential-like token appears in the store"),
    # duplicates
    "duplicate.email": ("warning", "two people records share an email address"),
    "duplicate.name": ("warning", "two people (or two orgs) records share a full name"),
    "duplicate.project": ("warning", "two project records share a name"),
    # answers (validate_answers)
    "answers.json": ("error", "the answers file is not valid JSON"),
    "answers.schema": ("error", "an answer fails the answer schema or has the wrong type"),
    "answers.missing": ("error", "a question has no answer"),
    "answers.unknown": (
        "warning",
        "an answer is keyed by a question ID that is not in the questions file",
    ),
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ARTIFACT_ID_RE = re.compile(r"^[a-z]{2}-[A-Za-z0-9-]+$")
ARTIFACT_PREFIXES = frozenset(CHANNEL_PREFIX.values())
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

#: Front-matter fields holding record links, per record type: field -> kind of the target.
LINK_FIELDS: dict[str, dict[str, str]] = {
    "person": {"org": "org"},
    "org": {},
    "project": {
        "owner": "person",
        "people": "person",
        "orgs": "org",
        "parent": "project",
        "split_into": "project",
        "merged_into": "project",
    },
    "loop": {"owner": "person", "counterparty": "person", "others": "person", "project": "project"},
    "log": {},
}

#: Top-level front-matter fields that hold dates.
DATE_FIELDS = ("date", "created", "updated", "due", "target_date", "decided_on", "reversed_on")

#: Expected order of project body sections.
PROJECT_SECTIONS = ("Current state", "Knowledge", "Log")


# ================================================================= store validation
def validate_store(
    root: Path, *, secrets: list[str] | None = None, delivered: set[str] | None = None
) -> list[Issue]:
    """Check the store at `root` against the Track A contract.

    `secrets`: literal strings that must not appear anywhere in the store (the world's planted
    secrets, gold state's `secrets`). `delivered`: artifact IDs delivered so far; when given,
    evidence sources and citations outside it get a warning. Raises FileNotFoundError if
    `root` is not a directory. Issues are ordered by file path, store-level issues first.
    """
    store = load_store(Path(root))
    delivered_set = set(delivered) if delivered is not None else None
    issues: list[Issue] = []
    issues += check_layout(store)
    for rec in store.records.values():
        issues += check_record(rec, store, delivered_set)
    issues += check_privacy(store, secrets or [])
    issues += check_duplicates(store)
    return sorted(issues, key=lambda i: i.path or "")


# ---------------------------------------------------------------- layout
def check_layout(store: Store) -> list[Issue]:
    """Store-level layout: people/me.md, CONTRACT.md and stray files in record directories."""
    issues: list[Issue] = []
    if "people/me" not in store.records:
        issues.append(
            error("me.missing", "the worker's record people/me.md does not exist", "people/me.md")
        )
    if "CONTRACT.md" not in store.other_files:
        issues.append(
            warning(
                "contract.missing",
                "CONTRACT.md is missing; keep the copy you were given",
                "CONTRACT.md",
            )
        )
    elif _contract_modified(store.root / "CONTRACT.md"):
        issues.append(
            warning(
                "contract.modified",
                "CONTRACT.md differs from the benchmark's contract; do not edit it",
                "CONTRACT.md",
            )
        )
    for rel in store.other_files:
        if rel.split("/", 1)[0] in RECORD_DIRS and "/" in rel:
            issues.append(
                warning(
                    "file.unexpected",
                    "record directories should hold only .md records; move other files to notes/ or sources/",
                    rel,
                )
            )
    return issues


def _contract_modified(path: Path) -> bool:
    ref = contract_dir() / "CONTRACT.md"
    if not ref.exists():
        return False

    def canon(p: Path) -> str:
        return "\n".join(
            line.rstrip() for line in p.read_text(encoding="utf-8", errors="replace").splitlines()
        ).strip()

    return canon(path) != canon(ref)


# ---------------------------------------------------------------- one record
def check_record(rec: Record, store: Store, delivered: set[str] | None = None) -> list[Issue]:
    """All checks for one record. Stops after the file-name and front-matter checks if those fail."""
    issues = check_record_name(rec)
    if rec.error:
        return issues + [error("frontmatter", rec.error, rec.path)]
    name_ok = not issues
    kind = rec.dir_type
    if rec.type != kind:
        got = "missing 'type'" if rec.type is None else f"type {rec.type!r}"
        issues.append(
            error(
                "type.mismatch",
                f"{got}, but records in {rec.expected_id.split('/')[0]}/ must have type {kind!r}",
                rec.path,
            )
        )
    if name_ok and rec.id != rec.expected_id:
        got = "missing 'id'" if rec.id is None else f"id {rec.id!r}"
        issues.append(
            error(
                "id.mismatch",
                f"{got}; expected {rec.expected_id!r} (the path without .md)",
                rec.path,
            )
        )
    schema_issues, bad_fields = check_schema(rec)
    issues += schema_issues
    issues += check_dates(rec)
    issues += check_links(rec, store, skip=bad_fields)
    issues += check_body_links(rec, store)
    issues += check_citations(rec, delivered)
    if kind == "project":
        issues += check_project_body(rec)
    if kind in ("person", "project", "loop"):
        issues += check_log_section(rec)
    if kind == "loop":
        issues += check_evidence(rec, delivered, skip=bad_fields)
    if kind == "log":
        issues += check_daily_log(rec)
    return issues


def check_record_name(rec: Record) -> list[Issue]:
    """File name is a lowercase slug (a date for logs) directly inside its record directory."""
    parts = rec.expected_id.split("/")
    if len(parts) != 2:
        return [
            error(
                "path.nested",
                f"records must sit directly in {parts[0]}/, not in a subdirectory",
                rec.path,
            )
        ]
    stem = parts[1]
    if rec.dir_type == "log":
        if not DATE_RE.match(stem):
            return [
                error(
                    "name.slug",
                    f"daily log file names must be YYYY-MM-DD.md, got {stem + '.md'!r}",
                    rec.path,
                )
            ]
    elif not SLUG_RE.match(stem):
        return [
            error(
                "name.slug",
                f"file name {stem!r} is not a lowercase slug matching [a-z0-9][a-z0-9-]*",
                rec.path,
            )
        ]
    return []


@functools.cache
def _schema_validator(type_: str):
    import jsonschema

    schema = read_json(contract_dir() / "schemas" / f"{type_}.schema.json")
    return jsonschema.Draft202012Validator(schema)


_REQUIRED_MSG = re.compile(r"^'(.+)' is a required property$")


def check_schema(rec: Record) -> tuple[list[Issue], set[str]]:
    """Validate front matter against the schema for the record's directory.

    Reports one error per location (field path, or missing field). When several schema rules
    reject the same value, as for a task `status` that fails both the general enum and the
    task-specific one, the most specific rule (the longest schema path) is reported.

    Returns the issues and the set of top-level fields that failed, so later checks can skip
    them instead of reporting the same mistake twice. Problems with `id` and `type` are left to
    the dedicated `id.mismatch` and `type.mismatch` checks.
    """
    best: dict[tuple[tuple[str, ...], str], Any] = {}
    for err in _schema_validator(rec.dir_type).iter_errors(rec.meta):
        missing = _REQUIRED_MSG.match(err.message) if err.validator == "required" else None
        key = (tuple(str(p) for p in err.absolute_path), missing.group(1) if missing else "")
        if key not in best or len(err.schema_path) > len(best[key].schema_path):
            best[key] = err
    issues: list[Issue] = []
    bad: set[str] = set()
    for (path, missing_field), err in sorted(best.items()):
        top = path[0] if path else missing_field
        if top in ("id", "type"):
            continue
        if top:
            bad.add(top)
        loc = "/".join(path)
        msg = f"missing required field {missing_field!r}" if missing_field else err.message
        issues.append(error("schema", f"{loc}: {msg}" if loc else msg, rec.path))
    return issues, bad


def check_dates(rec: Record) -> list[Issue]:
    """YYYY-MM-DD values in date fields and evidence entries must be real calendar dates."""
    values: list[tuple[str, Any]] = [(f, rec.meta.get(f)) for f in DATE_FIELDS]
    evidence = rec.meta.get("evidence")
    if isinstance(evidence, list):
        values += [
            (f"evidence/{i}/date", e.get("date"))
            for i, e in enumerate(evidence)
            if isinstance(e, dict)
        ]
    issues = [
        error("date.invalid", f"{name}: {value!r} is not a calendar date", rec.path)
        for name, value in values
        if isinstance(value, str) and DATE_RE.match(value) and not _is_date(value)
    ]
    created, updated = rec.meta.get("created"), rec.meta.get("updated")
    if _is_date(created) and _is_date(updated) and created > updated:
        issues.append(
            warning("date.order", f"created {created} is after updated {updated}", rec.path)
        )
    return issues


def check_links(rec: Record, store: Store, skip: Iterable[str] = ()) -> list[Issue]:
    """Front-matter link fields must name existing records.

    The schemas already require each link to carry the right directory prefix (an `owner` must
    look like 'people/<slug>'), so only existence is checked here. Fields listed in `skip`
    failed the schema and are not checked again.
    """
    issues: list[Issue] = []
    for field_name, kind in LINK_FIELDS.get(rec.dir_type, {}).items():
        if field_name in skip:
            continue
        value = rec.meta.get(field_name)
        for target in value if isinstance(value, list) else [value]:
            if isinstance(target, str) and target and store.get(target) is None:
                issues.append(
                    error("link.missing", f"{field_name}: no {kind} record {target!r}", rec.path)
                )
    return issues


_BODY_LINK_RE = re.compile(r"\[\[([^\[\]|#]+)(?:[|#][^\[\]]*)?\]\]")


def check_body_links(rec: Record, store: Store) -> list[Issue]:
    """Body `[[...]]` links should resolve to a record or another store file (warning)."""
    files = _file_refs(store)
    issues = []
    for target in sorted(set(_BODY_LINK_RE.findall(_strip_code(rec.body)))):
        ref = normalize_ref(target)
        if ref not in store.records and ref not in files:
            issues.append(
                warning(
                    "link.unresolved",
                    f"[[{target.strip()}]] does not resolve to a record",
                    rec.path,
                )
            )
    return issues


def _file_refs(store: Store) -> frozenset[str]:
    """Ways a body link may name a non-record file: its path, with or without extension."""
    return _file_refs_of(tuple(store.other_files))


@functools.lru_cache(maxsize=8)
def _file_refs_of(files: tuple[str, ...]) -> frozenset[str]:
    return frozenset(files) | {f.rsplit(".", 1)[0] for f in files if "." in f.rsplit("/", 1)[-1]}


_CITATION_RE = re.compile(r"\[src:\s*([^\]]*)\]", re.I)


def check_citations(rec: Record, delivered: set[str] | None) -> list[Issue]:
    """`[src: em-0193, mt-0057]` citations in the body should name (delivered) artifacts."""
    bad_format: list[str] = []
    undelivered: list[str] = []
    for group in _CITATION_RE.findall(_strip_code(rec.body)):
        for item in re.split(r"[,;]", group):
            token = item.strip().split(" ")[0] if item.strip() else ""
            if not token:
                continue
            if not _looks_like_artifact(token):
                bad_format.append(token)
            elif delivered is not None and token not in delivered:
                undelivered.append(token)
    issues = []
    if bad_format:
        issues.append(
            warning(
                "citation.format", f"not artifact IDs: {', '.join(_uniq(bad_format))}", rec.path
            )
        )
    if undelivered:
        issues.append(
            warning(
                "citation.undelivered",
                f"never delivered: {', '.join(_uniq(undelivered))}",
                rec.path,
            )
        )
    return issues


# ---------------------------------------------------------------- record-type rules
_AS_OF_RE = re.compile(r"^[*_]{0,2}As of (\d{4}-\d{2}-\d{2})\b")
_BLOCK_LINE_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)]|#{1,6}|>)\s")


def current_state_problem(text: str | None) -> str | None:
    """Why a project's `Current state` section text is invalid, or None if it is valid.

    Valid means: exactly one non-empty paragraph (no blank-line breaks, lists, headings or
    quotes) that begins `As of YYYY-MM-DD`, with a real date.
    """
    if text is None:
        return "missing '## Current state' section"
    paragraphs = [p for p in re.split(r"\n[ \t]*\n", text.strip()) if p.strip()]
    if not paragraphs:
        return "'## Current state' is empty"
    if len(paragraphs) > 1:
        return f"'## Current state' must be exactly one paragraph, found {len(paragraphs)}"
    para = paragraphs[0].strip()
    if any(_BLOCK_LINE_RE.match(line) for line in para.splitlines()):
        return "'## Current state' must be a single prose paragraph, not a list, heading or quote"
    m = _AS_OF_RE.match(para)
    if not m:
        return "'## Current state' must begin 'As of YYYY-MM-DD:'"
    if not _is_date(m.group(1)):
        return f"'## Current state' date {m.group(1)!r} is not a calendar date"
    return None


def check_project_body(rec: Record) -> list[Issue]:
    """Current state (error), plus Knowledge and Log sections in order (warnings)."""
    issues = []
    problem = current_state_problem(rec.section("Current state"))
    if problem:
        issues.append(error("project.current-state", problem, rec.path))
    missing = [s for s in PROJECT_SECTIONS[1:] if rec.section(s) is None]
    if missing:
        names = " and ".join(f"'## {s}'" for s in missing)
        issues.append(warning("project.section", f"missing {names} section", rec.path))
    order = [s.strip().lower() for s in rec.sections]
    positions = [order.index(s.lower()) for s in PROJECT_SECTIONS if s.lower() in order]
    if positions != sorted(positions):
        issues.append(
            warning(
                "project.section",
                "sections should be in the order Current state, Knowledge, Log",
                rec.path,
            )
        )
    return issues


_BULLET_RE = re.compile(r"^[-*+]\s+(.*)$")
_DATED_BULLET_RE = re.compile(r"^[*_]{0,2}(\d{4}-\d{2}-\d{2})[*_]{0,2}(?:\s*[:–—-]|\s|$)")


def check_log_section(rec: Record) -> list[Issue]:
    """`## Log` bullets read `- YYYY-MM-DD: ...` and run oldest to newest (warnings)."""
    text = rec.section("Log")
    if not text:
        return []
    undated: list[str] = []
    dates: list[str] = []
    for line in text.splitlines():
        m = _BULLET_RE.match(line)  # top-level bullets only; indented lines are continuations
        if not m:
            continue
        d = _DATED_BULLET_RE.match(m.group(1))
        if d:
            dates.append(d.group(1))
        else:
            undated.append(line.strip())
    issues = []
    if undated:
        issues.append(
            warning(
                "log.bullet",
                f"{len(undated)} Log bullet(s) do not start with a date, e.g. {_clip(undated[0])!r}; use '- YYYY-MM-DD: ...'",
                rec.path,
            )
        )
    if dates != sorted(dates):
        issues.append(
            warning(
                "log.order",
                "Log bullets are not in date order; append new entries at the end",
                rec.path,
            )
        )
    return issues


def check_evidence(
    rec: Record, delivered: set[str] | None, skip: Iterable[str] = ()
) -> list[Issue]:
    """Loop evidence sources should use known artifact prefixes and (if known) be delivered."""
    evidence = rec.meta.get("evidence")
    if "evidence" in skip or not isinstance(evidence, list):
        return []
    sources = [
        e.get("source")
        for e in evidence
        if isinstance(e, dict) and isinstance(e.get("source"), str)
    ]
    unknown = [s for s in sources if s[:2] not in ARTIFACT_PREFIXES]
    issues = []
    if unknown:
        prefixes = ", ".join(sorted(ARTIFACT_PREFIXES))
        issues.append(
            warning(
                "evidence.source",
                f"unknown artifact prefix in {', '.join(_uniq(unknown))} (known: {prefixes})",
                rec.path,
            )
        )
    if delivered is not None:
        missing = [s for s in sources if s not in delivered and s not in unknown]
        if missing:
            issues.append(
                warning(
                    "evidence.undelivered",
                    f"evidence cites artifacts never delivered: {', '.join(_uniq(missing))}",
                    rec.path,
                )
            )
    return issues


_LOG_ENTRY_RE = re.compile(r"^[*_`\[]{0,3}([a-z]{2}-[A-Za-z0-9-]+)")


def check_daily_log(rec: Record) -> list[Issue]:
    """`logs/<date>.md` has `date` equal to its file name; bullets start with an artifact ID."""
    issues = []
    date = rec.meta.get("date")
    if isinstance(date, str) and DATE_RE.match(rec.stem) and date != rec.stem:
        issues.append(
            error("log.date", f"date {date!r} does not match the file name {rec.stem}.md", rec.path)
        )
    bad = []
    for line in _strip_code(rec.body).splitlines():
        m = _BULLET_RE.match(line)
        if m:
            a = _LOG_ENTRY_RE.match(m.group(1))
            if not a or not _looks_like_artifact(a.group(1)):
                bad.append(line.strip())
    if bad:
        issues.append(
            warning(
                "log.entry",
                f"{len(bad)} bullet(s) do not start with an artifact ID, e.g. {_clip(bad[0])!r}; use '- em-0193 (email): ...'",
                rec.path,
            )
        )
    return issues


# ================================================================= privacy
# Each finder returns (start, end, code, description) tuples for one kind of leak.
# privacy_findings() runs them all and merges overlapping matches into one finding.

_PLACEHOLDER_WORDS = frozenset(
    {"none", "n/a", "na", "tbd", "tbc", "null", "hidden", "removed", "omitted"}
)
_VALUE_STRIP = ".,:;'\"`*()[]<>{}"

#: Secrets shorter than this are not searched for: they would match ordinary text.
MIN_SECRET_LEN = 4


def is_placeholder(value: str) -> bool:
    """'[redacted]', 'REDACTED', '***', 'xxxx', 'n/a' and similar stand-ins for a removed value."""
    core = value.strip(_VALUE_STRIP)
    return (
        not core
        or "redact" in core.lower()
        or bool(re.fullmatch(r"[*x•#._-]+", core, re.I))
        or core.lower() in _PLACEHOLDER_WORDS
    )


def find_secrets(text: str, secrets: Iterable[str]) -> list[tuple[int, int, str, str]]:
    """Case-insensitive occurrences of literal secrets in `text`.

    A secret that begins or ends with a letter or digit only matches at a word boundary, so
    passcode '514227' does not match inside '88514227'. For a URL secret, the form without
    'https://' is also searched. Secrets shorter than MIN_SECRET_LEN are skipped.
    """
    found = []
    for s in secrets:
        s = str(s).strip()
        if len(s) < MIN_SECRET_LEN:
            continue
        variants = {s, re.sub(r"^[a-z][a-z0-9+.-]*://", "", s, flags=re.I)}
        for v in variants:
            pat = (
                (r"(?<![A-Za-z0-9])" if v[0].isalnum() else "")
                + re.escape(v)
                + (r"(?![A-Za-z0-9])" if v[-1].isalnum() else "")
            )
            for m in re.finditer(pat, text, re.I):
                found.append((m.start(), m.end(), "privacy.secret", f"planted secret {_mask(s)}"))
    return found


# -- join links ---------------------------------------------------------------
_URL_RE = re.compile(
    r"(?:\b[a-z][a-z0-9+.-]*://)?"  # optional scheme
    r"(?<![\w@.-])((?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,})"  # host
    r"(?::\d+)?"  # optional port
    r"([/?][^\s<>\"'`\])}]*)?",  # path and query
    re.I,
)
_MEETING_HOST_RE = re.compile(
    r"(?:^|\.)(?:zoom|webex|bluejeans|gotomeeting|gotomeet|whereby|jitsi|meet\.jit|chime|ringcentral)\.|"
    r"^(?:meet|join|video|conf|conference|webinar|call|calls|teams)\.|teams\.microsoft\.|meet\.google\.",
    re.I,
)
_JOIN_PATH_RE = re.compile(
    r"/(?:j|w|wc/join)/\d{5,}|/l/meetup-join/|/meetup-join/|/join/\d{5,}", re.I
)
_JOIN_QUERY_RE = re.compile(
    r"[?&](?:pwd|passcode|password|meetingid|meeting_id|meeting-id|mtid|confno|confid|"
    r"conference_?id|room_?id|pin|access_?code)=[^&\s]+",
    re.I,
)
_ID_SEGMENT_RE = re.compile(
    r"\d{6,}|(?<![a-z])[a-z]{3}-[a-z]{4}-[a-z]{3}(?![a-z])|/my/[\w.-]{3,}", re.I
)
_MEETING_ID_RE = re.compile(r"\bmeeting\s*(?:id|number|no\.?|#)\s*[:#]?\s*(\d[\d \-]{6,}\d)", re.I)


def find_join_links(text: str) -> list[tuple[int, int, str, str]]:
    """Video-meeting join links and meeting IDs.

    A URL (with or without scheme) is a join link if its path looks like a join path
    (`/j/<digits>`, `/meetup-join/`, `/join/<digits>`), its query carries a meeting ID or
    password (`?pwd=`, `?MTID=`, `?confno=`, ...), or its host is a meeting service
    (`meet.`, `join.`, `zoom.`, `teams.microsoft.`, ...) and its path holds an ID (6+ digits,
    a code like 'abc-defg-hij', or a personal room '/my/<name>').
    """
    found = []
    for m in _URL_RE.finditer(text):
        host, rest = m.group(1), m.group(2) or ""
        if not rest:
            continue
        if (
            _JOIN_PATH_RE.search(rest)
            or _JOIN_QUERY_RE.search(rest)
            or (_MEETING_HOST_RE.search(host) and _ID_SEGMENT_RE.search(rest))
        ):
            found.append((m.start(), m.end(), "privacy.join-link", f"meeting join link to {host}"))
    for m in _MEETING_ID_RE.finditer(text):
        if sum(c.isdigit() for c in m.group(1)) >= 9:
            found.append((m.start(), m.end(), "privacy.join-link", "meeting ID"))
    return found


# -- passcodes ----------------------------------------------------------------
_CRED_KEYWORDS = (
    r"pass\s?code|password|passwd|pwd|access\s+code|participant\s+code|attendee\s+id|"
    r"conference\s+id|host\s+key|one[-\s]time\s+(?:pass)?code|otp|verification\s+code|security\s+code"
)
_CRED_VALUE = r"(?P<val>\d[\d \-]{2,}\d#?|[^\s,;)\]]+)"
_CRED_RE = re.compile(
    rf"\b(?P<kw>{_CRED_KEYWORDS})\b(?P<sep>[ \t]*(?:is|was|:|=|#|-)?[ \t]*){_CRED_VALUE}", re.I
)
# 'PIN' is matched in capitals only, so the verb 'pin' ('pin the agenda') is never considered.
_PIN_RE = re.compile(
    rf"\b(?P<kw>PIN)\b(?P<sep>[ \t]*(?:code|number|is|:|=|#)?[ \t]*:?[ \t]*){_CRED_VALUE}"
)


def credential_value(value: str, sep: str) -> bool:
    """Whether the word after 'password'/'passcode'/'PIN'/... looks like an actual credential.

    Flags values with at least 4 characters including a digit ('514227', 'hunter2'), and, after
    an explicit ':' or '=', mixed-case or symbol-bearing values of 6+ characters ('Tr!ckyPass').
    Prose such as 'password reset ticket' or 'passcode expired' is not flagged, nor are
    placeholders such as '[redacted]', '***' or 'n/a', nor bare dates. `sep` is the text between
    the keyword and the value; a value glued to the keyword ('pwd/notes') is not a credential.
    """
    v = value.strip(_VALUE_STRIP)
    if not sep or is_placeholder(value) or DATE_RE.match(v):
        return False
    if any(c.isdigit() for c in v) and len(v.replace(" ", "").replace("-", "")) >= 4:
        return True
    if ":" in sep or "=" in sep:
        mixed = re.search(r"[A-Z]", v[1:]) and re.search(r"[a-z]", v)
        return len(v) >= 6 and bool(mixed or re.search(r"[^A-Za-z0-9]", v))
    return False


def find_passcodes(text: str) -> list[tuple[int, int, str, str]]:
    """'passcode: 514227', 'pwd=abc123', 'PIN 4821', 'access code 123 4567' and similar."""
    found = []
    for rx in (_CRED_RE, _PIN_RE):
        for m in rx.finditer(text):
            if credential_value(m.group("val"), m.group("sep")):
                kw = " ".join(m.group("kw").split()).lower()
                found.append(
                    (m.start(), m.end(), "privacy.passcode", f"{kw!r} followed by a value")
                )
    return found


# -- dial-in numbers ----------------------------------------------------------
_PHONE = r"\+?\(?\d[\d \t().-]{6,}\d"
_DIAL_KEYWORD_RE = re.compile(
    rf"\b(?:dial[ \t-]?in|call-in|dial)\b[^\n\d+]{{0,30}}({_PHONE})", re.I
)
_PHONE_ACCESS_RE = re.compile(rf"({_PHONE})[ \t]*,,+[ \t]*\d{{4,}}#?")
_LEADING_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def find_dial_ins(text: str) -> list[tuple[int, int, str, str]]:
    """Dial-in numbers: 'Dial-in: +1 415 555 0100', or a phone number with ',,<access code>'.

    Ordinary phone numbers (for example in an email signature) are not flagged.
    """
    found = []
    for rx in (_DIAL_KEYWORD_RE, _PHONE_ACCESS_RE):
        for m in rx.finditer(text):
            number = m.group(1).strip()
            if sum(c.isdigit() for c in number) >= 8 and not _LEADING_DATE_RE.match(number):
                found.append((m.start(), m.end(), "privacy.dial-in", "dial-in number"))
    return found


# -- API keys -----------------------------------------------------------------
_KEY_RES = [
    # sk-..., sk-ant-api03-..., sk-proj-...
    re.compile(r"\bsk-(?:[A-Za-z0-9]+-){0,3}[A-Za-z0-9_]{16,}"),
    re.compile(r"\b[rps]k_(?:live|test)_[A-Za-z0-9]{16,}"),  # payment-provider keys
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),  # cloud access key IDs
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),  # code-host tokens
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),  # chat bot tokens
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
_KEY_ASSIGN_RE = re.compile(
    r"\b(?:api[_ -]?key|secret[_ -]?key|access[_ -]?token|auth[_ -]?token|client[_ -]?secret|bearer)\b"
    r"[ \t]*[:=]?[ \t]*['\"]?([A-Za-z0-9_\-./+=]{12,})",
    re.I,
)
_HEX_RE = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{32,}(?![A-Za-z0-9])")
_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9+/_=-])[A-Za-z0-9+/_-]{32,}={0,2}(?![A-Za-z0-9+/_=-])")


def looks_random(token: str) -> bool:
    """Heuristic for a random base64-style token rather than a word, slug or path.

    Requires upper- and lower-case letters (3+ each), digits in 3+ separate runs, few
    separators ('-', '_', '/', '+') and high character entropy. Slugs, CamelCase names with a
    year, UUIDs and file paths fail at least one of these.
    """
    t = token.rstrip("=")
    if sum(c.isupper() for c in t) < 3 or sum(c.islower() for c in t) < 3:
        return False
    if len(re.findall(r"\d+", t)) < 3:
        return False
    if sum(c in "-_/+" for c in t) > len(t) / 10:
        return False
    counts = Counter(t)
    entropy = -sum(n / len(t) * math.log2(n / len(t)) for n in counts.values())
    return entropy >= 4.0


def find_api_keys(text: str) -> list[tuple[int, int, str, str]]:
    """API keys and tokens: well-known key prefixes, `api_key: ...` assignments, long hex
    strings (32+ hex digits mixing letters and digits) and long random-looking base64 tokens."""
    found = []
    for rx in _KEY_RES:
        found += [
            (m.start(), m.end(), "privacy.api-key", f"API key {_mask(m.group(0))}")
            for m in rx.finditer(text)
        ]
    for m in _KEY_ASSIGN_RE.finditer(text):
        v = m.group(1)
        if re.search(r"\d", v) and re.search(r"[A-Za-z]", v) and not is_placeholder(v):
            found.append((m.start(), m.end(), "privacy.api-key", f"credential {_mask(m.group(0))}"))
    for m in _HEX_RE.finditer(text):
        v = m.group(0)
        if re.search(r"\d", v) and re.search(r"[a-fA-F]", v):
            found.append((m.start(), m.end(), "privacy.api-key", f"hex token {_mask(v)}"))
    for m in _TOKEN_RE.finditer(text):
        if looks_random(m.group(0)):
            found.append((m.start(), m.end(), "privacy.api-key", f"token {_mask(m.group(0))}"))
    return found


PRIVACY_FINDERS = (find_join_links, find_dial_ins, find_passcodes, find_api_keys)


def privacy_findings(text: str, secrets: Iterable[str] = ()) -> list[tuple[int, int, str, str]]:
    """All privacy findings in `text` as `(start, end, code, description)`, sorted by position.

    Overlapping matches (directly or through a chain of overlaps, e.g. a join link containing
    both a planted secret and a `pwd=` value) form one leak and are reported once. The
    reported finding is the highest-priority one: planted secrets first, then the order of
    PRIVACY_FINDERS.
    """
    candidates = find_secrets(text, secrets)  # list order is priority order
    for finder in PRIVACY_FINDERS:
        candidates += finder(text)
    clusters: list[tuple[int, list[int]]] = []  # (end of cluster, candidate indexes)
    for i in sorted(range(len(candidates)), key=lambda i: candidates[i][:2]):
        start, end = candidates[i][:2]
        if clusters and start < clusters[-1][0]:
            last_end, members = clusters[-1]
            clusters[-1] = (max(last_end, end), [*members, i])
        else:
            clusters.append((end, [i]))
    return sorted(candidates[min(members)] for _, members in clusters)


def check_privacy(store: Store, secrets: Iterable[str] = ()) -> list[Issue]:
    """Privacy errors for every text file in the store (records, sources/, notes/, ...)."""
    secrets = list(secrets)  # reused for every file
    issues = []
    for rel, text in store.iter_text():
        for start, _end, code, desc in privacy_findings(text, secrets):
            line = text.count("\n", 0, start) + 1
            issues.append(error(code, f"line {line}: {desc}; write [redacted] instead", rel))
    return issues


# ================================================================= duplicates
def check_duplicates(store: Store) -> list[Issue]:
    """Warnings for likely duplicate entities (rule 1: one record per real entity)."""
    issues: list[Issue] = []
    by_email: dict[str, list[Record]] = defaultdict(list)
    for rec in store.of_type("person"):
        for email in sorted(_emails(rec.meta)):
            by_email[email].append(rec)
    for email, recs in sorted(by_email.items()):
        if len(recs) > 1:
            issues.append(
                warning(
                    "duplicate.email", f"{_ids(recs)} share the email address {email}", recs[0].path
                )
            )
    for type_, code in (
        ("person", "duplicate.name"),
        ("org", "duplicate.name"),
        ("project", "duplicate.project"),
    ):
        by_name: dict[str, list[Record]] = defaultdict(list)
        for rec in store.of_type(type_):
            name = rec.meta.get("name")
            if isinstance(name, str) and name.strip():
                by_name[normalize(name)].append(rec)
        for recs in by_name.values():
            if len(recs) > 1:
                name = recs[0].meta["name"]
                issues.append(
                    warning(
                        code,
                        f"{_ids(recs)} share the name {name!r}; merge them or tell them apart",
                        recs[0].path,
                    )
                )
    return issues


def _emails(meta: dict) -> set[str]:
    """Email addresses from a person's `email` field and email-shaped aliases, lowercased."""
    raw = meta.get("email")
    values = raw if isinstance(raw, list) else [raw]
    aliases = meta.get("aliases") if isinstance(meta.get("aliases"), list) else []
    return {
        str(v).strip().lower()
        for v in [*values, *aliases]
        if isinstance(v, str) and EMAIL_RE.match(v.strip())
    }


# ================================================================= answers
def load_questions(path: Path) -> list[dict]:
    """Questions from a visible `.wcb/questions.json` ({date, questions}), a gold
    `gold/questions/<cp>.json` ({world, checkpoint, date, questions}) or a bare list."""
    data = read_json(path)
    questions = data.get("questions") if isinstance(data, dict) else data
    if not isinstance(questions, list):
        raise ValueError(f"{path}: expected a 'questions' list")
    for q in questions:
        if not isinstance(q, dict) or "id" not in q or "type" not in q:
            raise ValueError(f"{path}: every question needs an 'id' and a 'type'")
    return questions


def validate_answers(answers_path: Path, questions_path: Path | None = None) -> list[Issue]:
    """Check an answers file against contract/answers/answers.schema.json.

    With `questions_path`, also checks that every question has an answer whose `type` matches
    the question (a missing answer is an error) and flags answers to unknown question IDs
    (warning). An answer that fails validation scores 0. Raises FileNotFoundError if a file is
    missing and ValueError if the questions file is malformed.
    """
    answers_path = Path(answers_path)
    try:
        answers = read_json(answers_path)
    except json.JSONDecodeError as e:
        return [error("answers.json", f"not valid JSON: {e}", str(answers_path))]
    questions = load_questions(Path(questions_path)) if questions_path else None
    issues = []
    for qid, problems in check_answers(answers, questions).items():
        path = str(answers_path) if qid == "<root>" else qid
        for p in problems:
            if p == "missing answer":
                issues.append(error("answers.missing", "no answer for this question", path))
            elif p == "answer for unknown question ID":
                issues.append(
                    warning(
                        "answers.unknown",
                        "answer for a question ID not in the questions file",
                        path,
                    )
                )
            else:
                issues.append(error("answers.schema", p, path))
    return issues


# ================================================================= helpers
def _is_date(value: Any) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _looks_like_artifact(token: str) -> bool:
    return bool(ARTIFACT_ID_RE.match(token)) and token[:2] in ARTIFACT_PREFIXES


_FENCED_RE = re.compile(r"^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$", re.M | re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def _strip_code(text: str) -> str:
    """Body text without fenced code blocks and inline code spans (for link and citation scans)."""
    return _INLINE_CODE_RE.sub("", _FENCED_RE.sub("", text))


def _mask(s: str) -> str:
    """Show only the start of a sensitive string in validator output."""
    s = " ".join(s.split())
    return f"'{s[:6]}...' ({len(s)} chars)" if len(s) > 8 else f"'{s[:2]}...' ({len(s)} chars)"


def _clip(s: str, n: int = 60) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def _uniq(xs: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(xs))


def _ids(recs: list[Record]) -> str:
    return ", ".join(r.expected_id for r in recs)
