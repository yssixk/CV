"""Central configuration.

Secrets come from the environment (or Streamlit secrets in deployment) — never
from source code. See SECURITY_CHECKLIST.md. All thresholds live here so the
evaluation harness can vary them deliberately.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields


def _load_dotenv_if_present() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:  # pragma: no cover - dotenv is in requirements, this is belt & braces
        pass


_load_dotenv_if_present()


def _streamlit_secrets() -> dict:
    """Return Streamlit's secrets mapping when running under Streamlit, else {}.

    On Streamlit Community Cloud the secrets manager is the ONLY config surface
    (there are no user-settable environment variables), so every setting must
    be readable from here — not just the API key.
    """
    try:
        import streamlit as st  # noqa: PLC0415
        # st.secrets supports `in` and mapping access on flat TOML files.
        return dict(st.secrets)
    except Exception:  # noqa: BLE001 - not running under Streamlit / no secrets file
        return {}


def _setting(name: str):
    """Resolve a setting: environment variable first, then Streamlit secrets.

    Values from st.secrets may be native TOML types (bool/int/float), not
    just strings, so callers must accept both.
    """
    raw = os.environ.get(name)
    if raw is not None:
        return raw
    secrets = _streamlit_secrets()
    return secrets.get(name)


@dataclass(frozen=True)
class Config:
    # --- LLM feedback layer (Phase 8) — fenced, OFF by default -------------
    use_llm_feedback: bool = False
    gemini_api_key: str = field(default="", repr=False)   # never logged, never serialized
    gemini_model: str = "gemini-2.0-flash"
    llm_temperature: float = 0.0
    llm_max_output_tokens: int = 1024
    llm_timeout_seconds: float = 20.0

    # --- Upload safety (security/validate_upload) --------------------------
    max_upload_mb: float = 5.0
    parse_timeout_seconds: float = 15.0

    # --- Rate limiting (security/rate_limit) -------------------------------
    rate_limit_calls_per_minute: int = 5

    # --- Semantic layer thresholds -----------------------------------------
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    redundancy_threshold: float = 0.85
    relevance_match_threshold: float = 0.50   # calibrated on MiniLM sims (see DECISIONS.md menu 3)
    relevance_top_k: int = 5

    # --- Extraction merge (Phase 4) ----------------------------------------
    nlp_extractor_enabled: bool = True
    ner_model: str = "Davlan/xlm-roberta-base-ner-hrl"

    # --- Verifier -----------------------------------------------------------
    verifier_mode: str = "keyword"        # "keyword" | "embedding"
    verifier_embedding_threshold: float = 0.60

    @classmethod
    def from_env(cls) -> "Config":
        """Build config from environment variables and/or Streamlit secrets.

        Every setting resolves from (1) the process environment, then (2)
        Streamlit's secrets manager (deployment). The API key is never logged
        or printed; ``active_fields`` redacts it in serialized output.
        """
        _load_dotenv_if_present()

        def _bool(name: str, default: bool) -> bool:
            raw = _setting(name)
            if raw is None:
                return default
            if isinstance(raw, bool):
                return raw
            return str(raw).strip().lower() in {"1", "true", "yes", "on"}

        def _float(name: str, default: float) -> float:
            raw = _setting(name)
            if raw is None:
                return default
            try:
                return float(raw)
            except (TypeError, ValueError):
                return default

        def _int(name: str, default: int) -> int:
            raw = _setting(name)
            if raw is None:
                return default
            try:
                return int(raw)
            except (TypeError, ValueError):
                return default

        def _str(name: str, default: str) -> str:
            raw = _setting(name)
            return default if raw is None else str(raw)

        api_key = _setting("GEMINI_API_KEY") or ""

        return cls(
            use_llm_feedback=_bool("USE_LLM_FEEDBACK", False),
            gemini_api_key=str(api_key),
            gemini_model=_str("GEMINI_MODEL", "gemini-2.0-flash"),
            llm_temperature=_float("LLM_TEMPERATURE", 0.0),
            llm_max_output_tokens=_int("LLM_MAX_OUTPUT_TOKENS", 1024),
            llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 20.0),
            max_upload_mb=_float("MAX_UPLOAD_MB", 5.0),
            parse_timeout_seconds=_float("PARSE_TIMEOUT_SECONDS", 15.0),
            rate_limit_calls_per_minute=_int("RATE_LIMIT_PER_MINUTE", 5),
            embedding_model=_str("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"),
            redundancy_threshold=_float("REDUNDANCY_THRESHOLD", 0.85),
            relevance_match_threshold=_float("RELEVANCE_MATCH_THRESHOLD", 0.50),
            relevance_top_k=_int("RELEVANCE_TOP_K", 5),
            nlp_extractor_enabled=_bool("NLP_EXTRACTOR_ENABLED", True),
            ner_model=_str("NER_MODEL", "Davlan/xlm-roberta-base-ner-hrl"),
            verifier_mode=_str("VERIFIER_MODE", "keyword"),
        )


# Process-wide default. Built from the environment at import time so every
# module shares the same configuration (and the same fenced-off LLM flag).
DEFAULT_CONFIG: Config = Config.from_env()


def active_fields(cfg: Config) -> dict[str, object]:
    """Return the config as a dict with the API key redacted (safe for logs/meta)."""
    out: dict[str, object] = {}
    for f in fields(cfg):
        val = getattr(cfg, f.name)
        out[f.name] = "***redacted***" if f.name == "gemini_api_key" else val
    return out
