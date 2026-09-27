"""Tiny deterministic text helpers shared across modules."""
from __future__ import annotations


def light_stem(token: str) -> str:
    """Deterministic plural/inflection trimming so 'dashboards' matches 'dashboard'.

    Deliberately NOT real lemmatization — just enough to stop brittle token
    mismatches, kept tiny and inspectable (project rule: explainability).
    """
    for suffix in ("ies", "es", "s", "ing", "ed"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            token = token[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    if token.endswith("e") and len(token) >= 4:
        token = token[:-1]
    return token
