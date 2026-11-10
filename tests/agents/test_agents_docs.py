"""Document text extraction (wcb.agents.docs_text)."""

from __future__ import annotations

import zlib

import pytest
from agents_office_files import make_docx, make_pptx, make_xlsx, make_zip

from wcb.agents.docs_text import DocumentError, eml_text, extract_text, ics_text, pdf_text


def test_docx_paragraphs_headings_lists_and_tables(tmp_path):
    text = extract_text(make_docx(tmp_path / "dc-0001.docx"))
    lines = text.splitlines()
    assert lines[0] == "# Vendor review"
    assert "Decision: go with option 2\t[owner]" in text
    assert "second line" in text
    assert "- Send pricing by 2027-03-05" in lines
    assert "Item | Cost" in lines and "Hosting | 1200" in lines
    assert "After the table" in text
    assert "deleted" not in text  # tracked deletions are not current text
    # Document order is preserved.
    assert text.index("Vendor review") < text.index("Hosting") < text.index("After the table")


def test_xlsx_sheets_shared_strings_numbers_and_dates(tmp_path):
    text = extract_text(make_xlsx(tmp_path / "dc-0002.xlsx"))
    assert "## Sheet: Budget" in text and "## Sheet: Dates" in text
    assert "1: Line item | Amount" in text  # shared strings, including rich-text runs
    assert "2: Hosting | 1200" in text  # integers lose the trailing .0
    assert "3: Total |  | 1200.5 | TRUE" in text  # gap kept, cached formula value, boolean
    assert "1: Due | 2027-03-01 | 2027-03-02 12:00 | Due" in text  # custom + builtin date formats


def test_pptx_slides_in_presentation_order(tmp_path):
    text = extract_text(make_pptx(tmp_path / "deck.pptx"))
    assert text.index("## Slide 1") < text.index("First slide title")
    assert text.index("## Slide 2") < text.index("Second slide title")
    assert text.index("First slide title") < text.index("Second slide title")


def _pdf(content: bytes, *, flate: bool = False) -> bytes:
    stream = zlib.compress(content) if flate else content
    filt = b" /Filter /FlateDecode" if flate else b""
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Length "
        + str(len(stream)).encode()
        + filt
        + b" >>\nstream\n"
        + stream
        + b"\nendstream\nendobj\n%%EOF\n"
    )


PDF_CONTENT = (
    b"BT /F1 12 Tf 72 720 Td (Quarterly review \\(draft\\)) Tj 0 -14 Td "
    b"[(Budget) -300 (approved) 20 (!)] TJ T* (Owner: Dana) Tj "
    b"0 -14 Td <48656C6C6F> Tj (caf\\351) ' ET"
)


@pytest.mark.parametrize("flate", [False, True])
def test_pdf_text_operators(flate):
    text = pdf_text(_pdf(PDF_CONTENT, flate=flate))
    lines = text.splitlines()
    assert lines[0] == "Quarterly review (draft)"
    assert "Budget approved!" in lines
    assert "Owner: Dana" in lines
    assert "Hello" in lines
    assert "café" in lines  # octal escape decoded as WinAnsi


def test_pdf_without_text_and_non_pdf():
    assert "no extractable text" in pdf_text(_pdf(b"0 0 m 10 10 l S"))
    with pytest.raises(DocumentError):
        pdf_text(b"not a pdf")


def test_office_renderer_round_trip(tmp_path):
    """Files written by the benchmark's own renderer are extracted cleanly."""
    office = pytest.importorskip("wcb.render.office")
    md = "# Plan v2\n\nIntro with **bold** text.\n\n- first\n- second\n\n| A | B |\n|---|---|\n| x | 12 |\n"
    office.write_docx(tmp_path / "a.docx", md)
    office.write_pdf(tmp_path / "a.pdf", md)
    office.write_xlsx(tmp_path / "a.xlsx", {"S": [["h", "n"], ["x", 3]]})
    for name in ("a.docx", "a.pdf"):
        text = extract_text(tmp_path / name)
        assert "Plan v2" in text and "Intro with bold text." in text and "second" in text
        assert "x | 12" in text
    assert "2: x | 3" in extract_text(tmp_path / "a.xlsx")


def test_eml_headers_body_and_attachments():
    raw = (
        b"From: Cora Velez <cora@tessellate.example>\r\nTo: Ada <ada@larchmont.example>\r\n"
        b"Subject: =?utf-8?q?Questionnaire_=E2=80=93_due_Tuesday?=\r\nDate: Mon, 04 Jan 2027 09:10:00 -0800\r\n"
        b"Message-ID: <em-0001@tessellate.example>\r\nMIME-Version: 1.0\r\n"
        b'Content-Type: multipart/mixed; boundary="b1"\r\n\r\n'
        b"--b1\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n"
        b"Please return it by Tuesday =E2=80=94 thanks.\r\n"
        b"--b1\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename=q.pdf\r\n"
        b"Content-Transfer-Encoding: base64\r\n\r\nJVBERi0=\r\n--b1--\r\n"
    )
    text = eml_text(raw)
    assert "From: Cora Velez <cora@tessellate.example>" in text
    assert "Subject: Questionnaire – due Tuesday" in text
    assert "Please return it by Tuesday — thanks." in text
    assert "Attachments: q.pdf (application/pdf)" in text


def test_eml_html_only_body():
    raw = b"From: a@x.example\r\nContent-Type: text/html\r\n\r\n<p>Hello <b>there</b></p><p>Bye &amp; out</p>"
    text = eml_text(raw)
    assert "Hello there" in text and "Bye & out" in text and "<p>" not in text


def test_ics_unfolds_lines():
    raw = "BEGIN:VEVENT\r\nSUMMARY:Reconciliation\r\n  review\r\nDESCRIPTION:Walk\r\n\tthrough\r\nEND:VEVENT\r\n"
    assert (
        ics_text(raw)
        == "BEGIN:VEVENT\nSUMMARY:Reconciliation review\nDESCRIPTION:Walkthrough\nEND:VEVENT\n"
    )


def test_fixture_inputs_read_as_text(mini_world_dir):
    inbox = mini_world_dir / "inbox"
    assert "Subject: Tessellate security questionnaire" in extract_text(
        inbox / "2027-01-04" / "em-0001.eml"
    )
    assert "SUMMARY:Reconciliation review" in extract_text(inbox / "2027-01-11" / "ca-0001.ics")
    assert "<v Sam Reyes>" in extract_text(inbox / "2027-01-07" / "mt-0001.vtt")


def test_errors_for_broken_or_unsupported_files(tmp_path):
    (tmp_path / "bad.docx").write_bytes(b"not a zip")
    with pytest.raises(DocumentError, match="not a valid .docx"):
        extract_text(tmp_path / "bad.docx")
    make_zip(tmp_path / "empty.docx", {"other.xml": "<x/>"})
    with pytest.raises(DocumentError, match="no word/document.xml"):
        extract_text(tmp_path / "empty.docx")
    (tmp_path / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    with pytest.raises(DocumentError, match="binary"):
        extract_text(tmp_path / "img.png")
