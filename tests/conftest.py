"""Shared test fixtures."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

_TEST_RUNTIME_DIR = Path("output") / ".test-runtime"
_TEST_RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
os.environ.pop("TRANSFORMERS_CACHE", None)
os.environ.setdefault("HF_HOME", str(_TEST_RUNTIME_DIR / "hf-home"))


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure required env vars are set for all tests."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PRODUCER_MODEL", "deepseek-chat")
    monkeypatch.setenv("SUBAGENT_MODEL", "deepseek-chat")
    monkeypatch.setenv("JUDGE_MODEL", "deepseek-chat")
    monkeypatch.delenv("TRANSFORMERS_CACHE", raising=False)
    monkeypatch.setenv("HF_HOME", str(_TEST_RUNTIME_DIR / "hf-home"))


@pytest.fixture
def tmp_path() -> Path:
    """Use a workspace-local temp dir to avoid system temp permission issues."""
    base = Path("output") / "pytest-tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"case-{uuid.uuid4().hex}"
    path.mkdir()
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
