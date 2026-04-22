"""Scriptwriter subagent."""
from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain.tools import tool

from ..config import cfg
from ..llm import get_llm
from ..prompts import load_prompt


@tool
def read_research(research_file: str) -> str:
    """Read research.md text."""
    try:
        return Path(research_file).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        return f"[read_research error] {exc}"


@tool
def read_file(file_path: str) -> str:
    """Read a UTF-8 text file."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        return f"[read_file error] {exc}"


@tool
def summarize_script_plan(file_path: str) -> str:
    """Summarize script-plan.json into a shorter text form."""
    import json

    try:
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        return f"[plan summary error] {exc}"

    scenes = data.get("scenes") or []
    lines = [
        f"target_audience: {data.get('target_audience', '')}",
        f"opening_type: {data.get('opening_type', '')}",
        f"closing_type: {data.get('closing_type', '')}",
        f"total_duration_estimate: {data.get('total_duration_estimate', '')}",
        "scene_plan:",
    ]
    for scene in scenes:
        lines.append(
            "- "
            + f"#{scene.get('scene_number')} | "
            + f"type={scene.get('type', '')} | "
            + f"topic={scene.get('contract_topic', '')} | "
            + f"role={scene.get('narrative_role', '')} | "
            + f"duration={scene.get('duration_estimate', '')} | "
            + f"purpose={scene.get('purpose', '')}"
        )
    return "\n".join(lines)


@tool
def write_script_plan(output_dir: str, content: str) -> str:
    """Write {output_dir}/script-plan.json."""
    path = Path(output_dir) / "script-plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


@tool
def write_script(output_dir: str, content: str) -> str:
    """Write {output_dir}/script.md."""
    path = Path(output_dir) / "script.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


@tool
def write_contract(output_dir: str, contract_json: str) -> str:
    """Write {output_dir}/script-contract.json after JSON validation."""
    import json

    path = Path(output_dir) / "script-contract.json"
    try:
        json.loads(contract_json)
    except json.JSONDecodeError as exc:
        return f"[JSON validation error] {exc}"
    path.write_text(contract_json, encoding="utf-8")
    return str(path)


SYSTEM_PROMPT = load_prompt("scriptwriter")


def create_scriptwriter_agent() -> Runnable:
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.6)
    return create_agent(
        model=model,
        tools=[read_research, read_file, summarize_script_plan, write_script_plan, write_script, write_contract],
        system_prompt=SYSTEM_PROMPT,
        name="scriptwriter",
    )
