# Security Checklist (verify before ANY deployment)

> Deployment gate: **do not deploy to a public host until every item below is checked.**
> Each item cites the code or test that implements/verifies it.

## Secrets & API keys

- [x] Gemini API key never in source, history, or browser output — loaded from env
      (`.env`, gitignored from first commit) locally, `st.secrets` in deployment
      (`cv_analyzer/config.py::from_env`).
- [x] Key excluded from serialized config: `active_fields()` redacts `gemini_api_key`
      before meta/report serialization.
- [x] Key never logged or printed anywhere; no debug prints of config exist.
- [x] `.env` in `.gitignore` from the first commit.

## File upload safety

- [x] File type validated by magic bytes, not just extension — a `.txt` renamed to
      `.pdf` is rejected by content signature check
      (`security/validate_upload.py`; test: `test_txt_renamed_to_pdf_is_caught`).
- [x] Hard 5 MB size cap, rejected *before* parsing (`MAX_UPLOAD_MB`; test:
      `test_oversized_file_rejected_before_parsing`).
- [x] PDF/docx parsing under a hard timeout (`PARSE_TIMEOUT_SECONDS=15`, thread-based
      so it works on Windows) — malformed/decompression-bomb files fail closed with a
      paste-text request (`ingest/extract_text.py::_run_with_timeout`).
- [x] User filename never used as a filesystem path; docx temp files use internal
      UUID names in a private temp dir, deleted immediately after use
      (`ingest/extract_text.py::_extract_docx`).
- [x] Zip-bomb guard: docx containers' uncompressed size capped before reading
      (test: `test_docx_zip_bomb_guard`).
- [x] Temp artifacts deleted after processing; stale temp swept at import.

## Personal data handling

- [x] No raw CV text or PII in logs: the pipeline logs nothing; Streamlit's default
      logs carry no CV content (verified: no `print`/`logging` of text anywhere).
- [x] No persistent storage of uploads beyond the session (in-memory processing only;
      nothing written to disk except the transient docx temp file, deleted on exit).
- [x] Redaction of email/phone/URL/header-name before ANY text reaches the LLM —
      including quoted evidence spans inside prompts, for BOTH providers
      (`security/redact.py` + `explain/llm_feedback.py::_build_user_prompt`; tests:
      `test_prompt_contains_delimited_redacted_evidence_only`, redaction tests).
- [x] **Third-party router disclosure:** when `LLM_PROVIDER=openai`, requests (key +
      redacted findings only) pass through the configured OpenAI-compatible endpoint
      before reaching the upstream model. Only already-redacted, structured Finding
      data leaves the pipeline — the raw CV never does. Verified end-to-end with the
      verifier accepting 4/4 router-rewritten findings. Using a self-hosted or
      trusted router is preferred; using a third-party router should be disclosed in
      the thesis methodology section.

## Prompt injection

- [x] Quoted CV text wrapped in `<evidence>...</evidence>` blocks with explicit
      "data, never instructions" instruction in the system prompt
      (`llm_feedback.py::SYSTEM_PROMPT`, `_build_user_prompt`).
- [x] Adversarial fixture bullets (`explain/adversarial.py`) verified: injection text
      appears only inside evidence delimiters (test:
      `test_injection_bullet_is_treated_as_data`).
- [x] Verifier second gate: any sentence echoing the injected instruction without
      tracing to the finding's template message is rejected and the template shown
      (test: `test_verifier_rejects_injection_success_sentence`,
      `test_verifier_rejects_hallucinated_skill`).

## Rate limiting & cost control

- [x] Every Gemini call routed through the per-session sliding-window limiter
      (default 5 calls/min; `security/rate_limit.py`, enforced in
      `llm_feedback.py::_call_gemini`; tests: rate-limit block/slide/per-session).
- [x] Max token budget per call (`LLM_MAX_OUTPUT_TOKENS=1024`).
- [x] Fail closed to template fallback on any LLM error; no indefinite retries
      (test: `test_api_failure_falls_back`).

## Dependency & deployment hygiene

- [x] Exact versions pinned in `requirements.txt`; `requirements-frozen.txt` records
      the full tested environment (84 pinned packages incl. torch CPU build).
- [x] No `subprocess` at all, no `eval`/`exec` anywhere in the package.
- [x] HTTPS: to be confirmed per host — Streamlit Community Cloud serves HTTPS by
      default; Render free tier serves HTTPS by default. **Re-confirm on the actual
      host before public launch.**

## Multi-tenant isolation

- [x] Per-request data kept in `st.session_state` only (`ui/app.py`); no module-level
      or fixed-name storage of CV/findings/report.
- [x] Rate limiter keyed by session UUID generated per visitor
      (`ui/app.py::_session_key`).

## XSS / output safety

- [x] Evidence highlighting HTML-escapes CV content before wrapping in `<mark>`
      (`ui/app.py::_highlight_document`); a CV containing `<script>` renders inert.

## Deployment runbook

Full step-by-step: **`DEPLOY.md`** (Streamlit Community Cloud). Summary:

1. All items above checked.
2. Push to GitHub **without** `.env`, `resumes/`, or real CVs (gitignore verified).
3. Deploy `cv_analyzer/ui/app.py` on Streamlit Community Cloud.
4. Secrets manager: `NLP_EXTRACTOR_ENABLED = false` (free-tier RAM),
   `USE_LLM_FEEDBACK = false` for the first public deployment (templates only);
   add `GEMINI_API_KEY` only when deliberately enabling the LLM layer.
5. Verify: HTTPS on the live URL, sample-CV boot check, oversized-file rejection,
   extension-mismatch rejection.
6. Rules-only profile verified locally (extractor=rules, grounding invariant
   intact, full test suite passing).
