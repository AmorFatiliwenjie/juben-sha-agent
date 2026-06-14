from __future__ import annotations

import html
import re
import zipfile
from pathlib import Path
from typing import Iterable


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def xml_escape(value: str) -> str:
    return html.escape(str(value), quote=False)


def run_xml(text: str, *, bold: bool = False, color: str | None = None, size: int | None = None) -> str:
    props = [
        '<w:rFonts w:ascii="宋体" w:hAnsi="宋体" w:eastAsia="宋体"/>',
    ]
    if bold:
        props.append("<w:b/>")
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    if size:
        props.append(f'<w:sz w:val="{size}"/>')
    rpr = f"<w:rPr>{''.join(props)}</w:rPr>"
    space = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
    return f"<w:r>{rpr}<w:t{space}>{xml_escape(text)}</w:t></w:r>"


def paragraph_xml(
    text: str = "",
    *,
    heading: int | None = None,
    bold: bool = False,
    color: str | None = None,
    first_line_indent: bool = True,
) -> str:
    size = None
    if heading == 1:
        size = 32
        bold = True
        first_line_indent = False
    elif heading == 2:
        size = 28
        bold = True
        first_line_indent = False
    elif heading == 3:
        size = 24
        bold = True
        first_line_indent = False

    ppr_parts = []
    if first_line_indent and text.strip():
        ppr_parts.append('<w:ind w:firstLine="420"/>')
    if heading:
        ppr_parts.append('<w:spacing w:before="160" w:after="120"/>')
    ppr = f"<w:pPr>{''.join(ppr_parts)}</w:pPr>" if ppr_parts else ""
    return f"<w:p>{ppr}{run_xml(text, bold=bold, color=color, size=size)}</w:p>"


def rich_paragraph_xml(parts: Iterable[tuple[str, bool, str | None]], *, first_line_indent: bool = True) -> str:
    ppr = '<w:pPr><w:ind w:firstLine="420"/></w:pPr>' if first_line_indent else ""
    runs = "".join(run_xml(text, bold=bold, color=color) for text, bold, color in parts if text)
    return f"<w:p>{ppr}{runs}</w:p>"


def table_xml(rows: list[list[str | tuple[str, str]]]) -> str:
    cells = []
    for row_index, row in enumerate(rows):
        row_cells = []
        for cell in row:
            if isinstance(cell, tuple):
                text, color = cell
                content = rich_paragraph_xml([(text, row_index == 0, color)], first_line_indent=False)
            else:
                content = paragraph_xml(str(cell), bold=row_index == 0, first_line_indent=False)
            row_cells.append(
                "<w:tc>"
                '<w:tcPr><w:tcW w:w="2400" w:type="dxa"/></w:tcPr>'
                f"{content}"
                "</w:tc>"
            )
        cells.append(f"<w:tr>{''.join(row_cells)}</w:tr>")
    borders = (
        "<w:tblPr>"
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/>'
        "</w:tblBorders>"
        "</w:tblPr>"
    )
    return f"<w:tbl>{borders}{''.join(cells)}</w:tbl>"


def markdown_to_docx_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    for raw_line in markdown.replace("\r\n", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            blocks.append(paragraph_xml("", first_line_indent=False))
            continue
        if line.startswith("### "):
            blocks.append(paragraph_xml(line[4:].strip(), heading=3))
        elif line.startswith("## "):
            blocks.append(paragraph_xml(line[3:].strip(), heading=2))
        elif line.startswith("# "):
            blocks.append(paragraph_xml(line[2:].strip(), heading=1))
        elif line.startswith(("- ", "* ")):
            blocks.append(paragraph_xml(f"· {line[2:].strip()}", first_line_indent=False))
        else:
            blocks.append(markdown_inline_to_paragraph(line))
    return blocks


def markdown_inline_to_paragraph(line: str) -> str:
    parts: list[tuple[str, bool, str | None]] = []
    pos = 0
    for match in re.finditer(r"\*\*(.+?)\*\*", line):
        if match.start() > pos:
            parts.append((line[pos : match.start()], False, None))
        parts.append((match.group(1), True, None))
        pos = match.end()
    if pos < len(line):
        parts.append((line[pos:], False, None))
    return rich_paragraph_xml(parts or [(line, False, None)])


def write_docx(path: Path, blocks: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}">'
        "<w:body>"
        + "".join(blocks)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
        + "</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)
