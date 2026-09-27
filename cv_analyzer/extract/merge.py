"""Merge logic (menu 2e): rules baseline + NLP layer with documented precedence.

Precedence policy (recorded in DECISIONS.md menu 2):
1. Skills: rules win on overlap. An NLP skill mention overlapping a rules
   mention of the same canonical is dropped; NLP mentions of a *new* canonical
   that the rules layer missed are added with extractor="rules+nlp" so the
   provenance of the improvement stays visible in the report.
2. Entities (ORG/PER) come only from the NLP layer (rules layer has no NER).
3. Experience/education entries: rules layer only (regex on dates/degrees);
   NLP ORG spans near a date range may later enrich entries (out of scope for
   this build — recorded as future work).
"""
from __future__ import annotations

from cv_analyzer.models import ExtractionResult, SkillMention


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def merge_extraction(
    rules_result: ExtractionResult,
    nlp_result: ExtractionResult | None,
) -> ExtractionResult:
    """Merge rules + NLP results. ``nlp_result=None`` degrades to rules-only."""
    if nlp_result is None:
        return ExtractionResult(
            skills=list(rules_result.skills),
            experiences=list(rules_result.experiences),
            education=list(rules_result.education),
            entities=[],
            extractor_name="rules",
        )

    merged_skills: list[SkillMention] = list(rules_result.skills)
    for nlp_skill in nlp_result.skills:
        overlaps_rules = any(
            _overlaps(nlp_skill.start, nlp_skill.end, r.start, r.end) and r.canonical == nlp_skill.canonical
            for r in rules_result.skills
        )
        if not overlaps_rules:
            merged_skills.append(
                SkillMention(
                    canonical=nlp_skill.canonical,
                    text=nlp_skill.text,
                    start=nlp_skill.start,
                    end=nlp_skill.end,
                    segment=nlp_skill.segment,
                    extractor="rules+nlp",
                    )
            )

    # de-duplicate identical spans from both extractors (keep rules provenance)
    seen: set[tuple[int, int, str]] = set()
    deduped: list[SkillMention] = []
    for m in sorted(merged_skills, key=lambda x: (x.start, -(x.end - x.start))):
        key = (m.start, m.end, m.canonical)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)

    return ExtractionResult(
        skills=deduped,
        experiences=list(rules_result.experiences),
        education=list(rules_result.education),
        entities=list(nlp_result.entities),
        extractor_name="rules+nlp",
    )
