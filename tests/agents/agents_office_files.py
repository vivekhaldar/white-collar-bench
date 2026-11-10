"""Tiny Office files built with zipfile, for the agents tests (imported as a plain module)."""

from __future__ import annotations

import zipfile
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def make_zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return path


def make_docx(path: Path) -> Path:
    """A Word file with a heading, a list item, a paragraph with a tab and break, and a table."""
    body = (
        f'<w:document xmlns:w="{W_NS}"><w:body>'
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Vendor review</w:t></w:r></w:p>'
        '<w:p><w:r><w:t xml:space="preserve">Decision: </w:t></w:r>'
        "<w:r><w:rPr><w:b/></w:rPr><w:t>go with option 2</w:t></w:r><w:r><w:tab/>"
        "<w:t>[owner]</w:t><w:br/><w:t>second line</w:t></w:r></w:p>"
        '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/></w:numPr></w:pPr>'
        "<w:r><w:t>Send pricing by 2027-03-05</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>Cost</w:t></w:r></w:p></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>Hosting</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>1200</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
        "<w:p><w:r><w:t>After the table</w:t></w:r><w:r><w:delText>deleted</w:delText></w:r></w:p>"
        "</w:body></w:document>"
    )
    return make_zip(path, {"word/document.xml": body})


def make_xlsx(path: Path) -> Path:
    """Two sheets: shared, inline, numeric, boolean, formula and date-formatted cells."""
    workbook = (
        f'<workbook xmlns="{S_NS}" xmlns:r="{R_NS}"><sheets>'
        '<sheet name="Budget" sheetId="1" r:id="rId1"/>'
        '<sheet name="Dates" sheetId="2" r:id="rId2"/>'
        "</sheets></workbook>"
    )
    rels = (
        f'<Relationships xmlns="{REL_NS}">'
        '<Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="x" Target="/xl/worksheets/sheet2.xml"/>'
        "</Relationships>"
    )
    shared = f'<sst xmlns="{S_NS}"><si><t>Line item</t></si><si><r><t>Amo</t></r><r><t>unt</t></r></si></sst>'
    styles = (
        f'<styleSheet xmlns="{S_NS}"><numFmts><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd"/>'
        '</numFmts><cellXfs><xf numFmtId="0"/><xf numFmtId="164"/><xf numFmtId="14"/></cellXfs>'
        "</styleSheet>"
    )
    sheet1 = (
        f'<worksheet xmlns="{S_NS}"><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>Hosting</t></is></c><c r="B2"><v>1200</v></c></row>'
        '<row r="3"><c r="A3" t="inlineStr"><is><t>Total</t></is></c>'
        '<c r="C3"><f>SUM(B2:B2)</f><v>1200.5</v></c><c r="D3" t="b"><v>1</v></c></row>'
        "</sheetData></worksheet>"
    )
    sheet2 = (
        f'<worksheet xmlns="{S_NS}"><sheetData>'
        '<row r="1"><c r="A1" t="inlineStr"><is><t>Due</t></is></c><c r="B1" s="1"><v>46447</v></c>'
        '<c r="C1" s="2"><v>46448.5</v></c><c r="D1" t="str"><f>A1</f><v>Due</v></c></row>'
        "</sheetData></worksheet>"
    )
    return make_zip(
        path,
        {
            "xl/workbook.xml": workbook,
            "xl/_rels/workbook.xml.rels": rels,
            "xl/sharedStrings.xml": shared,
            "xl/styles.xml": styles,
            "xl/worksheets/sheet1.xml": sheet1,
            "xl/worksheets/sheet2.xml": sheet2,
        },
    )


def make_pptx(path: Path) -> Path:
    def slide(*paras: str) -> str:
        ps = "".join(f"<a:p><a:r><a:t>{t}</a:t></a:r></a:p>" for t in paras)
        return f'<p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}"><p:cSld><p:spTree><p:sp><p:txBody>{ps}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>'

    pres = (
        f'<p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}"><p:sldIdLst>'
        '<p:sldId id="256" r:id="rId2"/><p:sldId id="257" r:id="rId1"/></p:sldIdLst></p:presentation>'
    )
    rels = (
        f'<Relationships xmlns="{REL_NS}">'
        '<Relationship Id="rId1" Type="x" Target="slides/slide1.xml"/>'
        '<Relationship Id="rId2" Type="x" Target="slides/slide2.xml"/></Relationships>'
    )
    return make_zip(
        path,
        {
            "ppt/presentation.xml": pres,
            "ppt/_rels/presentation.xml.rels": rels,
            "ppt/slides/slide1.xml": slide("Second slide title", "Roadmap"),
            "ppt/slides/slide2.xml": slide("First slide title"),
        },
    )
