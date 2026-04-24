"""Producer — research + script 两个 milestone 的主控 Agent。

流程:
  1. research → researcher agent → L1 ratify
  2. script  → GAN: 合约生成 → 合约审查(evaluator) → scriptwriter → 评估(evaluator) → 迭代
             → legacy: scriptwriter → L1 ratify
"""
from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path
from typing import Annotated

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("producer")

from langchain.agents import create_agent
from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langchain.messages import ToolMessage
from langchain_core.runnables import Runnable
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .agents import create_evaluator_agent, create_researcher_agent, create_scriptwriter_agent
from .config import cfg
from .llm import get_llm
from .middleware import make_ratify_middleware
from .prompts import render_prompt
from .state import VideoProductionState
from .task_context import infer_milestone, infer_phase
from .tracing import attach_eval_feedback


# ── Producer 专用工具 ────────────────────────────────────────────

@tool
def write_output_file(file_path: str, content: str) -> str:
    """写入文件到输出目录（Producer 用）。返回写入路径。"""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


# ── 单一派发工具 ─────────────────────────────────────────────────

def _recover_artifact_paths(
    agent_name: str,
    state: object,
    result: dict,
) -> dict[str, str]:
    """当 subagent 未显式回传路径时，从输出目录兜底恢复已落盘产物。"""
    recovered: dict[str, str] = {}
    output_dir = getattr(state, "output_dir", "") if state else ""
    if not output_dir:
        return recovered

    output_path = Path(output_dir)
    fallback_map = {
        "researcher": {"research_file": output_path / "research.md"},
        "scriptwriter": {
            "script_plan_file": output_path / "script-plan.json",
            "script_file": output_path / "script.md",
            "contract_file": output_path / "script-contract.json",
        },
        "evaluator": {
            "contract_review_file": output_path / "contract-review.json",
            "script_eval_file": output_path / "script-eval.json",
        },
    }
    for key, path in fallback_map.get(agent_name, {}).items():
        if result.get(key):
            continue
        if path.exists():
            recovered[key] = str(path)
    return recovered

def _summarize_tool_result(agent_name: str, description: str, result: dict, state: object) -> str:
    raw = result["messages"][-1].content
    output_dir = getattr(state, "output_dir", "") or ""

    if agent_name == "evaluator":
        payload = _parse_json_message(raw)
        if not payload:
            return raw[:300]
        milestone = infer_milestone(description, state, fallback="script")
        phase = infer_phase(description)
        if phase == "eval":
            passed = payload.get("pass", False)
            score = payload.get("weighted_total", "?")
            fixes_count = len(payload.get("iteration_fixes", []))
            violations = [v for v in payload.get("contract_violations", []) if v.get("severity") == "major"]
            status = "PASS" if passed else "FAIL"
            line = f"{milestone}.eval: {status} | score={score} | fixes={fixes_count}"
            if violations:
                line += f" | major_violations={len(violations)}"
            return line
        if phase == "contract_review":
            passed = payload.get("pass")
            status = "PASS" if passed is True else "FAIL" if passed is False else "UNKNOWN"
            return f"{milestone}.contract_review: {status}"
        return raw[:300]

    if agent_name == "researcher":
        rf = result.get("research_file") or (str(Path(output_dir) / "research.md") if output_dir else "unknown")
        return f"researcher: done | research_file={rf}"

    if agent_name == "scriptwriter":
        parts = []
        for k, fname in [("script_plan_file", "script-plan.json"), ("script_file", "script.md"), ("contract_file", "script-contract.json")]:
            v = result.get(k) or (str(Path(output_dir) / fname) if output_dir else None)
            if v:
                parts.append(f"{k}={v}")
        return "scriptwriter: done | " + " | ".join(parts)

    return raw[:300]


