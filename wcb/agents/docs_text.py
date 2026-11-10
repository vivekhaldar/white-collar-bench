"""Plain-text extraction for the input formats an agent meets in ``inbox/<date>/``.

Used by the simple harness's ``read_document`` and ``search`` tools (:mod:`wcb.agents.tools`), and
reusable by any custom agent::

    from wcb.agents.docs_text import extract_text
    print(extract_text("inbox/2027-03-01/dc-0007.docx"))

Everything here is standard library only and deliberately best-effort: the aim is text a model
can read, not a faithful rendering.

========  =====================================================================================
Suffix    What you get
========  =====================================================================================
.docx     Paragraphs in order; headings as ``#``; list items as ``-``; tables as ``a | b`` rows.
.xlsx     One ``## Sheet: <name>`` section per sheet; one ``<row>: a | b | c`` line per row.
          Shared, inline and formula strings are resolved; date-formatted cells become ISO dates.
.pptx     One ``## Slide N`` section per slide with its text frames.
.pdf      Text drawn by ``Tj``/``TJ``/``'``/``"`` operators in (optionally Flate-compressed)
          content streams, one line per text line. Scanned or CID-font PDFs yield little or none.
.eml      Key headers, the plain-text body (HTML stripped as a fallback) and a list of
          attachments.
.ics      The calendar text with folded lines unfolded.
other     The file decoded as UTF-8 (invalid bytes replaced). Binary files raise
          :class:`DocumentError`.
========  =====================================================================================
"""

from __future__ import annotations

import datetime as dt
import email
import email.policy
import html
import posixpath
import re
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

OFFICE_SUFFIXES = frozenset({".docx", ".xlsx", ".xlsm", ".pptx"})
DOCUMENT_SUFFIXES = OFFICE_SUFFIXES | {".pdf", ".eml", ".ics"}
"""Suffixes with a dedicated extractor. Anything else is read as text."""

BINARY_SUFFIXES = OFFICE_SUFFIXES | {
    ".pdf", ".zip", ".gz", ".tgz", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".mp3", ".mp4", ".wav", ".mov", ".doc", ".xls", ".ppt", ".exe", ".bin", ".so", ".dylib",
}  # fmt: skip
"""Suffixes that are never shown raw by ``read_file``."""

MAX_MEMBER_BYTES = 64 * 1024 * 1024
"""Largest uncompressed archive member we are willing to read (guards against zip bombs)."""

_NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


class DocumentError(ValueError):
    """The file cannot be turned into text. The message says why and what to try instead."""


def extract_text(path: str | Path) -> str:
    """Return the readable text of ``path``, dispatching on its suffix (see the module docs).

    Raises :class:`DocumentError` for corrupt or unsupported binary files.
    """
    p = Path(path)
    suffix = p.suffix.lower()
    try:
        if suffix == ".docx":
            return docx_text(p)
        if suffix in (".xlsx", ".xlsm"):
            return xlsx_text(p)
        if suffix == ".pptx":
            return pptx_text(p)
        if suffix == ".pdf":
            return pdf_text(p.read_bytes())
        if suffix == ".eml":
            return eml_text(p.read_bytes())
        if suffix == ".ics":
            return ics_text(p.read_text(encoding="utf-8", errors="replace"))
    except zipfile.BadZipFile as e:
        raise DocumentError(f"{p.name} is not a valid {suffix} file (bad zip archive: {e})") from e
    except ET.ParseError as e:
        raise DocumentError(f"{p.name}: malformed XML inside the document ({e})") from e
    data = p.read_bytes()
    if suffix in BINARY_SUFFIXES or b"\x00" in data[:8192]:
        raise DocumentError(
            f"{p.name} is a binary file in a format without a text extractor "
            f"(supported documents: {', '.join(sorted(DOCUMENT_SUFFIXES))})"
        )
    return data.decode("utf-8", errors="replace")


# ====================================================================== zip helpers
def _read_member(z: zipfile.ZipFile, name: str) -> bytes | None:
    try:
        info = z.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_MEMBER_BYTES:
        raise DocumentError(
            f"archive member {name} is too large to extract ({info.file_size} bytes)"
        )
    return z.read(info)


def _xml(z: zipfile.ZipFile, name: str) -> ET.Element | None:
    data = _read_member(z, name)
    return None if data is None else ET.fromstring(data)


def _rels(z: zipfile.ZipFile, part: str) -> dict[str, str]:
    """Relationship ID -> target part name (resolved relative to ``part``'s directory)."""
    folder, base = posixpath.split(part)
    root = _xml(z, posixpath.join(folder, "_rels", base + ".rels"))
    out: dict[str, str] = {}
    if root is None:
        return out
    for rel in root.findall("rel:Relationship", _NS):
        target = rel.get("Target", "")
        if rel.get("TargetMode") == "External":
            continue
        if target.startswith("/"):
            resolved = target.lstrip("/")
        else:
            resolved = posixpath.normpath(posixpath.join(folder, target))
        out[rel.get("Id", "")] = resolved
    return out


def _q(prefix: str, tag: str) -> str:
    return f"{{{_NS[prefix]}}}{tag}"


# ====================================================================== docx
def docx_text(path: str | Path) -> str:
    """Text of a Word document: body paragraphs and tables, in document order."""
    with zipfile.ZipFile(path) as z:
        root = _xml(z, "word/document.xml")
        if root is None:
            raise DocumentError(
                f"{Path(path).name} has no word/document.xml; is it really a .docx?"
            )
        body = root.find("w:body", _NS)
        lines: list[str] = []
        if body is not None:
            _docx_block(body, lines)
        for extra, label in (
            ("word/footnotes.xml", "Footnotes"),
            ("word/endnotes.xml", "Endnotes"),
        ):
            notes = _xml(z, extra)
            if notes is None:
                continue
            texts = [t for t in (_docx_par(p) for p in notes.iter(_q("w", "p"))) if t.strip()]
            if texts:
                lines += ["", f"## {label}", *texts]
    return _tidy("\n".join(lines))


def _docx_block(el: ET.Element, lines: list[str]) -> None:
    for child in el:
        if child.tag == _q("w", "p"):
            lines.append(_docx_par(child))
        elif child.tag == _q("w", "tbl"):
            for row in child.iter(_q("w", "tr")):
                cells = []
                for cell in row.findall("w:tc", _NS):
                    cells.append(" ".join(_docx_par(p) for p in cell.iter(_q("w", "p"))).strip())
                lines.append(" | ".join(cells))
            lines.append("")
        elif child.tag in (_q("w", "sdt"), _q("w", "sdtContent"), _q("w", "customXml")):
            _docx_block(child, lines)


def _docx_par(p: ET.Element) -> str:
    parts: list[str] = []
    for el in p.iter():
        if el.tag == _q("w", "t"):
            parts.append(el.text or "")
        elif el.tag == _q("w", "tab"):
            parts.append("\t")
        elif el.tag in (_q("w", "br"), _q("w", "cr")):
            parts.append("\n")
    text = "".join(parts)
    ppr = p.find("w:pPr", _NS)
    if ppr is not None and text.strip():
        style = ppr.find("w:pStyle", _NS)
        val = (style.get(_q("w", "val")) or "") if style is not None else ""
        m = re.match(r"(?i)heading\s*(\d)", val)
        if m:
            return "#" * min(int(m.group(1)), 6) + " " + text.strip()
        if val.lower() == "title":
            return "# " + text.strip()
        if ppr.find("w:numPr", _NS) is not None and not text.lstrip().startswith(("-", "•")):
            return "- " + text.strip()
    return text


# ====================================================================== xlsx
_BUILTIN_DATE_FORMATS = frozenset({14, 15, 16, 17, 18, 19, 20, 21, 22, 45, 46, 47})


