"""Statement classification (Phase 6): achievement vs. duty vs. responsibility.

Rules baseline (cue phrases + quantification detection), deterministic and
inspectable — the NLP upgrade path (a small fine-tuned classifier) is deferred
per the blueprint's Advanced tier. This module feeds the vagueness evaluator.

Definitions used (documented for the thesis):
- **achievement** — states an outcome with a quantifiable/observable result
  ("reduced processing time by 30%", "served 5,000 users", "won first place").
- **duty** — states an activity without outcome ("responsible for testing",
  "helped with various tasks").
- **responsibility** — duty language PLUS scope/authority markers ("led",
  "managed", "owned") — still no outcome, but indicates ownership.
"""
from __future__ import annotations

import re

from cv_analyzer.models import StatementType
from cv_analyzer.utils.gazetteer_loader import load_gazetteer

_NUM_RE = re.compile(r"\d")
_CURRENCY_RE = re.compile(r"[$€£Rp]\s?\d|(?:\d[\d.,]*)\s*(?:usd|eur|juta|ribu|miliar|billion|million|thousand|k\b)", re.IGNORECASE)
_PERCENT_RE = re.compile(r"\d\s?%|percent", re.IGNORECASE)
_MULTIPLIER_RE = re.compile(r"\b\d+(?:\.\d+)?\s?(?:x|times)\b", re.IGNORECASE)
_BIG_NUM_RE = re.compile(r"\b\d{3,}\b")

# outcome verbs: past-tense action verbs that imply a completed, observable result
_OUTCOME_VERBS = [
    "reduced", "increased", "improved", "cut", "grew", "achieved", "delivered",
    "launched", "built", "developed", "designed", "implemented", "automated",
    "optimized", "mengurangi", "meningkatkan", "membangun", "mengembangkan",
    "merancang", "mengimplementasikan", "meraih", "mencapai", "memenangkan",
]

_LEADERSHIP_CUES = [
    "led", "managed", "owned", "supervised", "coordinated", "mentored", "headed",
    "memimpin", "mengelola", "mengkoordinasi", "membimbing", "mengepalai",
]


def _vague_cues(text: str) -> list[str]:
    cues: list[str] = []
    gaz = load_gazetteer("vagueness_en")
    low = text.lower()
    for cue in gaz["duty_phrases"] + gaz["fuzzy_quantifiers"] + gaz["hedges"]:
        if cue in low:
            cues.append(cue)
    gaz_id = load_gazetteer("vagueness_id")
    for cue in gaz_id["duty_phrases"] + gaz_id["fuzzy_quantifiers"] + gaz_id["hedges"]:
        if cue in low:
            cues.append(cue)
    return cues


def _quantification_score(text: str) -> int:
    """Count independent quantification signals (percent, money, big numbers)."""
    score = 0
    if _PERCENT_RE.search(text):
        score += 2
    if _CURRENCY_RE.search(text):
        score += 2
    if _MULTIPLIER_RE.search(text):
        score += 2
    if _BIG_NUM_RE.search(text):
        score += 1
    return score


def classify_statement(text: str) -> StatementType:
    """Classify one bullet. Deterministic; explainable via cues_matched."""
    low = text.lower()
    cues: list[str] = []
    quant = _quantification_score(text)
    has_outcome_verb = any(v in low for v in _OUTCOME_VERBS)
    has_leadership = any(c in low for c in _LEADERSHIP_CUES)

    if quant >= 2 or (quant >= 1 and has_outcome_verb):
        label = "achievement"
        confidence = min(0.6 + 0.1 * quant, 0.95)
    elif has_leadership:
        label = "responsibility"
        confidence = 0.7
        cues.append("leadership cue")
    elif _vague_cues(low) or (has_outcome_verb and quant == 0):
        label = "duty"
        confidence = 0.65
    else:
        label = "other"
        confidence = 0.5

    cues.extend(_vague_cues(text))
    if has_outcome_verb:
        cues.append("outcome verb")
    if quant:
        cues.append(f"quantification={quant}")

    # offsets: we classify the bullet as a whole; start/end filled by caller
    return StatementType(bullet_start=0, bullet_end=len(text), label=label,
                         confidence=round(confidence, 3), cues_matched=cues)


def classify_bullet(bullet_text: str, bullet_start: int, bullet_end: int) -> StatementType:
    """Classify with real offsets into the document."""
    st = classify_statement(bullet_text)
    st.bullet_start = bullet_start
    st.bullet_end = bullet_end
    return st
