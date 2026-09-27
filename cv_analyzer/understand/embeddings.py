"""Multilingual sentence embeddings (menu 3b) — thin wrapper, one shared engine.

Powers redundancy (CV-internal), relevance (CV vs JD), and the verifier's
embedding mode. Model: ``paraphrase-multilingual-MiniLM-L12-v2`` — trained on
50+ languages (EN + ID included) in a single vector space, which is exactly
what the bilingual story needs (an English summary sentence and an Indonesian
experience bullet can be compared directly).

The model (~470 MB) downloads on first use and caches under ~/.cache. Loading
is lazy, cached process-wide, and degrades gracefully: if unavailable, callers
receive ``None`` and fall back to the lexical path (redundancy) or an error
message in the relevance module (no silent quality loss).
"""
from __future__ import annotations

import threading
from typing import Any

from cv_analyzer.config import DEFAULT_CONFIG

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {}


class EmbeddingUnavailable(RuntimeError):
    """Raised when the embedding model cannot be loaded (offline first run, OOM)."""


def get_model(model_name: str | None = None):
    """Load and cache the embedding model. Thread-safe, lazy, single instance."""
    name = model_name or DEFAULT_CONFIG.embedding_model
    with _LOCK:
        if name in _CACHE:
            return _CACHE[name]
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(name, device="cpu")
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            raise EmbeddingUnavailable(f"could not load embedding model {name!r}: {exc}") from exc
        _CACHE[name] = model
        return model


def embed(texts: list[str], model_name: str | None = None):
    """Embed texts -> normalized numpy array (n, dim). Raises EmbeddingUnavailable."""
    model = get_model(model_name)
    return model.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )


def similarity(vec_a, vec_b) -> float:
    """Cosine similarity of two (already normalized) vectors."""
    import numpy as np

    a = np.asarray(vec_a, dtype="float32").ravel()
    b = np.asarray(vec_b, dtype="float32").ravel()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def pairwise_similarities(texts: list[str], model_name: str | None = None):
    """All pairwise cosine similarities (i<j) as (i, j, score) triples."""
    import numpy as np

    vectors = embed(texts, model_name)
    scores = vectors @ vectors.T
    n = len(texts)
    out = []
    for i in range(n):
        for j in range(i + 1, n):
            out.append((i, j, float(scores[i, j])))
    return out
