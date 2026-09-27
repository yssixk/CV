"""PII redaction — applied before ANY text reaches the Gemini API.

This includes quoted evidence spans inside ``Finding`` messages, not just the
full CV text. Redaction is never applied in the local pipeline (which must keep
exact source offsets); it runs only at the LLM boundary in
``explain/llm_feedback.py``.

Detects: emails, phone numbers (international, +62/Indonesian mobile, US-style),
and a heuristic full name from the document header. Offsets in the returned
mapping are into the *redacted* string.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
)
PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?\d{3,4}[\s.-]?\d{3,4}(?:[\s.-]?\d{2,5})?"
)
URL_RE = re.compile(r"https?://\S+|www\.\S+|linkedin\.com/\S+|github\.com/\S+", re.IGNORECASE)

# heuristic full-name line: 2-4 capitalized words on the first non-empty line
NAME_LINE_RE = re.compile(
    r"^\s*[A-Z][a-z]+(?:['’\-][A-Z][a-z]+)?(?:\s+[A-Z][a-z]+(?:['’\-][A-Z][a-z]+)?){1,3}\s*$"
)

EMAIL_TOKEN = "[EMAIL]"
PHONE_TOKEN = "[PHONE]"
URL_TOKEN = "[URL]"
NAME_TOKEN = "[NAME]"


@dataclass(frozen=True)
class RedactionResult:
    redacted_text: str
    n_emails: int
    n_phones: int
    n_urls: int
    name_redacted: bool

    @property
    def n_replacements(self) -> int:
        return self.n_emails + self.n_phones + self.n_urls + int(self.name_redacted)


def _redact_pattern(text: str, pattern: re.Pattern[str], token: str) -> tuple[str, int]:
    return pattern.subn(token, text)


def redact_name_line(text: str) -> tuple[str, bool]:
    """Replace a plausible full-name line at the very top of the text."""
    lines = text.split("\n")
    for i, line in enumerate(lines[:5]):           # only the top of the document
        if not line.strip():
            continue
        if NAME_LINE_RE.match(line):
            lines[i] = NAME_TOKEN
            return "\n".join(lines), True
        break                                      # first non-empty line only
    return text, False


def redact_text(text: str) -> RedactionResult:
    """Redact emails, phones, URLs, and a header name line from ``text``."""
    out, n_emails = _redact_pattern(text, EMAIL_RE, EMAIL_TOKEN)
    out, n_urls = _redact_pattern(out, URL_RE, URL_TOKEN)
    # phone pass: URL/emails already tokenized, so we won't mangle them
    out, n_phones = _redact_pattern(out, PHONE_RE, PHONE_TOKEN)
    out, name_done = redact_name_line(out)
    return RedactionResult(
        redacted_text=out,
        n_emails=n_emails,
        n_phones=n_phones,
        n_urls=n_urls,
        name_redacted=name_done,
    )


def redact_findings_text(*texts: str) -> list[str]:
    """Convenience: redact several strings (e.g. finding message + evidence quotes)."""
    return [redact_text(t).redacted_text for t in texts]
