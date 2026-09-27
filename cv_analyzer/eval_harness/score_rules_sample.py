"""Score the rules baseline on a real-corpus sample (pre-annotation sanity check).

This is NOT the thesis evaluation (that requires hand annotation via the
scaffold). It validates the harness end-to-end on real CV texts from
``resumes/Resume.csv`` by auto-deriving a lenient pseudo-gold: a skill is
"gold" if the canonical name appears as a standalone token anywhere in the
text (document-level, set-based). Expect this to OVERESTIMATE recall for
rules (the pseudo-gold is lexical) — the printed caveat says so, and the
scaffold + hand annotation replaces it before any thesis number is reported.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cv_analyzer.eval_harness.build_gold_sample import load_resume_texts
from cv_analyzer.eval_harness.metrics import prf_for_sets
from cv_analyzer.explain.report_builder import build_report
from cv_analyzer.utils.gazetteer_loader import load_gazetteer


def _surface_to_canonical() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, spec in load_gazetteer("skills_en").items():
        for alias in spec.get("aliases", []):
            lookup[alias.lower()] = canonical
    return lookup


def _pseudo_gold_skills(text: str, lookup: dict[str, str]) -> set[str]:
    """Document-level pseudo-gold: alias appears as a standalone token (or phrase)."""
    import re

    low = text.lower()
    gold: set[str] = set()
    for alias, canonical in lookup.items():
        pattern = r"(?<![a-z0-9+#])" + re.escape(alias) + r"(?![a-z0-9+#])"
        if re.search(pattern, low):
            gold.add(canonical)
    return gold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("resumes/Resume/Resume.csv"))
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    import random

    rng = random.Random(args.seed)
    records = load_resume_texts(args.csv)
    sampled = rng.sample(records, min(args.n, len(records)))

    lookup = _surface_to_canonical()
    per_doc = []
    all_pred: set[str] = set()
    all_gold: set[str] = set()

    for rec in sampled:
        result = build_report(rec["text"], source_name=rec["cv_id"], use_nlp=False)
        extraction = result.report.extraction
        pred = extraction.skill_canonicals() if extraction else set()
        gold = _pseudo_gold_skills(rec["text"], lookup)
        all_pred |= pred
        all_gold |= gold
        per_doc.append({
            "cv_id": rec["cv_id"],
            "category": rec["category"],
            "n_pred": len(pred),
            "n_gold": len(gold),
        })

    corpus_prf = prf_for_sets(all_pred, all_gold)
    print("=== Rules baseline vs LEXICAL pseudo-gold (overestimates recall — NOT a thesis number) ===")
    print(f"docs: {len(sampled)}")
    print(f"corpus-level skill P/R/F1: {corpus_prf.precision:.3f} / {corpus_prf.recall:.3f} / {corpus_prf.f1:.3f}")
    print(f"docs with zero predictions: {sum(1 for d in per_doc if d['n_pred'] == 0)}")
    print(f"scaffold ready: hand-annotate data/gold_set/annotations_scaffold.json for the real evaluation")


if __name__ == "__main__":
    main()
