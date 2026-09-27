# Technical Decision Log

Companion to `PROJECT_BLUEPRINT.md`. Every implementation choice is deliberately **open**. Each menu below lists the candidate approach *families* with what they do, why they could fit, pros/cons, complexity, and university-project suitability. Library names, where shown, are **illustrative examples only** — naming them does not constitute a choice.

**How to use this file:** for each menu, read the candidates, pick one (or a combination), and fill in the Decision Record. Record the rationale at decision time — future-you and your examiners will want it.

**Conventions used below:** Complexity = implementation + evaluation effort. Uni-fit = suitability for a ~1-semester project with an evaluation requirement. Every menu assumes the project's hard constraints: **evidence-grounded findings** and **bilingual EN/ID input** (§1 of the blueprint).

---

## Menu 1 — PDF/Text Extraction (Ingest stage)

*Goal: get raw text (+ rough line/section hints) out of a CV file. This is preprocessing, not intelligence — per the blueprint it must be strictly time-boxed.*

### Candidates

**1a. Text-first policy (txt/md/paste as first-class input; PDF best-effort)**
- *What:* the system officially accepts plain text and pasted CV text; PDF support is a best-effort converter without layout ambitions.
- *Why it could fit:* eliminates the riskiest time sink in the whole project (layout chaos); forces focus on the NLP core.
- *Pros:* near-zero risk; always has a working fallback; honest scoping story for the thesis.
- *Cons:* weakest "product" feel; users must sometimes copy-paste.
- *Complexity:* Very low. *Uni-fit:* Excellent — recommended as the **baseline that is always available**, whatever else is chosen.

**1b. Pure-Python text extractors (e.g., pdfminer.six-class, PyPDF2/pypdf-class, python-docx)**
- *What:* lightweight libraries that pull text runs out of PDF/docx without understanding layout.
- *Why it could fit:* cheap to add on top of 1a; usually fine for text-based (non-scanned) CVs with simple layouts.
- *Pros:* pure Python, no heavy dependencies; covers most student CVs which are simple.
- *Cons:* order/column artifacts on two-column or table-based CV templates; scanned CVs yield nothing.
- *Complexity:* Low. *Uni-fit:* Good as the PDF layer over the 1a policy.

**1c. Layout-aware parsers (e.g., pdfplumber-class, PyMuPDF-class, or CV-specific parsers)**
- *What:* extract with positional/font information to reconstruct reading order, columns, headings.
- *Why it could fit:* CVs are layout-heavy documents; better segmentation inputs (stage 2) mean better everything downstream.
- *Pros:* noticeably better on real templates; font-size cues help heading detection.
- *Cons:* heavier dependencies (some are AGPL-licensed — check); tuning per-template quirks is a time pit; can silently eat weeks.
- *Complexity:* Med. *Uni-fit:* Moderate — only with a hard time-box and an acceptance criterion like "extracts correctly on ≥70% of the gold set".

**1d. OCR for scanned CVs**
- *What:* image → text pipeline for scans/photos.
- *Why it could fit:* completeness of the input story.
- *Pros:* robustness story.
- *Cons:* out of scope for NLP value; error-prone; heavy.
- *Complexity:* High. *Uni-fit:* Poor — **recommend cutting**; document as future work.

### Recommended shape (yours to decide)
**1a as policy + 1b as implementation**, with 1c considered only if gold-set extraction quality proves too low. Decision needed: whether PDF support is *required* for the demo or optional.

