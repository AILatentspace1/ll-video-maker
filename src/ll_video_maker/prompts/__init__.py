"""Prompt loading and rendering helpers."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent
_TEMPLATE_PATTERN = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load prompts/{name}.md and return its UTF-8 text."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **context: Any) -> str:
    """Load and render prompts/{name}.md with simple {{ variable }} placeholders."""
    prompt = load_prompt(name)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            raise KeyError(f"missing prompt variable: {key}")
        return str(context[key])

    return _TEMPLATE_PATTERN.sub(replace, prompt)
