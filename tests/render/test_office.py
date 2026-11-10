import zipfile

from wcb.render.office import extract_text, parse_markdown, write_docx, write_pdf, write_xlsx

MD = """# Capacity plan v2

Intro paragraph with **bold** text.

- first bullet
- second bullet

| Item | Cost |
|---|---|
| Hosting | 1200 |
"""


def test_parse_markdown():
    kinds = [k for k, _ in parse_markdown(MD)]
    assert kinds == ["h1", "p", "bullet", "bullet", "table"]


def test_docx_roundtrip(tmp_path):
    p = tmp_path / "d.docx"
    write_docx(p, MD, title="Capacity plan", author="Test Author", date="2027-03-01")
    with zipfile.ZipFile(p) as z:
        assert "word/document.xml" in z.namelist()
    text = extract_text(p)
    assert "Capacity plan v2" in text and "second bullet" in text and "Hosting" in text


def test_docx_deterministic(tmp_path):
    a, b = tmp_path / "a.docx", tmp_path / "b.docx"
    write_docx(a, MD)
    write_docx(b, MD)
    assert a.read_bytes() == b.read_bytes()


def test_xlsx_roundtrip(tmp_path):
    p = tmp_path / "s.xlsx"
    write_xlsx(p, {"Scores": [["Vendor", "Total"], ["Acme", 41], ["Total", {"f": "SUM(B2:B2)", "v": 41}]]})
    text = extract_text(p)
    assert "Vendor" in text and "41" in text and "SUM(B2:B2)" in text


def test_pdf_roundtrip(tmp_path):
    p = tmp_path / "x.pdf"
    write_pdf(p, MD + "\n" + "\n\n".join(f"Paragraph {i} about (things)." for i in range(120)), title="T")
    data = p.read_bytes()
    assert data.startswith(b"%PDF-1.4") and data.rstrip().endswith(b"%%EOF")
    text = extract_text(p)
    assert "Capacity plan v2" in text and "Paragraph 119 about (things)." in text
