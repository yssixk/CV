"""Eval harness tests: metrics math, two-mode runner, faithfulness replay mode."""
from __future__ import annotations

import json

import pytest

from cv_analyzer.eval_harness import metrics
from cv_analyzer.eval_harness.gold_set_runner import GoldItem, load_gold_items, run_gold_set, run_mode
from cv_analyzer.explain.report_builder import build_report
from cv_analyzer.eval_harness.faithfulness_runner import run_faithfulness_on_findings
from cv_analyzer.explain.llm_feedback import LLMFeedbackResult, RewrittenFinding
from cv_analyzer.models import Evidence, Finding


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def test_prf_perfect():
    gold = [("SQL", 0, 3), ("Python", 10, 16)]
    prf = metrics.prf_for_spans(gold, gold)
    assert prf.precision == 1.0 and prf.recall == 1.0 and prf.f1 == 1.0


def test_prf_lenient_overlap_counts_tp():
    pred = [("SQL", 0, 2)]          # gold span is (0,3) — lenient overlap
    gold = [("SQL", 0, 3)]
    prf = metrics.prf_for_spans(pred, gold)
    assert prf.tp == 1 and prf.precision == 1.0 and prf.recall == 1.0


def test_prf_strict_requires_exact_span():
    pred = [("SQL", 0, 2)]
    gold = [("SQL", 0, 3)]
    prf = metrics.prf_for_spans(pred, gold, strict=True)
    assert prf.tp == 0 and prf.precision == 0.0


def test_prf_label_mismatch_is_not_tp():
    pred = [("Java", 0, 3)]
    gold = [("SQL", 0, 3)]
    prf = metrics.prf_for_spans(pred, gold)
    assert prf.tp == 0 and prf.fp == 1 and prf.fn == 1


def test_prf_each_gold_matched_once():
    pred = [("SQL", 0, 3), ("SQL", 1, 4)]   # two preds overlap one gold
    gold = [("SQL", 0, 3)]
    prf = metrics.prf_for_spans(pred, gold)
    assert prf.tp == 1 and prf.fp == 1


def test_classification_accuracy():
    assert metrics.classification_accuracy(["a", "b", "a"], ["a", "b", "b"]) == pytest.approx(2 / 3)


def test_mrr():
    assert metrics.mean_reciprocal_rank([[False, True], [True]]) == pytest.approx(0.75)


def test_delta_table():
    b = {"skills": metrics.PRF(0.5, 0.5, 0.5, 5, 5, 5)}
    s = {"skills": metrics.PRF(0.7, 0.6, 0.65, 7, 3, 4)}
    delta = metrics.delta_table(b, s)
    assert delta["skills"]["delta_f1"] == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# gold-set runner (synthetic gold, NER disabled for CI determinism)
# ---------------------------------------------------------------------------

GOLD_DOCS = [
    {
        "cv_id": "synthetic_1",
        "text": (
            "BUDI SANTOSO\nSUMMARY\nHard worker with extensive experience.\n\n"
            "SKILLS\nPython, SQL, Docker\n\n"
            "EXPERIENCE\nAnalyst, Corp\nJan 2020 - Present\n- Responsible for various reports.\n\n"
            "EDUCATION\nBSc in Statistics, 2019, GPA 3.5\n"
        ),
        "skills": [],        # spans computed below from the text
        "education": [],
    },
]


def _with_spans(record):
    text = record["text"]
    skills = []
    for canonical, surface in [("Python", "Python"), ("SQL", "SQL"), ("Docker", "Docker")]:
        idx = text.find(surface)
        if idx >= 0:
            skills.append({"canonical": canonical, "start": idx, "end": idx + len(surface)})
    edu_idx = text.find("BSc in Statistics")
    record["skills"] = skills
    record["education"] = [{"start": edu_idx, "end": edu_idx + len("BSc in Statistics")}]
    return record


def test_gold_runner_two_modes_and_delta(tmp_path):
    records = [_with_spans(dict(r)) for r in GOLD_DOCS]
    path = tmp_path / "gold.json"
    path.write_text(json.dumps(records), encoding="utf-8")

    # force the NLP layer off so the test is deterministic offline
    from cv_analyzer.config import Config
    import cv_analyzer.explain.report_builder as rb

    cfg = Config(nlp_extractor_enabled=False)
    result = run_gold_set(path, nlp_available=False)
    assert result["n_docs"] == 1
    assert "skill_delta_f1" in result
    assert result["baseline"].startswith("mode=rules")
    # with NER disabled, system mode == baseline mode -> zero delta
    assert result["skill_delta_f1"] == 0.0


def test_run_mode_rules_only_scores():
    records = [_with_spans(dict(GOLD_DOCS[0]))]
    items = load_gold_items.__wrapped__ if False else None  # noqa: F841 (direct use below)
    from cv_analyzer.eval_harness.gold_set_runner import GoldItem

    rec = records[0]
    items = [GoldItem(
        cv_id=rec["cv_id"],
        text=rec["text"],
        skills=[(s["canonical"], s["start"], s["end"]) for s in rec["skills"]],
        education=[(e["start"], e["end"]) for e in rec["education"]],
    )]
    res = run_mode(items, use_nlp=False, ner_available=False)
    assert res.skill_prf["tp"] >= 3
    assert 0.0 <= res.skill_prf["f1"] <= 1.0


# ---------------------------------------------------------------------------
# faithfulness runner (replay mode, offline)
# ---------------------------------------------------------------------------

def _replay_factory(expected_messages):
    def factory(findings):
        items = []
        for i, f in enumerate(findings):
            # alternate faithful and hallucinated sentences
            if i % 2 == 0:
                text = f.message.replace("reads as", "reads as (rewritten)")
            else:
                text = "Your Kubernetes expertise and 300% growth are outstanding."
            items.append(RewrittenFinding(finding_id=i, original_message=f.message,
                                          llm_text=text, fallback_used=False))
        return LLMFeedbackResult(items=items, model="replay-model", params={"temperature": 0.0})
    return factory


def test_faithfulness_replay_counts_accept_and_reject(smoke_cv_text):
    result = build_report(smoke_cv_text, source_name="smoke", use_nlp=False)
    findings = result.report.findings[:4]
    assert findings, "fixture CV should produce findings"
    res = run_faithfulness_on_findings(findings, llm_result_factory:=None,
                                       llm_result=_replay_factory(findings)(findings))
    assert res.n_llm_sentences == len(findings)
    assert res.n_accepted + res.n_rejected + res.n_fallback == res.n_llm_sentences
    assert res.n_rejected >= 1, "hallucinated replay sentences must be rejected"


def test_faithfulness_empty():
    res = run_faithfulness_on_findings([])
    assert res.acceptance_rate == 0.0 and res.n_llm_sentences == 0
