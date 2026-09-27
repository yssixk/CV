"""Redundancy detection (Phase 5): paraphrase/duplicate bullet pairs within a CV.

Primary path: multilingual embedding cosine similarity (works cross-language —
an EN bullet duplicated in ID is still caught). Fallback (no model available):
lexical Jaccard over content-word sets, which catches copies but not
paraphrases. Both paths are deterministic for a given input.

Findings carry BOTH bullets as evidence spans, per the project's grounding
rule.
"""
from __future__ import annotations

import re

from cv_analyzer.models import Bullet, Evidence, Finding
from cv_analyzer.understand import embeddings
from cv_analyzer.utils.text import light_stem

WORD_RE = re.compile(r"[a-z0-9+#]+")

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by",
    "is", "are", "was", "were", "be", "been", "this", "that", "it", "as", "from",
    "dan", "atau", "di", "ke", "dari", "yang", "untuk", "dengan", "pada", "adalah",
}

MIN_BULLET_WORDS = 4   # short lines ("Python", "Java") would all correlate


def _content_words(text: str) -> set[str]:
    return {light_stem(w) for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS}


def _lexical_jaccard(a: str, b: str) -> float:
    wa, wb = _content_words(a), _content_words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def detect_redundancy(
    bullets: list[Bullet],
    document_text: str,
    threshold: float = 0.85,
    use_embeddings: bool = True,
) -> list[Finding]:
    """Flag bullet pairs (within a segment) above the similarity threshold."""
    candidates = [b for b in bullets if len(_content_words(b.stripped)) >= MIN_BULLET_WORDS]
    if len(candidates) < 2:
        return []

    scores: dict[tuple[int, int], float] = {}
    method_note = ""
    if use_embeddings:
        try:
            pairs = embeddings.pairwise_similarities([b.stripped for b in candidates])
            scores = {(i, j): s for i, j, s in pairs}
            method_note = "semantic (embedding) similarity"
        except embeddings.EmbeddingUnavailable:
            scores = {}
    if not scores:
        scores = {}
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                scores[(i, j)] = _lexical_jaccard(candidates[i].stripped, candidates[j].stripped)
        method_note = "lexical (Jaccard) fallback"

    findings: list[Finding] = []
    for (i, j), score in sorted(scores.items()):
        if score >= threshold:
            bi, bj = candidates[i], candidates[j]
            message = (
                f"Lines {bi.line_number} and {bj.line_number} look redundant "
                f"(similarity {score:.2f}, {method_note}); both describe the same point. "
                f"Consider merging or differentiating them."
            )
            ev = []
            for b in (bi, bj):
                s, e = b.stripped_span
                ev.append(Evidence(text=document_text[s:e], start=s, end=e,
                                   source_segment=b.segment, line_number=b.line_number))
            findings.append(
                Finding(
                    kind="redundant_pair",
                    message=message,
                    evidence=ev,
                    confidence=round(min(score, 1.0), 3),
                    details={"line_a": bi.line_number, "line_b": bj.line_number,
                             "score": round(min(score, 1.0), 3), "method": method_note},
                )
            )
    return findings
