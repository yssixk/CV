"""NLP extractor layer (menu 2c): pretrained multilingual transformer NER.

Model: ``Davlan/xlm-roberta-base-ner-hrl`` (XLM-R base, EN + ID among its
training languages). Labels: O / B-I-DATE / B-I-PER / B-I-ORG / B-I-LOC.

**Why word-level alignment instead of the HF pipeline:** this checkpoint ships
slow-tokenizer weights only (no ``tokenizer.json``) and misdeclares its
tokenizer class, which crashes the fast path on current ``transformers``; and
the slow-tokenizer pipeline returns word strings *without character offsets* —
unacceptable here, because every finding must carry an exact evidence span
(``text[start:end] == span``). So this module does its own offset-preserving
tokenization:

1. word-tokenize the document with a regex (every word knows its char span);
2. encode words with ``is_split_into_words=True`` (piece ids per word tracked
   manually — the slow tokenizer has no ``word_ids()``);
3. run the model directly (eval mode, no sampling -> deterministic);
4. map BIO predictions back through word spans to character offsets.

The model loads lazily and is cached process-wide. Any load failure raises
``NLPExtractorUnavailable`` and the pipeline degrades to rules-only — the NLP
layer is an enhancement, never a dependency.
"""
from __future__ import annotations

import re
import threading
from typing import Any

from cv_analyzer.config import Config, DEFAULT_CONFIG
from cv_analyzer.models import EntityMention, ExtractionResult, SkillMention
from cv_analyzer.utils.gazetteer_loader import load_gazetteer

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[str, tuple[Any, Any]] = {}

