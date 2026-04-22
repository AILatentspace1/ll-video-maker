"""Shared state for the video production pipeline."""
from __future__ import annotations

from typing import Any, Literal, Optional

from langchain.agents import AgentState


class VideoProductionState(AgentState):
    output_dir: str = ""

    current_milestone: Literal["research", "script", "done"] = "research"
    milestone_research: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    milestone_script: Literal["pending", "in_progress", "completed", "failed"] = "pending"

    retry_research: int = 0
    retry_script: int = 0

    research_file: Optional[str] = None
    script_plan_file: Optional[str] = None
    script_file: Optional[str] = None
    contract_file: Optional[str] = None
    contract_review_file: Optional[str] = None
    script_eval_file: Optional[str] = None

    eval_round: int = 0
    eval_best_score: float = 0.0
    last_eval_result: Optional[dict[str, Any]] = None
    last_contract_review: Optional[dict[str, Any]] = None
    iteration_fixes: list[dict[str, Any]] = []
    contract_violations: list[dict[str, Any]] = []
    must_fix_summary: str = ""

    ratify_feedback: Optional[str] = None
    ratify_level: Literal["strict", "normal", "fast"] = "normal"
