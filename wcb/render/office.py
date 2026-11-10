"""Minimal, dependency-free writers for Office and PDF artifacts.

World authors and the generator use these to produce realistic binary inputs (`.docx`,
`.xlsx`, `.pdf`) from simple sources. The output opens in common office suites and is
readable by standard extractors (python-docx, openpyxl, pdftotext, pypdf).

CLI::

    python -m wcb.render.office docx  source.md   out.docx  [--title T] [--author A] [--date YYYY-MM-DD]
    python -m wcb.render.office pdf   source.md   out.pdf   [--title T]
    python -m wcb.render.office xlsx  source.json out.xlsx  [--author A] [--date YYYY-MM-DD]

Markdown support is deliberately small: `#`/`##`/`###` headings, paragraphs, `-`/`*` bullets,
`1.` numbered items, `**bold**` spans, and pipe tables. The xlsx source is JSON:
`{"Sheet name": [["header", ...], [1, "text", "=SUM(A2:A3)"], ...], ...}`. A string cell
starting with `=` is written as a formula; give its cached value as `{"f": "SUM(A2:A3)", "v": 42}`.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

FIXED_ZIP_TIME = (2027, 1, 1, 0, 0, 0)  # deterministic archives


# ---------------------------------------------------------------- markdown model
def parse_markdown(md: str) -> list[tuple[str, object]]:
    """Parse a tiny Markdown subset into blocks: (kind, payload).

    kinds: h1 h2 h3 p bullet number table
    """
    blocks: list[tuple[str, object]] = []
    para: list[str] = []
    lines = md.splitlines()
    i = 0

    def flush():
        if para:
            blocks.append(("p", " ".join(s.strip() for s in para)))
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush()
        elif m := re.match(r"^(#{1,3})\s+(.*)$", line):
            flush()
            blocks.append((f"h{len(m[1])}", m[2].strip()))
        elif re.match(r"^\s*[-*]\s+", line):
            flush()
            blocks.append(("bullet", re.sub(r"^\s*[-*]\s+", "", line)))
        elif re.match(r"^\s*\d+[.)]\s+", line):
            flush()
            blocks.append(("number", line.strip()))
        elif line.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        else:
            para.append(line)
        i += 1
    flush()
    return blocks


def _runs(text: str) -> list[tuple[str, bool]]:
    """Split text on **bold** markers into (text, bold) runs."""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    out = []
    for p in parts:
        if not p:
            continue
        if p.startswith("**") and p.endswith("**"):
            out.append((p[2:-2], True))
        else:
            out.append((p, False))
    return out


# ---------------------------------------------------------------- zip helper
def _write_zip(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data.encode("utf-8"))


def _core_props(title: str, author: str, date: str) -> str:
    ts = f"{date}T09:00:00Z" if date else "2027-01-01T00:00:00Z"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>{escape(author)}</dc:creator>"
        f"<cp:lastModifiedBy>{escape(author)}</cp:lastModifiedBy>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{ts}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{ts}</dcterms:modified>'
        "</cp:coreProperties>"
    )


# ---------------------------------------------------------------- docx
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _docx_par(text: str, style: str | None = None, prefix: str = "") -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    runs = []
    if prefix:
        runs.append(f'<w:r><w:t xml:space="preserve">{escape(prefix)}</w:t></w:r>')
    for t, bold in _runs(text):
        rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
        runs.append(f'<w:r>{rpr}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>')
    return f"<w:p>{ppr}{''.join(runs)}</w:p>"


def _docx_table(rows: list[list[str]]) -> str:
    out = ['<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>']
    for r_i, row in enumerate(rows):
        out.append("<w:tr>")
        for cell in row:
            out.append(f"<w:tc>{_docx_par(f'**{cell}**' if r_i == 0 and cell else cell)}</w:tc>")
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def write_docx(path: str | Path, markdown: str, *, title: str = "", author: str = "", date: str = "") -> None:
    body = []
    for kind, payload in parse_markdown(markdown):
        if kind in ("h1", "h2", "h3"):
            body.append(_docx_par(str(payload), f"Heading{kind[1]}"))
        elif kind == "bullet":
            body.append(_docx_par(str(payload), "ListParagraph", "• "))
        elif kind == "number":
            body.append(_docx_par(str(payload), "ListParagraph"))
        elif kind == "table":
            body.append(_docx_table(payload))  # type: ignore[arg-type]
        else:
            body.append(_docx_par(str(payload)))
    document = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document {_W}><w:body>'
        + "".join(body)
        + '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:body></w:document>'
    )
    styles = (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:styles {_W}>'
        + "".join(
            f'<w:style w:type="paragraph" w:styleId="Heading{n}"><w:name w:val="heading {n}"/>'
            f'<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="{36 - 4 * n}"/></w:rPr></w:style>'
            for n in (1, 2, 3)
        )
        + '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
        + '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
        + '<w:pPr><w:ind w:left="720"/></w:pPr></w:style>'
        + '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/></w:style>'
        + "</w:styles>"
    )
    files = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            "</Relationships>"
        ),
        "word/_rels/document.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"
        ),
        "word/document.xml": document,
        "word/styles.xml": styles,
        "docProps/core.xml": _core_props(title, author, date),
    }
    _write_zip(Path(path), files)


# ---------------------------------------------------------------- xlsx
def _col(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _xlsx_cell(ref: str, v: object) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, dict) and "f" in v:
        cached = v.get("v")
        val = "" if cached is None else (
            f"<v>{cached}</v>" if isinstance(cached, (int, float)) else f"<v>{escape(str(cached))}</v>"
        )
        t = "" if cached is None or isinstance(cached, (int, float)) else ' t="str"'
        return f'<c r="{ref}"{t}><f>{escape(str(v["f"]).lstrip("="))}</f>{val}</c>'
    if isinstance(v, bool):
        return f'<c r="{ref}" t="b"><v>{int(v)}</v></c>'
    if isinstance(v, (int, float)):
        return f'<c r="{ref}"><v>{v}</v></c>'
    s = str(v)
    if s.startswith("="):
        return f'<c r="{ref}"><f>{escape(s[1:])}</f></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(s)}</t></is></c>'


def write_xlsx(path: str | Path, sheets: dict[str, list[list[object]]], *, author: str = "", date: str = "", title: str = "") -> None:
    names = list(sheets)
    files: dict[str, str] = {}
    for i, name in enumerate(names, 1):
        rows_xml = []
        for r, row in enumerate(sheets[name], 1):
            cells = "".join(_xlsx_cell(f"{_col(c)}{r}", v) for c, v in enumerate(row))
            rows_xml.append(f'<row r="{r}">{cells}</row>')
        files[f"xl/worksheets/sheet{i}.xml"] = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f"<sheetData>{''.join(rows_xml)}</sheetData></worksheet>"
        )
    files["xl/workbook.xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
        + "".join(
            f'<sheet name="{escape(n[:31])}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1)
        )
        + "</sheets></workbook>"
    )
    files["xl/_rels/workbook.xml.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(names) + 1)
        )
        + "</Relationships>"
    )
    files["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(names) + 1)
        )
        + '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        "</Types>"
    )
    files["_rels/.rels"] = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        "</Relationships>"
    )
    files["docProps/core.xml"] = _core_props(title, author, date)
    _write_zip(Path(path), files)


# ---------------------------------------------------------------- pdf
def _pdf_escape(s: str) -> str:
    s = s.encode("cp1252", "replace").decode("cp1252")
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, width: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def write_pdf(path: str | Path, markdown: str, *, title: str = "") -> None:
    """Write a simple multi-page text PDF (Helvetica, uncompressed streams)."""
    lines: list[tuple[str, int]] = []  # (text, font size)
    for kind, payload in parse_markdown(markdown):
        if kind in ("h1", "h2", "h3"):
            lines.append(("", 11))
            lines += [(t, {"h1": 16, "h2": 13, "h3": 12}[kind]) for t in _wrap(str(payload), 60)]
        elif kind == "table":
            for row in payload:  # type: ignore[union-attr]
                lines += [(t, 10) for t in _wrap("  |  ".join(row), 95)]
        elif kind == "bullet":
            lines += [(("• " if j == 0 else "  ") + t, 10) for j, t in enumerate(_wrap(str(payload).replace("**", ""), 92))]
        else:
            lines += [(t, 10) for t in _wrap(str(payload).replace("**", ""), 95)]
            lines.append(("", 10))
    pages: list[list[tuple[str, int]]] = [[]]
    y = 0
    for ln in lines:
        h = ln[1] + 4
        if y + h > 700:
            pages.append([])
            y = 0
        pages[-1].append(ln)
        y += h
    objs: list[str] = []
    n_pages = len(pages)
    font_id = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objs.append("<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>")
    for i, page in enumerate(pages):
        content = ["BT", "/F1 10 Tf", "72 760 Td"]
        prev = 0
        for text, size in page:
            content.append(f"0 {-(prev or size) - 4} Td /F1 {size} Tf ({_pdf_escape(text)}) Tj")
            prev = size
        content.append("ET")
        stream = "\n".join(content)
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {4 + 2 * i} 0 R >>"
        )
        objs.append(f"<< /Length {len(stream.encode('cp1252', 'replace'))} >>\nstream\n{stream}\nendstream")
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    info_id = len(objs) + 1
    objs.append(f"<< /Title ({_pdf_escape(title)}) /Producer (wcb) >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode("cp1252", "replace")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {info_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(bytes(out))


# ---------------------------------------------------------------- text extraction (for checks)
def extract_text(path: str | Path) -> str:
    """Best-effort plain text of an artifact file, for consistency checks."""
    p = Path(path)
    suf = p.suffix.lower()
    if suf in (".docx", ".xlsx", ".pptx"):
        chunks = []
        with zipfile.ZipFile(p) as z:
            for name in sorted(z.namelist()):
                if name.endswith(".xml") and ("word/document" in name or "worksheets/" in name or "slides/" in name or "sharedStrings" in name):
                    xml = z.read(name).decode("utf-8", "replace")
                    xml = re.sub(r"</(w:p|row|a:p)>", "\n", xml)
                    chunks.append(re.sub(r"<[^>]+>", " ", xml))
        text = "\n".join(chunks)
        return re.sub(r"[ \t]+", " ", text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))
    if suf == ".pdf":
        data = p.read_bytes().decode("cp1252", "replace")
        parts = re.findall(r"\((.*?)(?<!\\)\)\s*Tj", data)
        return "\n".join(s.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\") for s in parts)
    return p.read_text(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m wcb.render.office")
    ap.add_argument("kind", choices=["docx", "xlsx", "pdf"])
    ap.add_argument("source")
    ap.add_argument("out")
    ap.add_argument("--title", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--date", default="")
    a = ap.parse_args(argv)
    src = Path(a.source).read_text(encoding="utf-8")
    if a.kind == "docx":
        write_docx(a.out, src, title=a.title, author=a.author, date=a.date)
    elif a.kind == "pdf":
        write_pdf(a.out, src, title=a.title)
    else:
        write_xlsx(a.out, json.loads(src), author=a.author, date=a.date, title=a.title)
    print(a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
