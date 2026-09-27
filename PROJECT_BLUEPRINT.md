# Project Blueprint

**Working title:** Pengembangan Sistem AI untuk Analisis dan Evaluasi Curriculum Vitae Berbasis Natural Language Processing
**System concept:** *CV Quality Coach + Relevance Mode* — an NLP-based system that understands and evaluates CV text, giving evidence-backed quality feedback, with an optional semantic relevance analysis against a target role or job description.
**Status:** Foundation document — scope and direction decided at the concept level; all technical implementation choices deliberately open (see `DECISIONS.md`).

---

## 1. Vision and Chosen Direction

### 1.1 Core principle

> **NLP is the core intelligence of this project, not a supporting feature.**

CV **parsing** (turning a file into structured fields) is a solved commodity. This project is about CV **analysis and evaluation** — *understanding meaning, judging quality, finding relationships, and explaining why something is good, weak, missing, or inconsistent, with evidence from the text itself.*

The differentiator, concretely:

- A parser says: *"skill: Python, line 14."*
- This system says: *"The summary claims 'expert in data analysis', but no experience entry demonstrates analytical work with measurable outcomes — considered unsupported (evidence: lines 3, 27)."*

Every analytical finding produced by the system must **cite the exact CV text** it is based on. This "evidence-grounded" rule is a hard design constraint, not a nice-to-have.

### 1.2 Chosen direction

The project combines two directions (with a third embedded as a feature):

| Direction | Role in project |
|---|---|
| **A — CV Quality Coach** (candidate-facing) | **Primary.** Input: a CV. Output: an evidence-backed quality report — clarity, impact language, redundancy, unsupported claims, completeness, concrete suggestions. |
| **B — Relevance Analyzer** | **Secondary, a toggleable module.** Input: CV + job description / target-role profile. Output: semantic alignment report — matched areas, gaps, evidence. |
| **D — Insight/Summary Generator** | **Embedded feature, not a direction.** A structured candidate-profile summary appears inside the quality report (and relevance report). |

Direction C (comparative NLP study) is **not** the product direction, but a comparative experiment is included in the *evaluation plan* (§8) because it is the strongest way to prove that NLP adds value over rule-based heuristics.

### 1.3 Originality lever: bilingual (EN/ID) CVs

Real student CVs in Indonesia are frequently **mixed English/Indonesian** — and off-the-shelf parsers handle them poorly. Handling bilingual input is therefore both the most realistic scenario **and** the project's original contribution. Strategy:

- **Language identification per segment / per bullet**, not per document. A CV may have an English summary and Indonesian experience bullets.
- **Do not translate everything.** Decide per shipped feature whether it is bilingual or English-only-with-detection. Features are built English-first, with Indonesian support added module by module (§6).
- Multilingual semantic models make bilingual similarity feasible without translation, but the specific model is an open decision (`DECISIONS.md`, menu 3).

---

## 2. Problem and Users

### 2.1 Problems solved

- Students/fresh graduates do not know how their CV *reads*: vague bullets, unsupported claims, irrelevant content.
- University career centers cannot review hundreds of student CVs line-by-line; they need consistent first-pass analysis and common-weakness reports.
- Mentors/supervisors want to give targeted advice but lack time; highlighted evidence and structured notes speed that up.
- (Relevance mode) Candidates applying to a specific role need to know where their profile semantically aligns and where it does not.

### 2.2 Target users (primary → secondary)

1. **Students and fresh graduates** improving their own CVs.
2. **University career centers** running first-pass reviews at scale.
3. **Mentors/supervisors** giving targeted feedback.

**Explicitly out of scope as a user story:** recruiters making hiring decisions. The system is **advisory, never decisional** — it never ranks people, never produces hire/no-hire output, and gives feedback *to* the candidate or their advisor. This stance avoids most ethical/legal hazards of automated screening (§9) and is a deliberate, defensible scoping decision worth stating in the thesis.

### 2.3 What users actually need

- Concrete, explainable feedback ("this bullet describes a duty, not an achievement") rather than scores without reasons.
- Consistency: the same CV should get the same analysis.
- Speed: far faster than a human line-by-line review.
- Safety: their (personal) data handled with consent and care.

---

## 3. NLP Capability Map

How the candidate capabilities map to underlying NLP tasks. Difficulty: Low / Med / Med-High / High. Value is judged **for this project** (candidate-facing coach + relevance mode).

| Capability | Underlying NLP tasks | Difficulty | Value | Tier |
|---|---|---|---|---|
| Extract skills, education, experience, achievements | NER / sequence labeling, keyphrase extraction, taxonomy linking | Med | High — foundation for everything else | Essential |
| Understand meaning & context of content | Embeddings, sentence classification (achievement vs. duty vs. responsibility) | Med | High | Essential |
| Relationships between pieces of information | Coreference, entity linking, **claim–evidence alignment** | Med-High | High — real differentiator | Optional→Advanced |
| Compare information within a CV | Semantic textual similarity (redundancy), contradiction detection | Med | Med-High | Essential (redundancy) |
| Evaluate relevance / appropriateness | Relevance classification, buzzword-vs-substance ("semantic density"), style analysis | Med | High | Essential |
| Detect missing / unclear / repetitive / inconsistent info | Vagueness detection ("responsible for…", "various tasks"), redundancy, timeline consistency | Low-Med | High — very demo-able | Essential (vagueness, redundancy) |
| Experience ↔ skills relationship | Implicit skill extraction from experience bullets, evidence linking, skill graph | High | High | Advanced |
| Generate insights | Extractive/abstractive summarization, grounded feedback generation | Med-High | High | Essential (report), Optional (profile summary) |
| Compare CV against a requirement/target role | Semantic matching, gap analysis vs. job description or role profile | Med | High | Essential (as toggleable module) |