def _format_iteration_fixes(iteration_fixes: list[dict]) -> str:
    if not iteration_fixes:
        return ""
    lines = ["## 迭代修复清单"]
    for idx, item in enumerate(iteration_fixes, start=1):
        priority = item.get("priority", idx)
        target = item.get("target", "unknown")
        action = item.get("action", "")
        impact = item.get("expected_impact", "")
        lines.append(f"{idx}. priority={priority}; target={target}")
        if action:
            lines.append(f"   action: {action}")
        if impact:
            lines.append(f"   expected_impact: {impact}")
    lines.append("## 修复清单结束")
    return "\n".join(lines)


def _parse_json_message(content: str) -> dict | None:
    try:
        return json.loads(content)
    except Exception:
        return None


def _child_config(base: dict, *, agent_name: str, description: str) -> dict:
    """从根 config 派生子 agent config：去掉 run_id / configurable，注入追踪元数据。"""
    from .task_context import infer_milestone, infer_phase

    run_id = base.get("run_id")
    configurable = base.get("configurable") or {}
    thread_id = configurable.get("thread_id", "")
    milestone = infer_milestone(description, None, fallback="")
    phase = infer_phase(description)

    base_meta = dict(base.get("metadata") or {})
    child_meta = {
        **base_meta,
        "agent_name": agent_name,
        "milestone": milestone,
        "phase": phase,
        "thread_id": thread_id,
    }
    if run_id is not None:
        child_meta["pipeline_run_id"] = str(run_id)

    base_tags = list(base.get("tags") or [])
    extra_tags = [f"agent:{agent_name}"]
    if milestone:
        extra_tags.append(f"milestone:{milestone}")
    if phase:
        extra_tags.append(f"phase:{phase}")
    child_tags = base_tags + extra_tags

    child: dict = {}
    for key in base:
        if key in ("run_id", "configurable"):
            continue
        child[key] = base[key]
    child["metadata"] = child_meta
    child["tags"] = child_tags
    return child


def _root_langsmith_extra(config: dict) -> dict:
    """返回根 agent LangSmith extra，注入 pipeline_run_id / thread_id。"""
    run_id = config.get("run_id")
    configurable = config.get("configurable") or {}
    thread_id = configurable.get("thread_id", "")
    base_meta = dict(config.get("metadata") or {})
    meta = {
        **base_meta,
        "thread_id": thread_id,
    }
    if run_id is not None:
        meta["pipeline_run_id"] = str(run_id)
    return {"run_id": run_id, "metadata": meta}


def _extract_eval_state_updates(
    agent_name: str,
    description: str,
    content: str,
    state: object,
    context: dict | None = None,
) -> dict:
    updates: dict = {}
    payload = _parse_json_message(content)

    # Fall back to reading the result file when content is not parseable JSON
    if agent_name == "evaluator" and not payload and context:
        phase_hint = infer_phase(description)
        file_key = "contract_review_file" if phase_hint == "contract_review" else "script_eval_file"
        result_file = context.get(file_key)
        if result_file:
            try:
                payload = json.loads(Path(result_file).read_text(encoding="utf-8"))
            except Exception:
                pass

    if agent_name != "evaluator" or not payload:
        return updates

    milestone = infer_milestone(description, state, fallback="script")
    phase = infer_phase(description)
    if milestone != "script":
        return updates

    if phase == "contract_review":
        updates["last_contract_review"] = payload
        return updates

    if phase == "eval":
        updates["last_eval_result"] = payload
        updates["iteration_fixes"] = payload.get("iteration_fixes", []) or []
        updates["contract_violations"] = payload.get("contract_violations", []) or []
        weighted_total = payload.get("weighted_total")
        if isinstance(weighted_total, (int, float)):
            updates["eval_best_score"] = max(
                float(weighted_total),
                float(getattr(state, "eval_best_score", 0.0) or 0.0),
            )
        updates["eval_round"] = int(getattr(state, "eval_round", 0) or 0) + 1
        updates["must_fix_summary"] = _format_iteration_fixes(updates["iteration_fixes"])
        attach_eval_feedback(payload)

    return updates


