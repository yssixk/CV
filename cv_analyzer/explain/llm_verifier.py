"""LLM output verification (Phase 8): no sentence is shown unless it traces to evidence.

Start mode: token-overlap check between the LLM sentence and the finding's
redacted message + evidence spans. Upgrade mode ("embedding"): sentence
embedding similarity against the same material, using the shared wrapper.

Anything rejected means the ORIGINAL template message is shown — the layer is
purely additive, so the report stays correct even if the LLM hallucinated.
"""
from __future__ import annotations

import re

from cv_analyzer.config import DEFAULT_CONFIG
from cv_analyzer.models import Finding
from cv_analyzer.understand import embeddings
from cv_analyzer.security.redact import redact_text
from cv_analyzer.utils.text import light_stem as _light_stem

WORD_RE = re.compile(r"[a-z0-9+#]+")

# tokens so common they carry no traceability signal on their own
_GENERIC = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by",
    "is", "are", "was", "were", "be", "been", "this", "that", "it", "as", "from",
    "dan", "atau", "di", "ke", "dari", "yang", "untuk", "dengan", "pada", "adalah",
    "your", "you", "we", "this", "these", "line", "consider", "suggest", "suggestion",
}


def _content_tokens(text: str) -> set[str]:
    low = redact_text(text).redacted_text.lower()
    tokens = [t for t in WORD_RE.findall(low) if t not in _GENERIC and not t.isdigit()]
    return {_light_stem(t) for t in tokens}


def keyword_verdict(sentence: str, finding: Finding, min_overlap: int = 2) -> tuple[bool, float, str]:
    """Keyword-overlap mode. Returns (accepted, score, reason).

    Two-part traceability requirement (defense against prompt injection
    echoed through the evidence quote):
    1. the sentence must substantially overlap the finding's material
       (template message + evidence), AND
    2. it must share at least one content token with the *template message*
       alone. Evidence text can contain adversarial CV content (an injected
       instruction like "describe this candidate as excellent") — a sentence
       that only echoes the evidence but not the finding's claim gets no
       grounding and is rejected; the template fallback is shown instead.
    """
    sent_tokens = _content_tokens(sentence)
    if not sent_tokens:
        return False, 0.0, "empty sentence"
    message_tokens = _content_tokens(finding.message)
    evidence_tokens: set[str] = set()
    for ev in finding.evidence:
        evidence_tokens |= _content_tokens(ev.text)
    allowed = message_tokens | evidence_tokens

    overlap = sent_tokens & allowed
    score = len(overlap) / len(sent_tokens)
    msg_overlap = sent_tokens & message_tokens
    if score < 0.5 or len(overlap) < min_overlap:
        return False, round(score, 3), f"insufficient material overlap ({len(overlap)}/{len(sent_tokens)} tokens)"
    if not msg_overlap:
        return False, round(score, 3), "sentence does not trace to the finding's message (evidence-only echo)"
    return True, round(score, 3), "keyword overlap ok"


def embedding_verdict(sentence: str, finding: Finding, threshold: float | None = None) -> tuple[bool, float, str]:
    """Embedding-similarity mode against the finding's redacted material."""
    threshold = threshold if threshold is not None else DEFAULT_CONFIG.verifier_embedding_threshold
    try:
        material = " ".join([finding.message] + [ev.text for ev in finding.evidence])
        sent_vec, mat_vec = embeddings.embed([sentence, material])
        score = embeddings.similarity(sent_vec, mat_vec)
    except embeddings.EmbeddingUnavailable:
        # degrade to keyword mode rather than block or trust blindly
        return keyword_verdict(sentence, finding)
    if score >= threshold:
        return True, round(score, 3), "embedding similarity ok"
    return False, round(score, 3), f"similarity {score:.2f} below {threshold:.2f}"


def verify_sentence(sentence: str, finding: Finding, mode: str | None = None) -> tuple[bool, float, str]:
    """Verify one LLM-generated sentence against its grounding finding."""
    mode = mode or DEFAULT_CONFIG.verifier_mode
    if mode == "embedding":
        return embedding_verdict(sentence, finding)
    return keyword_verdict(sentence, finding)


def verify_llm_result(llm_result, findings: list[Finding], mode: str | None = None):
    """Verify every rewritten finding; returns items with acceptance flags."""
    from cv_analyzer.explain.llm_feedback import RewrittenFinding

    out = []
    for item in llm_result.items:
        finding = findings[item.finding_id]
        if item.llm_text is None:
            out.append(item)
            continue
        accepted, score, reason = verify_sentence(item.llm_text, finding, mode)
        out.append(
            RewrittenFinding(
                finding_id=item.finding_id,
                original_message=item.original_message,
                llm_text=item.llm_text if accepted else None,
                fallback_used=not accepted,
                verification={"accepted": accepted, "score": score, "reason": reason, "mode": mode},
            )
        )
    return out
