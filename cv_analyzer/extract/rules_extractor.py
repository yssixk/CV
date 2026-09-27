"""Rules baseline extractor (menu 2a): gazetteer skills + regex dates/degrees/GPA.

This is the deterministic baseline every NLP improvement is measured against.
Every extracted item carries exact character offsets (evidence spans). Fully
reproducible: no randomness, no model downloads, no network.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from cv_analyzer.models import (
    EducationEntry,
    ExperienceEntry,
    ExtractionResult,
    SkillMention,
)
from cv_analyzer.utils.gazetteer_loader import load_gazetteer

# ---------------------------------------------------------------------------
# Gazetteer compilation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AliasRule:
    canonical: str
    regex: re.Pattern[str]


def _alias_to_regex(alias: str) -> re.Pattern[str]:
    """Compile an alias into a boundary-safe regex.

    Short aliases (<= 2 chars) are matched case-sensitively to avoid drowning
    in false positives ("R", "ML", "js" appear inside ordinary words/units);
    everything else is case-insensitive. Boundaries exclude alphanumeric and
    skill-relevant symbols (+ # .) so "C++" and "Node.js" match cleanly.
    """
    escaped = re.escape(alias)
    left = r"(?<![A-Za-z0-9+#.])"
    right = r"(?![A-Za-z0-9+#])"
    flags = 0 if len(alias) <= 2 else re.IGNORECASE
    alternatives = [escaped]
    if len(alias) <= 2:
        alternatives.append(re.escape(alias.upper()))
    pattern = "|".join(alternatives)
    return re.compile(rf"{left}(?:{pattern}){right}", flags)


def _compile_skill_rules() -> list[AliasRule]:
    rules: list[AliasRule] = []
    for canonical, spec in load_gazetteer("skills_en").items():
        for alias in spec.get("aliases", []):
            rules.append(AliasRule(canonical=canonical, regex=_alias_to_regex(alias)))
    for canonical, aliases in load_gazetteer("skills_id").items():
        for alias in aliases:
            rules.append(AliasRule(canonical=canonical, regex=_alias_to_regex(alias)))
    return rules


_SKILL_RULES = _compile_skill_rules()


def _segment_for_offset(segments: list[tuple[int, int, str]], offset: int) -> str:
    for start, end, name in segments:
        if start <= offset < end:
            return name
    return "document"


# ---------------------------------------------------------------------------
# Skills
# ---------------------------------------------------------------------------

def extract_skills(
    text: str,
    segments: list[tuple[int, int, str]] | None = None,
) -> list[SkillMention]:
    """Gazetteer skill matching. ``segments`` is (start, end, name) triples."""
    segs = segments or []
    mentions: list[SkillMention] = []
    for rule in _SKILL_RULES:
        for match in rule.regex.finditer(text):
            mentions.append(
                SkillMention(
                    canonical=rule.canonical,
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    segment=_segment_for_offset(segs, match.start()),
                    extractor="rules",
                )
            )
    # De-duplicate: same canonical overlapping span -> keep the longest mention.
    mentions.sort(key=lambda m: (m.start, -(m.end - m.start)))
    deduped: list[SkillMention] = []
    for m in mentions:
        if any(d.canonical == m.canonical and m.start < d.end and d.start < m.end for d in deduped):
            continue
        deduped.append(m)
    return deduped


# ---------------------------------------------------------------------------
# Dates & experience entries
# ---------------------------------------------------------------------------

MONTHS_EN = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
MONTHS_ID = r"(?:Jan(?:uari)?|Feb(?:ruari)?|Mar(?:et)?|Apr(?:il)?|Mei|Jun(?:i)?|Jul(?:i)?|Agu|Ags|Aug|Sep(?:t)?|Okt|Oktober|Nov|Des|Desember)"
PRESENT_EN = r"(?:Present|Current|Now|Ongoing|Until now|To date)"
PRESENT_ID = r"(?:Sekarang|Saat ini|Hingga saat ini|Sampai sekarang|Masih)"

DATE_RANGE_RE = re.compile(
    rf"{MONTHS_EN}\s+\d{{4}}\s*(?:-|–|—|to|until|s\.?d\.?)\s*(?:{MONTHS_EN}\s+\d{{4}}|{PRESENT_EN})"
    rf"|{MONTHS_ID}\s+\d{{4}}\s*(?:-|–|—|s\.?d\.?|hingga|sampai)\s*(?:{MONTHS_ID}\s+\d{{4}}|{PRESENT_ID})"
    rf"|\d{{1,2}}/\d{{4}}\s*(?:-|–|—)\s*(?:\d{{1,2}}/\d{{4}}|{PRESENT_EN}|{PRESENT_ID})"
    rf"|\b(?:19|20)\d{{2}}\s*(?:-|–|—|to|until|s\.?d\.?)\s*(?:(?:19|20)\d{{2}}|{PRESENT_EN}|{PRESENT_ID})\b",
    re.IGNORECASE,
)

TITLE_COMPANY_RE = re.compile(
    r"^(?P<title>[^,\-–|]{2,60}?)\s*(?:,|-|–|—|\||@|at|di)\s*(?P<company>[^,\-–|]{2,60})$",
    re.IGNORECASE,
)


def _parse_line_for_entry(
    line: str, preceding_head: str, date_offset_in_line: int, matched_text: str
) -> ExperienceEntry:
    """Heuristic: 'Title, Company' / 'Title at Company' / 'Title - Company'.

    In the common CV layout the date range sits on its own line and the
    title/company on the line above it; ``preceding_head`` supplies that text.
    ``date_offset_in_line`` is the date match's offset WITHIN ``line`` (the
    regex match carries full-document offsets; they must not be mixed).
    ``matched_text`` is the date-range string itself.
    """
    head = line[:date_offset_in_line].strip(" -–—:|\u2022") or preceding_head.strip()
    entry = ExperienceEntry(title=None, company=None, start_date=None, end_date=None,
                            start=0, end=0, segment="document", text=line)
    m = TITLE_COMPANY_RE.match(head)
    if m:
        entry.title = m.group("title").strip() or None
        entry.company = m.group("company").strip() or None
    elif head:
        entry.title = head or None
    # dates
    matched = matched_text
    if re.search(PRESENT_EN, matched, re.IGNORECASE) or re.search(PRESENT_ID, matched, re.IGNORECASE):
        entry.end_date = "present"
    else:
        entry.end_date = matched.split("-")[-1].split("–")[-1].split("—")[-1].strip()
    entry.start_date = re.search(rf"(?:{MONTHS_EN}|{MONTHS_ID})?\s*\d{{1,2}}/\d{{4}}|\b(?:19|20)\d{{2}}\b|{MONTHS_EN}\s+\d{{4}}|{MONTHS_ID}\s+\d{{4}}", matched, re.IGNORECASE).group(0)  # type: ignore[union-attr]
    return entry


def extract_experiences(text: str) -> list[ExperienceEntry]:
    """Find date-ranged experience entries; the span covers the date line."""
    entries: list[ExperienceEntry] = []
    for match in DATE_RANGE_RE.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        line_end = len(text) if line_end == -1 else line_end
        line = text[line_start:line_end]
        date_offset_in_line = match.start() - line_start
        # the title/company line above the date line (standard CV layout)
        prev_line_start = text.rfind("\n", 0, line_start - 1) + 1 if line_start > 0 else 0
        preceding_head = text[prev_line_start:line_start].strip() if line_start > 0 else ""
        entry = _parse_line_for_entry(line, preceding_head, date_offset_in_line, match.group(0))
        entry.start, entry.end = line_start, line_end
        entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

DEGREE_RE = re.compile(
    r"\b(Bachelor(?:'s)?(?: of [A-Za-z ]+)?|Master(?:'s)?(?: of [A-Za-z ]+)?|Ph\.?D\.?|Doctor(?:ate)?|"
    r"B\.?S\.?c?\.?|M\.?S\.?c?\.?|B\.?A\.?|M\.?A\.?|B\.?Eng|M\.?Eng|M\.?Tech|"
    r"Sarjana|S1|S2|S3|D3|D4|Diploma|Magister|Doktor)\b(?:\s+(?:in|of)\s+([A-Za-z &]{2,40}))?",
    re.IGNORECASE,
)

GPA_RE = re.compile(r"\b(?:GPA|IPK)\s*[:\-]?\s*(\d(?:[.,]\d{1,2})?)\b(?:\s*/\s*(\d(?:[.,]\d)?))?", re.IGNORECASE)


def extract_education(text: str) -> list[EducationEntry]:
    entries: list[EducationEntry] = []
    lines = text.splitlines(keepends=True)
    offset = 0
    for line in lines:
        line_wo_nl = line.rstrip("\r\n")
        degree_match = DEGREE_RE.search(line_wo_nl)
        gpa_match = GPA_RE.search(line_wo_nl)
        if degree_match or gpa_match:
            field = degree_match.group(2) if degree_match else None
            entries.append(
                EducationEntry(
                    degree=degree_match.group(1) if degree_match else None,
                    field_of_study=field,
                    institution=None,
                    gpa=gpa_match.group(1).replace(",", ".") if gpa_match else None,
                    start=offset,
                    end=offset + len(line_wo_nl),
                    segment="document",
                    text=line_wo_nl,
                )
            )
        offset += len(line)
    return entries


# ---------------------------------------------------------------------------
# Top-level baseline
# ---------------------------------------------------------------------------

def run_rules_extraction(
    text: str,
    segments: list[tuple[int, int, str]] | None = None,
) -> ExtractionResult:
    """Run the full rules baseline. Deterministic; safe to call in tests."""
    skills = extract_skills(text, segments)
    experiences = extract_experiences(text)
    education = extract_education(text)
    # apply segment attribution to entries
    segs = segments or []

    def _seg_of(start: int) -> str:
        return _segment_for_offset(segs, start)

    for e in experiences:
        e.segment = _seg_of(e.start)
    for e in education:
        e.segment = _seg_of(e.start)
    return ExtractionResult(
        skills=skills, experiences=experiences, education=education, extractor_name="rules"
    )
