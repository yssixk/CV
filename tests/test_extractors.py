"""Per-extraction-type unit tests (Phase 2 acceptance): synthetic fixture bullets."""
from __future__ import annotations

import pytest

from cv_analyzer.extract.rules_extractor import (
    DATE_RANGE_RE,
    DEGREE_RE,
    GPA_RE,
    extract_education,
    extract_experiences,
    extract_skills,
)


def test_skill_exact_match_with_offset():
    text = "Skills: Python, SQL and Docker"
    skills = extract_skills(text)
    canonicals = {s.canonical for s in skills}
    assert {"Python", "SQL", "Docker"} <= canonicals
    py = next(s for s in skills if s.canonical == "Python")
    assert text[py.start:py.end] == "Python"


def test_skill_synonym_mapping():
    skills = extract_skills("Experienced with js and postgres on k8s")
    canonicals = {s.canonical for s in skills}
    assert "JavaScript" in canonicals
    assert "PostgreSQL" in canonicals
    assert "Kubernetes" in canonicals


def test_skill_word_boundary_no_false_positive():
    skills = extract_skills("We measure outcomes, not effort. Analysis of variance followed.")
    # "analysis" must not trigger "Data Analysis" (multiword alias only matches as a phrase)
    assert all(s.canonical != "Analysis" for s in skills)


def test_short_alias_case_sensitivity():
    # 'R' must match standalone capital R only, not the r in 'reports'
    skills = extract_skills("Used R for statistics.")
    assert any(s.canonical == "R" and s.text == "R" for s in skills)
    assert not any(s.canonical == "R" for s in extract_skills("Prepared reports daily."))


def test_indonesian_skill_alias():
    skills = extract_skills("Mahir dalam analisis data dan kerja tim.")
    canonicals = {s.canonical for s in skills}
    assert "Data Analysis" in canonicals
    assert "Teamwork" in canonicals


def test_date_range_english():
    m = DATE_RANGE_RE.search("Analyst, Corp    Jan 2020 - Present")
    assert m and m.group(0).lower().startswith("jan 2020")


def test_date_range_indonesian():
    m = DATE_RANGE_RE.search("Staf Admin    Feb 2021 - Sekarang")
    assert m, "Indonesian date range should match"


def test_date_range_years_only():
    m = DATE_RANGE_RE.search("Software Engineer 2018 - 2021 TechCorp")
    assert m and "2018" in m.group(0)


def test_experience_entry_fields():
    text = "Data Analyst, Acme Corp\nJun 2021 - Present\n- Responsible for reports.\n"
    entries = extract_experiences(text)
    assert entries, "date line should produce an entry"
    entry = entries[0]
    assert entry.title == "Data Analyst"
    assert entry.company == "Acme Corp"
    assert entry.end_date == "present"
    # evidence span slice equals the entry line
    assert text[entry.start:entry.end].strip().startswith("Jun 2021 - Present")


def test_degree_patterns():
    assert DEGREE_RE.search("BSc in Statistics, 2019")
    assert DEGREE_RE.search("Bachelor of Computer Science")
    assert DEGREE_RE.search("S1 Teknik Informatika")
    assert DEGREE_RE.search("Master's degree in Data Science")   # 'Master's'
    assert not DEGREE_RE.search("Passed the professional exam twice")


def test_gpa_patterns():
    assert GPA_RE.search("GPA: 3.65").group(1) == "3.65"
    assert GPA_RE.search("IPK 3,55").group(1) == "3,55"   # Indonesian comma form kept, normalized later
    assert GPA_RE.search("GPA 3.5/4.0").group(2) == "4.0"


def test_education_entry_evidence_slice():
    text = "EDUCATION\nBSc in Statistics, University of Indonesia, 2019, GPA 3.65\n"
    entries = extract_education(text)
    assert entries
    e = entries[0]
    assert text[e.start:e.end] == "BSc in Statistics, University of Indonesia, 2019, GPA 3.65"
    assert e.degree and e.gpa == "3.65"