def xlsx_text(path: str | Path) -> str:
    """Text of an Excel workbook: every sheet, every non-empty row."""
    with zipfile.ZipFile(path) as z:
        wb = _xml(z, "xl/workbook.xml")
        if wb is None:
            raise DocumentError(f"{Path(path).name} has no xl/workbook.xml; is it really a .xlsx?")
        rels = _rels(z, "xl/workbook.xml")
        pr = wb.find("s:workbookPr", _NS)
        date1904 = pr is not None and pr.get("date1904") in ("1", "true")
        shared = _shared_strings(z)
        date_styles = _date_styles(z)
        out: list[str] = []
        sheets = wb.find("s:sheets", _NS)
        for i, sheet in enumerate(sheets if sheets is not None else [], 1):
            name = sheet.get("name") or f"Sheet{i}"
            part = rels.get(sheet.get(_q("r", "id")) or "", f"xl/worksheets/sheet{i}.xml")
            root = _xml(z, part)
            out.append(f"## Sheet: {name}")
            if root is None:
                out.append("(sheet data not found)")
                continue
            rows = _sheet_rows(root, shared, date_styles, date1904)
            out += rows if rows else ["(empty)"]
            out.append("")
    return _tidy("\n".join(out))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    root = _xml(z, "xl/sharedStrings.xml")
    if root is None:
        return []
    out = []
    for si in root.findall("s:si", _NS):
        # Rich-text runs are <r><t>; phonetic hints (<rPh>) are skipped.
        texts = [t.text or "" for t in si.findall("s:t", _NS)]
        texts += [t.text or "" for r in si.findall("s:r", _NS) for t in r.findall("s:t", _NS)]
        out.append("".join(texts))
    return out


def _date_styles(z: zipfile.ZipFile) -> set[int]:
    """Indexes into cellXfs whose number format displays a date or time."""
    root = _xml(z, "xl/styles.xml")
    if root is None:
        return set()
    custom: dict[int, str] = {}
    fmts = root.find("s:numFmts", _NS)
    for f in fmts if fmts is not None else []:
        try:
            custom[int(f.get("numFmtId", "-1"))] = f.get("formatCode", "")
        except ValueError:
            pass
    out: set[int] = set()
    xfs = root.find("s:cellXfs", _NS)
    for idx, xf in enumerate(xfs if xfs is not None else []):
        try:
            fid = int(xf.get("numFmtId", "0"))
        except ValueError:
            continue
        if fid in _BUILTIN_DATE_FORMATS or (fid in custom and _is_date_format(custom[fid])):
            out.add(idx)
    return out


def _is_date_format(code: str) -> bool:
    code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", code)  # drop literals, colours, escapes
    return bool(re.search(r"[dmyhs]", code, re.I)) and not re.fullmatch(r"[#0.,%\s]*", code)


def _col_index(ref: str) -> int:
    n = 0
    for ch in ref:
        if not ch.isalpha():
            break
        n = n * 26 + (ord(ch.upper()) - 64)
    return max(n - 1, 0)


def _sheet_rows(
    root: ET.Element, shared: list[str], date_styles: set[int], date1904: bool
) -> list[str]:
    lines = []
    data = root.find("s:sheetData", _NS)
    for n, row in enumerate(data if data is not None else [], 1):
        cells: dict[int, str] = {}
        for pos, c in enumerate(row.findall("s:c", _NS)):
            ref = c.get("r") or ""
            col = _col_index(ref) if ref else pos
            value = _cell_value(c, shared, date_styles, date1904)
            if value != "":
                cells[col] = value
        if cells:
            width = max(cells) + 1
            label = row.get("r") or str(n)
            lines.append(f"{label}: " + " | ".join(cells.get(i, "") for i in range(width)))
    return lines


def _cell_value(c: ET.Element, shared: list[str], date_styles: set[int], date1904: bool) -> str:
    t = c.get("t", "n")
    v = c.find("s:v", _NS)
    raw = v.text if v is not None and v.text is not None else None
    if t == "inlineStr":
        is_ = c.find("s:is", _NS)
        return "".join(x.text or "" for x in is_.iter(_q("s", "t"))) if is_ is not None else ""
    if t == "s":
        try:
            return shared[int(raw or "")]
        except (ValueError, IndexError):
            return ""
    if t == "b":
        return "TRUE" if raw == "1" else "FALSE"
    if raw is None:
        f = c.find("s:f", _NS)
        return f"={f.text}" if f is not None and f.text else ""
    if t in ("str", "e"):
        return raw
    try:
        num = float(raw)
    except ValueError:
        return raw
    try:
        style = int(c.get("s", "-1"))
    except ValueError:
        style = -1
    if style in date_styles:
        return _excel_date(num, date1904)
    return str(int(num)) if num.is_integer() and abs(num) < 1e15 else repr(num)


