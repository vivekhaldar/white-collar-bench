"""Tests for the privacy leak scanner.

Everything here is invented. The "private repository" is a fake built in tmp_path; names such as
Quillon Marbeck, Vexmoor and Zephyrine are made up, and every domain uses the reserved .example
TLD. Because the scanner ignores .example by design, tests that need a domain overlap use the
`example_is_real` fixture, which makes the scanner treat .example like an ordinary TLD.
"""

from __future__ import annotations

import os
import zipfile
import zlib
from pathlib import Path

import pytest

from wcb.cli import main
from wcb.privacy import scan as scan_mod
from wcb.privacy.scan import ALLOWLIST_FILENAME, Finding, extract_terms, scan

PHRASE = "we fold the brindle quorvane into the halcyon tessarine before each frostmark audit"

# Shared by both sides but harmless: greetings, weekdays, title-case headings, a generic host,
# a documentation-domain address and an all-common-words sentence.
BENIGN = """\
Thanks for the update. See you Monday.

## Next Steps

Please let me know if you have any questions about the budget review.
Source: https://github.com/example-org/tools
CC: someone@example.com
"""

PRIVATE_NOTE = f"""\
# Weekly notes

Met with Quillon Marbeck about the Vexmoor rollout. He said
{PHRASE}.
Michael said the forecast is on track.
Zephyrine is the codename for the archive migration.
Private only: the Orsolina renewal is at risk.

{BENIGN}
"""

PRIVATE_MAIL = """\
From: Quillon Marbeck <quillon.marbeck@harrowgate.example>
To: ops@harrowgate.example
Subject: runbook

The runbook lives at https://portal.vexmoor.example/runbooks/42 for now.
"""

CORPUS_EMAIL = f"""\
From: Quillon Marbeck <quillon.marbeck@harrowgate.example>
To: Ada Quist <ada.quist@larchmont.example>
Date: Mon, 04 Jan 2027 09:10:00 -0800
Subject: Vexmoor rollout

Hi Ada,

Thanks for the call on Monday. As agreed, {PHRASE}, as planned.
The runbook is at https://portal.vexmoor.example/runbooks/42 and dispatch@harrowgate.example
has the details. Michael will join the budget review.
Zephyrine kicks off next week.

Best,
Quillon
"""

# Terms placed where the scanner must not look on the private side.
HIDDEN = "Calloway Brisk, Dunmore Fallow and Pellwick Strand"