# checkpoint label -> internal entity kind
_LABEL_MAP = {
    "PER": "name",
    "ORG": "org",
    "LOC": "misc",
    "DATE": "date",
}

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[.'+#/-][A-Za-z0-9]+)*")
_WORDS_PER_CHUNK = 100          # ~<=400 XLM-R pieces, safely inside the 512 limit
_MAX_PIECES = 510               # [CLS] + pieces + [SEP]


class NLPExtractorUnavailable(RuntimeError):
    """Raised when the transformer backend cannot be loaded (offline, no RAM...)."""


def _load_components(model_name: str) -> tuple[Any, Any]:
    key = model_name
    with _MODEL_LOCK:
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        try:
            import torch
            from transformers import AutoModelForTokenClassification, XLMRobertaTokenizer

            # Explicit slow (sentencepiece) tokenizer: this repo has no
            # tokenizer.json and misdeclares its class; AutoTokenizer would
            # take the broken fast-conversion path (see module docstring).
            tokenizer = XLMRobertaTokenizer.from_pretrained(model_name)
            model = AutoModelForTokenClassification.from_pretrained(model_name)
            model.eval()   # no dropout at inference -> deterministic
        except Exception as exc:  # noqa: BLE001 — degrade gracefully, never crash the pipeline
            raise NLPExtractorUnavailable(f"could not load NER model {model_name!r}: {exc}") from exc
        _MODEL_CACHE[key] = (tokenizer, model)
        return tokenizer, model


def _word_spans(text: str) -> list[tuple[str, int, int]]:
    """Offset-preserving word tokenization: [(word, start, end)]."""
    return [(m.group(), m.start(), m.end()) for m in _WORD_RE.finditer(text)]


def _encode_words(tokenizer, words: list[str]):
    """Encode a word list; returns (ids, attention_mask, word_piece_spans).

    ``word_piece_spans[i]`` is the [start_piece, end_piece) range of word i
    inside the piece sequence (before adding specials). Built manually because
    slow tokenizers do not provide ``word_ids()``.
    """
    cls_id = tokenizer.cls_token_id
    sep_id = tokenizer.sep_token_id
    ids: list[int] = []
    word_piece_spans: list[tuple[int, int]] = []
    for word in words:
        piece_ids = tokenizer.encode(word, add_special_tokens=False)
        if not piece_ids:
            piece_ids = [tokenizer.unk_token_id]
        start = len(ids)
        ids.extend(piece_ids)
        word_piece_spans.append((start, len(ids)))
    input_ids = [cls_id] + ids[:_MAX_PIECES] + [sep_id]
    attention = [1] * len(input_ids)
    return input_ids, attention, word_piece_spans


def _predict_chunk(tokenizer, model, words: list[str]) -> list[str]:
    """BIO label per word for one chunk. Words truncated away get 'O'."""
    import torch

    input_ids, attention, word_piece_spans = _encode_words(tokenizer, words)
    with torch.no_grad():
        logits = model(
            input_ids=torch.tensor([input_ids]),
            attention_mask=torch.tensor([attention]),
        ).logits[0]                      # (seq_len, num_labels)
    piece_labels = logits.argmax(dim=-1).tolist()

    def _piece_label(piece_index: int) -> str:
        if piece_index >= len(piece_labels):
            return "O"
        return model.config.id2label[int(piece_labels[piece_index])]

    word_labels: list[str] = []
    for start, end in word_piece_spans:
        if start >= _MAX_PIECES:
            word_labels.append("O")      # truncated away
            continue
        labels = [_piece_label(p) for p in range(start, min(end, _MAX_PIECES))]
        # first non-O wins (B- tags preferred by construction of argmax order)
        chosen = next((l for l in labels if l != "O"), "O")
        word_labels.append(chosen)
    return word_labels


def _group_entities(words: list[tuple[str, int, int]], labels: list[str]) -> list[tuple[str, int, int]]:
    """Merge consecutive BIO word labels into (kind, start, end) char spans."""
    entities: list[tuple[str, int, int]] = []
    current_kind: str | None = None
    current_start = 0
    current_end = 0
    for (word, w_start, w_end), label in zip(words, labels):
        if label.startswith("B-"):
            if current_kind is not None:
                entities.append((current_kind, current_start, current_end))
            current_kind = label[2:]
            current_start, current_end = w_start, w_end
        elif label.startswith("I-") and current_kind == label[2:]:
            current_end = w_end
        else:
            if current_kind is not None:
                entities.append((current_kind, current_start, current_end))
            current_kind = None
    if current_kind is not None:
        entities.append((current_kind, current_start, current_end))
    return entities


def extract_entities(
    text: str,
    segments: list[tuple[int, int, str]] | None = None,
    model_name: str | None = None,
) -> list[EntityMention]:
    """Run NER over the whole document; returns entities with exact char spans."""
    cfg = DEFAULT_CONFIG if model_name is None else Config(ner_model=model_name)
    tokenizer, model = _load_components(cfg.ner_model)

    all_words = _word_spans(text)
    entities: list[EntityMention] = []
    segs = segments or []

    def _segment_of(start: int) -> str:
        for s, e, name in segs:
            if s <= start < e:
                return name
        return "document"

    for chunk_start in range(0, len(all_words), _WORDS_PER_CHUNK):
        chunk = all_words[chunk_start:chunk_start + _WORDS_PER_CHUNK]
        labels = _predict_chunk(tokenizer, model, [w for w, _, _ in chunk])
        for kind, start, end in _group_entities(chunk, labels):
            span_text = text[start:end]
            if not span_text.strip():
                continue
            entities.append(
                EntityMention(
                    label=_LABEL_MAP.get(kind, "misc"),
                    canonical=span_text.strip().upper()[:80],
                    text=span_text,
                    start=start,
                    end=end,
                    segment=_segment_of(start),
                    extractor="nlp",
                )
            )
    return entities


def _build_alias_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for canonical, spec in load_gazetteer("skills_en").items():
        for alias in spec.get("aliases", []):
            lookup[alias.lower()] = canonical
        lookup[canonical.lower()] = canonical
    for canonical, aliases in load_gazetteer("skills_id").items():
        for alias in aliases:
            lookup[alias.lower()] = canonical
    return lookup


def extract_skills_nlp(
    text: str,
    segments: list[tuple[int, int, str]] | None = None,
) -> list[SkillMention]:
    """Derive skill candidates from NLP entity spans.

    This checkpoint has no MISC label, so the cross-check runs over ORG/LOC
    spans (models frequently tag skill names as ORG in CV-like text): an
    entity surface that matches a gazetteer alias becomes an NLP skill
    mention. Skills the rules layer already covers are merged out later
    (``merge.py``) — provenance stays visible.
    """
    alias_lookup = _build_alias_lookup()
    mentions: list[SkillMention] = []
    for ent in extract_entities(text, segments):
        if ent.label not in {"org", "misc"}:
            continue
        canonical = alias_lookup.get(ent.text.strip().lower())
        if canonical:
            mentions.append(
                SkillMention(
                    canonical=canonical,
                    text=ent.text,
                    start=ent.start,
                    end=ent.end,
                    segment=ent.segment,
                    extractor="nlp",
                )
            )
    return mentions


def run_nlp_extraction(
    text: str,
    segments: list[tuple[int, int, str]] | None = None,
) -> ExtractionResult:
    """Run the NLP layer. Raises NLPExtractorUnavailable if the model can't load."""
    entities = extract_entities(text, segments)
    skills = extract_skills_nlp(text, segments)
    return ExtractionResult(skills=skills, entities=entities, extractor_name="nlp")
