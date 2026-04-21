"""Researcher subagent — 对应 agents/researcher.md。"""
from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain.tools import tool
from ..llm import get_llm
from ..config import cfg


@tool
def web_search(query: str) -> str:
    """搜索网络，返回结果摘要。"""
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().run(query)
    except Exception as e:
        return f"[搜索失败] {e}"


@tool
def read_file(file_path: str) -> str:
    """读取本地文件内容（local-file 来源时使用）。"""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except Exception as e:
        return f"[读取失败] {e}"


@tool
def write_research(output_dir: str, content: str) -> str:
    """将调研报告写入 {output_dir}/research.md，返回文件路径。"""
    path = Path(output_dir) / "research.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


SYSTEM_PROMPT = """你是视频制作团队的调研专家。根据话题收集素材，写入 research.md。

## 输出结构（9 个章节）
1. 核心事实（标注叙事位置：hook/setup/development/climax/cta）
2. 关键数据（精确数字，标注来源）
3. 视觉素材线索（visual_strategy: image_heavy|image_light|image_none）
4. 叙事结构建议
5. 参考来源（URL + 日期）
6. 视觉风格指南（Style Spine：主色调、光线、构图关键词）
7. 创作者观点
8. 数据可视化候选表格（claim/type/items/source，至少 3 行）
9. 金句候选（至少 2 条，供 quote_card）

## 规则
- 数据必须标注来源，禁止模糊表述（"约"、"超过"等）
- web_search 至少搜索 3 次，覆盖：最新动态、市场格局、专家观点
- 完成后调用 write_research 写入文件，返回路径
"""


def create_researcher_agent():
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.3)
    return create_agent(
        model=model,
        tools=[web_search, read_file, write_research],
        system_prompt=SYSTEM_PROMPT,
        name="researcher",
    )
