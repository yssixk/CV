# CV NLP Analyzer — CV Quality Coach + Relevance Mode

Evidence-grounded, bilingual (EN/ID) CV quality analysis in Python. **NLP is the
core intelligence**: every finding the system produces cites the exact source
text (character-offset span + line number). Advisory only — the system never
scores, ranks, or makes decisions about people.

Companion documents: [`PROJECT_BLUEPRINT.md`](PROJECT_BLUEPRINT.md) (vision,
scope, roadmap, evaluation plan) · [`DECISIONS.md`](DECISIONS.md) (open
technical decisions and their rationale) · [`SECURITY_CHECKLIST.md`](SECURITY_CHECKLIST.md)
(deployment gate).

## Architecture

```
Ingest → Segment → Extract → Understand → Evaluate → Explain
```

| Stage | Module | What it does | Baseline/NLP split |
|---|---|---|---|
| Ingest | `ingest/extract_text.py` | text/paste first-class; PDF (pdfminer→pypdf) & docx best-effort, timeout-guarded | — |
| Segment | `segment/segmenter.py` | EN+ID heading heuristics → summary/experience/education/skills | rules baseline (NLP upgrade deferred) |
| Extract | `extract/rules_extractor.py` | gazetteer skills + date/degree/GPA regex, exact spans | rules baseline |
| | `extract/nlp_extractor.py` | multilingual transformer NER (XLM-R), MISC↔gazetteer cross-check | NLP layer |
| | `extract/merge.py` | precedence merge (rules win overlaps; NLP adds new canonicals) | both |
| Understand | `understand/lang_id.py` | per-bullet EN/ID/mixed (seeded langdetect + wordlist/morphology fallback) | rules + statistical |
| | `understand/embeddings.py` | multilingual sentence embeddings (paraphrase-multilingual-MiniLM-L12-v2) | NLP |
| | `understand/statement_classifier.py` | achievement / duty / responsibility by cue phrases + quantification | rules baseline |
| Evaluate | `evaluate/vagueness.py` | duty-language bullets, unsupported self-assessment claims | rules |
| | `evaluate/redundancy.py` | paraphrase/duplicate bullet pairs (embeddings; lexical fallback) | NLP + rules fallback |
| | `evaluate/relevance.py` | CV vs JD semantic gap list (embeddings; lexical fallback) | NLP + rules fallback |
| Explain | `explain/report_builder.py` | assembles the full structured report — **complete with no LLM call** | — |
| | `explain/templates_en/id.py` + `message_renderer.py` | grounded template messages, EN + ID | rules |
| | `explain/summary.py` | extractive profile summary (selects real sentences, never generates) | NLP |
| | `explain/llm_feedback.py` + `llm_verifier.py` | **optional** Gemini rewrite of templated findings, behind flag + verification | NLP (fenced) |
| Security | `security/` | upload validation, PII redaction, rate limiting | — |
| Eval | `eval_harness/` | metrics, two-mode gold-set runner + delta, LLM faithfulness runner | — |

**Hard invariants** (enforced in `models.py`, verified in tests):
- every `Finding` carries ≥1 `Evidence`; `Evidence.text` is always an exact
  slice of the source document (`document[start:end] == text`).
- Gemini never sees raw CV text — only redacted, structured `Finding` data;
  every generated sentence passes the verifier or the template is shown.
- rules-only path produces a complete report (LLM layer is additive only).

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Windows; use bin/ on POSIX
# CPU torch: if the plain install grabs a CUDA build, instead:
#   pip install torch --index-url https://download.pytorch.org/whl/cpu
cp .env.example .env                                 # fill in only if enabling the LLM layer
```

First run downloads the embedding model (~470 MB) and — only if the NLP
extraction layer is on — the XLM-R NER model (~1.1 GB), cached under
`~/.cache/huggingface`.

## Run

```bash
# UI
.venv/Scripts/streamlit run cv_analyzer/ui/app.py

# Full test suite
.venv/Scripts/python -m pytest -m "not slow"

# Rules baseline sanity score on the real corpus (NOT a thesis number)
.venv/Scripts/python -m cv_analyzer.eval_harness.score_rules_sample --n 50

# Build a hand-annotation scaffold from the resumes/ corpus
.venv/Scripts/python -m cv_analyzer.eval_harness.build_gold_sample \
    --csv resumes/Resume/Resume.csv --n 30 --out data/gold_set/annotations_scaffold.json
```

## Evaluation workflow (thesis)

1. **Gold set**: annotate the scaffold (skills/education spans) →
   `gold_set_runner.run_gold_set(path)` runs rules-only vs rules+NLP and
   reports per-feature P/R/F1 **delta** — the core evidence that the NLP layer
   adds value (menu 2e's "never worse than baseline, measurable delta").
2. **Faithfulness**: `faithfulness_runner.run_faithfulness(...)` scores what
   fraction of LLM sentences pass verification (replay mode keeps this
   offline/reproducible). Secondary evaluation chapter.
3. **Language ID**: the labeled 50-bullet set in `tests/test_lang_id.py`
   documents empirical accuracy (currently 98%, bar 80%).

## Data

`resumes/` holds the evaluation corpus (2,484 CVs, Kaggle/HF "Master Resumes",
MIT). It is the **eval set only** — never Gemini training data, never
committed (gitignored). `data/gold_set/` holds annotation scaffolds; real CVs
must never be committed.

## Out of scope (deliberately)

Full ATS/recruitment workflow, hiring decisions or ranking, OCR, translation-
bridge similarity, skill-graph reasoning, fine-tuned custom NER, CV template
generation, bulk CV scraping. See blueprint §6.
