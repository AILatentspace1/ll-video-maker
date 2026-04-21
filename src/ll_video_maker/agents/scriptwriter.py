"""Scriptwriter subagent — 对应 agents/scriptwriter.md（3-Pass 生成）。"""
from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain.tools import tool
from ..llm import get_llm
from ..config import cfg
from ..prompts import load_prompt


@tool
def read_research(research_file: str) -> str:
    """读取 research.md 内容。"""
    try:
        return Path(research_file).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        return f"[读取失败] {e}"


@tool
def read_file(file_path: str) -> str:
    """读取任意文件内容。"""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        return f"[读取失败] {e}"


@tool
def write_script(output_dir: str, content: str) -> str:
    """将脚本写入 {output_dir}/script.md，返回文件路径。"""
    path = Path(output_dir) / "script.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


@tool
def write_contract(output_dir: str, contract_json: str) -> str:
    """将脚本合约写入 {output_dir}/script-contract.json（GAN eval mode）。"""
    import json
    path = Path(output_dir) / "script-contract.json"
    try:
        json.loads(contract_json)
    except json.JSONDecodeError as e:
        return f"[JSON 验证失败] {e}"
    path.write_text(contract_json, encoding="utf-8")
    return str(path)


SYSTEM_PROMPT = load_prompt("scriptwriter")


def create_scriptwriter_agent() -> Runnable:
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.6)
    return create_agent(
        model=model,
        tools=[read_research, read_file, write_script, write_contract],
        system_prompt=SYSTEM_PROMPT,
        name="scriptwriter",
    )
