"""Script vs JSON plan consistency validator."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _extract_script_scenes(text: str) -> list[dict[str, object]]:
    scenes: list[dict[str, object]] = []
    for block in re.findall(r"^## Scene.*?(?=^## Scene|\Z)", text, re.MULTILINE | re.DOTALL):
        idx_match = re.search(r"^## Scene\s+(\d+):\s*(.+)$", block, re.MULTILINE)
        type_match = re.search(r"^type:\s*(\w+)", block, re.MULTILINE)
        topic_match = re.search(r'^contract_topic:\s*"?(.+?)"?\s*$', block, re.MULTILINE)
        role_match = re.search(r"^narrative_role:\s*(\w+)", block, re.MULTILINE)
        duration_match = re.search(r"^duration_estimate:\s*([0-9]+(?:\.[0-9]+)?)", block, re.MULTILINE)
        scenes.append({
            "index": int(idx_match.group(1)) if idx_match else len(scenes) + 1,
            "type": type_match.group(1).strip() if type_match else "",
            "contract_topic": topic_match.group(1).strip() if topic_match else "",
            "narrative_role": role_match.group(1).strip() if role_match else "",
            "duration_estimate": float(duration_match.group(1)) if duration_match else 0.0,
        })
    return scenes


def check_script_plan_consistency(output_dir: str) -> list[str]:
    base = Path(output_dir)
    plan_path = base / "script-plan.json"
    script_path = base / "script.md"
    if not plan_path.exists() or not script_path.exists():
        return []

    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["script-plan.json ????"]

    plan_scenes = plan.get("scenes") or []
    script_scenes = _extract_script_scenes(script_path.read_text(encoding="utf-8"))
    if not plan_scenes or not script_scenes:
        return []

    errors: list[str] = []
    if len(plan_scenes) != len(script_scenes):
        errors.append(f"script ? plan ??????: script={len(script_scenes)}, plan={len(plan_scenes)}")

    compare_len = min(len(plan_scenes), len(script_scenes))
    for i in range(compare_len):
        plan_scene = plan_scenes[i]
        script_scene = script_scenes[i]
        if str(plan_scene.get("type", "")).strip() and script_scene["type"] != str(plan_scene.get("type", "")).strip():
            errors.append(f"Scene {script_scene['index']} type ?? plan: script={script_scene['type']}, plan={plan_scene.get('type')}")
        plan_topic = str(plan_scene.get("contract_topic", "")).strip()
        if plan_topic and script_scene["contract_topic"] != plan_topic:
            errors.append(f"Scene {script_scene['index']} contract_topic ?? plan: script={script_scene['contract_topic'] or '??'}, plan={plan_topic}")
        plan_role = str(plan_scene.get("narrative_role", "")).strip()
        if plan_role and script_scene["narrative_role"] != plan_role:
            errors.append(f"Scene {script_scene['index']} narrative_role ?? plan: script={script_scene['narrative_role'] or '??'}, plan={plan_role}")
        plan_duration = float(plan_scene.get("duration_estimate", 0) or 0)
        script_duration = float(script_scene["duration_estimate"] or 0)
        if plan_duration > 0 and abs(script_duration - plan_duration) > max(1.5, plan_duration * 0.35):
            errors.append(f"Scene {script_scene['index']} duration ?? plan: script={script_duration}, plan={plan_duration}")

    return errors
