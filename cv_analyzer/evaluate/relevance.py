"""Relevance mode (Phase 5): CV vs. pasted job description, semantic gap list.

Advisory framing: "which requirements does your CV speak to, and which don't
appear anywhere in it" — never a fit score, never a ranking of people. Each
requirement sentence of the JD is embedded and matched against all CV bullets;
the best match above the threshold marks the requirement as addressed, and the
matched bullet is attached as evidence (quoted back to the user).

The TF-IDF baseline (menu 3a) lives in the eval harness only, not here —
the production path is semantic matching.
"""
from __future__ import annotations

import re

from cv_analyzer.models import RelevanceArea, RelevanceResult
from cv_analyzer.understand import embeddings
from cv_analyzer.config import DEFAULT_CONFIG

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")
MIN_REQUIREMENT_WORDS = 3


def split_requirements(jd_text: str) -> list[str]:
    """Split a job description into requirement-ish sentences (deterministic)."""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(jd_text) if s.strip()]
    return [s for s in sentences if len(s.split()) >= MIN_REQUIREMENT_WORDS]


def analyze_relevance(
    cv_bullets_text: list[str],
    jd_text: str,
    match_threshold: float | None = None,
    use_embeddings: bool = True,
) -> RelevanceResult:
    """Match each JD requirement against the CV bullets (best match wins)."""
    cfg = DEFAULT_CONFIG
    threshold = match_threshold if match_threshold is not None else cfg.relevance_match_threshold
    requirements = split_requirements(jd_text)
    if not requirements or not cv_bullets_text:
        return RelevanceResult(requirement=jd_text, areas=[])

    similarities: list[list[float]] | None = None
    if use_embeddings:
        try:
            bullet_vecs = embeddings.embed(cv_bullets_text)
            req_vecs = embeddings.embed(requirements)
            similarities = (req_vecs @ bullet_vecs.T).tolist()
        except embeddings.EmbeddingUnavailable:
            similarities = None
    if similarities is None:
        # lexical fallback so the feature never hard-fails without the model
        similarities = _lexical_similarities(requirements, cv_bullets_text)

    areas: list[RelevanceArea] = []
    for req, row in zip(requirements, similarities):
        best_idx = max(range(len(row)), key=lambda k: row[k])
        best_score = row[best_idx]
        matched = best_score >= threshold
        areas.append(
            RelevanceArea(
                requirement_text=req,
                matched_bullet_text=cv_bullets_text[best_idx] if matched else None,
                similarity=round(best_score, 4),
                matched=matched,
            )
        )
    return RelevanceResult(requirement=jd_text, areas=areas)


def _lexical_similarities(requirements: list[str], bullets: list[str]) -> list[list[float]]:
    """Deterministic fallback (menu 3a spirit): requirement-term COVERAGE.

    Coverage (|req ∩ bullet| / |req|) is the right asymmetry here: a short
    bullet addresses a long requirement even when the bullet adds extra terms,
    which symmetric Jaccard wrongly punishes.
    """
    from cv_analyzer.evaluate.redundancy import _content_words

    req_sets = [_content_words(r) for r in requirements]
    bullet_sets = [_content_words(b) for b in bullets]
    rows: list[list[float]] = []
    for req_set in req_sets:
        row = []
        for b_set in bullet_sets:
            if not req_set:
                row.append(0.0)
                continue
            row.append(len(req_set & b_set) / len(req_set))
        rows.append(row)
    return rows
