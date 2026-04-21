"""视频制作 State — 只涵盖 research + script 两个 milestone。"""
from __future__ import annotations

from typing import Literal, Optional

from langchain.agents import AgentState


class VideoProductionState(AgentState):
    # 输出目录
    output_dir: str = ""

    # 里程碑状态
    current_milestone: Literal["research", "script", "done"] = "research"
    milestone_research: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    milestone_script: Literal["pending", "in_progress", "completed", "failed"] = "pending"

    # 重试计数
    retry_research: int = 0
    retry_script: int = 0

    # 产出物路径
    research_file: Optional[str] = None       # output_dir/research.md
    script_file: Optional[str] = None         # output_dir/script.md
    contract_file: Optional[str] = None       # output_dir/script-contract.json (GAN)

    # GAN eval 迭代
    eval_round: int = 0
    eval_best_score: float = 0.0

    # L1 失败反馈 (注入下次重试)
    ratify_feedback: Optional[str] = None

    # 审核强度
    ratify_level: Literal["strict", "normal", "fast"] = "normal"