def _set_milestone_status(updates: dict[str, str], milestone: str, status: str) -> None:
    key = f"milestone_{milestone}"
    updates[key] = status


def _derive_milestone_state_updates(
    *,
    agent_name: str,
    description: str,
    result: dict,
    state: object,
) -> dict[str, str]:
    """根据 subagent 产物推进里程碑状态机。"""
    current = getattr(state, "current_milestone", "research")
    updates: dict[str, str] = {}

    if agent_name == "researcher":
        has_research = bool(result.get("research_file"))
        _set_milestone_status(updates, "research", "completed" if has_research else "failed")
        _set_milestone_status(updates, "script", "in_progress" if has_research else str(getattr(state, "milestone_script", "pending")))
        updates["current_milestone"] = "script" if has_research else "research"
        return updates

    if agent_name == "scriptwriter":
        has_script = bool(result.get("script_file"))
        has_plan = bool(result.get("script_plan_file"))
        has_contract = bool(result.get("contract_file"))
        _set_milestone_status(updates, "research", str(getattr(state, "milestone_research", "pending")))
        _set_milestone_status(updates, "script", "in_progress" if (has_script and has_plan and has_contract) else "failed")
        updates["current_milestone"] = "script"
        return updates

    if agent_name == "evaluator":
        milestone = infer_milestone(description, state, fallback=str(current or "research"))
        phase = infer_phase(description)
        payload = _parse_json_message(result["messages"][-1].content)
        if getattr(state, "milestone_research", None) is not None:
            _set_milestone_status(updates, "research", str(getattr(state, "milestone_research", "pending")))
        if getattr(state, "milestone_script", None) is not None and milestone != "script":
            _set_milestone_status(updates, "script", str(getattr(state, "milestone_script", "pending")))
        if phase == "contract_review":
            passed = bool(payload and payload.get("pass"))
            _set_milestone_status(updates, milestone, "in_progress" if passed else "failed")
            updates["current_milestone"] = milestone
            return updates
        if phase == "eval":
            passed = bool(payload and payload.get("pass"))
            _set_milestone_status(updates, milestone, "completed" if passed else "in_progress")
            updates["current_milestone"] = "done" if (passed and milestone == "script") else milestone
            return updates

    updates["current_milestone"] = current if isinstance(current, str) and current else "research"
    return updates


def _augment_scriptwriter_description(description: str, state: object) -> str:
    fixes = getattr(state, "iteration_fixes", None) or []
    if not fixes:
        return description
    summary = getattr(state, "must_fix_summary", "") or _format_iteration_fixes(fixes)
    if summary and summary not in description:
        return description.rstrip() + "\n\n" + summary
    return description


def _maybe_short_circuit_evaluator(
    agent_name: str,
    description: str,
    state: object,
) -> dict | None:
    """在调用 LLM evaluator 之前运行确定性预检。
    若预检发现严重问题，直接写入结果文件并返回产物 dict，跳过 LLM 调用。
    返回 None 表示预检通过，继续正常流程。
    """
    from .validators import run_evaluator_precheck

    if agent_name != "evaluator":
        return None

    milestone = infer_milestone(description, state, fallback="script")
    phase = infer_phase(description)
    output_dir = getattr(state, "output_dir", "") or ""
    if not output_dir:
        return None

    result = run_evaluator_precheck(output_dir, milestone=milestone, phase=phase)
    if result is None:
        return None

    # Precheck found issues — persist result and short-circuit
    if phase == "eval":
        result_path = Path(output_dir) / "script-eval.json"
        result_key = "script_eval_file"
    elif phase == "contract_review":
        result_path = Path(output_dir) / "contract-review.json"
        result_key = "contract_review_file"
    else:
        return None

    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("~~~ precheck short-circuit: %s → %s", agent_name, str(result_path))
    return {result_key: str(result_path)}


