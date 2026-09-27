"""End-to-end smoke tests: full pipeline on fixture CVs (rules path, no models)."""
from __future__ import annotations

from cv_analyzer.explain.report_builder import build_report


def test_report_builds_and_is_grounded(smoke_cv_text):
    result = build_report(smoke_cv_text, source_name="smoke", use_nlp=False)
    report = result.report

    assert report.document.text == smoke_cv_text
    assert report.findings, "expected at least one finding on a deliberately flawed CV"

    for f in report.findings:
        assert f.evidence, f"finding {f.kind} has no evidence"
        for ev in f.evidence:
            # grounding invariant: the evidence text is an exact slice of the source
            assert report.document.text[ev.start:ev.end] == ev.text


def test_segmentation_buckets(smoke_cv_text):
    result = build_report(smoke_cv_text, source_name="smoke", use_nlp=False)
    segments = {s.name for s in result.report.document.segments}
    assert {"summary", "skills", "experience", "education"} <= segments


def test_rules_extraction_finds_skills_and_dates(smoke_cv_text):
    result = build_report(smoke_cv_text, source_name="smoke", use_nlp=False)
    extraction = result.report.extraction
    assert extraction is not None
    canonicals = extraction.skill_canonicals()
    assert "Python" in canonicals
    assert "SQL" in canonicals
    assert extraction.experiences, "expected date-ranged experience entries"
    assert extraction.education, "expected education entries"


def test_determinism_rules_path(smoke_cv_text):
    """Same input + same availability => identical report (no LLM, no stochasticity)."""
    r1 = build_report(smoke_cv_text, source_name="smoke", use_nlp=False)
    r2 = build_report(smoke_cv_text, source_name="smoke", use_nlp=False)
    d1, d2 = r1.report.to_dict(), r2.report.to_dict()
    d1["meta"].pop("run_id"), d2["meta"].pop("run_id")
    assert d1 == d2


def test_mixed_language_cv(smoke_cv_mixed_text):
    result = build_report(smoke_cv_mixed_text, source_name="mixed", use_nlp=False)
    dist = result.lang_distribution
    assert dist.get("id", 0) > 0, "expected Indonesian bullets to be detected"
    # grounding invariant holds on the mixed-language CV too
    for f in result.report.findings:
        for ev in f.evidence:
            assert result.report.document.text[ev.start:ev.end] == ev.text
