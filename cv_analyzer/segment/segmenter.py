"""Section segmentation: heading heuristics first (EN + ID), line reassignment second.

Outputs ``CVDocument`` with canonical segments (summary/education/experience/
skills/other). The NLP upgrade of this stage is deferred (blueprint §6) — the
heading heuristics are the rules baseline the harness will measure against.
"""
from __future__ import annotations

import re

from cv_analyzer.models import Bullet, CVDocument, Segment
from cv_analyzer.utils.gazetteer_loader import load_gazetteer

SECTION_ALIASES = {"SUMMARY": "summary", "EXPERIENCE": "experience", "EDUCATION": "education", "SKILLS": "skills"}
_ORDER = ["summary", "experience", "education", "skills"]
_LINE_MARKERS = load_gazetteer("heading_markers")

_UNORDERED_ALIASES = {v: k for k, v in SECTION_ALIASES.items()}


def _find_heading(line: str) -> str | None:
    """Return the canonical section for a heading line, else None.

    A heading is: 1-4 words, short, no terminal period, no digits, matches
    the gazetteer (normalized: lowercase, punctuation-stripped).
    """
    stripped = line.strip().rstrip(":")
    if not stripped or len(stripped) > 40 or "\t" in line:
        return None
    if stripped.endswith((".", "!", "?", ",")):
        return None
    if re.search(r"\d", stripped):
        return None
    words = stripped.split()
    if not 1 <= len(words) <= 4:
        return None

    normalized = re.sub(r"[^\w\s/&]", "", stripped.lower()).strip()
    for section_key, names in _LINE_MARKERS["en"]["section_names"].items():
        for name in names:
            if normalized == name.lower():
                return SECTION_ALIASES.get(section_key)
    for section_key, names in _LINE_MARKERS["id"]["section_names"].items():
        for name in names:
            if normalized == name.lower():
                return SECTION_ALIASES.get(section_key)
    # English plural variants ("Experiences") / possessive ("Work Experience:")
    for section_key, names in _LINE_MARKERS["en"]["section_names"].items():
        for name in names:
            if normalized == (name.lower() + "s") or normalized == (name.lower() + "es"):
                return SECTION_ALIASES.get(section_key)
    return None


def _looks_like_heading(line: str) -> bool:
    stripped = line.strip().rstrip(":")
    if not stripped or len(stripped) > 40:
        return False
    words = stripped.split()
    if not 1 <= len(words) <= 4 or re.search(r"\d", stripped):
        return False
    normalized = re.sub(r"[^\w\s/&]", "", stripped.lower()).strip()
    return normalized in {
        name.lower()
        for section in _LINE_MARKERS.values()
        for names in section["section_names"].values()
        for name in names
    }


def _bullet_line(line: str) -> bool:
    s = line.lstrip()
    return bool(re.match(r"(?:[-•▪◦*·•›>+]|\d+[.)])\s+\S", s))


def segment_document(text: str, source_name: str = "doc") -> CVDocument:
    """Segment ``text`` into canonical sections.

    Unrecognized lines go to the most recent section (CVs flow top-down);
    lines before the first heading go to "other".
    """
    lines = text.splitlines(keepends=True)
    # Compute each line's start/end offset in the ORIGINAL text.
    starts: list[int] = []
    pos = 0
    for line in lines:
        starts.append(pos)
        pos += len(line)

    segments: list[Segment] = []
    current: str | None = None
    current_start: int | None = None
    current_heading = ""

    def _close_segment(end: int) -> None:
        nonlocal current, current_start, current_heading
        if current is not None and current_start is not None:
            segments.append(Segment(name=current, heading=current_heading, start=current_start, end=end))
        current, current_start, current_heading = None, None, ""

    for idx, line in enumerate(lines):
        section = _find_heading(line)
        if section is not None:
            _close_segment(starts[idx])
            current = section
            current_start = starts[idx]
            current_heading = line.strip()
        elif current is None and not _looks_like_heading(line) and line.strip():
            pass  # pre-heading content stays in "other" (handled below)

    _close_segment(pos)  # close the final segment at end-of-text

    # Build bullet list with segment assignment (most recent heading wins).
    # The heading line itself belongs to its section (gold annotation convention).
    bullets: list[Bullet] = []
    current = "other"
    for idx, line in enumerate(lines):
        section = _find_heading(line)
        if section is not None:
            current = section
            bullets.append(Bullet(text=line, start=starts[idx], end=starts[idx] + len(line),
                                  segment=section, line_number=idx + 1))
            continue
        seg_name = current if current != "other" else "other"
        bullets.append(Bullet(text=line, start=starts[idx], end=starts[idx] + len(line),
                              segment=seg_name, line_number=idx + 1))

    # Pre-heading content (name/contact block) becomes an "other" segment.
    if segments:
        first_start = segments[0].start
        if first_start > 0:
            segments.insert(0, Segment(name="other", heading="", start=0, end=first_start))
    elif text:
        segments.append(Segment(name="other", heading="", start=0, end=len(text)))
    # merge adjacent same-name segments (repeat headings)
    merged: list[Segment] = []
    for seg in segments:
        if merged and merged[-1].name == seg.name and seg.start <= merged[-1].end:
            merged[-1] = Segment(name=seg.name, heading=merged[-1].heading,
                                 start=merged[-1].start, end=max(merged[-1].end, seg.end))
        else:
            merged.append(seg)

    return CVDocument(text=text, source_name=source_name, segments=merged, bullets=bullets)
