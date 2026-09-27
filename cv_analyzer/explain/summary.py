"""Extractive profile summary (menu 5c): select, never generate.

Picks the strongest *real* sentences from the CV by embedding similarity to a
small rubric of "strong CV sentence" exemplars (impact, specificity, scope).
Faithful by construction: every output sentence is a verbatim CV sentence —
zero hallucination risk, trivially bilingual (the exemplars are multilingual).
"""
from __future__ import annotations

from dataclasses import dataclass

from cv_analyzer.models import Bullet
from cv_analyzer.understand import embeddings

# Small, inspectable rubric: what a *strong, specific* CV sentence sounds like.
# Multilingual so EN and ID bullets compete in the same space.
RUBRIC_EXEMPLARS = [
    "Reduced processing time by 30% for 5,000 users by automating the data pipeline.",
    "Led a team of 4 to deliver the project two weeks ahead of schedule.",
    "Built a REST API serving 10,000 daily requests with 99.9% uptime.",
    "Mengurangi waktu pemrosesan 30% untuk 5.000 pengguna dengan mengotomasi alur data.",
    "Memimpin tim beranggotakan 4 orang menyelesaikan proyek lebih cepat dua minggu.",
    "Membangun REST API yang melayani 10.000 permintaan harian dengan uptime 99,9%.",
]

MIN_SENTENCE_WORDS = 6
MAX_SUMMARY_SENTENCES = 3


@dataclass(frozen=True)
class SummarySentence:
    text: str
    line_number: int
    score: float


def build_extractive_summary(
    bullets: list[Bullet],
    max_sentences: int = MAX_SUMMARY_SENTENCES,
) -> list[SummarySentence]:
    """Select top-scoring real sentences; empty if no model or no candidates."""
    candidates = [b for b in bullets if len(b.stripped.split()) >= MIN_SENTENCE_WORDS]
    if not candidates:
        return []
    try:
        rubric_vecs = embeddings.embed(RUBRIC_EXEMPLARS)
        cand_vecs = embeddings.embed([b.stripped for b in candidates])
    except embeddings.EmbeddingUnavailable:
        return []   # summary is optional; report remains complete without it

    # score each candidate by its best similarity to any exemplar
    scores = cand_vecs @ rubric_vecs.T          # (n_candidates, n_exemplars)
    best = scores.max(axis=1)
    ranked = sorted(zip(candidates, best.tolist()), key=lambda x: -x[1])

    out: list[SummarySentence] = []
    for bullet, score in ranked[:max_sentences]:
        out.append(SummarySentence(text=bullet.stripped, line_number=bullet.line_number, score=round(score, 4)))
    return out
