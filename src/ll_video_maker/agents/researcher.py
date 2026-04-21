"""Researcher subagent — 对应 agents/researcher.md。"""
from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain.tools import tool
from ..llm import get_llm
from ..config import cfg
from ..prompts import load_prompt
from .shared import read_file


@tool
def web_search(query: str) -> str:
    """搜索网络，返回结果摘要。"""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().run(query)
    except (ImportError, OSError) as e:
        return f"[搜索失败] {e}"


@tool
def write_research(output_dir: str, content: str) -> str:
    """将调研报告写入 {output_dir}/research.md，返回文件路径。"""
    path = Path(output_dir) / "research.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


SYSTEM_PROMPT = load_prompt("researcher")


def create_researcher_agent() -> Runnable:
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.3)
    return create_agent(
        model=model,
        tools=[web_search, read_file, write_research],
        system_prompt=SYSTEM_PROMPT,
        name="researcher",
    )
