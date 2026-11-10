"""Tests for wcb.contract.validate.validate_store.

Each broken-store case starts from a copy of tests/fixtures/sample-store, applies one change and
checks that the expected issue code appears with the severity listed in CODES.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from wcb.cli import main
from wcb.contract.validate import CODES, current_state_problem, validate_store
from wcb.paths import contract_dir
from wcb.world.model import World
from wcb.world.state import state_at

QUILLON = "projects/quillon.md"
QUESTIONNAIRE = "loops/return-tessellate-security-questionnaire.md"
DECISION = "loops/limit-quillon-pilot-to-reno.md"


def codes(issues) -> set[str]:
    return {i.code for i in issues}


def errors(issues) -> list:
    return [i for i in issues if i.severity == "error"]


# ---------------------------------------------------------------- the valid sample store
def test_sample_store_is_valid(sample_store_dir):
    issues = validate_store(sample_store_dir)
    assert [i.format() for i in issues if i.code != "contract.modified"] == []


def test_sample_store_contract_copy_is_current(sample_store_dir):
    assert (sample_store_dir / "CONTRACT.md").read_text() == (contract_dir() / "CONTRACT.md").read_text(), (
        "re-copy contract/CONTRACT.md to tests/fixtures/sample-store/CONTRACT.md"
    )


@pytest.mark.parametrize("date", ["2027-01-08", "2027-01-11", "2027-01-12"])
def test_sample_store_clean_against_mini_world_gold(sample_store_dir, mini_world_dir, date):
    """The sample store mirrors the mini world at its seed end (2027-01-08): every cited
    artifact is delivered by then, and no planted secret (e.g. ca-0001's passcode) appears."""
    state = state_at(World.load(mini_world_dir), date)
    issues = validate_store(sample_store_dir, secrets=state["secrets"], delivered=set(state["delivered"]))
    assert [i.format() for i in issues if i.code != "contract.modified"] == []


def test_cli_validate_store(sample_store_dir, store_copy, capsys):
    assert main(["validate", "store", str(sample_store_dir)]) == 0
    assert capsys.readouterr().out.strip().endswith("0 error(s), 0 warning(s)")
    (store_copy / "people" / "me.md").unlink()
    assert main(["validate", "store", str(store_copy)]) == 1
    assert "[me.missing]" in capsys.readouterr().out
    assert main(["validate", "store", str(store_copy / "nope")]) == 2


# ---------------------------------------------------------------- broken copies
def edit(rel: str, old: str, new: str) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        p = root / rel
        text = p.read_text()
        assert old in text, f"fixture text {old!r} not found in {rel}"
        p.write_text(text.replace(old, new, 1))

    return apply


def write(rel: str, text: str) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    return apply


def remove(rel: str) -> Callable[[Path], None]:
    return lambda root: (root / rel).unlink()


def move(src: str, dst: str) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        (root / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(root / src, root / dst)

    return apply


PERSON = "---\nid: people/{slug}\ntype: person\nname: {name}\naliases: []\nupdated: 2027-01-08\n{extra}---\n"
PROJECT_BODY_TAIL = "\n## Knowledge\n\nx\n\n## Log\n\n- 2027-01-04: x\n"

BROKEN = [
    # (case id, mutation, expected code, needle expected in the message or None)
    ("no-frontmatter", write("loops/plain.md", "Just text.\n"), "frontmatter", "missing YAML"),
    ("bad-yaml", write("loops/bad.md", "---\nid: [oops\n---\n"), "frontmatter", "invalid YAML"),
    ("impossible-date-unquoted", edit(QUESTIONNAIRE, "due: 2027-01-12", "due: 2027-02-30"), "frontmatter", "out of range"),
    ("missing-title", edit(QUESTIONNAIRE, "title: Return the Tessellate security questionnaire to Cora\n", ""), "schema", "'title'"),
    ("bad-status", edit(QUESTIONNAIRE, "status: open", "status: maybe"), "schema", "status"),
    ("bad-basis", edit(QUESTIONNAIRE, "basis: received", "basis: heard"), "schema", "evidence/0/basis"),
    ("no-evidence", edit(QUESTIONNAIRE, "  - {source: em-0001, basis: received, date: 2027-01-04}\n", "  []\n"), "schema", "evidence"),
    ("task-null-counterparty", edit(QUESTIONNAIRE, "counterparty: people/cora-velez", "counterparty: null"), "schema", "counterparty"),
    ("decision-without-outcome", edit(DECISION, "outcome: Limit the Quillon pilot to the Reno depot\n", ""), "schema", "'outcome'"),
    ("merged-without-status", edit(QUILLON, "status: active", "status: active\nmerged_into: projects/ledger-cleanup"), "schema", "merged"),
    ("aliases-null", edit("orgs/larchmont.md", "aliases: [Larchmont, larchmont.example]", "aliases: null"), "schema", "aliases"),
    ("datetime-not-date", edit(QUESTIONNAIRE, "updated: 2027-01-04", "updated: 2027-01-04 10:00"), "schema", "updated"),
    ("wrong-type", edit(QUESTIONNAIRE, "type: loop", "type: task"), "type.mismatch", "'task'"),
    ("missing-type", edit(QUESTIONNAIRE, "type: loop\n", ""), "type.mismatch", "missing"),
    ("wrong-id", edit(QUESTIONNAIRE, "id: loops/return-tessellate-security-questionnaire", "id: loops/questionnaire"), "id.mismatch", "expected"),
    ("missing-id", edit(QUESTIONNAIRE, "id: loops/return-tessellate-security-questionnaire\n", ""), "id.mismatch", "missing"),
    ("uppercase-name", move("orgs/tessellate.md", "orgs/Tessellate.md"), "name.slug", "Tessellate"),
    ("log-name-not-date", move("logs/2027-01-08.md", "logs/jan-8.md"), "name.slug", "YYYY-MM-DD"),
    ("nested-record", move(DECISION, "loops/archive/limit-quillon-pilot-to-reno.md"), "path.nested", None),
    ("no-me", remove("people/me.md"), "me.missing", None),
    ("owner-missing", edit(QUESTIONNAIRE, "owner: people/me", "owner: people/ada"), "link.missing", "people/ada"),
    ("project-people-missing", edit(QUILLON, "people/sam-reyes]", "people/sam-ryes]"), "link.missing", "people/sam-ryes"),
    ("person-org-missing", edit("people/me.md", "org: orgs/larchmont", "org: orgs/larchmont-freight"), "link.missing", None),
    ("quoted-impossible-date", edit(QUESTIONNAIRE, "due: 2027-01-12", "due: '2027-02-30'"), "date.invalid", "due"),
    ("evidence-impossible-date", edit(QUESTIONNAIRE, "date: 2027-01-04}", "date: '2027-13-04'}"), "date.invalid", "evidence/0/date"),
    ("cs-missing", edit(QUILLON, "## Current state", "## Status"), "project.current-state", "missing"),
    ("cs-two-paragraphs", edit(QUILLON, " Next dated step:", "\n\nNext dated step:"), "project.current-state", "found 2"),
    ("cs-no-as-of", edit(QUILLON, "As of 2027-01-07: Quillon", "Quillon"), "project.current-state", "As of"),
    ("cs-relative-date", edit(QUILLON, "As of 2027-01-07:", "As of today:"), "project.current-state", "As of"),
    ("cs-list", edit(QUILLON, " Next dated step:", "\n- Next dated step:"), "project.current-state", "list"),
    ("cs-bad-date", edit(QUILLON, "As of 2027-01-07:", "As of 2027-13-07:"), "project.current-state", "calendar"),
    ("cs-empty", edit("projects/ledger-cleanup.md", "As of 2027-01-05: Ben is reconciling", "\n\n## Notes\n\nBen is reconciling"), "project.current-state", "empty"),
    ("duplicate-current-state", edit(QUILLON, "## Knowledge", "## Current state\n\nAs of 2027-01-04: older.\n\n## Knowledge"), "project.current-state", "found 2"),
    ("log-date", edit("logs/2027-01-08.md", "date: 2027-01-08", "date: 2027-01-07"), "log.date", None),
    ("leaked-secret", write("notes/review.md", "Reconciliation review, code 514227 for the call.\n"), "privacy.secret", "planted secret"),
    ("join-link", write("sources/ca-0001.md", "Join: https://meet.vidlink.example/j/88812345\n"), "privacy.join-link", "meet.vidlink.example"),
    ("passcode", edit("people/ben-okoro.md", "## Context\n", "## Context\n\nReview call passcode: 663301.\n"), "privacy.passcode", "line 14"),
    ("dial-in", write("notes/calls.md", "Dial-in: +1 415 555 0100,,88812345#\n"), "privacy.dial-in", None),
    ("api-key", write("notes/setup.md", "key = sk-ant-api03-AbCdEf0123456789XyZabc\n"), "privacy.api-key", None),
    ("secret-in-frontmatter", edit(QUESTIONNAIRE, "  - {source: em-0001", "  - {note: 'pwd=Xy7pq2', source: em-0001"), "privacy.passcode", None),
]

WARNINGS = [
    ("body-link", edit(QUILLON, "- Decisions:", "- See [[projects/thistledown]].\n- Decisions:"), "link.unresolved", "projects/thistledown"),
    ("created-after-updated", edit(QUESTIONNAIRE, "created: 2027-01-04", "created: 2027-01-09"), "date.order", None),
    ("citation-format", edit(QUILLON, "[src: nt-0001].\n- Tessellate", "[src: email from Cora].\n- Tessellate"), "citation.format", "email"),
    ("no-knowledge", edit(QUILLON, "## Knowledge", "## Background"), "project.section", "Knowledge"),
    ("section-order", edit(QUILLON, "## Current state", "## Log\n\n- 2027-01-03: earlier\n\n## Current state"), "project.section", "order"),
    ("undated-log-bullet", edit(QUESTIONNAIRE, "- 2027-01-04: Cora", "- yesterday: Cora"), "log.bullet", "yesterday"),
    ("log-order", edit("people/me.md", "- 2027-01-04: Kicked", "- 2027-01-09: Kicked"), "log.order", None),
    ("evidence-prefix", edit(QUESTIONNAIRE, "source: em-0001", "source: zz-0001"), "evidence.source", "zz-0001"),
    ("log-entry", edit("logs/2027-01-08.md", "- em-0003 (email)", "- Newsletter (em-0003)"), "log.entry", "Newsletter"),
    ("dup-email", write("people/samir-patel.md", PERSON.format(slug="samir-patel", name="Samir Patel", extra="email: Sam.Patel@larchmont.example\n")), "duplicate.email", "sam.patel@larchmont.example"),
    ("dup-email-alias", write("people/samir.md", "---\nid: people/samir\ntype: person\nname: Samir\naliases: [sam.patel@larchmont.example]\nupdated: 2027-01-08\n---\n"), "duplicate.email", None),
    ("dup-person-name", write("people/ben.md", PERSON.format(slug="ben", name="ben okoro", extra="")), "duplicate.name", "people/ben, people/ben-okoro"),
    ("dup-org-name", write("orgs/tessellate-analytics.md", "---\nid: orgs/tessellate-analytics\ntype: org\nname: Tessellate Analytics\naliases: []\nupdated: 2027-01-08\n---\n"), "duplicate.name", None),
    ("dup-project", write("projects/quillon-2.md", "---\nid: projects/quillon-2\ntype: project\nname: Quillon\naliases: []\nstatus: active\nowner: people/me\nupdated: 2027-01-08\n---\n## Current state\n\nAs of 2027-01-08: x.\n" + PROJECT_BODY_TAIL), "duplicate.project", None),
    ("no-contract", remove("CONTRACT.md"), "contract.missing", None),
    ("edited-contract", edit("CONTRACT.md", "# Store contract (Track A)", "# My contract"), "contract.modified", None),
    ("stray-file", write("loops/todo.txt", "stray\n"), "file.unexpected", None),
]


@pytest.mark.parametrize("case, mutate, code, needle", BROKEN + WARNINGS, ids=[c[0] for c in BROKEN + WARNINGS])
def test_broken_store_reports_code(store_copy, case, mutate, code, needle):
    mutate(store_copy)
    issues = validate_store(store_copy, secrets=["514227"])
    hits = [i for i in issues if i.code == code]
    assert hits, f"{case}: expected [{code}], got {[i.format() for i in issues]}"
    assert all(i.severity == CODES[code][0] for i in hits)
    if needle:
        assert any(needle in i.message for i in hits), [i.format() for i in hits]


@pytest.mark.parametrize("case, mutate, code, needle", WARNINGS, ids=[c[0] for c in WARNINGS])
def test_warning_cases_have_no_errors(store_copy, case, mutate, code, needle):
    mutate(store_copy)
    assert [i.format() for i in errors(validate_store(store_copy))] == []


def test_every_emitted_code_is_documented(store_copy):
    for _, mutate, _, _ in BROKEN + WARNINGS:
        if not (store_copy / "people" / "me.md").exists():
            break
        try:
            mutate(store_copy)
        except (AssertionError, FileNotFoundError):
            continue  # an earlier mutation already changed this text
    issues = validate_store(store_copy, secrets=["514227"])
    assert issues and codes(issues) <= set(CODES)


def test_undelivered_evidence_and_citations(sample_store_dir):
    delivered = {"nt-0001", "em-0001", "ch-0001", "em-0002", "em-0003"}  # no mt-0001
    issues = validate_store(sample_store_dir, delivered=delivered)
    assert codes(issues) - {"contract.modified"} == {"evidence.undelivered", "citation.undelivered"}
    assert all(i.severity == "warning" and "mt-0001" in i.message for i in issues if i.code != "contract.modified")


def test_issues_are_sorted_by_path(store_copy):
    remove("CONTRACT.md")(store_copy)
    edit(QUESTIONNAIRE, "owner: people/me", "owner: people/ada")(store_copy)
    edit("orgs/larchmont.md", "aliases: [Larchmont, larchmont.example]", "aliases: null")(store_copy)
    paths = [i.path for i in validate_store(store_copy)]
    assert paths == sorted(paths)


def test_schema_and_link_errors_not_double_counted(store_copy):
    """A malformed link is one schema error, not also a missing link."""
    edit(QUESTIONNAIRE, "owner: people/me", "owner: people/me.md")(store_copy)
    issues = validate_store(store_copy)
    assert [i.code for i in errors(issues)] == ["schema"]


def test_one_schema_error_per_field(store_copy):
    """A task status outside the task enum fails two schema rules but is one mistake."""
    edit(QUESTIONNAIRE, "status: open", "status: in-progress")(store_copy)
    edit(QUESTIONNAIRE, "title: Return the Tessellate security questionnaire to Cora\n", "")(store_copy)
    edit(QUESTIONNAIRE, "accepted: true\n", "")(store_copy)
    msgs = sorted(i.message for i in errors(validate_store(store_copy)))
    assert len(msgs) == 3
    assert msgs[:2] == ["missing required field 'accepted'", "missing required field 'title'"]
    assert msgs[2].startswith("status:") and "'reversed'" not in msgs[2]


def test_bad_file_name_is_not_also_an_id_mismatch(store_copy):
    move("orgs/tessellate.md", "orgs/Tessellate.md")(store_copy)
    issues = errors(validate_store(store_copy))
    assert [i.code for i in issues if i.path == "orgs/Tessellate.md"] == ["name.slug"]


def test_extra_fields_and_lenient_forms_are_allowed(store_copy):
    edit(QUESTIONNAIRE, "due: 2027-01-12", "due: 2027-01-12\npriority: high\ntags: [security]")(store_copy)
    edit(QUILLON, "## Current state\n\nAs of 2027-01-07:", "## Current State\n\n**As of 2027-01-07:**")(store_copy)
    edit("people/me.md", "- 2027-01-04: Kicked", "- **2027-01-04** — Kicked")(store_copy)
    write("notes/scratch.md", "Join: [redacted]. Passcode: [redacted]. Password reset ticket filed.\n")(store_copy)
    write("sources/em-0003.eml", "From: Nina Hart <nina@freightwire.example>\nSubject: weekly\n")(store_copy)
    edit("logs/2027-01-08.md", "no change.", "no change. Archived as [[sources/em-0003]].")(store_copy)
    issues = validate_store(store_copy)
    assert [i.format() for i in issues if i.code != "contract.modified"] == []


def test_citations_and_links_in_code_are_ignored(store_copy):
    edit(QUILLON, "## Log\n", "## Log\n\n```\n[[projects/example]] [src: anything]\n```\n")(store_copy)
    issues = validate_store(store_copy)
    assert [i.format() for i in issues if i.code != "contract.modified"] == []


@pytest.mark.parametrize(
    "text, problem",
    [
        ("As of 2027-01-07: fine [src: em-0001].", None),
        ("As of 2027-01-07, fine.\nWrapped onto a second line.", None),
        ("_As of 2027-01-07:_ emphasis is fine.", None),
        (None, "missing"),
        ("", "empty"),
        ("As of 2027-01-07: one.\n\nAs of 2027-01-06: two.", "exactly one paragraph"),
        ("Status: fine.", "must begin"),
        ("As of 7 Jan: fine.", "must begin"),
        ("As of 2027-01-07:\n- bullet", "prose paragraph"),
        ("### Sub\nAs of 2027-01-07: x", "prose paragraph"),
        ("As of 2027-02-30: x", "calendar date"),
    ],
)
def test_current_state_problem(text, problem):
    got = current_state_problem(text)
    assert (got is None) if problem is None else (got is not None and problem in got)
