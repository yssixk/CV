"""Integration tests with REAL models (mark: slow — run with `pytest -m slow`).

Covers the Phase 4/5 acceptance criteria:
- rules-only vs NLP-only vs both on the same fixtures (the first delta
  measurement for the thesis),
- cross-lingual (EN/ID) redundancy via real multilingual embeddings,
- extractive summary returning verbatim CV sentences,
- embedding-based relevance matching.

Requires the models to be cached/downloadable; each test loads real weights
(XLM-R NER ~1.1 GB, MiniLM ~470 MB), so keep the set small.
"""
from __future__ import annotations

import pytest

from cv_analyzer.extract.merge import merge_extraction
from cv_analyzer.extract.rules_extractor import run_rules_extraction
from cv_analyzer.explain.report_builder import build_report
from cv_analyzer.segment.segmenter import segment_document


@pytest.mark.slow
def test_nlp_extractor_finds_entities(smoke_cv_text):
    from cv_analyzer.extract.nlp_extractor import extract_entities

    entities = extract_entities(smoke_cv_text)
    labels = {e.label for e in entities}
    assert labels & {"org", "per"}, f"expected ORG/PER entities, got {labels}"
    for e in entities:
        # grounding invariant holds for the NLP layer too
        assert smoke_cv_text[e.start:e.end] == e.text


@pytest.mark.slow
def test_first_delta_measurement_rules_vs_nlp(smoke_cv_text):
    """Run both extractors on the same fixture; report rules/NLP/both counts."""
    doc = segment_document(smoke_cv_text)
    seg_triples = [(s.start, s.end, s.name) for s in doc.segments]

    rules = run_rules_extraction(doc.text, seg_triples)
    from cv_analyzer.extract.nlp_extractor import extract_skills_nlp

    nlp_skills = extract_skills_nlp(doc.text, seg_triples)
    merged = merge_extraction(rules, type("R", (), {"skills": nlp_skills, "entities": [],
                                                    "experiences": [], "education": [],
                                                    "extractor_name": "nlp"})())

    rules_set = rules.skill_canonicals()
    nlp_set = {s.canonical for s in nlp_skills}
    merged_set = merged.skill_canonicals()

    # merge adds at least everything rules found, never removes any
    assert rules_set <= merged_set
    both = rules_set & nlp_set
    nlp_only = nlp_set - rules_set
    print(f"\ndelta on fixture: rules={len(rules_set)} nlp={len(nlp_set)} "
          f"both={len(both)} nlp_only={len(nlp_only)} merged={len(merged_set)}")
    # grounding invariant on merged output
    for m in merged.skills:
        assert doc.text[m.start:m.end] == m.text


@pytest.mark.slow
def test_cross_lingual_redundancy_detected():
    """An English bullet and its Indonesian paraphrase pair as redundant."""
    text = (
        "EXPERIENCE\n"
        "- Reduced report generation time by 40% by automating the pipeline with Python.\n"
        "- Mengurangi waktu pembuatan laporan sebesar 40% dengan mengotomasi pipeline menggunakan Python.\n"
    )
    doc = segment_document(text)
    from cv_analyzer.evaluate.redundancy import detect_redundancy

    findings = detect_redundancy(doc.bullets, text, threshold=0.70, use_embeddings=True)
    assert findings, "cross-lingual paraphrase pair should be flagged by the semantic path"
    for ev in findings[0].evidence:
        assert text[ev.start:ev.end] == ev.text


@pytest.mark.slow
def test_extractive_summary_returns_verbatim_sentences(smoke_cv_text):
    from cv_analyzer.explain.summary import build_extractive_summary

    doc = segment_document(smoke_cv_text)
    bullets = [b for b in doc.bullets if len(b.stripped.split()) >= 6]
    summary = build_extractive_summary(bullets)
    assert summary, "expected selected sentences with the embedding model available"
    for s in summary:
        assert s.text in smoke_cv_text, "summary must quote the CV verbatim (no generation)"


@pytest.mark.slow
def test_relevance_embedding_match():
    from cv_analyzer.evaluate.relevance import analyze_relevance

    bullets = [
        "Built dashboards and automated reports with SQL for the sales team.",
        "Led a team of four analysts on quarterly forecasting.",
    ]
    jd = "Requirements: 3 years of SQL experience. Strong dashboard and reporting skills. Public speaking."
    result = analyze_relevance(bullets, jd, use_embeddings=True)  # calibrated default threshold
    sql_area = next(a for a in result.areas if "SQL" in a.requirement_text)
    assert sql_area.matched, f"SQL requirement should match (score={sql_area.similarity})"
    assert "SQL" in (sql_area.matched_bullet_text or "")


@pytest.mark.slow
def test_full_pipeline_with_nlp_layer_grounded(smoke_cv_text):
    """End-to-end with the transformer layer on; grounding invariant still holds."""
    result = build_report(smoke_cv_text, source_name="smoke", use_nlp=True)
    for f in result.report.findings:
        for ev in f.evidence:
            assert result.report.document.text[ev.start:ev.end] == ev.text
    assert result.report.extraction is not None
    assert result.report.extraction.skill_canonicals(), "skills must be extracted in the full path"
