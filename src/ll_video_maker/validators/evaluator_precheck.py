from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .script_contract import check_script_contract
from .script_plan import check_script_plan
from .script_plan_consistency import check_script_plan_consistency


CANONICAL_NARRATIVE_ROLES = {"hook", "setup", "development", "climax", "cta"}


def run_evaluator_precheck(output_dir: str, *, milestone: str, phase: str) -> dict[str, Any] | None:
    if milestone != "script":
        return None
    if phase == "contract_review":
        return _precheck_script_contract_review(output_dir)
    if phase == "eval":
        return _precheck_script_eval(output_dir)
    return None


def _precheck_script_contract_review(output_dir: str) -> dict[str, Any] | None:
    path = Path(output_dir) / "script-contract.json"
    if not path.exists():
        return {
            "phase": "contract_review",
            "milestone": "script",
            "pass": False,
            "contract_review": {},
            "issues": [{"field": "script-contract.json", "reason": "文件不存在", "severity": "critical"}],
            "recommendation": "先生成合法的 script-contract.json 再进入 evaluator。",
        }

    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "phase": "contract_review",
            "milestone": "script",
            "pass": False,
            "contract_review": {},
            "issues": [{"field": "script-contract.json", "reason": "JSON 无法解析", "severity": "critical"}],
            "recommendation": "修复 script-contract.json 的 JSON 结构。",
        }

    issues: list[dict[str, str]] = []
    if contract.get("version") != 1:
        issues.append({"field": "version", "reason": "必须等于 1", "severity": "critical"})

    target_scene_count = contract.get("target_scene_count") or {}
    min_scenes = target_scene_count.get("min")
    max_scenes = target_scene_count.get("max")
    if not isinstance(min_scenes, int) or not isinstance(max_scenes, int) or min_scenes > max_scenes:
        issues.append({"field": "target_scene_count", "reason": "min/max 缺失或非法", "severity": "critical"})

    target_duration = contract.get("target_duration_frames") or {}
    min_frames = target_duration.get("min")
    max_frames = target_duration.get("max")
    if not isinstance(min_frames, int) or not isinstance(max_frames, int) or min_frames > max_frames:
        issues.append({"field": "target_duration_frames", "reason": "min/max 缺失或非法", "severity": "critical"})

    narrative = contract.get("narrative_structure") or {}
    opening_type = str(narrative.get("opening_type", "")).strip()
    closing_type = str(narrative.get("closing_type", "")).strip()
    if not opening_type or not closing_type:
        issues.append({"field": "narrative_structure", "reason": "opening_type/closing_type 缺失", "severity": "major"})
    else:
        if opening_type not in CANONICAL_NARRATIVE_ROLES:
            issues.append({"field": "narrative_structure.opening_type", "reason": "必须使用 canonical narrative_role: hook/setup/development/climax/cta", "severity": "critical"})
        if closing_type not in CANONICAL_NARRATIVE_ROLES:
            issues.append({"field": "narrative_structure.closing_type", "reason": "必须使用 canonical narrative_role: hook/setup/development/climax/cta", "severity": "critical"})
        if opening_type != "hook":
            issues.append({"field": "narrative_structure.opening_type", "reason": "当前状态机要求 opening_type 为 hook，以匹配首个内容场景", "severity": "major"})
        if closing_type != "cta":
            issues.append({"field": "narrative_structure.closing_type", "reason": "当前状态机要求 closing_type 为 cta，以匹配最后内容场景", "severity": "major"})

    if not isinstance(contract.get("audience"), str) or not str(contract.get("audience")).strip():
        issues.append({"field": "audience", "reason": "audience 缺失", "severity": "major"})

    key_topics = contract.get("key_topics") or []
    if not isinstance(key_topics, list) or len(key_topics) < 2:
        issues.append({"field": "key_topics", "reason": "至少需要 2 个 key_topics", "severity": "critical"})
    elif any(not isinstance(item, dict) for item in key_topics):
        issues.append({"field": "key_topics", "reason": "每个 key_topic 必须是包含 topic/narrative_role 的对象", "severity": "critical"})
    else:
        for idx, item in enumerate(key_topics):
            topic = str(item.get("topic", "")).strip()
            role = str(item.get("narrative_role", "")).strip()
            if not topic:
                issues.append({"field": f"key_topics[{idx}].topic", "reason": "topic 缺失或为空", "severity": "critical"})
            if role not in CANONICAL_NARRATIVE_ROLES:
                issues.append({"field": f"key_topics[{idx}].narrative_role", "reason": "必须是 hook/setup/development/climax/cta 之一，且使用小写英文", "severity": "critical"})
        first_role = str(key_topics[0].get("narrative_role", "")).strip()
        last_role = str(key_topics[-1].get("narrative_role", "")).strip()
        if opening_type and first_role and opening_type != first_role:
            issues.append({"field": "key_topics[0].narrative_role", "reason": f"必须与 opening_type 一致: {opening_type}", "severity": "major"})
        if closing_type and last_role and closing_type != last_role:
            issues.append({"field": f"key_topics[{len(key_topics) - 1}].narrative_role", "reason": f"必须与 closing_type 一致: {closing_type}", "severity": "major"})

    constraints = contract.get("constraints") or {}
    if not isinstance(constraints.get("max_consecutive_same_type"), int):
        issues.append({"field": "constraints.max_consecutive_same_type", "reason": "缺失或非法", "severity": "critical"})

    if not issues:
        return None

    return {
        "phase": "contract_review",
        "milestone": "script",
        "pass": False,
        "contract_review": {},
        "issues": issues,
        "recommendation": "先修复 contract 的必填字段与区间约束，再进入 evaluator。",
    }


def _precheck_script_eval(output_dir: str) -> dict[str, Any] | None:
    errors = [
        *check_script_plan(output_dir),
        *check_script_contract(output_dir),
        *check_script_plan_consistency(output_dir),
    ]
    if not errors:
        return None

    fixes = [
        {
            "priority": idx,
            "target": "script_artifacts",
            "action": error,
            "expected_impact": "修复结构性问题后再进入 evaluator，可减少无效 LLM 调用。",
        }
        for idx, error in enumerate(errors[:5], start=1)
    ]
    dimensions = [
        {
            "name": name,
            "score": 20,
            "weight": weight,
            "evidence": "deterministic pre-check 发现结构性错误，当前版本不适合进入 evaluator。",
            "suggestion": "先修复 artifacts 的硬性约束错误，再做语义评估。",
        }
        for name, weight in [
            ("narrative_flow", 0.30),
            ("contract_compliance", 0.25),
            ("data_accuracy", 0.20),
            ("pacing", 0.15),
            ("visual_variety", 0.10),
        ]
    ]
    violations = [
        {
            "field": "precheck",
            "expected": "script artifacts 通过 deterministic validators",
            "actual": error,
            "severity": "major",
        }
        for error in errors[:5]
    ]
    return {
        "phase": "eval",
        "milestone": "script",
        "dimensions": dimensions,
        "contract_violations": violations,
        "weighted_total": 20.0,
        "pass": False,
        "iteration_fixes": fixes,
    }
