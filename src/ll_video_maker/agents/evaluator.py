"""Evaluator subagent — GAN eval mode 脚本质量评估（对应 agents/evaluator.md）。"""
from __future__ import annotations

import json
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain.tools import tool
from ..llm import get_llm
from ..config import cfg
from .shared import read_file


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


SYSTEM_PROMPT = """你是独立质量评估官。核心信念：**每个产出都有未被发现的缺陷——你的工作是证明它们存在**。

## 合约审查（phase=contract_review）
验证 script-contract.json 是否合理，输出：
```json
{"overall": "approved|rejected", "reviewed_items": [{"item": "...", "status": "ok|rejected", "suggestion": "..."}]}
```

## 脚本评估（phase=eval）
对照 contract 逐项检查 script.md，评估维度（加权）：
- narrative_flow 30%：故事弧完整、叙事连贯
- contract_compliance 25%：场景数量/类型符合合约
- data_accuracy 20%：数字可溯源到 research.md
- pacing 15%：高密度场景不连续、时长合理
- visual_variety 10%：类型多样

输出：
```json
{
  "pass": true/false,
  "weighted_total": 75.5,
  "dimension_scores": {"narrative_flow": 80, ...},
  "contract_violations": ["..."],
  "iteration_fixes": [{"priority": 1, "issue": "...", "fix": "..."}]
}
```

## 规则
- 引用具体场景编号和文本片段作为证据
- "看起来还行"不是通过理由
- 完成后用 write_eval_result 写入文件
"""


def create_evaluator_agent() -> Runnable:
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.2)
    return create_agent(
        model=model,
        tools=[read_file, write_eval_result],
        system_prompt=SYSTEM_PROMPT,
        name="evaluator",
    )
