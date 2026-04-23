"""Shared test fixtures."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_KOTLIN_DIR = FIXTURES_DIR / "sample_kotlin"


@pytest.fixture
def sample_kotlin_dir():
    return SAMPLE_KOTLIN_DIR


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR
