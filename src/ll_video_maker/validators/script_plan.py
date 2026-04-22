"""Script plan validator."""
from __future__ import annotations

import json
from pathlib import Path


def _load_plan(plan_path: Path) -> dict | None:
    try:
        return json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def check_script_plan(output_dir: str) -> list[str]:
    base = Path(output_dir)
    plan_path = base / "script-plan.json"
    contract_path = base / "script-contract.json"
    if not plan_path.exists() or not contract_path.exists():
        return []

    plan = _load_plan(plan_path)
    if plan is None:
        return ["script-plan.json ????"]

    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["script-contract.json ????"]

    scenes = plan.get("scenes") or []
    if not isinstance(scenes, list) or not scenes:
        return ["script-plan.json ?? scenes"]

    errors: list[str] = []
    for i, scene in enumerate(scenes, start=1):
        if int(scene.get("scene_number", i)) != i:
            errors.append(f"plan scene_number ???: ?? {i}, ?? {scene.get('scene_number')}")

    target_scene_count = contract.get("target_scene_count") or {}
    scene_count = len(scenes)
    min_scenes = target_scene_count.get("min")
    max_scenes = target_scene_count.get("max")
    if isinstance(min_scenes, int) and scene_count < min_scenes:
        errors.append(f"plan ?????: {scene_count} < {min_scenes}")
    if isinstance(max_scenes, int) and scene_count > max_scenes:
        errors.append(f"plan ?????: {scene_count} > {max_scenes}")

    total_duration = sum(float(scene.get("duration_estimate", 0) or 0) for scene in scenes)
    total_frames = round(total_duration * 30)
    target_frames = contract.get("target_duration_frames") or {}
    min_frames = target_frames.get("min")
    max_frames = target_frames.get("max")
    if isinstance(min_frames, int) and total_frames < min_frames:
        errors.append(f"plan ?????: {total_frames} frames < {min_frames}")
    if isinstance(max_frames, int) and total_frames > max_frames:
        errors.append(f"plan ?????: {total_frames} frames > {max_frames}")

    if abs(float(plan.get("total_duration_estimate", 0) or 0) - total_duration) > max(2.0, total_duration * 0.2):
        errors.append("plan total_duration_estimate ? scenes ????????")

    topic_map = {
        str(scene.get("contract_topic", "")).strip(): scene
        for scene in scenes
        if str(scene.get("contract_topic", "")).strip()
    }
    key_topics = contract.get("key_topics") or []
    for item in key_topics:
        topic = str(item.get("topic", "")).strip()
        expected_role = str(item.get("narrative_role", "")).strip()
        if not topic:
            continue
        scene = topic_map.get(topic)
        if not scene:
            errors.append(f"plan key_topic ???: {topic}")
            continue
        actual_role = str(scene.get("narrative_role", "")).strip()
        if expected_role and actual_role != expected_role:
            errors.append(f"plan topic role ???: {topic} ?? {expected_role}, ??? {actual_role or '??'}")

    opening_type = str(contract.get("narrative_structure", {}).get("opening_type", "")).strip()
    closing_type = str(contract.get("narrative_structure", {}).get("closing_type", "")).strip()
    content_scenes = [s for s in scenes if str(s.get("type", "")) not in {"title_card", "transition"}]
    if content_scenes:
        if opening_type and str(content_scenes[0].get("narrative_role", "")).strip() != opening_type:
            errors.append(f"plan opening_type ???: ?? {opening_type}, ?? {content_scenes[0].get('narrative_role') or '??'}")
        if closing_type and str(content_scenes[-1].get("narrative_role", "")).strip() != closing_type:
            errors.append(f"plan closing_type ???: ?? {closing_type}, ?? {content_scenes[-1].get('narrative_role') or '??'}")

    return errors
