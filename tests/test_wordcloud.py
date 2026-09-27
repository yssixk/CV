"""Wordcloud tests: determinism, alias merging, file output, empty-input error."""
from __future__ import annotations

from cv_analyzer.explain.wordcloud_gen import (
    generate_finding_cloud,
    generate_skill_cloud,
    word_frequencies,
)
from cv_analyzer.models import Evidence, Finding


def test_frequencies_merge_aliases():
    freq = word_frequencies(["Skilled in js and JavaScript, plus javascript frameworks."])
    # js + JavaScript + javascript all map to the "javascript" canonical
    assert freq.get("javascript", 0) == 3
    assert "js" not in freq


def _ev(text: str, start: int = 0) -> Evidence:
    return Evidence(text=text, start=start, end=start + len(text), source_segment="experience")


def test_frequencies_drop_stopwords():
    freq = word_frequencies(["Responsible for the reports and the dashboards."])
    assert "the" not in freq and "and" not in freq and "for" not in freq
    assert freq.get("reports", 0) == 1 and freq.get("dashboards", 0) == 1


def test_cloud_is_deterministic(tmp_path):
    """Same input -> byte-identical PNG (seeded), required for the paper."""
    texts = ["Built REST APIs with Python and SQL for 5000 users.",
             "Responsible for various dashboards."]
    p1, p2 = tmp_path / "a.png", tmp_path / "b.png"
    generate_skill_cloud(texts, p1)
    generate_skill_cloud(texts, p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_cloud_default_is_color(tmp_path):
    """Default output: BERWARNA (pengecualian wordcloud) — valid PNG with color."""
    from PIL import Image

    p = tmp_path / "wc.png"
    generate_skill_cloud(["Python Python Python SQL Machine Learning dashboards"], p)
    img = Image.open(p)
    assert img.format == "PNG"
    rgb = img.convert("RGB")
    pixels = list(rgb.getdata())[::997]
    colored = [px for px in pixels if px[0] != px[1] or px[1] != px[2]]
    assert colored, "default wordcloud should contain colored pixels"


def test_cloud_grayscale_option(tmp_path):
    """grayscale=True still available for a black-and-white figure."""
    from PIL import Image

    p = tmp_path / "wc_gray.png"
    generate_skill_cloud(["Python Python Python SQL Machine Learning dashboards"], p,
                         grayscale=True)
    img = Image.open(p).convert("RGB")
    pixels = list(img.getdata())[::997]
    colored = [px for px in pixels if px[0] != px[1] or px[1] != px[2]]
    assert not colored, "grayscale option must produce only gray pixels"


def test_finding_cloud(tmp_path):
    findings = [
        Finding(kind="vague_bullet", message="Line 3 reads as a duty rather than an achievement.",
                evidence=[_ev("Responsible for reports.")]),
        Finding(kind="vague_bullet", message="Line 9 reads as a duty rather than an achievement.",
                evidence=[_ev("Helped with tasks.")]),
    ]
    p = tmp_path / "f.png"
    generate_finding_cloud(findings, p)
    assert p.exists() and p.stat().st_size > 0


def test_empty_input_raises():
    import pytest

    with pytest.raises(ValueError):
        generate_skill_cloud([], "unused.png")
