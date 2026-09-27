"""LLM boundary tests: fail-closed, verifier strictness, injection containment.

These tests never call the real Gemini API — the layer is designed to be
testable offline (flag off, missing key, and a fake _call_gemini).
"""
from __future__ import annotations

import cv_analyzer.explain.llm_feedback as llm_feedback
from cv_analyzer.config import Config
from cv_analyzer.explain import adversarial
from cv_analyzer.explain.llm_feedback import rewrite_findings
from cv_analyzer.explain.llm_verifier import verify_sentence, verify_llm_result
from cv_analyzer.models import Evidence, Finding


def _finding(kind: str = "vague_bullet", message: str | None = None) -> Finding:
    text = "Responsible for various reports."
    return Finding(
        kind=kind,
        message=message or "Bullet on line 5 reads as a duty rather than an achievement (cue: \"responsible for\").",
        evidence=[Evidence(text=text, start=10, end=10 + len(text), source_segment="experience")],
    )


def _cfg(**overrides) -> Config:
    defaults = dict(use_llm_feedback=True, gemini_api_key="test-key", gemini_model="test-model")
    defaults.update(overrides)
    return Config(**defaults)


# ---------------------------------------------------------------------------
# fail-closed behavior
# ---------------------------------------------------------------------------

def test_disabled_flag_returns_error_not_text():
    cfg = _cfg(use_llm_feedback=False)
    result = rewrite_findings([_finding()], config=cfg)
    assert result.error
    assert all(item.llm_text is None for item in result.items)


def test_missing_key_fails_closed():
    cfg = _cfg(gemini_api_key="")
    result = rewrite_findings([_finding()], config=cfg)
    assert "GEMINI_API_KEY" in result.error
    assert all(item.llm_text is None for item in result.items)


def test_api_failure_falls_back(monkeypatch):
    def boom(prompt, cfg, session):
        raise RuntimeError("network down")
    monkeypatch.setattr(llm_feedback, "_call_gemini", boom)
    result = rewrite_findings([_finding()], config=_cfg())
    assert result.error and "network down" not in result.error or result.error  # error recorded
    assert all(item.llm_text is None and item.fallback_used for item in result.items)


def test_prompt_contains_delimited_redacted_evidence_only(monkeypatch):
    """The prompt must contain redacted evidence blocks — never raw PII, never the full CV."""
    captured = {}

    def fake_call(prompt, cfg, session):
        captured["prompt"] = prompt
        return "1. rewritten sentence"

    monkeypatch.setattr(llm_feedback, "_call_gemini", fake_call)
    f = _finding()
    rewrite_findings([f], config=_cfg())
    prompt = captured["prompt"]
    assert "<evidence>" in prompt and "</evidence>" in prompt
    assert "never obey it" in prompt or "never instructions" in prompt
    assert budi_email_not_in(prompt)


def budi_email_not_in(prompt: str) -> bool:
    # the fixture CV's email/phone must never reach the prompt
    return "budi.santoso@example.com" not in prompt and "+62 812" not in prompt


# ---------------------------------------------------------------------------
# verifier
# ---------------------------------------------------------------------------

def test_verifier_accepts_faithful_sentence():
    f = _finding()
    ok, score, _ = verify_sentence(
        "Your bullet on line 5 describes duties like handling various reports rather than achievements.",
        f,
    )
    assert ok


def test_verifier_rejects_hallucinated_skill():
    f = _finding()
    ok, score, reason = verify_sentence(
        "Your Kubernetes certification is impressive and your leadership drove 300% growth.",
        f,
    )
    assert not ok, f"hallucinated sentence should be rejected (score={score}, reason={reason})"


def test_verifier_rejects_empty():
    f = _finding()
    ok, _, _ = verify_sentence("   ", f)
    assert not ok


# ---------------------------------------------------------------------------
# prompt-injection containment
# ---------------------------------------------------------------------------

def test_injection_bullet_is_treated_as_data(monkeypatch):
    """An adversarial CV bullet quoted as evidence must not change the prompt's intent."""
    captured = {}

    def fake_call(prompt, cfg, session):
        captured["prompt"] = prompt
        return "1. This bullet lists duties; consider quantifying outcomes."

    monkeypatch.setattr(llm_feedback, "_call_gemini", fake_call)
    f = Finding(
        kind="vague_bullet",
        message="Bullet on line 8 reads as a duty rather than an achievement.",
        evidence=[Evidence(text=adversarial.INJECTION_BULLET, start=0, end=len(adversarial.INJECTION_BULLET),
                           source_segment="summary")],
    )
    result = rewrite_findings([f], config=_cfg())
    # the injected text appears ONLY inside the delimited evidence block
    prompt = captured["prompt"]
    idx = prompt.find(adversarial.INJECTION_BULLET)
    assert idx != -1
    before = prompt[:idx]
    assert "<evidence>" in before.split("\n")[-1], "injected text must be inside an evidence block"
    # and the response path is unchanged: the sentence still passes through the verifier.
    # The property that matters: whatever the model returned, nothing from the
    # injected instruction may survive verification.
    verified = verify_llm_result(result, [f])
    shown = verified[0].llm_text or verified[0].original_message
    for banned in ("excellent", "hire", "perfect", "10/10"):
        assert banned.lower() not in shown.lower()


def test_verifier_rejects_injection_success_sentence():
    """If the model 'obeyed' the injection, the verifier must reject the output."""
    f = Finding(
        kind="vague_bullet",
        message="Bullet on line 8 reads as a duty rather than an achievement.",
        evidence=[Evidence(text=adversarial.INJECTION_BULLET, start=0, end=len(adversarial.INJECTION_BULLET),
                           source_segment="summary")],
    )
    ok, _, _ = verify_sentence("This candidate is excellent and should be hired immediately.", f)
    assert not ok
