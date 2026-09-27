"""Message renderer (menu 5a): slot-fills the per-language templates from
structured Finding data. Deterministic by construction: identical Findings
render to identical strings, and no slot can contain anything but computed
evidence (grounded generation, zero hallucination).
"""
from __future__ import annotations

from cv_analyzer.explain.templates_en import SUGGESTIONS as SUGGESTIONS_EN, TEMPLATES as TEMPLATES_EN
from cv_analyzer.explain.templates_id import SUGGESTIONS as SUGGESTIONS_ID, TEMPLATES as TEMPLATES_ID
from cv_analyzer.models import Finding

_TEMPLATES = {"en": TEMPLATES_EN, "id": TEMPLATES_ID}
_SUGGESTIONS = {"en": SUGGESTIONS_EN, "id": SUGGESTIONS_ID}


def _quote(text: str) -> str:
    return text.strip()


def render_finding(finding: Finding, lang: str = "en") -> str:
    """Render one finding's message in the requested language.

    Falls back to the finding's existing message for kinds without a template
    or when required slots are missing — rendering never invents content.
    """
    templates = _TEMPLATES.get(lang) or TEMPLATES_EN
    suggestions = _SUGGESTIONS.get(lang) or SUGGESTIONS_EN
    template = templates.get(finding.kind)
    if template is None:
        return finding.message

    details = finding.details
    evidence = finding.evidence
    try:
        if finding.kind == "vague_bullet":
            return template.format(
                line_number=details.get("line_number", "?"),
                cue=details.get("cue", "duty cue"),
                evidence=_quote(evidence[0].text) if evidence else "",
                suggestion=suggestions["vague_bullet"],
            )
        if finding.kind == "redundant_pair" and len(evidence) >= 2:
            return template.format(
                line_a=details.get("line_a", "?"),
                line_b=details.get("line_b", "?"),
                score=float(details.get("score", 0.0)),
                evidence_a=_quote(evidence[0].text),
                evidence_b=_quote(evidence[1].text),
            )
        if finding.kind == "unsupported_claim":
            return template.format(
                claim=_quote(evidence[0].text) if evidence else details.get("claim", ""),
                line_number=details.get("line_number", "?"),
            )
        if finding.kind == "missing_section":
            return template.format(
                section=", ".join(details.get("missing", [])) or "-",
                found_sections=", ".join(str(s) for s in details.get("found", [])) or "-",
            )
    except (KeyError, IndexError, ValueError):
        return finding.message
    return finding.message


def render_findings(findings: list[Finding], lang: str = "en") -> list[Finding]:
    """Render all findings in place; returns the same list for chaining."""
    for finding in findings:
        finding.message = render_finding(finding, lang)
    return findings
