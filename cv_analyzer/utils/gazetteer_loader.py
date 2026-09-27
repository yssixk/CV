"""Shared helpers for loading JSON gazetteers from ``cv_analyzer/data``."""
from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=None)
def load_gazetteer(name: str) -> dict[str, Any]:
    """Load a gazetteer JSON file by bare name (e.g. ``"skills_en"``)."""
    resource = resources.files("cv_analyzer") / "data" / "gazetteers" / f"{name}.json"
    with resource.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"gazetteer {name!r} must be a JSON object")
    return data


def clear_gazetteer_cache() -> None:
    """Reset the cache (used by tests that mutate gazetteers)."""
    load_gazetteer.cache_clear()
