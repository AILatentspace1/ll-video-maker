"""Shared test fixtures."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure required env vars are set for all tests."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("PRODUCER_MODEL", "deepseek-chat")
    monkeypatch.setenv("SUBAGENT_MODEL", "deepseek-chat")
    monkeypatch.setenv("JUDGE_MODEL", "deepseek-chat")