def _build_task_tool(subagents: dict[str, Runnable]) -> type:
    @tool
    def task(
        agent_name: str,
        description: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
        runtime: ToolRuntime[None, VideoProductionState],
    ) -> Command:
        """派发任务给 subagent。agent_name: researcher | scriptwriter | evaluator"""
        if agent_name not in subagents:
            return Command(update={"messages": [ToolMessage(
                content=f"[ERROR] 未知 agent: {agent_name}",
                tool_call_id=tool_call_id,
            )]})

        try:
            state = runtime.state
        except AttributeError:
            state = {}
        parent_config = getattr(runtime, "config", None) or {}
        if agent_name == "scriptwriter":
            description = _augment_scriptwriter_description(description, state)
        invoke_input = {"messages": [{"role": "user", "content": description}]}
        for key in ("output_dir", "current_milestone", "ratify_feedback", "iteration_fixes", "must_fix_summary", "contract_file", "research_file", "script_plan_file"):
            val = getattr(state, key, None)
            if val:
                invoke_input[key] = val

        # Evaluator precheck: skip LLM call if deterministic checks already fail
        short_circuit = _maybe_short_circuit_evaluator(agent_name, description, state)
        if short_circuit is not None:
            sc_summary = _summarize_tool_result(agent_name, description, {**short_circuit, "messages": [{"content": ""}]}, state)
            sc_updates: dict = {"messages": [ToolMessage(content=sc_summary, tool_call_id=tool_call_id)]}
            sc_updates.update(_extract_eval_state_updates(agent_name, description, "", state, context=short_circuit))
            for key in ("contract_review_file", "script_eval_file"):
                if val := short_circuit.get(key):
                    sc_updates[key] = val
            return Command(update=sc_updates)

        child_config = _child_config(parent_config, agent_name=agent_name, description=description)
        child_config["recursion_limit"] = 50
        log.info(">>> task(%s) 开始, description: %s", agent_name, description[:120])
        result = subagents[agent_name].invoke(invoke_input, child_config)
        log.info("<<< task(%s) 完成", agent_name)

        recovered = _recover_artifact_paths(agent_name, state, result)
        if recovered:
            log.info("~~~ task(%s) recovered artifacts: %s", agent_name, recovered)
            result = {**result, **recovered}

        summary = _summarize_tool_result(agent_name, description, result, state)
        updates: dict = {"messages": [ToolMessage(
            content=summary,
            tool_call_id=tool_call_id,
        )]}
        updates.update(_derive_milestone_state_updates(
            agent_name=agent_name,
            description=description,
            result=result,
            state=state,
        ))
        updates.update(_extract_eval_state_updates(agent_name, description, result["messages"][-1].content, state, context=result))
        # 恢复产物路径
        for key in ("research_file", "script_plan_file", "script_file", "contract_file", "contract_review_file", "script_eval_file"):
            if val := result.get(key):
                updates[key] = val

        return Command(update=updates)

    return task


# ── Producer system prompt ───────────────────────────────────────

PRODUCER_PROMPT = render_prompt("producer")


# ── 初始化目录 ──────────────────────────────────────────────────

def init_output_dir(topic: str, project_root: str) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", topic.lower())[:30].strip("-")
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_dir = str(Path(project_root) / "output" / f"{ts}-video-{slug}")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return output_dir


# ── 工厂函数 ─────────────────────────────────────────────────────

def create_producer(project_root: str = ".") -> Runnable:
    """创建 Producer agent，返回可调用的 LangGraph Pregel 对象。"""
    subagents = {
        "researcher": create_researcher_agent(),
        "scriptwriter": create_scriptwriter_agent(),
        "evaluator": create_evaluator_agent(),
    }

    task_tool = _build_task_tool(subagents)
    ratify_mw = make_ratify_middleware()

    model = get_llm(cfg.PRODUCER_MODEL, temperature=0.3)

    return create_agent(
        model=model,
        tools=[task_tool, write_output_file],
        system_prompt=PRODUCER_PROMPT,
        middleware=[ratify_mw],
        state_schema=VideoProductionState,
        checkpointer=InMemorySaver(),
        name="video_producer",
    )
