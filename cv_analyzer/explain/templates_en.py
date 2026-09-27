"""English finding templates (menu 5a).

Grounded by construction: every message embeds verbatim evidence text or
line numbers, so no template can state anything not present in the CV.
Slots come only from computed Finding data.
"""

TEMPLATES = {
    "vague_bullet": (
        "Bullet on line {line_number} reads as a duty rather than an achievement "
        "(cue: \"{cue}\"). Evidence: \"{evidence}\". Suggestion: {suggestion}"
    ),
    "redundant_pair": (
        "Lines {line_a} and {line_b} express the same point (similarity {score:.2f}). "
        "Evidence A: \"{evidence_a}\" Evidence B: \"{evidence_b}\" Consider merging them."
    ),
    "unsupported_claim": (
        "The claim \"{claim}\" (line {line_number}) is not demonstrated elsewhere in the CV. "
        "Suggestion: add a concrete project or metric that shows it."
    ),
    "missing_section": (
        "No {section} section was detected. Sections found: {found_sections}. "
        "A standard CV usually includes summary, experience, education, and skills."
    ),
    "very_short_bullet": (
        "Line {line_number} is very short (\"{evidence}\"); a hiring reviewer cannot tell what you actually did."
    ),
    "long_bullet": (
        "Line {line_number} runs over 40 words; split it so each line carries one point."
    ),
    "generic_duty_summary": (
        "Your summary uses generic phrasing (\"{evidence}\"); tailor it to the role you're targeting."
    ),
}

SUGGESTION_HINTS = {
    "vague_bullet": "rewrite with the outcome: what changed, by how much, for whom.",
    "redundant_pair": "merge the two bullets and keep the stronger one.",
    "unsupported_claim": "support the claim with a concrete example.",
}

SUGGESTIONS = {
    "vague_bullet": "rewrite with the outcome: what changed, by how much, for whom.",
    "redundant_pair": "merge the two bullets and keep the stronger one.",
    "unsupported_claim": "support the claim with a concrete example.",
}