def _excel_date(serial: float, date1904: bool) -> str:
    base = dt.datetime(1904, 1, 1) if date1904 else dt.datetime(1899, 12, 30)
    try:
        when = base + dt.timedelta(days=serial)
    except OverflowError:
        return repr(serial)
    if serial == int(serial):
        return when.date().isoformat()
    if serial < 1:
        return when.time().isoformat(timespec="minutes")
    return when.isoformat(sep=" ", timespec="minutes")


# ====================================================================== pptx
def pptx_text(path: str | Path) -> str:
    """Text of a PowerPoint deck: each slide's text frames, in slide order."""
    with zipfile.ZipFile(path) as z:
        order: list[str] = []
        pres = _xml(z, "ppt/presentation.xml")
        if pres is not None:
            rels = _rels(z, "ppt/presentation.xml")
            ids = pres.find("p:sldIdLst", _NS)
            for sid in ids if ids is not None else []:
                target = rels.get(sid.get(_q("r", "id")) or "")
                if target:
                    order.append(target)
        if not order:
            names = [n for n in z.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
            order = sorted(names, key=lambda n: int(re.findall(r"\d+", n)[-1]))
        out = []
        for i, part in enumerate(order, 1):
            root = _xml(z, part)
            out.append(f"## Slide {i}")
            if root is not None:
                for para in root.iter(_q("a", "p")):
                    text = "".join(t.text or "" for t in para.iter(_q("a", "t")))
                    if text.strip():
                        out.append(text)
            out.append("")
    return _tidy("\n".join(out))


# ====================================================================== pdf
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\n?endstream", re.S)
_SKIP_STREAM = re.compile(
    rb"/Subtype\s*/Image|/FontFile|/Length[123]\b|/Type\s*/XRef|/Type\s*/ObjStm"
)
_PDF_TOKEN = re.compile(
    rb"\((?:\\.|[^\\()]|\((?:\\.|[^\\()])*\))*\)"  # literal string (one level of nesting)
    rb"|<[0-9A-Fa-f\s]*>"  # hex string
    rb"|\[|\]"
    rb"|/[^\s/\[\]()<>{}%]+"  # name
    rb"|[-+]?(?:\d+\.?\d*|\.\d+)"  # number
    rb"|[A-Za-z'\"*]+"  # operator
)


def pdf_text(data: bytes) -> str:
    """Best-effort text of a PDF: the strings shown by text operators, one line per text line.

    Handles uncompressed and Flate-compressed content streams with single-byte (WinAnsi-like)
    fonts, which covers PDFs written by simple generators. Anything else yields what it can.
    """
    if not data.startswith(b"%PDF"):
        raise DocumentError("not a PDF file (missing %PDF header)")
    chunks: list[str] = []
    for m in _STREAM.finditer(data):
        head = data[max(0, m.start() - 400) : m.start()]
        head = head[head.rfind(b"<<") :] if b"<<" in head else head
        if _SKIP_STREAM.search(head):
            continue
        body = m.group(1)
        if b"FlateDecode" in head:
            try:
                body = zlib.decompressobj().decompress(body)
            except zlib.error:
                continue
        if b"BT" not in body:
            continue
        text = _pdf_stream_text(body)
        if text.strip():
            chunks.append(text)
    if not chunks:
        return (
            "[no extractable text found in this PDF; it may be scanned or use embedded CID fonts]"
        )
    return _tidy("\n\n".join(chunks))


def _pdf_stream_text(stream: bytes) -> str:
    lines: list[str] = []
    cur: list[str] = []
    operands: list[bytes | list[bytes]] = []
    array: list[bytes] | None = None

    def newline() -> None:
        lines.append("".join(cur))
        cur.clear()

    def last_string() -> str | None:
        if operands and isinstance(operands[-1], bytes) and operands[-1][:1] in (b"(", b"<"):
            return _pdf_string(operands[-1])
        return None

    for tok in _PDF_TOKEN.findall(stream):
        if tok == b"[":
            array = []
            continue
        if tok == b"]":
            operands.append(array or [])
            array = None
            continue
        if array is not None:
            array.append(tok)
            continue
        if tok[:1] in (b"(", b"<", b"/") or re.fullmatch(rb"[-+]?[\d.]+", tok):
            operands.append(tok)
            continue
        op = tok
        if op == b"Tj":
            s = last_string()
            if s is not None:
                cur.append(s)
        elif op == b"TJ" and operands and isinstance(operands[-1], list):
            for part in operands[-1]:
                if part[:1] in (b"(", b"<"):
                    cur.append(_pdf_string(part))
                elif _number(part) < -200:  # a large negative kern is a word gap
                    cur.append(" ")
        elif op in (b"'", b'"'):
            newline()
            s = last_string()
            if s is not None:
                cur.append(s)
        elif op in (b"Td", b"TD") and len(operands) >= 2:
            dx, dy = _number(operands[-2]), _number(operands[-1])
            if dy != 0:
                newline()
            elif dx > 0 and cur and not cur[-1].endswith(" "):
                cur.append(" ")
        elif op in (b"T*", b"ET", b"Tm") and cur:
            newline()
        operands = []
    if cur:
        newline()
    return "\n".join(line.rstrip() for line in lines if line.strip())


def _number(tok: bytes | list[bytes]) -> float:
    try:
        return float(tok) if isinstance(tok, bytes) else 0.0
    except ValueError:
        return 0.0


_PDF_ESCAPES = {b"n": "\n", b"r": "\r", b"t": "\t", b"b": "\b", b"f": "\f"}


def _pdf_string(tok: bytes) -> str:
    if tok.startswith(b"<"):
        hexs = re.sub(rb"\s", b"", tok[1:-1])
        if len(hexs) % 2:
            hexs += b"0"
        raw = bytes.fromhex(hexs.decode("ascii"))
    else:
        raw = _pdf_unescape(tok[1:-1])
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    return raw.decode("cp1252", errors="replace")


def _pdf_unescape(s: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(s):
        ch = s[i : i + 1]
        if ch != b"\\":
            out += ch
            i += 1
            continue
        nxt = s[i + 1 : i + 2]
        if nxt in _PDF_ESCAPES:
            out += _PDF_ESCAPES[nxt].encode()
            i += 2
        elif nxt in (b"\n", b"\r"):  # line continuation
            i += 2
            if nxt == b"\r" and s[i : i + 1] == b"\n":
                i += 1
        elif nxt.isdigit():
            m = re.match(rb"[0-7]{1,3}", s[i + 1 : i + 4])
            digits = m.group(0) if m else b"0"
            out.append(int(digits, 8) & 0xFF)
            i += 1 + len(digits)
        else:  # \( \) \\ and unknown escapes: the character itself
            out += nxt
            i += 2
    return bytes(out)


# ====================================================================== eml
_EML_HEADERS = (
    "From", "To", "Cc", "Bcc", "Reply-To", "Date", "Subject", "Message-ID", "In-Reply-To",
    "References", "X-Draft",
)  # fmt: skip


def eml_text(data: bytes) -> str:
    """Headers, plain-text body and attachment list of an RFC 5322 email."""
    msg = email.message_from_bytes(data, policy=email.policy.default)
    lines = [f"{h}: {msg[h]}" for h in _EML_HEADERS if msg[h] is not None]
    plain: list[str] = []
    htmls: list[str] = []
    attachments: list[str] = []
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.is_multipart():
            continue
        ctype = part.get_content_type()
        filename = part.get_filename()
        if filename or part.get_content_disposition() == "attachment":
            attachments.append(f"{filename or '(unnamed)'} ({ctype})")
            continue
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            content = part.get_content()
        except (LookupError, ValueError):
            payload = part.get_payload(decode=True) or b""
            content = payload.decode("utf-8", errors="replace")
        (plain if ctype == "text/plain" else htmls).append(str(content))
    body = "\n\n".join(plain) if plain else "\n\n".join(_strip_html(h) for h in htmls)
    lines += ["", body.strip()]
    if attachments:
        lines += ["", "Attachments: " + "; ".join(attachments)]
    return _tidy("\n".join(lines))


def _strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d)>", "\n", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


# ====================================================================== ics
def ics_text(text: str) -> str:
    """Calendar text with RFC 5545 folded lines joined back together."""
    return re.sub(r"\r?\n[ \t]", "", text).replace("\r\n", "\n")


# ====================================================================== helpers
def _tidy(text: str) -> str:
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
