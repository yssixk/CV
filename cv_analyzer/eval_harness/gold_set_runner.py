"""Gold-set runner (Phase 10) — the single most important script for the thesis.

Runs the full pipeline over annotated CVs in two modes:
  - rules-only   (use_nlp=False)
  - rules+NLP    (use_nlp=True)
and reports per-feature P/R/F1 and the delta between the two — the empirical
evidence that the NLP layer adds value over the deterministic baseline.

Gold annotation format (JSON, one file per CV):
{
  "cv_file": "resumes/data/data/ADMIN/12345.pdf" | "path/to/cv.txt",
  "text_file": "path/to/extracted_text.txt"        (optional; else extracted)
  "skills":    [{"canonical": "SQL", "start": 210, "end": 213}],
  "education": [{"start": 900, "end": 990}]
}

Spans are character offsets into the extracted text. For the 2,484-CV set in
``resumes/`` (PDF + Resume.csv text), hand-annotating a sample is enough: the
brief allows a smaller annotated subset for the delta, and the rest serves the
faithfulness runner.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cv_analyzer.explain.report_builder import build_report
from cv_analyzer.ingest.extract_text import ingest_text


@dataclass
class GoldItem:
    cv_id: str
    text: str
    skills: list[tuple[str, int, int]] = field(default_factory=list)
    education: list[tuple[int, int]] = field(default_factory=list)


@dataclass
class RunnerResult:
    mode: str
    n_docs: int
    skill_prf: dict
    education_prf: dict
    per_doc: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"mode={self.mode} n={self.n_docs} "
            f"skills P/R/F1={self.skill_prf['precision']:.3f}/{self.skill_prf['recall']:.3f}/{self.skill_prf['f1']:.3f} "
            f"education P/R/F1={self.education_prf['precision']:.3f}/{self.education_prf['recall']:.3f}/{self.education_prf['f1']:.3f}"
        )


def load_gold_items(annotations_path: Path, text_loader=None) -> list[GoldItem]:
    """Load gold annotations. ``text_loader(cv_id, record)`` returns the CV text."""
    items: list[GoldItem] = []
    with open(annotations_path, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    for rec in records:
        cv_id = rec["cv_id"]
        if text_loader is not None:
            text = text_loader(cv_id, rec)
        elif "text_file" in rec:
            text = Path(rec["text_file"]).read_text(encoding="utf-8")
        elif "text" in rec:
            text = rec["text"]
        else:
            raise ValueError(f"gold record {cv_id} has no text source")
        items.append(
            GoldItem(
                cv_id=cv_id,
                text=text,
                skills=[(s["canonical"], s["start"], s["end"]) for s in rec.get("skills", [])],
                education=[(e["start"], e["end"]) for e in rec.get("education", [])],
            )
        )
    return items


def run_mode(items: list[GoldItem], use_nlp: bool, ner_available: bool | None = None) -> RunnerResult:
    """Run one extraction mode over all gold items and score it.

    ``ner_available=False`` forces the NLP layer fully OFF (no model load, no
    download attempt) so the harness stays hermetic when the transformer
    backend is not usable — the system mode then degrades to rules-only and
    the reported delta is honestly zero.
    """
    from cv_analyzer.config import Config
    from cv_analyzer.eval_harness.metrics import prf_for_spans

    skill_preds: list[tuple[str, int, int]] = []
    skill_golds: list[tuple[str, int, int]] = []
    edu_preds: list[tuple[int, int]] = []      # label "" per span
    edu_golds: list[tuple[int, int]] = []
    per_doc: list[dict] = []

    # rules-only mode, or system mode with NER explicitly unavailable:
    # disable the NLP layer at config level so nothing attempts a model load.
    disable_nlp = (not use_nlp) or (ner_available is False)
    cfg = Config(nlp_extractor_enabled=False) if disable_nlp else None

    for item in items:
        result = build_report(item.text, source_name=item.cv_id, use_nlp=use_nlp, config=cfg)
        extraction = result.report.extraction
        assert extraction is not None
        doc_preds = [(s.canonical, s.start, s.end) for s in extraction.skills]
        doc_golds = list(item.skills)
        skill_preds.extend(doc_preds)
        skill_golds.extend(doc_golds)
        edu_preds.extend([(e.start, e.end) for e in extraction.education])
        edu_golds.extend(item.education)
        per_doc.append({
            "cv_id": item.cv_id,
            "pred_skills": len(doc_preds),
            "gold_skills": len(doc_golds),
        })

    skill_prf = prf_for_spans(skill_preds, skill_golds).as_dict()
    edu_prf = prf_for_spans(
        [("", s, e) for s, e in edu_preds], [("", s, e) for s, e in edu_golds]
    ).as_dict()
    mode_name = "rules+nlp" if use_nlp and ner_available is not False else "rules"
    return RunnerResult(mode=mode_name, n_docs=len(items), skill_prf=skill_prf,
                        education_prf=edu_prf, per_doc=per_doc)


def run_gold_set(
    annotations_path: Path,
    text_loader=None,
    nlp_available: bool | None = None,
) -> dict:
    """Full two-mode run + delta table. If NER can't load, the delta is rules-vs-rules."""
    from cv_analyzer.eval_harness.metrics import delta_table, prf_for_spans

    items = load_gold_items(annotations_path, text_loader)
    baseline = run_mode(items, use_nlp=False, ner_available=False)
    system = run_mode(items, use_nlp=True, ner_available=nlp_available)

    skill_delta = delta_table(
        {"skills": prf_for_spans([], [])}, {"skills": prf_for_spans([], [])}
    )  # placeholder to keep import shape; real delta computed below
    skill_b = baseline.skill_prf
    skill_s = system.skill_prf
    edu_b = baseline.education_prf
    edu_s = system.education_prf
    return {
        "baseline": baseline.summary(),
        "system": system.summary(),
        "skill_delta_f1": round(skill_s["f1"] - skill_b["f1"], 4),
        "skill_delta_recall": round(skill_s["recall"] - skill_b["recall"], 4),
        "skill_delta_precision": round(skill_s["precision"] - skill_b["precision"], 4),
        "education_delta_f1": round(edu_s["f1"] - edu_b["f1"], 4),
        "n_docs": baseline.n_docs,
        "per_doc": baseline.per_doc,
    }
