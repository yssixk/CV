"""Vagueness evaluation (Phase 6): duty-language bullets lacking quantified outcomes.

Builds directly on the statement classifier: every "duty" bullet with no
quantification signal becomes a ``vague_bullet`` finding, and generic
self-assessment claims ("excellent communication skills") with no supporting
experience become ``unsupported_claim`` findings. Both quote the offending
text verbatim. Advisory, never a verdict about the candidate.
"""
from __future__ import annotations

from cv_analyzer.models import Bullet, Evidence, Finding
from cv_analyzer.understand.statement_classifier import classify_bullet
from cv_analyzer.utils.gazetteer_loader import load_gazetteer

_SKILLS_SEGMENT_HINTS = {"summary", "skills", "document", "other"}


def _find_claim_spans(text: str, claims: list[str]) -> list[tuple[int, int]]:
    """Locate claim phrase spans (case-insensitive) inside a bullet.

    Returned position-sorted: claim lists are iterated in gazetteer order, so
    unsorted spans could make spans[0] start after spans[-1] ends and produce
    a degenerate evidence span.
    """
    low = text.lower()
    spans = []
    for claim in claims:
        idx = 0
        while True:
            i = low.find(claim, idx)
            if i == -1:
                break
            spans.append((i, i + len(claim)))
            idx = i + len(claim)
    return sorted(spans)


def detect_vagueness(
    bullets: list[Bullet],
    document_text: str,
    min_words: int = 5,
) -> list[Finding]:
    """Flag duty-language bullets without quantified outcomes."""
    findings: list[Finding] = []
    for bullet in bullets:
        stripped = bullet.stripped
        if len(stripped.split()) < min_words:
            continue
        st = classify_bullet(stripped, bullet.start, bullet.end)
        if st.label != "duty":
            continue
        message = (
            f"Line {bullet.line_number} describes an activity rather than an outcome "
            f"(duty language: '{st.cues_matched[0] if st.cues_matched else 'duty cue'}'). "
            f"Consider stating what changed as a result — e.g. a number, a percentage, or who benefited."
        )
        ev_start, ev_end = bullet.stripped_span
        findings.append(
            Finding(
                kind="vague_bullet",
                message=message,
                evidence=[Evidence(text=document_text[ev_start:ev_end], start=ev_start, end=ev_end,
                                   source_segment=bullet.segment, line_number=bullet.line_number)],
                confidence=st.confidence,
                details={"line_number": bullet.line_number,
                         "cue": st.cues_matched[0] if st.cues_matched else "duty cue",
                         "label": st.label},
            )
        )
    return findings


def detect_unsupported_claims(
    bullets: list[Bullet],
    document_text: str,
) -> list[Finding]:
    """Flag generic self-assessment claims that never reappear in experience bullets.

    A claim counts as supported if the same claim phrase OR any of its
    keywords appear in a different (experience/education/skills) segment.
    """
    gaz = load_gazetteer("vagueness_en")
    gaz_id = load_gazetteer("vagueness_id")
    claims = gaz["unquantified_claims"] + gaz_id["unquantified_claims"]
    if not claims:
        return []

    findings: list[Finding] = []
    # Support corpus: experience/education CONTENT only. Heading lines must be
    # excluded — the word "EXPERIENCE" in a heading would otherwise "support"
    # a summary claim of "extensive experience" (real bug caught by test).
    from cv_analyzer.segment.segmenter import _find_heading

    experience_text = " ".join(
        b.stripped.lower() for b in bullets
        if b.segment in {"experience", "education"} and _find_heading(b.text) is None
    )

    for bullet in bullets:
        if bullet.segment not in _SKILLS_SEGMENT_HINTS:
            continue
        stripped = bullet.stripped
        if len(stripped.split()) < 4:
            continue
        spans = _find_claim_spans(stripped, claims)
        if not spans:
            continue
        # support check: claim keywords present in experience/education text
        claim_text = stripped[spans[0][0]:spans[-1][1]].lower()
        claim_words = {w for w in claim_text.split() if len(w) > 3}
        supported = any(w in experience_text for w in claim_words)
        if supported:
            continue
        base = bullet.stripped_span[0]
        start = base + spans[0][0]
        end = base + spans[-1][1]
        findings.append(
            Finding(
                kind="unsupported_claim",
                message=(
                    f"Line {bullet.line_number} states '{document_text[start:end]}' but no "
                    f"experience entry demonstrates it. Back the claim with a concrete example "
                    f"(project, metric, or artifact), or soften it."
                ),
                evidence=[Evidence(text=document_text[start:end], start=start, end=end,
                                   source_segment=bullet.segment, line_number=bullet.line_number)],
                confidence=0.6,
                details={"line_number": bullet.line_number},
            )
        )
    return findings
