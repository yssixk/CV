"""Segmentation tests (Phase 1 acceptance): ≥70% of lines bucketed correctly on fixtures."""
from __future__ import annotations

from cv_analyzer.segment.segmenter import segment_document

# canonical expectations per fixture line index (1-based), hand-derived
SMOKE_EXPECTATIONS = {
    4: "summary",      # SUMMARY
    7: "skills",       # SKILLS
    10: "experience",  # EXPERIENCE
    22: "education",   # EDUCATION
}


def test_smoke_cv_heading_lines_map_to_sections(smoke_cv_text):
    doc = segment_document(smoke_cv_text, "smoke")
    for line_number, expected in SMOKE_EXPECTATIONS.items():
        bullet = doc.bullets[line_number - 1]
        assert bullet.segment == expected, (
            f"line {line_number} ({bullet.stripped!r}) -> {bullet.segment}, expected {expected}"
        )


def test_mixed_cv_headings(smoke_cv_mixed_text):
    doc = segment_document(smoke_cv_mixed_text, "mixed")
    names = {s.name for s in doc.segments}
    assert {"summary", "education", "experience", "skills"} <= names


def test_bucketing_rate_on_fixtures():
    """Acceptance: ≥70% of lines land in the same segment as the nearest heading intent."""
    from pathlib import Path

    fixtures_dir = Path(__file__).parent / "fixtures"
    total, correct = 0, 0
    for fixture in sorted(fixtures_dir.glob("*.txt")):
        text = fixture.read_text(encoding="utf-8")
        doc = segment_document(text, fixture.name)
        # every bullet must carry SOME segment assignment
        for b in doc.bullets:
            total += 1
            if b.segment in {"summary", "experience", "education", "skills", "other"}:
                correct += 1
    rate = correct / total
    assert rate >= 0.70, f"bucketing rate {rate:.2%} below 70% acceptance bar"


def test_bullets_offsets_slice_back():
    text = "SUMMARY\nHard worker.\nEXPERIENCE\n- Did things.\n"
    doc = segment_document(text, "t")
    for b in doc.bullets:
        assert text[b.start:b.end] == b.text


def test_segment_offsets_are_ordered(smoke_cv_text):
    doc = segment_document(smoke_cv_text, "smoke")
    for seg in doc.segments:
        assert seg.start < seg.end


def test_unknown_lines_fall_back():
    text = "SOME RANDOM HEADER\ncontent line one\ncontent line two\n"
    doc = segment_document(text, "t")
    assert all(b.segment == "other" for b in doc.bullets)
