"""Evaluator subagent — GAN eval mode 脚本质量评估（对应 agents/evaluator.md）。"""
from __future__ import annotations

import json
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain.tools import tool
from ..llm import get_llm
from ..config import cfg
from ..prompts import render_prompt
from .shared import read_file


@tool
def read_file(file_path: str) -> str:
    """读取任意文件内容。"""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        return f"[读取失败] {e}"


@tool
def write_eval_result(output_dir: str, result_json: str, phase: str = "eval") -> str:
    """写入评估结果 JSON。phase: contract_review | eval。"""
    names = {"contract_review": "contract-review.json", "eval": "script-eval.json"}
    path = Path(output_dir) / names.get(phase, f"{phase}.json")
    try:
        json.loads(result_json)
    except json.JSONDecodeError as e:
        return f"[JSON 验证失败] {e}"
    path.write_text(result_json, encoding="utf-8")
    return str(path)


SYSTEM_PROMPT = render_prompt("evaluator")


def create_evaluator_agent() -> Runnable:
    model = get_llm(cfg.JUDGE_MODEL, temperature=0.2)
    return create_agent(
        model=model,
        tools=[read_file, write_eval_result],
        system_prompt=SYSTEM_PROMPT,
        name="evaluator",
    )
