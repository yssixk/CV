"""Evaluation metrics (Phase 10): set-based P/R/F1, ranking quality, accuracy.

Designed for span-level comparison against a gold set: predictions are
(canonical, start, end) triples; matches are counted if the predicted span
overlaps a gold span of the same canonical label (lenient overlap), or exactly
(strict mode) — both are reported so the thesis can show both numbers.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PRF:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int

    def as_dict(self) -> dict[str, float | int]:
        return {"precision": round(self.precision, 4), "recall": round(self.recall, 4),
                "f1": round(self.f1, 4), "tp": self.tp, "fp": self.fp, "fn": self.fn}


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def prf_for_spans(
    predicted: list[tuple[str, int, int]],
    gold: list[tuple[str, int, int]],
    strict: bool = False,
) -> PRF:
    """Span-level P/R/F1. Lenient: same label + any overlap = TP (each gold matched once)."""
    matched_gold: set[int] = set()
    tp = 0
    for label, s, e in predicted:
        for i, (glabel, gs, ge) in enumerate(gold):
            if i in matched_gold:
                continue
            label_ok = label == glabel
            span_ok = (s, e) == (gs, ge) if strict else _overlaps((s, e), (gs, ge))
            if label_ok and span_ok:
                tp += 1
                matched_gold.add(i)
                break
    fp = len(predicted) - tp
    fn = len(gold) - tp
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return PRF(precision, recall, f1, tp, fp, fn)


def prf_for_sets(predicted: set[str], gold: set[str]) -> PRF:
    """Set-based P/R/F1 (e.g. canonical skills per document)."""
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return PRF(precision, recall, f1, tp, fp, fn)


def classification_accuracy(predicted: list[str], gold: list[str]) -> float:
    if len(predicted) != len(gold):
        raise ValueError("predicted/gold length mismatch")
    return sum(p == g for p, g in zip(predicted, gold)) / len(gold) if gold else 0.0


def mean_reciprocal_rank(ranked_lists: list[list[bool]]) -> float:
    """MRR over ranked relevance lists (True = relevant item)."""
    reciprocal_sum, n = 0.0, 0
    for ranked in ranked_lists:
        n += 1
        for rank, relevant in enumerate(ranked, 1):
            if relevant:
                reciprocal_sum += 1.0 / rank
                break
    return reciprocal_sum / n if n else 0.0


def delta_table(
    baseline: dict[str, PRF], system: dict[str, PRF]
) -> dict[str, dict[str, float]]:
    """Per-feature baseline-vs-system delta — the thesis's core table."""
    out: dict[str, dict[str, float]] = {}
    for feature in baseline:
        b, s = baseline[feature], system.get(feature)
        if s is None:
            continue
        out[feature] = {
            "baseline_f1": round(b.f1, 4),
            "system_f1": round(s.f1, 4),
            "delta_f1": round(s.f1 - b.f1, 4),
            "baseline_recall": round(b.recall, 4),
            "system_recall": round(s.recall, 4),
            "delta_recall": round(s.recall - b.recall, 4),
        }
    return out
