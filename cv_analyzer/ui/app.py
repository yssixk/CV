"""CV Quality Coach — Streamlit UI (Phase 9).

Thin display layer ONLY: every computation lives in cv_analyzer modules.
Multi-tenant isolation: all per-visitor state lives in ``st.session_state``
(free hosts run one shared instance; module-level state would leak CVs
between visitors). CV text is never logged. Evidence rendering HTML-escapes
CV content before wrapping it in <mark> tags (a CV containing
"<script>" must never execute).
"""
from __future__ import annotations

import html
import sys
import uuid
from pathlib import Path

import streamlit as st

# Host-proofing: make ``cv_analyzer`` importable no matter which working
# directory the platform launches the app from (Streamlit Cloud / Docker).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from cv_analyzer.config import DEFAULT_CONFIG
from cv_analyzer.explain.llm_feedback import rewrite_findings
from cv_analyzer.explain.llm_verifier import verify_llm_result
from cv_analyzer.explain.report_builder import build_report
from cv_analyzer.ingest.extract_text import IngestError, ingest_bytes, ingest_text

st.set_page_config(page_title="CV Quality Coach", page_icon=None, layout="wide")

MAX_DISPLAY_FINDINGS = 50


def _session_key() -> str:
    if "session_key" not in st.session_state:
        st.session_state["session_key"] = uuid.uuid4().hex
    return st.session_state["session_key"]


def _highlight_document(text: str, evidence_spans: list[tuple[int, int]]) -> str:
    """Return HTML with evidence spans marked; CV content is always escaped."""
    if not evidence_spans:
        return f"<pre style='white-space:pre-wrap'>{html.escape(text)}</pre>"
    spans = sorted(set(evidence_spans))
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    parts: list[str] = []
    pos = 0
    for start, end in merged:
        parts.append(html.escape(text[pos:start]))
        parts.append(
            f"<mark style='background-color:#ffe58f'>{html.escape(text[start:end])}</mark>"
        )
        pos = end
    parts.append(html.escape(text[pos:]))
    return f"<pre style='white-space:pre-wrap'>{ ''.join(parts) }</pre>"


def _render_report() -> None:
    result = st.session_state.get("result")
    if result is None:
        st.info("Analyze a CV to see the report here.")
        return
    report = result.report
    doc = report.document

    st.subheader("Profile summary (extracted from your CV — verbatim)")
    if report.summary_sentences:
        for s in report.summary_sentences:
            st.markdown(f"> {s}")
    else:
        st.caption("No strong summary sentences could be selected (semantic model unavailable or CV too short).")

    col1, col2, col3 = st.columns(3)
    col1.metric("Findings", len(report.findings))
    col2.metric("Skills detected", len(report.extraction.skills) if report.extraction else 0)
    lang = report.meta.get("lang_distribution", {})
    col3.metric("Language mix", ", ".join(f"{k}:{v}" for k, v in sorted(lang.items())) or "n/a")

    st.subheader("Findings")
    if not report.findings:
        st.success("No issues found by the current analysis modules.")
    for f in report.findings[:MAX_DISPLAY_FINDINGS]:
        with st.expander(f"{f.kind} — {f.message[:110]}{'…' if len(f.message) > 110 else ''}"):
            for i, ev in enumerate(f.evidence, 1):
                st.markdown(f"**Evidence {i}** (chars {ev.start}–{ev.end}, segment: {ev.source_segment}):")
                st.markdown(f"> {ev.text}")
            if f.confidence is not None:
                st.caption(f"confidence: {f.confidence}")

    st.subheader("Annotated CV")
    spans = [(ev.start, ev.end) for f in report.findings for ev in f.evidence]
    st.markdown(_highlight_document(doc.text, spans), unsafe_allow_html=True)

    # Wordcloud dari isi CV (fitur luaran makalah; hitam-putih, deterministik)
    if st.button("Generate wordcloud dari CV ini"):
        from cv_analyzer.explain.wordcloud_gen import generate_skill_cloud

        out = result and _session_wordcloud(doc.text)
        if out:
            st.image(str(out), caption="Wordcloud isi CV (grayscale, seed tetap)")


