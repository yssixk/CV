"""Faithfulness runner (Phase 10) — the secondary evaluation chapter.

Answers: "what fraction of LLM-generated sentences pass verification unmodified
vs. get rejected/rewritten?" on a sample of gold CVs. Requires only sentence-
level pass/fail judgments (no full extraction annotation), so a small random
sample suffices. To keep evaluation reproducible and offline, the runner can
replay *recorded* LLM responses (recorded once per model+prompt version) —
calling the live API during evaluation is optional and clearly flagged.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from cv_analyzer.explain.llm_feedback import rewrite_findings, LLMFeedbackResult
from cv_analyzer.explain.llm_verifier import verify_llm_result
from cv_analyzer.explain.report_builder import build_report
from cv_analyzer.models import Finding


@dataclass
class FaithfulnessResult:
    n_findings: int
    n_llm_sentences: int
    n_accepted: int
    n_rejected: int
    n_fallback: int
    acceptance_rate: float
    per_finding: list[dict] = field(default_factory=list)
    mode: str = "live"

    def summary(self) -> str:
        return (
            f"faithfulness [{self.mode}]: {self.n_accepted}/{self.n_llm_sentences} accepted "
            f"({self.acceptance_rate:.1%}), {self.n_rejected} rejected, "
            f"{self.n_fallback} API failures -> template fallback"
        )


def _sentence_fallback(finding: Finding) -> str:
    return finding.message


def run_faithfulness_on_findings(
    findings: list[Finding],
    language: str = "en",
    llm_result: LLMFeedbackResult | None = None,
    config=None,
) -> FaithfulnessResult:
    """Score one LLM feedback batch. ``llm_result`` may be a recorded replay."""
    from cv_analyzer.explain.llm_verifier import verify_llm_result  # local import avoids cycle

    if llm_result is None:
        llm_result = rewrite_findings(findings, language=language, config=config)
    verified = verify_llm_result(llm_result, findings)
    accepted = sum(1 for it in verified if it.llm_text is not None)
    rejected = sum(1 for it in verified if it.llm_text is None and (it.verification or {}).get("accepted") is False)
    fallback = sum(1 for it in verified
                   if it.llm_text is None and (it.verification or {}).get("accepted") is None)
    n = len(verified)
    return FaithfulnessResult(
        n_findings=len(findings),
        n_llm_sentences=n,
        n_accepted=accepted,
        n_rejected=rejected,
        n_fallback=fallback,
        acceptance_rate=accepted / n if n else 0.0,
        per_finding=[
            {
                "finding_id": it.finding_id,
                "accepted": it.llm_text is not None,
                "score": (it.verification or {}).get("score"),
                "reason": (it.verification or {}).get("reason"),
            }
            for it in verified
        ],
        mode="live" if llm_result.error is None else "replay",
    )


def run_faithfulness(
    annotations_path: Path,
    sample_size: int = 20,
    language: str = "en",
    text_loader=None,
    llm_result_factory=None,
) -> FaithfulnessResult:
    """Sample gold CVs, run the LLM layer, and report the acceptance rate."""
    from cv_analyzer.eval_harness.gold_set_runner import load_gold_items

    items = load_gold_items(annotations_path, text_loader)
    items = items[:sample_size]
    all_findings: list[Finding] = []
    for item in items:
        result = build_report(item.text, source_name=item.cv_id, use_nlp=False)
        all_findings.extend(result.report.findings[:5])   # cap per CV for cost control

    if not all_findings:
        return FaithfulnessResult(0, 0, 0, 0, 0, 0.0, mode="empty")

    if llm_result_factory is None:
        return run_faithfulness_on_findings(all_findings, language=language)
    # replay mode: a recorded batch keeps evaluation offline/reproducible
    llm_result = llm_result_factory(all_findings)
    return run_faithfulness_on_findings(all_findings, language=language, llm_result=llm_result)


def save_results(result: FaithfulnessResult, out_path: Path) -> None:
    out_path.write_text(json.dumps({
        "summary": result.summary(),
        "n_findings": result.n_findings,
        "n_llm_sentences": result.n_llm_sentences,
        "n_accepted": result.n_accepted,
        "n_rejected": result.n_rejected,
        "n_fallback": result.n_fallback,
        "acceptance_rate": result.acceptance_rate,
        "per_finding": result.per_finding,
    }, indent=2), encoding="utf-8")
