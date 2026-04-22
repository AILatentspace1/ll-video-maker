"""Prompt loading helpers."""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load prompts/{name}.md and return its UTF-8 text."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
