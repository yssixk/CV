"""Build a gold-annotation scaffold from the local ``resumes/`` corpus.

The 2,484-CV set (``resumes/Resume.csv`` + PDFs) is the evaluation set, not
training data. This script samples N CVs and emits an annotation scaffold:
for each sampled CV, the extracted text and empty gold fields for a human to
fill in (skills spans, education spans). Hand-annotation then feeds
``gold_set_runner.run_gold_set``.

Usage:
    python -m cv_analyzer.eval_harness.build_gold_sample \
        --csv resumes/Resume/Resume.csv --n 30 --out data/gold_set/annotations_scaffold.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def load_resume_texts(csv_path: Path, limit: int | None = None) -> list[dict]:
    """Load (id, category, text) records from the Kaggle Resume.csv."""
    import pandas as pd

    df = pd.read_csv(csv_path)
    if limit:
        df = df.head(limit)
    records = []
    for _, row in df.iterrows():
        records.append({
            "cv_id": str(row["ID"]),
            "category": str(row["Category"]),
            "text": str(row["Resume_str"]),
        })
    return records


def build_scaffold(records: list[dict], n: int, seed: int = 42) -> list[dict]:
    """Random-sample n CVs (seeded = reproducible sampling) into scaffold records."""
    rng = random.Random(seed)
    sampled = rng.sample(records, min(n, len(records)))
    scaffold = []
    for rec in sampled:
        scaffold.append({
            "cv_id": rec["cv_id"],
            "category": rec["category"],
            "text_file": "",                # annotator: path to saved text file, or paste below
            "text": rec["text"],            # kept here for convenience; move to text_file for large sets
            "skills": [],                   # annotator: [{"canonical": "SQL", "start": 0, "end": 0}]
            "education": [],                # annotator: [{"start": 0, "end": 0}]
            "notes": "",
        })
    return scaffold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="path to Resume.csv")
    parser.add_argument("--n", type=int, default=30, help="sample size")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    records = load_resume_texts(args.csv)
    scaffold = build_scaffold(records, args.n, seed=args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scaffold, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(scaffold)} scaffold records to {args.out}")
    print("next: hand-annotate skills/education spans, then run gold_set_runner.run_gold_set")


if __name__ == "__main__":
    main()
