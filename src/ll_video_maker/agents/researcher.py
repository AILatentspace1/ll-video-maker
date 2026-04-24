"""Researcher subagent — 对应 agents/researcher.md。"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.runnables import Runnable
from langchain_core.runnables.config import RunnableConfig

logger = logging.getLogger(__name__)
from ..llm import get_llm
from ..config import cfg
from ..prompts import render_prompt
from .shared import read_file


def _run_single_search(query: str, config: RunnableConfig | None = None) -> str:
    from langchain_community.tools import DuckDuckGoSearchResults

    tool = DuckDuckGoSearchResults(
        num_results=5,
        output_format="json",
        keys_to_include=["title", "link", "snippet"],
    )
    if config:
        return tool.invoke(query, config=config)
    return tool.run(query)


def _normalize_queries(queries: list[str], *, limit: int = 5) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in queries:
        query = " ".join(str(raw or "").split()).strip()
        if not query:
            continue
        key = query.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(query)
        if len(normalized) >= limit:
            break
    return normalized


@tool
def web_search(query: str, config: RunnableConfig) -> str:
    """搜索网络，返回带 title/link/snippet 的结果摘要；link 必须写入 research.md Sources。"""
    try:
        return _run_single_search(query, config)
    except Exception as e:
        logger.exception(f"搜索单条 query 失败: {query}")
        return f"[搜索失败] {e}"


@tool
def parallel_web_search(queries: list[str], config: RunnableConfig) -> str:
    """并行搜索多个 query，返回带 title/link/snippet 的合并摘要；link 必须写入 research.md Sources。"""
    normalized = _normalize_queries(queries)
    if not normalized:
        return "[搜索失败] 空 queries"

    from langchain_core.runnables.config import ensure_config
    
    # 获取 current config 并浅拷贝传递给每个子任务
    local_config = ensure_config(config)

    with ThreadPoolExecutor(max_workers=min(len(normalized), 5)) as executor:
        future_to_query = {
            executor.submit(_run_single_search, q, local_config): q for q in normalized
        }
        ordered: dict[str, str] = {}
        for future in as_completed(future_to_query):
            query = future_to_query[future]
            try:
                ordered[query] = future.result()
            except Exception as e:
                logger.exception(f"并行搜索抛出异常 query={query}")
                ordered[query] = f"[搜索失败] {e}"

    merged: list[str] = []
    for index, query in enumerate(normalized, start=1):
        merged.append(f"## Query {index}: {query}\n{ordered[query]}")
    return "\n\n".join(merged)


@tool
def write_research(output_dir: str, content: str) -> str:
    """将调研报告写入 {output_dir}/research.md，返回文件路径。"""
    path = Path(output_dir) / "research.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


SYSTEM_PROMPT = render_prompt("researcher")


def create_researcher_agent() -> Runnable:
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.3)
    return create_agent(
        model=model,
        tools=[parallel_web_search, web_search, read_file, write_research],
        system_prompt=SYSTEM_PROMPT,
        name="researcher",
    )
