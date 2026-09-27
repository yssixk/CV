"""Shared data model.

Hard project rules enforced here (see PROJECT_BLUEPRINT.md §1.1):
- Every ``Finding`` must carry at least one ``Evidence`` entry; constructing an
  evidence-free finding raises immediately. No ungrounded claims, ever.
- ``Evidence.text`` is always an *exact* slice of the analyzed document
  (``end - start == len(text)``), so every claim can be checked against the
  source by offset.

All types are plain dataclasses with no framework coupling so the evaluation
harness can call any module in isolation.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

# Canonical segment names (also used as language for report templates)
SEGMENT_SUMMARY = "summary"
SEGMENT_EDUCATION = "education"
SEGMENT_EXPERIENCE = "experience"
SEGMENT_SKILLS = "skills"
SEGMENT_OTHER = "other"
SEGMENT_DOCUMENT = "document"        # whole-document findings
SEGMENT_JOB_DESCRIPTION = "job_description"

CANONICAL_SEGMENTS = (SEGMENT_SUMMARY, SEGMENT_EDUCATION, SEGMENT_EXPERIENCE, SEGMENT_SKILLS)


@dataclass(frozen=True)
class Evidence:
    """A verbatim span of source text. ``text`` MUST equal ``document[start:end]``."""

    text: str
    start: int
    end: int
    source_segment: str = SEGMENT_DOCUMENT
    line_number: int | None = None   # 1-based source line, when known

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or len(self.text) == 0:
            raise ValueError("Evidence.text must be a non-empty string")
        if self.start < 0 or self.end <= self.start:
            raise ValueError(f"Evidence offsets invalid: [{self.start}, {self.end})")
        if self.end - self.start != len(self.text):
            raise ValueError(
                f"Evidence span/length mismatch: text has {len(self.text)} chars "
                f"but offsets span {self.end - self.start}"
            )

    @classmethod
    def from_span(cls, document_text: str, start: int, end: int, source_segment: str) -> "Evidence":
        """Build evidence by slicing — guarantees the exact-span invariant."""
        return cls(text=document_text[start:end], start=start, end=end, source_segment=source_segment)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Finding:
    """One analysis output. Advisory-only: messages describe the CV text, never the person."""

    kind: str                     # e.g. "vague_bullet", "redundant_pair", "unsupported_claim"
    message: str                  # human-readable, template-generated
    evidence: list[Evidence] = field(default_factory=list)
    confidence: float | None = None
    details: dict[str, Any] = field(default_factory=dict)   # structured slots for templates

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError(f"Finding of kind {self.kind!r} must carry at least one Evidence entry")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be within [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "confidence": self.confidence,
            "details": self.details,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class Segment:
    """A contiguous region of the document assigned to one canonical CV section."""

    name: str                     # canonical: summary/education/experience/skills/other
    heading: str                  # the matched heading line ("" if inferred)
    start: int
    end: int                      # offsets into the full document text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Bullet:
    """A single line-level text unit (usually a sentence or bullet line)."""

    text: str                     # exact slice of the document (may include trailing newline)
    start: int
    end: int
    segment: str
    line_number: int              # 1-based line number in the document

    @property
    def stripped(self) -> str:
        return self.text.strip()

    @property
    def stripped_span(self) -> tuple[int, int]:
        """Offsets of ``stripped`` within the document (whitespace-adjusted).

        Guarantees ``document[stripped_span[0]:stripped_span[1]] == stripped``
        so evidence built from it satisfies the exact-span invariant.
        """
        lead = len(self.text) - len(self.text.lstrip())
        return (self.start + lead, self.start + lead + len(self.stripped))


@dataclass
class CVDocument:
    """Result of ingestion + segmentation."""

    text: str
    source_name: str              # internal (UUID-based) name — never the user's filename
    segments: list[Segment] = field(default_factory=list)
    bullets: list[Bullet] = field(default_factory=list)

    def segment_of(self, name: str) -> Segment | None:
        for seg in self.segments:
            if seg.name == name:
                return seg
        return None

    def bullets_in(self, name: str) -> list[Bullet]:
        return [b for b in self.bullets if b.segment == name]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "text": self.text,
            "segments": [s.to_dict() for s in self.segments],
            "bullets": [asdict(b) for b in self.bullets],
        }


@dataclass
class SkillMention:
    canonical: str
    text: str
    start: int
    end: int
    segment: str
    extractor: str                # "rules" | "nlp" | "rules+nlp"

    def to_evidence(self) -> Evidence:
        return Evidence(text=self.text, start=self.start, end=self.end, source_segment=self.segment)


@dataclass
class ExperienceEntry:
    title: str | None
    company: str | None
    start_date: str | None
    end_date: str | None
    start: int
    end: int
    segment: str
    text: str = ""  # verbatim line this entry came from

    def to_evidence(self) -> Evidence:
        return Evidence(text=self.text, start=self.start, end=self.end, source_segment=self.segment)


@dataclass
class EducationEntry:
    degree: str | None
    field_of_study: str | None
    institution: str | None
    gpa: str | None
    start: int
    end: int
    segment: str
    text: str = ""  # verbatim line this entry came from


@dataclass
class EntityMention:
    """A generic NER entity (ORG/PER/MISC) from the NLP extractor layer."""

    label: str                    # "ORG" | "PER" | "MISC"
    canonical: str                # surface form (upper-cased, normalized)
    text: str
    start: int
    end: int
    segment: str
    extractor: str = "nlp"

    def to_evidence(self) -> Evidence:
        return Evidence(text=self.text, start=self.start, end=self.end, source_segment=self.segment)


@dataclass
class ExtractionResult:
    """Output of an extractor (rules baseline, NLP layer, or merged)."""

    skills: list[SkillMention] = field(default_factory=list)
    experiences: list[ExperienceEntry] = field(default_factory=list)
    education: list[EducationEntry] = field(default_factory=list)
    entities: list[EntityMention] = field(default_factory=list)
    extractor_name: str = "unknown"

    def skill_canonicals(self) -> set[str]:
        return {s.canonical for s in self.skills}

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractor_name": self.extractor_name,
            "skills": [asdict(s) for s in self.skills],
            "experiences": [asdict(e) for e in self.experiences],
            "education": [asdict(e) for e in self.education],
            "entities": [asdict(e) for e in self.entities],
        }


@dataclass
class LangLabel:
    """Per-segment language identification result."""

    lang: str                     # "en" | "id" | "mixed" | "other"
    confidence: float | None
    method: str                   # "langdetect" | "wordlist" | "combined"


@dataclass
class StatementType:
    """Classification of one bullet's rhetorical type (Phase 6)."""

    bullet_start: int
    bullet_end: int
    label: str                    # "achievement" | "duty" | "responsibility" | "other"
    confidence: float | None
    cues_matched: list[str] = field(default_factory=list)


@dataclass
class RelevanceArea:
    """One matched or unmatched area between the CV and a job description (Phase 5)."""

    requirement_text: str         # verbatim requirement sentence from the JD
    matched_bullet_text: str | None
    similarity: float
    matched: bool


@dataclass
class RelevanceResult:
    requirement: str              # full pasted job description text
    areas: list[RelevanceArea] = field(default_factory=list)

    @property
    def matched_count(self) -> int:
        return sum(1 for a in self.areas if a.matched)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "areas": [asdict(a) for a in self.areas],
            "matched_count": self.matched_count,
        }


@dataclass
class Report:
    """Final structured, evidence-grounded report. Fully computable with no LLM call."""

    document: CVDocument
    summary_sentences: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    extraction: ExtractionResult | None = None
    completeness: dict[str, bool] = field(default_factory=dict)
    relevance: RelevanceResult | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary_sentences": self.summary_sentences,
            "findings": [f.to_dict() for f in self.findings],
            "extraction": self.extraction.to_dict() if self.extraction else None,
            "completeness": self.completeness,
            "relevance": self.relevance.to_dict() if self.relevance else None,
            "meta": self.meta,
        }
