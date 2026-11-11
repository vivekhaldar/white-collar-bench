"""Check that an agent's runtime can read every white-collar-bench input format.

Run it where the agent's own commands run (inside its container or sandbox, with the
interpreter the agent's tools use), not on the host:

    docker run --rm -v "$PWD/docker:/check:ro" wcb-simple python -I /check/smoke_tools.py
    docker run --rm -v "$PWD/docker:/check:ro" -v "$PWD/worlds/dev/gen-s2-w1/inbox:/in:ro" \
        wcb-simple python -I /check/smoke_tools.py /in

Without arguments it checks that each reader imports and round-trips a document it writes
itself (PDF text extraction is checked only on real files). With directories or files as
arguments it also extracts text from every .pdf, .docx, .xlsx, .pptx and .md file found and
reports any that fail or come out empty. Exits 1 if anything is missing or fails.

Standard library only apart from the readers it checks. Public synthetic inputs only.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

problems: list[str] = []


def check(name: str, fn, optional: bool = False) -> None:
    try:
        detail = fn()
    except Exception as e:  # noqa: BLE001 - report every failure, keep going
        if not optional:
            problems.append(name)
        print(f"{'warn' if optional else 'FAIL'}  {name}: {type(e).__name__}: {e}")
    else:
        print(f"ok    {name}: {detail}")


def yaml_front_matter() -> str:
    import yaml

    text = "---\nid: people/sample\naliases: [Sam]\nupdated: 2027-01-05\n---\nBody\n"
    meta = yaml.safe_load(text.split("---\n")[1])
    assert meta["aliases"] == ["Sam"], meta
    return f"PyYAML {yaml.__version__}"


def docx_roundtrip() -> str:
    import docx

    buf = io.BytesIO()
    d = docx.Document()
    d.add_paragraph("Decision: option two")
    d.save(buf)
    got = "\n".join(p.text for p in docx.Document(io.BytesIO(buf.getvalue())).paragraphs)
    assert "option two" in got, got
    return "python-docx " + _version("python-docx")


def xlsx_roundtrip() -> str:
    import openpyxl

    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    wb.active.append(["Line item", 1200])
    wb.save(buf)
    row = next(openpyxl.load_workbook(io.BytesIO(buf.getvalue())).active.iter_rows(values_only=True))
    assert row == ("Line item", 1200), row
    return f"openpyxl {openpyxl.__version__}"


def pptx_roundtrip() -> str:
    import pptx

    buf = io.BytesIO()
    p = pptx.Presentation()
    p.slides.add_slide(p.slide_layouts[0]).shapes.title.text = "Quarterly review"
    p.save(buf)
    slide = pptx.Presentation(io.BytesIO(buf.getvalue())).slides[0]
    assert slide.shapes.title.text == "Quarterly review"
    return "python-pptx " + _version("python-pptx")


def pypdf_import() -> str:
    import pypdf

    return f"pypdf {pypdf.__version__}"


def pdftotext() -> str:
    exe = shutil.which("pdftotext")
    if exe is None:
        raise FileNotFoundError("pdftotext is not on PATH (optional: pypdf reads PDFs too)")
    out = subprocess.run([exe, "-v"], capture_output=True, text=True, timeout=30)
    return (out.stderr or out.stdout).splitlines()[0]


def _version(dist: str) -> str:
    from importlib.metadata import version

    return version(dist)


def extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pypdf

        return "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(path).pages)
    if suffix == ".docx":
        import docx

        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    if suffix == ".xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        return "\n".join(
            " ".join(str(c) for c in row if c is not None)
            for ws in wb.worksheets
            for row in ws.iter_rows(values_only=True)
        )
    if suffix == ".pptx":
        import pptx

        return "\n".join(
            sh.text_frame.text
            for slide in pptx.Presentation(path).slides
            for sh in slide.shapes
            if sh.has_text_frame
        )
    import yaml  # .md: YAML front matter, if any, must parse

    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n") and "\n---" in text[4:]:
        yaml.safe_load(text[4 : text.index("\n---", 4)])
    return text


def main(argv: list[str]) -> int:
    print(f"python {sys.version.split()[0]} at {sys.executable}")
    check("YAML front matter", yaml_front_matter)
    check("PDF (pypdf)", pypdf_import)
    check("PDF (pdftotext)", pdftotext, optional=True)
    check("DOCX", docx_roundtrip)
    check("XLSX", xlsx_roundtrip)
    check("PPTX", pptx_roundtrip)
    required = list(problems)
    files = []
    for arg in argv:
        p = Path(arg)
        files += sorted(p.rglob("*")) if p.is_dir() else [p]
    files = [f for f in files if f.suffix.lower() in {".pdf", ".docx", ".xlsx", ".pptx", ".md"}]
    for f in files:
        try:
            text = extract(f).strip()
        except Exception as e:  # noqa: BLE001
            required.append(str(f))
            print(f"FAIL  {f}: {type(e).__name__}: {e}")
            continue
        if not text:
            required.append(str(f))
            print(f"FAIL  {f}: no text extracted")
        else:
            print(f"ok    {f}: {len(text)} characters")
    print("all readers work" if not required else f"{len(required)} problem(s)")
    return 1 if required else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