def _write(path: Path, text: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    """A fake private repository and a fake benchmark corpus with planted overlaps."""
    private = tmp_path / "private"
    _write(private / "notes" / "weekly.md", PRIVATE_NOTE)
    _write(private / "mail" / "thread.eml", PRIVATE_MAIL)
    # Skipped locations and files on the private side.
    _write(private / ".git" / "description", f"{HIDDEN}\n")
    _write(private / "node_modules" / "pkg" / "readme.md", f"{HIDDEN}\n")
    _write(private / ".venv" / "notes.md", f"{HIDDEN}\n")
    _write(private / "env" / "pyvenv.cfg", "home = /usr/bin\n")
    _write(private / "env" / "notes.md", f"{HIDDEN}\n")
    _write(private / "binary.md", b"\x00\x01" + HIDDEN.encode() + b"\x00")
    _write(private / "huge.md", HIDDEN + "\n" + "filler words here\n" * 150_000)
    _write(private / "image.png", HIDDEN.encode())

    corpus = tmp_path / "bench"
    _write(corpus / "worlds" / "w1" / "inbox" / "2027-01-04" / "em-0001.eml", CORPUS_EMAIL)
    _write(corpus / "docs" / "guide.md", BENIGN + f"\nThe cast also includes {HIDDEN}.\n")
    return private, corpus


@pytest.fixture
def example_is_real(monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat .example as an ordinary TLD so synthetic domains can stand in for real ones."""
    monkeypatch.setattr(scan_mod, "RESERVED_TLDS", frozenset({"test", "invalid", "localhost"}))


def _by_term(findings: list[Finding]) -> dict[str, Finding]:
    return {f.term: f for f in findings}


# ------------------------------------------------------------------------------ scan


def test_planted_overlaps_are_high(repos, example_is_real):
    private, corpus = repos
    findings = scan(private, [corpus / "worlds", corpus / "docs"])
    high = {(f.kind, f.term) for f in findings if f.severity == "high"}
    assert high == {
        ("email", "quillon.marbeck@harrowgate.example"),
        ("domain", "harrowgate.example"),  # via dispatch@, which is not itself in the private repo
        ("url_host", "portal.vexmoor.example"),
        ("proper_noun", "Quillon Marbeck"),
        ("phrase", PHRASE),
    }
    by_term = _by_term(findings)
    assert by_term["Quillon Marbeck"].count_private == 2  # the note and the mail thread
    eml = "worlds/w1/inbox/2027-01-04/em-0001.eml"
    assert all(f.corpus_file.endswith(eml) for f in findings if f.severity == "high")


def test_benign_overlaps_are_not_reported(repos):
    private, corpus = repos
    findings = scan(private, [corpus / "worlds", corpus / "docs"])
    kinds = {f.kind for f in findings}
    # .example domains, example.com and github.com are never reported.
    assert not kinds & {"email", "domain", "url_host"}
    terms = {f.term for f in findings}
    for benign in ("Monday", "Thanks", "Next Steps", "Next", "Steps", "Please", "Best", "Hi"):
        assert benign not in terms
    assert not any("questions" in t or "budget" in t for t in terms)
    # Terms only present in skipped private locations are never reported.
    assert not any(name in t for t in terms for name in ("Calloway", "Dunmore", "Pellwick"))
    assert {(f.kind, f.term) for f in findings if f.severity == "high"} == {
        ("proper_noun", "Quillon Marbeck"),
        ("phrase", PHRASE),
    }


def test_single_words_get_medium_or_low(repos):
    private, corpus = repos
    by_term = _by_term(scan(private, [corpus]))
    assert by_term["Zephyrine"].severity == "medium"
    assert by_term["Vexmoor"].severity == "medium"
    assert by_term["Michael"].severity == "low"  # very common first name
    # "Quillon" and "Marbeck" alone are explained by the "Quillon Marbeck" finding.
    assert "Quillon" not in by_term and "Marbeck" not in by_term


def test_findings_are_sorted_and_deterministic(repos, example_is_real):
    private, corpus = repos
    first = scan(private, [corpus])
    second = scan(private, [corpus])
    assert first == second
    assert first == sorted(first, key=Finding.sort_key)
    ranks = [("high", "medium", "low").index(f.severity) for f in first]
    assert ranks == sorted(ranks)


def test_scan_writes_no_files(repos, tmp_path, monkeypatch, example_is_real):
    private, corpus = repos

    def snapshot() -> dict[str, tuple[int, int]]:
        out = {}
        for dirpath, dirnames, filenames in os.walk(tmp_path):
            for name in dirnames + filenames:
                p = Path(dirpath) / name
                st = p.stat()
                out[str(p)] = (st.st_size, st.st_mtime_ns)
        return out

    before = snapshot()
    monkeypatch.chdir(tmp_path)
    assert scan(private, [corpus])
    assert snapshot() == before


def test_output_never_reveals_private_paths_or_context(repos, example_is_real):
    private, corpus = repos
    findings = scan(private, [corpus])
    text = "\n".join(f.format() for f in findings) + repr([f.to_dict() for f in findings])
    assert str(private) not in text
    assert "weekly.md" not in text and "thread.eml" not in text
    assert "Orsolina" not in text  # private-only word next to a planted one
    assert "ops@harrowgate.example" not in text  # private-only address on a shared domain


def test_format_line(repos):
    private, corpus = repos
    f = _by_term(scan(private, [corpus]))["Quillon Marbeck"]
    line = f.format()
    assert line.startswith("HIGH   proper_noun")
    assert '"Quillon Marbeck"' in line
    assert f.corpus_file in line
    assert "private file" in line


def test_phrase_count_and_merge(repos):
    private, corpus = repos
    phrase = next(f for f in scan(private, [corpus]) if f.kind == "phrase")
    assert phrase.term == PHRASE  # overlapping 6-word windows merged into one span
    assert phrase.count_private == 1


def test_min_len_filters_single_words(repos):
    private, corpus = repos
    terms = {f.term for f in scan(private, [corpus], min_len=8)}
    assert "Vexmoor" not in terms  # 7 letters
    assert "Zephyrine" in terms


def test_allowlist_file(repos):
    private, corpus = repos
    _write(
        corpus / ALLOWLIST_FILENAME,
        "# reviewed: invented codenames\nZephyrine\nvexmoor  # case-insensitive\nMichael\n",
    )
    stats: dict = {}
    terms = {f.term for f in scan(private, [corpus], stats=stats)}
    assert not terms & {"Zephyrine", "Vexmoor", "Michael"}
    assert "Quillon Marbeck" in terms
    assert stats["allowlist_files"] == [str((corpus / ALLOWLIST_FILENAME).resolve())]


def test_allowlist_found_at_repository_root(repos):
    private, corpus = repos
    _write(corpus / "pyproject.toml", "[project]\nname = 'bench'\n")
    _write(corpus / ALLOWLIST_FILENAME, "Zephyrine\n")
    terms = {f.term for f in scan(private, [corpus / "worlds"])}
    assert "Zephyrine" not in terms
    assert "Quillon Marbeck" in terms


def test_allowlist_hosts_cover_subdomains(repos, example_is_real):
    private, corpus = repos
    _write(corpus / ALLOWLIST_FILENAME, "vexmoor.example\n")
    kinds_terms = {(f.kind, f.term) for f in scan(private, [corpus])}
    assert ("url_host", "portal.vexmoor.example") not in kinds_terms
    assert ("domain", "harrowgate.example") in kinds_terms


def test_stats(repos):
    private, corpus = repos
    stats: dict = {}
    scan(private, [corpus], stats=stats)
    assert stats["corpus_files"] == 2
    assert stats["private_files"] == 2  # weekly.md and thread.eml
    assert stats["private_files_skipped"] == 2  # binary.md and huge.md


def test_file_names_are_scanned(tmp_path):
    private = tmp_path / "private"
    _write(private / "people" / "Ottoline Vray.md", "role: vendor contact\n")
    corpus = tmp_path / "corpus"
    _write(corpus / "note.md", "Ottoline Vray will send the quote.\n")
    terms = {f.term for f in scan(private, [corpus])}
    assert "Ottoline Vray" in terms


def test_corpus_inside_private_repo_is_not_compared_with_itself(tmp_path):
    private = tmp_path / "private"
    _write(private / "notes.md", "Nothing shared here.\n")
    corpus = private / "bench" / "worlds"
    _write(corpus / "a.md", "Quillon Marbeck and Zephyrine.\n")
    _write(private / "bench" / "pyproject.toml", "[project]\nname = 'bench'\n")
    _write(private / "bench" / "README.md", "Quillon Marbeck and Zephyrine.\n")
    assert scan(private, [corpus]) == []


def test_private_repo_inside_corpus_is_skipped(tmp_path):
    corpus = tmp_path / "bench"
    _write(corpus / "a.md", "Quillon Marbeck and Zephyrine.\n")
    private = corpus / "private-notes"
    _write(private / "notes.md", "Nothing about anyone in particular.\n")
    assert scan(private, [corpus]) == []


def test_errors(tmp_path):
    private = tmp_path / "private"
    corpus = tmp_path / "corpus"
    _write(private / "a.md", "text\n")
    _write(corpus / "b.md", "text\n")
    with pytest.raises(FileNotFoundError, match="private repository not found"):
        scan(tmp_path / "missing", [corpus])
    with pytest.raises(FileNotFoundError, match="corpus path not found"):
        scan(private, [tmp_path / "missing"])
    with pytest.raises(ValueError, match="private repository itself"):
        scan(private, [private])
    with pytest.raises(ValueError, match="no corpus paths"):
        scan(private, [])
    with pytest.raises(ValueError, match="min_len"):
        scan(private, [corpus], min_len=0)
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="no readable files found in the corpus"):
        scan(private, [empty])
    with pytest.raises(ValueError, match="no readable text files found in the private"):
        scan(empty, [corpus])


# ------------------------------------------------------------------------------ documents


def _docx(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<w:document xmlns:w="urn:w"><w:body>'
            "<w:p><w:r><w:t>Prepared by Quill</w:t></w:r><w:r><w:t>on Marbeck</w:t></w:r></w:p>"
            "<w:p><w:r><w:t>Next steps</w:t></w:r></w:p>"
            "</w:body></w:document>",
        )
        zf.writestr(
            "docProps/core.xml",
            '<cp:coreProperties xmlns:cp="urn:cp" xmlns:dc="urn:dc">'
            "<dc:creator>Zephyrine Office</dc:creator><cp:lastModifiedBy>Ada</cp:lastModifiedBy>"
            "</cp:coreProperties>",
        )
        zf.writestr(
            "word/_rels/document.xml.rels",
            '<Relationships><Relationship Id="rId1" Target="https://portal.vexmoor.example/x" '
            'TargetMode="External"/></Relationships>',
        )
        zf.writestr("word/media/image1.png", b"\x89PNG Calloway Brisk")
    return path


def _pdf(content: bytes, *, compress: bool = True) -> bytes:
    stream = zlib.compress(content) if compress else content
    flt = b" /Filter /FlateDecode" if compress else b""
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Length "
        + str(len(stream)).encode()
        + flt
        + b" >>\nstream\n"
        + stream
        + b"\nendstream\nendobj\n2 0 obj\n<< /Author (Quillon Marbeck) /Title (Q\\(1\\) plan) >>\n"
        b"endobj\ntrailer\n<< /Info 2 0 R >>\n%%EOF\n"
    )


def test_office_text_extraction(tmp_path):
    text = scan_mod._office_text(_docx(tmp_path / "a.docx").read_bytes())
    assert "Prepared by Quillon Marbeck" in text  # runs are joined without spaces
    assert "Zephyrine Office" in text  # document metadata
    assert "https://portal.vexmoor.example/x" in text  # hyperlink targets
    assert "Calloway" not in text  # media files are not read
    assert scan_mod._office_text(b"not a zip") is None


def test_xlsx_shared_strings(tmp_path):
    path = tmp_path / "b.xlsx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "xl/sharedStrings.xml", "<sst><si><t>Zephyrine</t></si><si><t>Quillon</t></si></sst>"
        )
    text = scan_mod._office_text(path.read_bytes())
    assert "Zephyrine" in text.split()
    assert "Quillon" in text.split()


@pytest.mark.parametrize("compress", [True, False])
def test_pdf_text_extraction(compress):
    content = (
        b"BT /F1 12 Tf 72 720 Td (Zephyrine kicks off) Tj 0 -14 Td "
        b"[(Quill) 20 (on) -400 (Marbeck)] TJ T* <48656c6c6f> Tj ET"
    )
    text = scan_mod._pdf_text(_pdf(content, compress=compress))
    assert "Zephyrine kicks off" in text
    assert "Quillon Marbeck" in text  # TJ array with a word-gap kerning value
    assert "Hello" in text  # hex string
    assert "Q(1) plan" in text  # escaped parentheses in metadata


def test_documents_are_scanned_in_corpus_only(tmp_path, repos):
    private, corpus = repos
    _docx(corpus / "worlds" / "w1" / "inbox" / "2027-01-05" / "dc-0001.docx")
    _write(
        corpus / "worlds" / "w1" / "inbox" / "2027-01-06" / "dc-0002.pdf",
        _pdf(b"BT (Zephyrine plan) Tj ET"),
    )
    by_term = _by_term(scan(private, [corpus]))
    files = {by_term["Quillon Marbeck"].corpus_file, *by_term["Quillon Marbeck"].other_files}
    assert any(f.endswith("dc-0001.docx") for f in files)
    zfiles = {by_term["Zephyrine"].corpus_file, *by_term["Zephyrine"].other_files}
    assert any(f.endswith("dc-0002.pdf") for f in zfiles)

    # A .docx in the private repository is not read (private side is plain text only).
    other = tmp_path / "private2"
    _write(other / "notes.md", "Nothing to see.\n")
    _docx(other / "secret.docx")
    assert scan(other, [corpus]) == []


# ------------------------------------------------------------------------------ extract_terms


def test_extract_terms_proper_nouns():
    terms = extract_terms(
        [
            "Attendees: Quillon Marbeck, Ada Quist. See you Monday.",
            "Thanks to Ludo van Brakel and Quillon K. Marbeck for the Next Steps.",
            "Hi Ottoline-led teams at the Brakel Institute of Vray.",
        ]
    )
    nouns = terms["proper_noun"]
    assert {"Quillon Marbeck", "Ada Quist", "Ludo van Brakel", "Quillon K. Marbeck"} <= nouns
    assert {"Quillon", "Marbeck", "Quist", "Ottoline"} <= nouns
    assert "Brakel Institute of Vray" in nouns
    assert "Ada" not in nouns  # shorter than min_len
    for common in ("Monday", "Attendees", "See", "Thanks", "Next Steps", "Next", "Hi"):
        assert common not in nouns


def test_extract_terms_lowercase_use_means_common_word():
    # "Telemetry" is capitalized only at sentence starts and used in lowercase elsewhere.
    terms = extract_terms(["Telemetry is ready.", "We check telemetry daily and log telemetry."])
    assert "Telemetry" not in terms["proper_noun"]
    # A slug such as quillon-marbeck does not count as lowercase use of "Quillon".
    terms = extract_terms(["Quillon joined. See [[people/quillon-marbeck]]."])
    assert "Quillon" in terms["proper_noun"]


def test_extract_terms_hosts_and_emails(example_is_real):
    terms = extract_terms(
        [
            "Mail jo.pine@harrowgate.example or noreply@github.com; see "
            "https://user:pw@Wiki.Vexmoor.example:8443/a, www.brakel.example and "
            "notes.md, https://github.com/x, crestline-ops.example, https://quorvane.slack.com/archives",
        ]
    )
    assert terms["email"] == {"jo.pine@harrowgate.example"}
    assert terms["url_host"] == {"wiki.vexmoor.example", "brakel.example", "quorvane.slack.com"}
    assert terms["domain"] == {"harrowgate.example", "crestline-ops.example"}


def test_extract_terms_ignores_reserved_domains_by_default():
    terms = extract_terms(["ada@larchmont.example https://meet.vidlink.example/j/1 x@y.test"])
    assert terms["email"] == terms["domain"] == terms["url_host"] == set()


def test_extract_terms_phrases():
    terms = extract_terms([PHRASE, "please let me know if you have any questions about it"])
    assert "brindle quorvane into the halcyon tessarine" in terms["phrase"]
    assert not any("questions" in p for p in terms["phrase"])  # all common words


def test_host_keys():
    key = scan_mod._host_key
    # Invented labels; only the public suffixes are real.
    assert key("mail.quorvane-widgets.com") == "quorvane-widgets.com"
    assert key("quorvane.co.uk") == key("www2.quorvane.co.uk") == "quorvane.co.uk"
    assert key("quorvane.slack.com") == "quorvane.slack.com"
    for ignored in (
        "app.slack.com",
        "us02web.zoom.us",
        "github.com",
        "docs.google.com",
        "x.example",
        "localhost",
        "10.0.0.1",
        "arxiv.org",
    ):
        assert key(ignored) is None, ignored


# ------------------------------------------------------------------------------ CLI


def test_cli_exit_codes(repos, tmp_path, capsys):
    private, corpus = repos
    assert main(["privacy", "scan", "--private-repo", str(private), str(corpus)]) == 1
    out = capsys.readouterr().out
    assert "Quillon Marbeck" in out
    assert "potential leak(s)" in out

    clean = tmp_path / "clean"
    _write(clean / "a.md", "Thanks for the update. See you Monday.\n")
    assert main(["privacy", "scan", "--private-repo", str(private), str(clean)]) == 0
    assert "0 potential leak(s)" in capsys.readouterr().out

    assert main(["privacy", "scan", "--private-repo", str(tmp_path / "nope"), str(clean)]) == 2
    assert "private repository not found" in capsys.readouterr().err


def test_extract_terms_structured_formats():
    ics = (
        "ATTENDEE;CN=Quillon Marbeck:mailto:q@harrowgate.example\n"
        "DESCRIPTION:Call with Ottoline Vray\\nAgenda: pricing"
    )
    vtt = "00:00:01.000 --> 00:00:06.000\n<v Brakel Strand>Thanks for making time."
    nouns = extract_terms([ics, vtt])["proper_noun"]
    assert {"Quillon Marbeck", "Ottoline Vray", "Brakel Strand"} <= nouns
    assert not {"Attendee", "ATTENDEE", "DESCRIPTION", "Agenda"} & nouns


def test_read_text_formats(tmp_path):
    from email.message import EmailMessage

    read = scan_mod._read_text
    j = _write(tmp_path / "c.json", '{"user": "Ottoline Vray", "text": "Hi\\nQuillon", "n": 3}')
    assert read(j, max_bytes=10**6, documents=False).splitlines() == [
        "user",
        "Ottoline Vray",
        "text",
        "Hi",
        "Quillon",
        "n",
    ]
    h = _write(
        tmp_path / "p.html",
        '<p>Ottoline <b>Vray</b></p><script>var hidden = "Calloway";</script>'
        '<a href="https://portal.vexmoor.example/x">runbook</a>',
    )
    text = read(h, max_bytes=10**6, documents=False)
    assert "Ottoline Vray" in " ".join(text.split())
    assert "https://portal.vexmoor.example/x" in text
    assert "Calloway" not in text

    msg = EmailMessage()
    msg["From"] = "Quillon Marbeck <q@harrowgate.example>"
    msg["Subject"] = "Zephyrine"
    msg.set_content("Ottoline Vray approved the brindle quorvane.\n", cte="base64")
    e = _write(tmp_path / "m.eml", msg.as_string())
    assert "Ottoline Vray approved" in read(e, max_bytes=10**6, documents=False)
    assert read(e, max_bytes=10, documents=False) is None  # over the size limit


def test_runs_may_start_with_a_first_name_that_is_also_a_word():
    nouns = extract_terms(["Met Mark Quellby and Grant Vexley about the Grant Proposal."])[
        "proper_noun"
    ]
    assert {"Mark Quellby", "Grant Vexley"} <= nouns
    assert "Grant Proposal" not in nouns
