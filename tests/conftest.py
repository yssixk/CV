"""Shared test fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Expose a marker so slow model-loading tests can be deselected:
#   pytest -m "not slow"
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: downloads/loads heavy models (deselect with -m 'not slow')")


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def smoke_cv_text() -> str:
    return (FIXTURES_DIR / "smoke_cv.txt").read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def smoke_cv_mixed_text() -> str:
    return (FIXTURES_DIR / "smoke_cv_mixed.txt").read_text(encoding="utf-8")
