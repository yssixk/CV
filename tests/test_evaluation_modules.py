"""Evaluation-module tests: statement types, vagueness, redundancy, relevance."""
from __future__ import annotations

from cv_analyzer.evaluate.redundancy import detect_redundancy
from cv_analyzer.evaluate.relevance import analyze_relevance, split_requirements
from cv_analyzer.evaluate.vagueness import detect_unsupported_claims, detect_vagueness
from cv_analyzer.understand.statement_classifier import classify_statement
from cv_analyzer.segment.segmenter import segment_document


# ---------------------------------------------------------------------------
# statement classification
# ---------------------------------------------------------------------------

def test_achievement_with_metric():
    st = classify_statement("Reduced report generation time by 40% with Python.")
    assert st.label == "achievement"


def test_achievement_with_big_number():
    st = classify_statement("Built an API serving 5000 daily requests.")
    assert st.label == "achievement"


def test_duty_language():
    st = classify_statement("Responsible for various reports and dashboards.")
    assert st.label == "duty"
    assert any("responsible for" in c for c in st.cues_matched)


def test_responsibility_leadership():
    st = classify_statement("Led a team of four analysts on quarterly reporting.")
    assert st.label == "responsibility"


def test_indonesian_duty():
    st = classify_statement("Bertanggung jawab atas laporan penjualan bulanan.")
    assert st.label == "duty"


# ---------------------------------------------------------------------------
# vagueness
# ---------------------------------------------------------------------------

def test_vague_bullet_flagged_with_evidence():
    text = "EXPERIENCE\n- Responsible for various reports and dashboards for the sales team.\n"
    doc = segment_document(text)
    findings = detect_vagueness(doc.bullets, text)
    assert findings and findings[0].kind == "vague_bullet"
    ev = findings[0].evidence[0]
    assert text[ev.start:ev.end] == ev.text       # grounding invariant
    assert "Responsible" in ev.text


def test_achievement_not_flagged():
    text = "EXPERIENCE\n- Reduced processing time by 40% for 5000 users.\n"
    doc = segment_document(text)
    assert not detect_vagueness(doc.bullets, text)


def test_unsupported_claim_flagged():
    text = (
        "SUMMARY\nExcellent communicator with extensive experience in data analysis.\n\n"
        "EXPERIENCE\n- Responsible for various reports.\n"
    )
    doc = segment_document(text)
    findings = detect_unsupported_claims(doc.bullets, text)
    assert any(f.kind == "unsupported_claim" for f in findings)
    f = next(f for f in findings if f.kind == "unsupported_claim")
    assert f.evidence[0].text.lower() in text.lower()


# ---------------------------------------------------------------------------
# redundancy
# ---------------------------------------------------------------------------

def test_identical_bullets_flagged_lexically():
    text = (
        "EXPERIENCE\n"
        "- Reduced report generation time by 40% by automating the pipeline with Python.\n"
        "- Reduced report generation time by 40% by automating the pipeline with Python.\n"
    )
    doc = segment_document(text)
    findings = detect_redundancy(doc.bullets, text, threshold=0.85, use_embeddings=False)
    assert findings and findings[0].kind == "redundant_pair"
    assert len(findings[0].evidence) == 2
    for ev in findings[0].evidence:
        assert text[ev.start:ev.end] == ev.text


def test_different_bullets_not_flagged():
    text = (
        "EXPERIENCE\n"
        "- Reduced processing time by 40% with automated pipelines.\n"
        "EDUCATION\n- BSc in Statistics, University of Indonesia, 2019.\n"
    )
    doc = segment_document(text)
    assert not detect_redundancy(doc.bullets, text, threshold=0.85, use_embeddings=False)


def test_short_lines_ignored():
    text = "SKILLS\nPython\nSQL\nJava\n"
    doc = segment_document(text)
    assert not detect_redundancy(doc.bullets, text, use_embeddings=False)


# ---------------------------------------------------------------------------
# relevance
# ---------------------------------------------------------------------------

def test_split_requirements():
    jd = ("We are looking for a data analyst.\n\n"
          "Requirements:\n"
          "1. 3+ years of experience with SQL. 2. Experience building dashboards.\n")
    reqs = split_requirements(jd)
    assert len(reqs) >= 3
    assert all(len(r.split()) >= 3 for r in reqs)


def test_relevance_lexical_fallback_matches_skill():
    cv_bullets = [
        "Built dashboards and reports with SQL for the sales team.",
        "Led a team of four analysts.",
    ]
    jd = "Requirements: strong SQL skills and dashboard experience. Must be a good communicator."
    result = analyze_relevance(cv_bullets, jd, match_threshold=0.3, use_embeddings=False)
    assert result.areas
    matched_sql = next(a for a in result.areas if "SQL" in a.requirement_text)
    assert matched_sql.matched
    assert "SQL" in (matched_sql.matched_bullet_text or "")


def test_relevance_no_bullets_is_safe():
    result = analyze_relevance([], "Requires Python experience.", use_embeddings=False)
    assert result.areas == []