### 3.1 The three strongest "NLP heart" candidates

These are genuinely semantic (a parser or keyword list cannot do them), produce explainable output, and can be evaluated with modest hand-labeled data:

1. **Impact/vagueness language analysis** — distinguishing "helped with various tasks" from "reduced processing time by 30% for 5,000 users". *→ Essential.*
2. **Claim–evidence consistency** — a skill claimed in the summary but never demonstrated in experience; dates that contradict; a repeated, paraphrased bullet. *→ Optional (advanced version of redundancy).*
3. **Semantic relevance matching** — CV-to-job-description alignment that is *semantic*, not keyword counting. *→ Essential as toggleable module.*

---

## 4. What Genuinely Requires NLP (and What Doesn't)

| Category | Items | Rationale |
|---|---|---|
| **Not NLP** (but needed) | File/text extraction, contact extraction, date normalization, word counts, formatting checks, storage, UI | Deterministic plumbing; cap effort here |
| **Hybrid** (rules + NLP) | Section segmentation, completeness vs. section checklist, readability metrics, terminology consistency | Heuristic first pass, NLP catches what rules miss |
| **Truly NLP** | Synonym/context-aware skill recognition ("JS" ↔ "JavaScript" ↔ "ECMAScript" in context), semantic similarity, claim–evidence linking, redundancy via paraphrase detection, vagueness detection, relevance to a target, summarization, feedback generation | Impossible or unreliable without language understanding |

**Design principle:** build each feature as a **rule-based baseline + NLP improvement**, then measure the delta. This yields both a robust fallback and a thesis chapter (§8).

---

## 5. Conceptual Pipeline

```
Ingest → Segment → Extract → Understand → Evaluate → Explain
 (1)       (2)        (3)         (4)          (5)         (6)
```

1. **Ingest** — text extraction from PDF/docx/plain text, plus a "paste text" fallback. *Preprocessing, not intelligence — strictly time-boxed (§9).*
2. **Segment** — split into summary / education / experience / skills. Hybrid: heading heuristics first, NLP to catch non-standard CVs.
3. **Extract** — skills, experience entries, education, quantified achievements. Rules baseline → NLP improvement.
4. **Understand** — the semantic layer: per-segment language identification (bilingual core), embeddings for meaning/similarity, statement-type classification (achievement vs. duty).
5. **Evaluate** — rubric-based quality dimensions: impact/vagueness, redundancy, unsupported claims, completeness, relevance-to-target. **Every finding cites exact evidence spans.**
6. **Explain** — the report: findings, grounded suggestions, embedded candidate-profile summary, optional relevance/gap analysis vs. a JD.

The evaluation harness (§8) wraps this pipeline and is designed **independently of implementation choices**.

---

## 6. Scope Tiers

### Essential — the semester's non-negotiables

- Ingestion (text-first, PDF best-effort) + section segmentation
- Core extraction: skills + experience entries + education (rules baseline → NLP layer)
- Language identification + bilingual handling *of shipped features* (chosen per module)
- Two evaluation modules: **impact/vagueness language analysis** + **redundancy detection**
- **Relevance mode**: CV vs. pasted job description — semantic matching + gap list
- Evidence-grounded report + simple web UI
- Small evaluation: 30–50 CV gold set, precision/recall, baseline-vs-NLP delta, ~10-person Likert survey

### Optional — add if weeks allow

