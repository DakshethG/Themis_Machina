"""Parse Indian bare-act PDFs (indiacode format) into structured sections.

indiacode layout: front-matter "ARRANGEMENT OF SECTIONS" (a TOC listing every
section as a short one-liner), then the body where each section reads
`N. Heading.— <full text>`. The em-dash separator is NOT universal across acts,
so we detect sections by line-start `N.` markers and disambiguate TOC-vs-body by
keeping the longest text per section number. If the result looks wrong
(too few sections, or one giant blob), we fall back to page-based chunking and
flag it via ParsedStatute.parse_mode.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import fitz  # PyMuPDF
from pydantic import BaseModel

from themis.config import get_settings
from themis.schemas import StatuteSection

# A section starts at line-start with a number, optional letter suffix (2A), then "."
_SECTION_RE = re.compile(r"(?m)^[ \t]*(\d{1,4}[A-Z]{0,3})\.[ \t—\-]")
# Footnotes (page-bottom amendment notes) also match _SECTION_RE; their body begins
# with an amendment-citation lead-in. Used to reject them as section starts.
_FOOTNOTE_LEAD = re.compile(
    r"^\s*(Subs|Ins|Omitted|Omit|Added|Add|Rep|Substituted|Inserted|The words?|"
    r"The figures?|The brackets?|Certain words|Cl\.|Clause|Now|See|Vide|Earlier|"
    r"Prior|w\.e\.f)\b", re.I)
# Subsection markers like "(1)", "(2A)".
_SUBSEC_RE = re.compile(r"(?m)^[ \t]*\((\d{1,3}[A-Z]?)\)")

MIN_SECTIONS = 3          # fewer than this => parse looks broken
MAX_GIANT_FRACTION = 0.7  # one section >70% of chars => parse looks broken
MAX_SECTION_NUM = 700     # no Indian act exceeds this; rejects years / page numbers
MAX_SECTION_GAP = 60      # a single jump larger than this is spurious (year, cross-ref)


class ParsedStatute(BaseModel):
    statute_key: str
    statute_title: str
    parse_mode: str  # "sections" | "page_fallback"
    sections: list[StatuteSection]
    n_sections: int


def load_manifest() -> dict[str, dict]:
    path = get_settings().corpus_statutes_dir / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_pages(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    try:
        return [page.get_text("text") for page in doc]
    finally:
        doc.close()


def _split_heading_body(block: str) -> tuple[str, str]:
    """Given text after 'N.', separate heading from body."""
    # Prefer an em-dash separator if present early in the block.
    m = re.search(r"—|—", block[:200])
    if m:
        return block[:m.start()].strip(), block[m.end():].strip()
    # Otherwise: heading is up to the first sentence-ending period or newline.
    nl = block.find("\n")
    dot = block.find(". ")
    cut = min(x for x in (nl, dot) if x != -1) if (nl != -1 or dot != -1) else len(block)
    cut = min(cut, 120)
    return block[:cut].strip(" .").strip(), block[cut:].strip()


def _numval(num: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([A-Z]*)", num)
    return (int(m.group(1)), m.group(2)) if m else (10**9, num)


def _find_body_start(full: str, markers: list[re.Match]) -> int:
    """Return the char offset where the body (real sections) begins, skipping the
    front-matter 'ARRANGEMENT OF SECTIONS' TOC."""
    # Preferred signal: the enacting formula precedes the body in most acts.
    low = full.lower()
    for kw in ("be it enacted", "hereby enacted", "it is hereby enacted"):
        idx = low.find(kw)
        if 0 <= idx < len(full) * 0.5:
            return idx
    # Fallback: the TOC is an increasing run 1..N; the body restarts to a low
    # number. Take the first such restart after climbing past a high section.
    climbed = False
    for i in range(1, len(markers)):
        v = _numval(markers[i].group(1))[0]
        prev = _numval(markers[i - 1].group(1))[0]
        if prev >= 8:
            climbed = True
        if climbed and v <= 3 and v < prev:
            return markers[i].start()
    return 0


def _parse_sections(full_text: str, key: str, title: str) -> list[StatuteSection]:
    markers = list(_SECTION_RE.finditer(full_text))
    if not markers:
        return []

    body_start = _find_body_start(full_text, markers)
    body_markers = [m for m in markers if m.start() >= body_start]

    # Walk markers in document order; accept only strictly increasing section
    # numbers. Footnotes reset to low numbers each page and get rejected, as do
    # cross-references. Each section spans up to the next ACCEPTED marker so the
    # full body (including any interleaved footnotes) is captured.
    accepted: list[tuple[str, int, int]] = []  # (num, text_start, marker_start)
    current = (0, "")
    for m in body_markers:
        num = m.group(1)
        following = full_text[m.end():m.end() + 60]
        if _FOOTNOTE_LEAD.match(following):
            continue
        val = _numval(num)
        if val[0] > MAX_SECTION_NUM:      # year / page number / OCR noise
            continue
        if val <= current:                # footnote reset or cross-reference
            continue
        if val[0] - current[0] > MAX_SECTION_GAP:  # wild jump — skip, keep scanning
            continue
        accepted.append((num, m.end(), m.start()))
        current = val

    sections: list[StatuteSection] = []
    for i, (num, tstart, _) in enumerate(accepted):
        tend = accepted[i + 1][2] if i + 1 < len(accepted) else len(full_text)
        block = full_text[tstart:tend]
        heading, body = _split_heading_body(block)
        body = re.sub(r"[ \t]+", " ", body).strip()
        if len(body) < 10 and len(heading) < 5:
            continue
        subs = _SUBSEC_RE.findall(block)
        is_def = "definition" in heading.lower()
        sections.append(StatuteSection(
            statute_key=key, statute_title=title, section_number=num,
            section_heading=heading, text=body,
            subsections=[f"({s})" for s in subs], is_definitions=is_def,
        ))
    return sections


def _looks_broken(sections: list[StatuteSection]) -> bool:
    if len(sections) < MIN_SECTIONS:
        return True
    total = sum(s.char_count if hasattr(s, "char_count") else len(s.text) for s in sections)
    if total == 0:
        return True
    biggest = max(len(s.text) for s in sections)
    return biggest / total > MAX_GIANT_FRACTION


def _page_fallback(pages: list[str], key: str, title: str) -> list[StatuteSection]:
    sections = []
    for i, txt in enumerate(pages, 1):
        txt = re.sub(r"[ \t]+", " ", txt).strip()
        if not txt:
            continue
        sections.append(StatuteSection(
            statute_key=key, statute_title=title, section_number=f"p{i}",
            section_heading=f"Page {i}", text=txt,
        ))
    return sections


def parse_statute(pdf_path: Path, statute_key: str, statute_title: str) -> ParsedStatute:
    pages = _extract_pages(pdf_path)
    full = "\n".join(pages)
    sections = _parse_sections(full, statute_key, statute_title)
    if _looks_broken(sections):
        sections = _page_fallback(pages, statute_key, statute_title)
        mode = "page_fallback"
    else:
        mode = "sections"
    return ParsedStatute(
        statute_key=statute_key, statute_title=statute_title, parse_mode=mode,
        sections=sections, n_sections=len(sections),
    )


def parse_from_manifest(statute_key: str) -> ParsedStatute:
    manifest = load_manifest()
    entry = manifest[statute_key]
    pdf_path = get_settings().corpus_statutes_dir / entry["filename"]
    return parse_statute(pdf_path, statute_key, entry["title"])
