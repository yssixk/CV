"""Language identification: per-segment EN/ID/mixed classification.

Two methods, per DECISIONS.md menu 4:
- ``langdetect`` (4a) — decent on longer text, known-weak on short bullets.
- wordlist/morphology classifier (4b) — deterministic, tuned for CV jargon:
  scores function words + Indonesian affix markers; product names (which are
  neither) don't pollute the signal. Handles mixed bullets by span.

Policy: bullets with >= 8 tokens go to langdetect; shorter ones go to the
wordlist classifier; wildly disagreeing results are labeled "mixed".
"""
from __future__ import annotations

import re
from functools import lru_cache

from cv_analyzer.models import LangLabel
from cv_analyzer.utils.gazetteer_loader import load_gazetteer

# --- deterministic wordlists (kept inline: tiny, inspectable, testable) ----
EN_FUNCTION_WORDS = {
    "the", "a", "an", "and", "or", "but", "with", "for", "from", "in", "on", "at",
    "to", "of", "by", "as", "is", "are", "was", "were", "be", "been", "this", "that",
    "these", "those", "it", "its", "their", "our", "my", "his", "her", "which", "while",
    "during", "after", "before", "about", "into", "over", "under", "than", "then", "also",
}
ID_FUNCTION_WORDS = {
    "dan", "atau", "tetapi", "dengan", "untuk", "dari", "di", "ke", "pada", "dalam",
    "adalah", "ialah", "yaitu", "yang", "ini", "itu", "saya", "kami", "kita", "anda",
    "oleh", "sebagai", "kepada", "akan", "telah", "sedang", "tidak", "bisa", "dapat",
    "agar", "serta", "selama", "setelah", "sebelum", "hingga", "sampai", "antara",
    "semua", "setiap", "para", "para*", "juga", "masih", "sudah", "belum", "ada",
}
ID_AFFIX_MARKERS = (
    "meng", "meny", "mem", "men", "peng", "peny", "pem", "pen", "ber", "ter", "per", "di", "ke",
)
ID_SUFFIXES = ("kan", "an", "i", "nya", "lah", "kah")

WORD_RE = re.compile(r"[A-Za-z]+")
SHORT_BULLET_TOKENS = 8
MIXED_RATIO = 0.34  # if the minority language carries >= ~1/3 of the signal, call it mixed


def _tokens(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


def _wordlist_scores(text: str) -> tuple[float, float]:
    """Return (en_score, id_score). Normalized to the token count."""
    tokens = _tokens(text)
    if not tokens:
        return 0.0, 0.0
    en = sum(1 for t in tokens if t in EN_FUNCTION_WORDS)
    id_hits = sum(1 for t in tokens if t in ID_FUNCTION_WORDS)
    # Indonesian morphology: affix markers on content words
    for t in tokens:
        if t in EN_FUNCTION_WORDS or t in ID_FUNCTION_WORDS:
            continue
        if len(t) > 5 and any(t.startswith(m) for m in ID_AFFIX_MARKERS) and any(t.endswith(s) for s in ID_SUFFIXES):
            id_hits += 1
    n = len(tokens)
    return en / n, id_hits / n


def wordlist_classify(text: str) -> LangLabel:
    """Deterministic classifier: EN vs ID vs mixed, by function-word ratio."""
    en, idn = _wordlist_scores(text)
    total = en + idn
    if total == 0:
        return LangLabel(lang="other", confidence=None, method="wordlist")
    en_share = en / total
    id_share = idn / total
    if en_share >= 1 - MIXED_RATIO and id_share >= MIXED_RATIO:
        label = "mixed"
    elif id_share >= 1 - MIXED_RATIO and en_share >= MIXED_RATIO:
        label = "mixed"
    elif en_share > id_share:
        label = "en"
    else:
        label = "id"
    confidence = abs(en_share - id_share)
    return LangLabel(lang=label, confidence=round(confidence, 3), method="wordlist")


@lru_cache(maxsize=4096)
def _langdetect_cached(text: str) -> tuple[str, float]:
    from langdetect import DetectorFactory, detect_langs

    DetectorFactory.seed = 42  # langdetect is stochastic unless seeded — reproducibility
    langs = detect_langs(text)
    if not langs:
        return "other", 0.0
    top = langs[0]
    return top.lang, float(top.prob)


def langdetect_classify(text: str) -> LangLabel:
    """Wrapper around langdetect with a fixed seed (deterministic)."""
    try:
        lang, prob = _langdetect_cached(text)
    except Exception:  # noqa: BLE001 — langdetect raises LangDetectException on junk
        return LangLabel(lang="other", confidence=None, method="langdetect")
    if lang not in {"en", "id"}:
        return LangLabel(lang="other", confidence=prob, method="langdetect")
    return LangLabel(lang=lang, confidence=prob, method="langdetect")


def classify_language(text: str) -> LangLabel:
    """Classify one segment/bullet. Long text -> langdetect; short -> wordlist.

    Disagreement between the two on long text is resolved toward "mixed" when
    both languages carry substantial signal, else the higher-confidence wins.
    """
    stripped = text.strip()
    if not stripped:
        return LangLabel(lang="other", confidence=None, method="combined")

    tokens = _tokens(stripped)
    if len(tokens) < SHORT_BULLET_TOKENS:
        return wordlist_classify(stripped)

    long_result = langdetect_classify(stripped)
    short_result = wordlist_classify(stripped)
    if long_result.lang == short_result.lang:
        return long_result
    if {long_result.lang, short_result.lang} == {"en", "id"}:
        return LangLabel(lang="mixed", confidence=min(long_result.confidence or 0.5, 0.9), method="combined")
    return long_result if (long_result.confidence or 0) >= (short_result.confidence or 0) else short_result
