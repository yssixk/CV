"""Report builder (Phase 7): assembles the complete structured report.

Runs the full local pipeline (segmentation -> extraction -> understanding ->
evaluation -> summary) and produces a :class:`Report` that is complete with
NO LLM call. Deterministic given identical input + model availability.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from cv_analyzer.config import Config, DEFAULT_CONFIG, active_fields
from cv_analyzer.evaluate.redundancy import detect_redundancy
from cv_analyzer.evaluate.relevance import analyze_relevance
from cv_analyzer.evaluate.vagueness import detect_unsupported_claims, detect_vagueness
from cv_analyzer.explain.summary import build_extractive_summary
from cv_analyzer.extract.merge import merge_extraction
from cv_analyzer.extract.rules_extractor import run_rules_extraction
from cv_analyzer.models import (
    CANONICAL_SEGMENTS,
    CVDocument,
    Evidence,
    Finding,
    Report,
    SEGMENT_DOCUMENT,
)
from cv_analyzer.segment.segmenter import segment_document
from cv_analyzer.understand.lang_id import classify_language
from cv_analyzer.understand.statement_classifier import classify_bullet

MIN_WORDS = 5


@dataclass
class PipelineResult:
    report: Report
    lang_distribution: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def _detect_language_mix(bullets) -> dict[str, int]:
    dist: dict[str, int] = {}
    for b in bullets:
        if not b.stripped:
            continue
        label = classify_language(b.stripped)
        dist[label.lang] = dist.get(label.lang, 0) + 1
    return dist


def _completeness_findings(doc: CVDocument, lang: str) -> list[Finding]:
    """Missing-section findings (rules-based completeness check)."""
    found = {seg.name for seg in doc.segments}
    missing = [s for s in CANONICAL_SEGMENTS if s not in found]
    findings: list[Finding] = []
    if missing:
        section_labels = {
            "summary": "summary" if lang == "en" else "ringkasan",
            "experience": "experience" if lang == "en" else "pengalaman",
            "education": "education" if lang == "en" else "pendidikan",
            "skills": "skills" if lang == "en" else "keahlian",
        }
        head = doc.text[:80]
        stripped_head = head.strip()
        lead = len(head) - len(head.lstrip())
        evidence = Evidence(
            text=stripped_head or "(empty document)",
            start=lead,
            end=lead + len(stripped_head),
            source_segment=SEGMENT_DOCUMENT,
        )
        findings.append(
            Finding(
                kind="missing_section",
                message=f"Missing sections: {', '.join(missing)}. Found: {sorted(found)}",
                evidence=[evidence],
                details={"missing": missing, "found": sorted(found)},
            )
        )
    return findings


def build_report(
    text: str,
    source_name: str = "paste",
    jd_text: str | None = None,
    config: Config | None = None,
    use_nlp: bool = True,
) -> PipelineResult:
    """Run the whole local pipeline and return the structured report.

    ``use_nlp=False`` runs the rules-only baseline path (eval harness mode).
    """
    cfg = config or DEFAULT_CONFIG
    doc = segment_document(text, source_name=source_name)

    # language distribution (per-bullet, bilingual core)
    lang_dist = _detect_language_mix(doc.bullets)
    report_lang = "id" if lang_dist.get("id", 0) > lang_dist.get("en", 0) else "en"

    # extraction (rules always; NLP layer optional + mergeable)
    seg_triples = [(s.start, s.end, s.name) for s in doc.segments]
    rules_result = run_rules_extraction(doc.text, seg_triples)
    nlp_result = None
    if use_nlp and cfg.nlp_extractor_enabled:
        try:
            from cv_analyzer.extract.nlp_extractor import NLPExtractorUnavailable, run_nlp_extraction

            nlp_result = run_nlp_extraction(doc.text, seg_triples)
        except Exception:  # noqa: BLE001 — NLP layer is an enhancement, never a dependency
            nlp_result = None
    extraction = merge_extraction(rules_result, nlp_result)

    # findings
    findings: list[Finding] = []
    findings.extend(_completeness_findings(doc, report_lang))
    findings.extend(detect_vagueness(doc.bullets, doc.text))
    findings.extend(detect_redundancy(doc.bullets, doc.text, threshold=cfg.redundancy_threshold))
    findings.extend(detect_unsupported_claims(doc.bullets, doc.text))

    # relevance mode (optional, toggleable)
    relevance = None
    if jd_text:
        bullet_texts = [b.stripped for b in doc.bullets if b.stripped and len(b.stripped.split()) >= 3]
        relevance = analyze_relevance(bullet_texts, jd_text, match_threshold=cfg.relevance_match_threshold)

    summary_sentences = build_extractive_summary(
        [b for b in doc.bullets if b.stripped and len(b.stripped.split()) >= 6]
    )

    # Render messages through the per-language templates (deterministic).
    from cv_analyzer.explain.message_renderer import render_findings

    render_findings(findings, lang=report_lang)

    report = Report(
        document=doc,
        summary_sentences=[s.text for s in summary_sentences],
        findings=findings,
        extraction=extraction,
        completeness={s: (s in {seg.name for seg in doc.segments}) for s in CANONICAL_SEGMENTS},
        relevance=relevance,
        meta={
            "report_language": report_lang,
            "lang_distribution": lang_dist,
            "config": active_fields(cfg),
            "pipeline_version": "0.1.0",
            "run_id": uuid.uuid4().hex,
        },
    )
    return PipelineResult(report=report, lang_distribution=lang_dist)