- Claim–evidence consistency check
- Candidate-profile summary generation (embedded in report)
- Skill normalization to a taxonomy (ESCO / O*NET — **check licensing and ID coverage first**)
- Readability / tone metrics
- CV history comparison (two versions of one person's CV)

### Advanced — thesis-stretching; cut first under pressure

- Fine-tuned NER on your own annotated corpus (a real ML contribution)
- Skill-graph reasoning (ontology-based inference)
- Cross-lingual alignment as an explicit research question
- Comparative benchmark chapter (rules vs. classical ML vs. transformers vs. LLM prompting on one task)

### Unnecessary — keep out (over-engineering traps)

- Full ATS/recruitment workflow (pipelines, user management, scheduling)
- Training models from scratch; deploying your own large model
- Personality/emotion prediction from CV text (scientifically weak, bias-prone)
- CV template design/generation (not NLP)
- Scraping CVs at scale (privacy/legal risk)
- Automated hire/no-hire scoring as a headline feature

---

## 7. Semester Roadmap (~14–16 weeks)

| Weeks | Milestone | Notes |
|---|---|---|
| 1–2 | **Corpus & rubric** | Collect 30–50 consenting sample CVs (+ synthetic for gaps); define the quality rubric *before* building anything |
| 3–4 | **Ingestion + segmentation baseline** | Text-first; language-ID spike |
| 5–7 | **Extraction layer** | Skills, experience: rules baseline first, then NLP improvement; measure both |
| 8–10 | **Evaluation modules** | Impact/vagueness → redundancy → relevance mode (toggleable) |
| 11–12 | **Report + web UI** | Evidence-grounded output; thin UI over a solid core |
| 13–14 | **Evaluation experiments + user study** | Gold-set metrics, baseline-vs-NLP delta, Likert survey |
| 15–16 | **Writing, polish, defense prep** | Blueprint/decision docs → thesis material |

**Sequencing recommendation (accept or reject):** build the **English path first**, then add Indonesian via language-aware components. Bilingual-first multiplies every task; English-first + ID modules gives a working system early and a clean bilingual extension story.

---

## 8. Evaluation Plan (how NLP quality is proven)

### 8.1 Data

- **Gold set:** 30–50 CVs, hand-annotated for the features shipped (sections, skills, vague bullets, redundant pairs, etc.). Sources: consenting classmates/colleagues (privacy — §9), public sample datasets (**check licenses**), synthetic CVs to fill gaps.
- **Annotation guidelines** written down before annotating; a second annotator on a subset gives inter-annotator agreement (even a small Cohen's κ strengthens the thesis considerably).

### 8.2 Metrics

- **Intrinsic:** precision / recall / F1 for extraction; ranking quality for similarity; classification accuracy for statement types.
- **Baselines:** rules-only vs. NLP-augmented on every feature. **The delta is the strongest possible argument that NLP is the core.**
- **Generation quality (report/summaries):** fluency, actionability, and **faithfulness** — does every generated statement trace to real CV content? (Human-rated on a small scale.)
- **User study:** ~10 participants, Likert survey on usefulness and clarity of the report. Cheap, persuasive in a defense.

### 8.3 Embedded comparative experiment

One well-defined task (e.g., skill extraction or relevance estimation) is benchmarked across approach families (rules / classical ML / pretrained transformers / LLM prompting). This gives the project empirical rigor without becoming the product direction.

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Bilingual scope creep multiplies every task | English-first build order (§7); per-feature decision on bilingual support; language ID keeps unhandled languages detectable and honest |
| PDF parsing rabbit hole (layout chaos eats months) | Text-first policy; PDF is best-effort; "paste text" fallback always available; time-boxed ingestion phase |
| CVs are personal data | Explicit consent, anonymization where possible, synthetic data for gaps, secure local storage, no uploads to third-party services without checking policy |
| "Good CV" is subjective → unmeasurable | Quality rubric defined **first** (weeks 1–2); every evaluation module maps to a rubric criterion |
| LLM-generated feedback hallucinates | Grounded generation: every statement must cite extracted evidence; verification layer if generative models are used (decision menu 5) |
| Reproducibility of external LLM APIs | Record model/version/parameters; prefer deterministic components for graded paths; LLM as comparison baseline or clearly-fenced feature |
| Relevance mode drifts toward a recruitment system | Module is toggleable, advisory-only, and framed as "candidate's gap analysis", never ranking |
| Bias & fairness concerns | Advisory stance by design; document limitations; no demographic inference, no personality prediction |

---

## 10. Future Development (beyond the semester)

- Full multilingual expansion (more languages, better ID-specific models as the ecosystem matures)
- Domain adaptation: fresh-grad vs. senior CVs; field-specific rubrics
- Portfolio/LinkedIn context enrichment
- Interview-question suggestions derived from CV claims (grounded)
- Cohort-level analytics for career centers (common weaknesses across a program)
- Active-learning loop: user corrections improve extractors over time

---

## 11. Open Decisions

All implementation choices are deliberately open and tracked in **`DECISIONS.md`** with candidate approaches, trade-offs, and a decision record to fill in:

1. PDF/text extraction strategy
2. Skill & experience extraction approach
3. Semantic layer (similarity/matching)
4. Language identification approach
5. Feedback/report generation approach
6. Web UI framework

The evaluation harness (§8) is designed independently of these — the project must remain defensible regardless of which option is finally chosen.

---

## 12. Build Status (2026-09-27)

The core pipeline (Phases 1–10 of the build plan) is **implemented and tested**: 82 fast tests + 6 slow (real-model) integration tests, all passing. All six technical menus are decided and recorded in `DECISIONS.md` — including one empirically important finding: the locked NER checkpoint (`Davlan/xlm-roberta-base-ner-hrl`) ships slow-tokenizer weights only and returns no character offsets through the standard pipeline, which conflicts with the evidence-span invariant; it currently runs through a custom offset-preserving word-alignment layer, and a candidate replacement (offset-capable, EN+ID) is the top open follow-up for the extraction delta. The gold-set scaffold over the 2,484-CV corpus is generated; hand-annotation and the quality rubric (roadmap weeks 1–2) are the next project milestones before any thesis numbers are reported.