def _session_wordcloud(text: str):
    """Generate (sekali per sesi) dan tampilkan wordcloud isi CV."""
    from cv_analyzer.explain.wordcloud_gen import generate_skill_cloud

    if "wc_path" not in st.session_state:
        import uuid
        from pathlib import Path

        out_dir = Path(".wordclouds")   # ephemeral di host; tidak berisi PII (hanya frekuensi kata)
        out_dir.mkdir(exist_ok=True)
        st.session_state["wc_path"] = generate_skill_cloud([text], out_dir / f"wc_{uuid.uuid4().hex[:8]}.png")
    return st.session_state["wc_path"]

    if report.relevance is not None:
        st.subheader("Relevance vs. job description")
        for area in report.relevance.areas:
            icon = "✅" if area.matched else "⚠️"
            st.markdown(f"{icon} **{area.requirement_text}** — best match {area.similarity:.2f}")
            if area.matched_bullet_text:
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;↳ matched: *{area.matched_bullet_text}*")


def _llm_panel() -> None:
    """Side-by-side template vs LLM feedback. Gated by config flag + key."""
    st.subheader("LLM feedback layer (experimental)")
    cfg = DEFAULT_CONFIG
    _llm_diagnostics()
    if not cfg.use_llm_feedback:
        st.caption("Disabled by default (USE_LLM_FEEDBACK=false). Templates below are the graded, "
                   "deterministic output — the LLM layer is optional fluency polish on top.")
    result = st.session_state.get("result")
    if result is None:
        return
    findings = result.report.findings[:10]
    if not findings:
        return
    if not cfg.gemini_api_key:
        st.warning("No GEMINI_API_KEY configured — showing template output only.")
        return
    if st.button("Rewrite top findings with LLM", disabled=not cfg.use_llm_feedback):
        llm_result = rewrite_findings(findings, language=result.report.meta.get("report_language", "en"),
                                      session_key=_session_key())
        verified = verify_llm_result(llm_result, findings)
        st.session_state["llm_items"] = verified
        st.session_state["llm_meta"] = {"model": llm_result.model, **llm_result.params, "error": llm_result.error}
    items = st.session_state.get("llm_items")
    if items:
        meta = st.session_state.get("llm_meta", {})
        provider = DEFAULT_CONFIG.llm_provider
        provider_note = ("OpenAI-compatible router" if provider == "openai" else "Google Gemini")
        st.caption(f"provider: {provider_note} · model: {meta.get('model')} · "
                   f"temperature: {meta.get('temperature')} · params logged for reproducibility")
        for item in items:
            st.markdown(f"**Template:** {item.original_message}")
            if item.llm_text:
                st.markdown(f"**LLM (verified ✅):** {item.llm_text}")
            else:
                reason = (item.verification or {}).get("reason", "unavailable")
                st.markdown(f"**LLM:** rejected/failed ({reason}) — template shown instead")
            st.divider()


