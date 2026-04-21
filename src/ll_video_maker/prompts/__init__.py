"""Prompt 加载工具 — 从 prompts/ 目录读取 .md 文件作为 system prompt。"""
from __future__ import annotations

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """加载 prompts/{name}.md，返回内容字符串。"""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
