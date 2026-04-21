"""共享 tools — 多个 subagent 复用的基础工具。"""
from __future__ import annotations

from pathlib import Path

from langchain.tools import tool


@tool
def read_file(file_path: str) -> str:
    """读取文件内容。"""
    if not file_path:
        return "[空路径]"
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        return f"[读取失败] {e}"