def _llm_diagnostics() -> None:
    """Show exactly what config the running app sees + live router test.

    Exists because 'the LLM tab says disabled' has too many possible causes
    (secrets not saved, app not restarted, typo'd key name...). This makes the
    truth visible in the UI instead of guesswork. Displays no secret values.

    Uses getattr fallbacks throughout: if Streamlit hot-reloads app.py while an
    older cv_analyzer.config module is still cached in the process, missing
    attributes degrade to 'unknown' instead of crashing the whole app.
    """
    with st.expander("LLM diagnostics (what does this app actually see?)"):
        cfg = DEFAULT_CONFIG
        use_llm = getattr(cfg, "use_llm_feedback", None)
        provider = getattr(cfg, "llm_provider", "unknown (config module outdated — reboot the app)")
        api_key = getattr(cfg, "gemini_api_key", "") or ""
        model = getattr(cfg, "gemini_model", "unknown")
        base_url = getattr(cfg, "llm_base_url", "") or ""
        timeout_s = getattr(cfg, "llm_timeout_seconds", "?")

        c1, c2 = st.columns(2)
        c1.metric("USE_LLM_FEEDBACK", str(use_llm))
        c2.metric("Provider", str(provider))
        st.write({
            "GEMINI_API_KEY present": bool(api_key),
            "key length": len(api_key),
            "key prefix": (api_key[:6] + "…") if api_key else "—",
            "model": model,
            "base URL": base_url or "—",
            "timeout (s)": timeout_s,
        })
        st.caption("Values come from environment variables and/or Streamlit secrets. "
                   "If USE_LLM_FEEDBACK is False or the key is absent, save the secrets "
                   "(Manage app → Settings → Secrets) and let the app restart. "
                   "If Provider shows 'unknown', the app process predates the latest code — "
                   "Manage app → ⋮ → Reboot forces a clean reload.")
        if st.button("Test router connection"):
            if not (use_llm and api_key and base_url and provider == "openai"):
                st.error("Provider not fully configured — fix the secrets above first.")
            else:
                import httpx

                try:
                    resp = httpx.post(
                        base_url.rstrip("/") + "/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": model,
                              "messages": [{"role": "user", "content": "Reply with exactly: PONG"}],
                              "temperature": 0, "max_tokens": 10, "stream": False},
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        from cv_analyzer.explain.llm_feedback import _parse_sse
                        body = resp.json()["choices"][0]["message"]["content"] \
                            if "application/json" in resp.headers.get("content-type", "") \
                            else _parse_sse(resp.text)
                        st.success(f"Router reachable — model replied: {body[:40]!r}")
                    else:
                        st.error(f"Router returned HTTP {resp.status_code}: {resp.text[:120]}")
                except Exception as exc:  # noqa: BLE001 - diagnostics must not crash the app
                    st.error(f"Router unreachable: {type(exc).__name__}: {exc}")


def main() -> None:
    st.title("CV Quality Coach")
    st.caption("No CV Stored only processed")

    tab_analyze, tab_llm = st.tabs(["Analyze CV", "LLM feedback (experimental)"])

    with tab_analyze:
        input_method = st.radio("Input method", ["Paste text", "Upload file"], horizontal=True)
        jd_text = st.text_area(
            "Job description (optional — enables relevance mode)",
            height=120,
            help="Paste a job description to see which requirements your CV addresses semantically.",
        )
        use_nlp = st.checkbox(
            "Use NLP extraction layer (transformer NER; downloads ~1 GB model on first run)",
            value=DEFAULT_CONFIG.nlp_extractor_enabled,
            disabled=not DEFAULT_CONFIG.nlp_extractor_enabled,
            help=("Disabled in this deployment: the free host's ~1 GB RAM cannot hold the "
                  "transformer NER model. The rules-based extraction path is complete without it "
                  "(see DECISIONS.md menu 2).") if not DEFAULT_CONFIG.nlp_extractor_enabled else None,
        )

        cv_text: str | None = None
        if input_method == "Paste text":
            pasted = st.text_area("Paste your CV text", height=240)
            if st.button("Analyze pasted CV", type="primary") and pasted.strip():
                try:
                    ing = ingest_text(pasted)
                    cv_text = ing.text
                except IngestError as exc:
                    st.error(str(exc))
        else:
            uploaded = st.file_uploader("Upload CV (pdf, docx, txt, md — max 5 MB)",
                                        type=["pdf", "docx", "txt", "md"])
            if uploaded is not None and st.button("Analyze uploaded CV", type="primary"):
                data = uploaded.getvalue()
                try:
                    ing = ingest_bytes(data, uploaded.name)   # validation inside, before parsing
                    cv_text = ing.text
                    for w in ing.warnings:
                        st.caption(w)
                except IngestError as exc:
                    st.error(str(exc))

        if cv_text is not None:
            with st.spinner("Analyzing (local pipeline; first run may download models)..."):
                result = build_report(cv_text, source_name="ui", jd_text=jd_text or None, use_nlp=use_nlp)
            st.session_state["result"] = result
            st.success(f"Analysis complete — {len(result.report.findings)} findings.")

        _render_report()

    with tab_llm:
        _llm_panel()


if __name__ == "__main__":
    main()
