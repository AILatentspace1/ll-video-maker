"""任务上下文解析：统一处理 milestone / phase / validation target。"""
from __future__ import annotations

import re


def infer_milestone(description: str, state: object, fallback: str = "research") -> str:
    match = re.search(r"(?im)^\s*milestone:\s*([a-z_][a-z0-9_]*)\s*$", str(description or ""))
    if match:
        return match.group(1).strip().lower()

    current = getattr(state, "current_milestone", None)
    if isinstance(current, str) and current and current != "done":
        return current

    return fallback


def infer_phase(description: str) -> str:
    match = re.search(r"(?im)^\s*phase:\s*([a-z_][a-z0-9_]*)\s*$", str(description or ""))
    if match:
        return match.group(1).strip().lower()

    normalized = str(description or "").lower()
    if "contract_review" in normalized:
        return "contract_review"
    if re.search(r"phase:\s*eval\b", normalized):
        return "eval"
    return ""


def infer_validation_target(agent_name: str, description: str, state: object) -> str:
    if agent_name == "researcher":
        return "research"
    if agent_name == "scriptwriter":
        return "script"
    if agent_name != "evaluator":
        return infer_milestone(description, state)

    milestone = infer_milestone(description, state)
    phase = infer_phase(description)
    if phase == "contract_review":
        return f"{milestone}_contract_review"
    if phase == "eval":
        return f"{milestone}_eval"
    return milestone