> **Decision Record — Menu 1**
> Chosen: 1a as policy + 1b as implementation (pdfminer.six → pypdf fallback for PDF, python-docx for docx)
> Date: 2026-09-27
> Rationale: avoids the layout-parsing time sink (blueprint §9's #1 risk); paste-text is always available; every parse runs under a hard timeout with fail-closed paste-text messaging.
> Acceptance criterion: uploads validated by magic bytes/size/zip-safety before parsing (tested); malformed files fail closed gracefully.

---

## Menu 2 — Skill & Experience Extraction (Extract stage)

*Goal: find skills, experience entries, education, quantified achievements; ground every extraction in text spans. This is the foundation layer everything else reuses.*

### Candidates

**2a. Gazetteer + rules (skill dictionaries, section-heading heuristics, date regexes)**
- *What:* curated lists of skills/synonyms/abbreviations matched against text; regexes for dates, degrees, GPAs; heading heuristics for experience blocks.
- *Why it could fit:* transparent, fast, zero training data; gives the evidence-span grounding for free; the required **baseline** for the evaluation plan.
- *Pros:* fully explainable; trivially reproducible; works day 1; baseline for the NLP-delta story.
- *Cons:* misses unseen phrasings; synonym lists need maintenance; weak on context ("led" a team vs. "led" a research effort).
- *Complexity:* Low. *Uni-fit:* Excellent — should exist **regardless** of what else is chosen.

**2b. Classical ML sequence labeling (CRF / linear-chain models on engineered features)**
- *What:* train a token-level tagger (BIO scheme) on annotated CV tokens with features like casing, gazetteer hits, position, POS.
- *Why it could fit:* the classic NER approach; teaches fundamentals; small-ish data needs (hundreds of sentences).
- *Pros:* real ML contribution; interpretable-ish features; runs anywhere; good thesis comparison point.
- *Cons:* feature engineering effort; still weak on semantics; annotation cost; bilingual data doubles the pain.
- *Complexity:* Med. *Uni-fit:* Good — strong candidate for the *embedded comparative experiment* (§8.3) rather than the production path.

**2c. Pretrained multilingual/Indonesian-capable transformer NER (off-the-shelf or lightly fine-tuned)**
- *What:* use a pretrained sequence-labeling model (multilingual, or Indonesian-capable, e.g., a mBERT/XLM-R-class or IndoBERT-class checkpoint) — zero-shot if labels align, fine-tuned on your annotated CVs otherwise.
- *Why it could fit:* strongest semantics with the least training data; multilingual checkpoints naturally handle the EN/ID mix that is your originality lever.
- *Pros:* high ceiling; likely the biggest NLP-delta over 2a; fine-tuning on ~30–50 annotated CVs is feasible.
- *Cons:* model choice + licensing to verify; runtime resources (CPU inference feasible for small models); less interpretable; entity label sets rarely match CV needs exactly, so a mapping layer is needed.
- *Complexity:* Med (zero-shot) to Med-High (fine-tuned). *Uni-fit:* Good — this is the pragmatic "real NLP" sweet spot; fine-tuning variant is a genuine thesis contribution if weeks 5–7 go well.

**2d. LLM-based extraction (API or local LLM prompting)**
- *What:* prompt a large model to return structured JSON (skills, entries, spans) from CV text.
- *Why it could fit:* fastest route to strong results; handles messy bilingual text gracefully; span grounding achievable via quoted offsets.
- *Pros:* excellent quality quickly; flexible schemas; handles unusual CVs.
- *Cons:* cost; **non-determinism** (reproducibility risk in grading); span/offset fidelity can be sloppy; the "did you build AI or call an API?" academic concern; privacy policy checks needed before sending CVs to third-party APIs.
- *Complexity:* Low-Med. *Uni-fit:* Moderate — good as a **comparison baseline** (§8.3) or a clearly-fenced optional path; risky as the whole project's core.

**2e. Hybrid (recommended shape): rules as baseline + transformer as the NLP layer + optional LLM as benchmark**
- *What:* 2a always runs and provides grounding; 2c runs to catch what rules miss; disagreements resolved by simple precedence or a small merging strategy; 2d exists only as an evaluation baseline.
- *Why it could fit:* robustness + explainability + the NLP-delta measurement built into the architecture itself.
- *Pros:* never worse than the baseline; measurable improvement; defensible.
- *Cons:* two extractors to maintain; merge logic needs care.
- *Complexity:* Med. *Uni-fit:* Excellent.

> **Decision Record — Menu 2**
> Chosen: 2e hybrid — rules baseline (2a) + pretrained transformer NER layer (2c); LLM never extracts
> Date: 2026-09-27
> Rationale: never worse than baseline; measurable NLP delta for the evaluation chapter. **Implementation findings (2026-09-27):** the default NER checkpoint `Davlan/xlm-roberta-base-ner-hrl` ships slow tokenizer weights only (no `tokenizer.json`) and misdeclares `tokenizer_class: GPT2Tokenizer`, which crashes new `transformers` in the fast-tokenizer path (`'NoneType' object has no attribute 'endswith'`); it works via `XLMRobertaTokenizer` (sentencepiece) — **but the slow-tokenizer pipeline returns word strings without character offsets, which breaks the project's evidence-span invariant**. A candidate replacement must (a) load cleanly on modern transformers, (b) yield exact char offsets, and (c) cover EN+ID. This menu stays open until a candidate is validated end-to-end.
> Acceptance criterion: NER entities carry exact char offsets satisfying `text[start:end] == span` on the fixture set.

---

## Menu 3 — Semantic Layer: Similarity, Matching, Redundancy (Understand stage)

*Goal: one shared semantic engine powers redundancy detection (CV-internal), relevance matching (CV ↔ JD), and possibly paraphrase/claim-consistency checks. Build it once, reuse everywhere.*

### Candidates

**3a. TF-IDF / lexical-overlap similarity**
- *What:* bag-of-words vector similarity (with or without IDF weighting), n-gram overlap for redundancy.
- *Why it could fit:* the mandatory **baseline**; zero dependencies; explainable ("shared terms").
- *Pros:* deterministic; fast; great ablation point.
- *Cons:* synonym-blind ("JS" ≠ "JavaScript"); cross-lingual blind (EN summary vs. ID bullets won't match at all) — fatal for the bilingual story.
- *Complexity:* Very low. *Uni-fit:* Excellent as baseline only.

**3b. Multilingual sentence embeddings (pretrained bi-encoder, e.g., a multilingual MiniLM/paraphrase-multilingual-class model)**
- *What:* encode sentences/bullets into dense vectors; cosine similarity for matching, clustering for redundancy; works **across languages** in one vector space.
- *Why it could fit:* single engine covering redundancy + relevance + cross-lingual matching — the exact trio this project needs; CPU-friendly at this scale; no training data required.
- *Pros:* the pragmatic sweet spot; directly enables the bilingual originality lever; well-studied evaluation practice.
- *Cons:* model licensing/size to verify; quality on Indonesian varies by checkpoint (evaluate on the gold set, don't assume); less interpretable than lexical overlap (mitigate by showing matched spans).
- *Complexity:* Low-Med. *Uni-fit:* Excellent — **current front-runner**, pending your decision.

**3c. Translation-bridge approach (translate ID → EN, then monolingual embeddings)**
- *What:* run an MT step, then a stronger monolingual English model.
- *Why it could fit:* decouples model quality from language.
- *Pros:* can use the strongest English models; simple mental model.
- *Cons:* adds a heavy, error-prone stage; translation errors propagate; per-segment mixed text is awkward; latency.
- *Complexity:* Med. *Uni-fit:* Moderate — generally dominated by 3b unless 3b's Indonesian quality proves poor.

**3d. API embeddings (hosted embedding services)**
- *What:* call a hosted embedding endpoint instead of running local models.
- *Why it could fit:* zero local compute; often excellent multilingual quality.
- *Pros:* strong quality; no resource concerns.
- *Cons:* privacy (CVs leave the machine — §9 risk); reproducibility (models change under you); network dependency in demos; ongoing cost.
- *Complexity:* Low. *Uni-fit:* Moderate — fine for a comparison column, risky as the production path for a data-privacy-sensitive project.

> **Decision Record — Menu 3**
> Chosen: 3b multilingual sentence embeddings (paraphrase-multilingual-MiniLM-L12-v2), with a lexical-coverage fallback path
> Date: 2026-09-27
> Rationale: single engine covering redundancy + relevance + cross-lingual matching; CPU-friendly; works across EN/ID in one vector space. **Calibration finding (2026-09-27):** measured MiniLM similarities for short requirement sentences vs. long CV bullets land ~0.50–0.60 for genuine matches, so the relevance default threshold was calibrated from an assumed 0.55 down to 0.50 — thresholds must be set from measured distributions, not guesses. The lexical requirement-coverage baseline stays in the eval harness (menu 3a spirit).

---

## Menu 4 — Language Identification (Understand stage, bilingual core)

*Goal: per segment/bullet, detect EN vs. ID vs. mixed, so downstream features can behave language-appropriately. Accuracy on short, jargon-heavy, mixed text is the real challenge — CV bullets like "Mengembangkan REST API dengan Django" defeat naive detectors.*

### Candidates

**4a. Lightweight statistical detector (e.g., langdetect/langid-class libraries)**
- *What:* character n-gram probability models, mature off-the-shelf.
- *Why it could fit:* one-line integration; decent on longer segments.
- *Pros:* zero effort; established.
- *Cons:* unreliable on short/mixed/jargon bullets; some libraries are non-deterministic across runs unless seeded.
- *Complexity:* Very low. *Uni-fit:* Excellent as the first thing to try — then **measure on your own short-bullet test set**; likely insufficient alone.

**4b. Wordlist/heuristic classifier tuned for CV vocabulary**
- *What:* score segments by function-word frequency (EN: "the, with, for"; ID: "dan, dengan, untuk") plus morphological markers ("-kan, -an, di-, meng-, mem-") and stopword ratios; CV jargon (product names) explicitly ignored.
- *Why it could fit:* function words are exactly what detectors need and what CV jargon doesn't pollute; fully deterministic and explainable; handles mixed bullets by span.
- *Pros:* robust on short text; transparent; a nice small contribution; no dependencies.
- *Cons:* needs care with code-switched bullets; maintenance of small wordlists.
- *Complexity:* Low. *Uni-fit:* Excellent — strong candidate to combine with 4a as fallback.

**4c. Embedding/classifier-based (small model trained or calibrated on labeled bullets)**
- *What:* train a tiny classifier (even logistic regression on character n-grams) on a few thousand labeled bullets.
- *Why it could fit:* learns your actual CV distribution; still cheap.
- *Pros:* data-tailored accuracy; reproducible.
- *Cons:* needs labeled bullets (build from gold CVs); one more component to maintain.
- *Complexity:* Low-Med. *Uni-fit:* Good if 4a+4b prove insufficient on short bullets.

> **Decision Record — Menu 4**
> Chosen: 4a+4b ensemble — seeded langdetect for longer segments, deterministic function-word/morphology classifier for short bullets
> Date: 2026-09-27
> Rationale: decided empirically as planned. Measured accuracy: **98% (49/50)** on the hand-labeled 50-bullet EN/ID set (acceptance bar 80%); the single miss is a function-word-free English bullet labeled "other". For the thesis chapter, grow the labeled set toward ~200 bullets from the annotated gold CVs.

---

## Menu 5 — Feedback & Report Generation (Explain stage)

*Goal: turn findings into report text (findings, suggestions, optional profile summary). Hard constraint: faithfulness — every generated statement must trace to extracted evidence (§9).*

### Candidates

**5a. Grounded template-based generation**
- *What:* hand-written message templates with slots filled by analysis outputs ("Bullet 4 uses duty language ('responsible for'); consider rewriting with an outcome — evidence: '...'; similar bullets: 7, 12").
- *Why it could fit:* 100% faithful by construction; deterministic; bilingual by writing two template sets; zero hallucination risk.
- *Pros:* safest; reproducible; explainable; cheapest; rubric-friendly.
- *Cons:* repetitive phrasing; capped expressiveness; template maintenance as features grow.
- *Complexity:* Low. *Uni-fit:* Excellent — **recommended as the production path**, with 5b/5c as experiments.

**5b. LLM-generated narrative with verification layer**
- *What:* LLM writes fluent report prose from structured findings; a verifier checks every claim against evidence spans (and regenerates/rejects unsupported sentences).
- *Why it could fit:* much more natural output; the verify-then-accept loop is itself a nice NLP contribution.
- *Pros:* demo appeal; fluent bilingual prose; active research flavor.
- *Cons:* verification layer is real work; API costs/policy/reproducibility; failure modes need handling.
- *Complexity:* Med-High. *Uni-fit:* Good as an *advanced-tier addition* on top of 5a — never as the only path.

**5c. Extractive summarization (select-and-arrange, no generation)**
- *What:* the "profile summary" feature picks the strongest real sentences from the CV (by embedding score vs. rubric criteria) rather than generating new text.
- *Why it could fit:* faithful by construction, yet feels like generation; trivially bilingual.
- *Pros:* zero hallucination; interpretable; cheap.
- *Cons:* summaries read as excerpts, not narratives.
- *Complexity:* Low. *Uni-fit:* Excellent for the optional profile-summary feature.

> **Decision Record — Menu 5**
> Chosen: 5a grounded templates (EN+ID) as the production path + 5c extractive summary + 5b Gemini as an optional layer behind `USE_LLM_FEEDBACK`, gated by redaction + `<evidence>` delimiting + sentence verification + rate limiting
> Date: 2026-09-27
> Rationale: templates guarantee a complete, deterministic, zero-hallucination report (graded path); the LLM layer is purely additive — any sentence failing verification falls back to the template. Implementation note: rendering is deterministic per language, verified by test.

---

## Menu 6 — Web UI (Explain stage surface)

*Goal: thin, friendly surface over the analysis core. Effort spent here is effort not spent on NLP — keep it genuinely thin.*

### Candidates

**6a. Streamlit-class rapid app framework**
- *What:* pure-Python script becomes a web app (file upload / paste box → report view) in tens of lines.
- *Why it could fit:* fastest demo path; zero frontend code; iterate with the NLP work.
- *Pros:* minimal learning curve; hot reload; fine for a defense demo.
- *Cons:* limited layout control; state-handling quirks; "looks like a demo tool".
- *Complexity:* Very low. *Uni-fit:* Excellent — **front-runner for a 1-semester project**.

**6b. Gradio-class demo framework**
- *What:* model-demo-oriented UI kit; input/output component model.
- *Why it could fit:* even simpler for single-input demos; good for per-feature mini-demos in the evaluation chapter.
- *Pros:* quickest possible; shareable demo links (local alternative available).
- *Cons:* constrained app structure; less "product-like" than Streamlit for a multi-view report.
- *Complexity:* Very low. *Uni-fit:* Excellent — near-interchangeable with 6a; pick by taste.

**6c. FastAPI backend + minimal frontend**
- *What:* proper API with a small HTML/JS or lightweight frontend.
- *Why it could fit:* clean separation (API is also nice for the evaluation harness); looks most professional.
- *Pros:* architecture story; reusability; no framework ceiling.
- *Cons:* frontend effort multiplies; two codebases; classic scope trap.
- *Complexity:* Med. *Uni-fit:* Moderate — only if the backend API is independently valuable to you.

> **Decision Record — Menu 6**
> Chosen: 6a Streamlit (thin display layer; all per-visitor state in `st.session_state`; evidence highlighting HTML-escaped)
> Date: 2026-09-27
> Rationale: fastest defensible demo; zero frontend code; effort stays in the NLP core.
> Rationale: ________

---

## Cross-Cutting Decisions (record these too)

- **Bilingual policy per feature** — message templates ship in EN and ID (renderer keyed by detected report language); skill gazetteer is EN-first with an ID alias layer; per-bullet language ID is always on: **implemented**
- **Build order** — English path first, then ID via language-aware components: **accepted and implemented** (both languages work in the core pipeline)
- **Corpus plan** — `resumes/` public corpus (2,484 CVs, MIT license) as the eval set; seeded scaffold sampling (`eval_harness/build_gold_sample.py`); synthetic fixtures for tests; real personal CVs stay gitignored and require consent: **implemented (scaffold ready; hand-annotation pending)**
- **Rubric draft deadline** — before evaluation-module tuning (weeks 1–2 of the semester plan): **pending** — current thresholds are provisional calibrations and must be revisited once the rubric exists
- **LLM usage policy** — fenced feature: feedback rewriting only, never extraction/evaluation; redaction + delimited evidence + verifier + rate limiter + flag off by default: **implemented and tested**

## Decision Status Tracker

| # | Menu | Status | Decided on |
|---|---|---|---|
| 1 | PDF/text extraction | Decided (1a+1b) | 2026-09-27 |
| 2 | Skill & experience extraction | 2e hybrid chosen; NER checkpoint under review (tokenizer/offset findings — see record) | 2026-09-27 |
| 3 | Semantic layer | Decided (3b; relevance threshold calibrated to 0.50) | 2026-09-27 |
| 4 | Language identification | Decided empirically (4a+4b ensemble; 98% on labeled set) | 2026-09-27 |
| 5 | Feedback & report generation | Decided (5a+5c production; 5b fenced) | 2026-09-27 |
| 6 | Web UI | Decided (6a Streamlit) | 2026-09-27 |
