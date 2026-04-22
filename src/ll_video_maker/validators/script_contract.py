"""Script contract validator."""
from __future__ import annotations

import json
import re
from pathlib import Path


def _extract_scenes(script_text: str) -> list[dict[str, object]]:
    scenes: list[dict[str, object]] = []
    for block in re.findall(r"^## Scene.*?(?=^## Scene|\Z)", script_text, re.MULTILINE | re.DOTALL):
        title_match = re.search(r"^## Scene\s+(\d+):\s*(.+)$", block, re.MULTILINE)
        type_match = re.search(r"^type:\s*(\w+)", block, re.MULTILINE)
        contract_topic_match = re.search(r'^contract_topic:\s*"?(.+?)"?\s*$', block, re.MULTILINE)
        role_match = re.search(r"^narrative_role:\s*(\w+)", block, re.MULTILINE)
        duration_match = re.search(r"^duration_estimate:\s*([0-9]+(?:\.[0-9]+)?)", block, re.MULTILINE)
        scenes.append(
            {
                "index": int(title_match.group(1)) if title_match else len(scenes) + 1,
                "title": title_match.group(2).strip() if title_match else "",
                "type": type_match.group(1).strip() if type_match else "",
                "contract_topic": contract_topic_match.group(1).strip() if contract_topic_match else "",
                "narrative_role": role_match.group(1).strip() if role_match else "",
                "duration_estimate": float(duration_match.group(1)) if duration_match else 0.0,
                "block": block,
            }
        )
    return scenes


def _topic_keywords(topic: str) -> list[str]:
    normalized = re.sub(r"[“”\"'`]", "", topic.strip().lower())
    parts = [
        part.strip()
        for part in re.split(r"[、,，:：;；/()\s]+|和|与|及|以及|and", normalized)
        if part.strip()
    ]
    keywords: list[str] = []
    for part in parts:
        if len(part) >= 2:
            keywords.append(part)
        if re.search(r"[\u4e00-\u9fff]", part):
            if len(part) >= 4:
                keywords.append(part[-4:])
            if len(part) >= 6:
                keywords.append(part[-6:])
    deduped: list[str] = []
    for item in keywords:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _find_topic_scene(scenes: list[dict[str, object]], topic: str) -> dict[str, object] | None:
    normalized_topic = topic.strip().lower()
    for scene in scenes:
        tagged = str(scene.get("contract_topic", "")).strip().lower()
        if tagged and tagged == normalized_topic:
            return scene

    keywords = _topic_keywords(topic)
    if not keywords:
        return None
    if normalized_topic:
        for scene in scenes:
            haystack = str(scene["block"]).lower()
            if normalized_topic in haystack:
                return scene

    best_scene: dict[str, object] | None = None
    best_score = 0
    for scene in scenes:
        haystack = str(scene["block"]).lower()
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score > best_score:
            best_score = score
            best_scene = scene

    min_score = 2 if len(keywords) >= 2 else 1
    return best_scene if best_score >= min_score else None


def check_script_contract(output_dir: str) -> list[str]:
    """Validate script.md against script-contract.json when available."""
    base = Path(output_dir)
    script_path = base / "script.md"
    contract_path = base / "script-contract.json"
    if not script_path.exists() or not contract_path.exists():
        return []

    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["script-contract.json 无法解析"]

    text = script_path.read_text(encoding="utf-8")
    scenes = _extract_scenes(text)
    if not scenes:
        return ["script.md 未解析到任何 Scene"]

    errors: list[str] = []

    target_scene_count = contract.get("target_scene_count") or {}
    min_scenes = target_scene_count.get("min")
    max_scenes = target_scene_count.get("max")
    scene_count = len(scenes)
    if isinstance(min_scenes, int) and scene_count < min_scenes:
        errors.append(f"contract 场景数不足: {scene_count} < {min_scenes}")
    if isinstance(max_scenes, int) and scene_count > max_scenes:
        errors.append(f"contract 场景数超限: {scene_count} > {max_scenes}")

    target_frames = contract.get("target_duration_frames") or {}
    min_frames = target_frames.get("min")
    max_frames = target_frames.get("max")
    total_frames = round(sum(float(scene["duration_estimate"]) for scene in scenes) * 30)
    if isinstance(min_frames, int) and total_frames < min_frames:
        errors.append(f"contract 总时长不足: {total_frames} frames < {min_frames}")
    if isinstance(max_frames, int) and total_frames > max_frames:
        errors.append(f"contract 总时长超限: {total_frames} frames > {max_frames}")

    narrative_structure = contract.get("narrative_structure") or {}
    content_scenes = [scene for scene in scenes if scene["type"] not in {"title_card", "transition"}]
    if content_scenes:
        opening_type = narrative_structure.get("opening_type")
        if opening_type and content_scenes[0]["narrative_role"] != opening_type:
            errors.append(
                f"contract opening_type 不匹配: 期望 {opening_type}, 实际 {content_scenes[0]['narrative_role'] or '缺失'}"
            )
        closing_type = narrative_structure.get("closing_type")
        if closing_type and content_scenes[-1]["narrative_role"] != closing_type:
            errors.append(
                f"contract closing_type 不匹配: 期望 {closing_type}, 实际 {content_scenes[-1]['narrative_role'] or '缺失'}"
            )

    key_topics = contract.get("key_topics") or []
    for item in key_topics:
        topic = str(item.get("topic", "")).strip()
        expected_role = str(item.get("narrative_role", "")).strip()
        if not topic:
            continue
        matched_scene = _find_topic_scene(scenes, topic)
        if matched_scene is None:
            errors.append(f"contract key_topic 未覆盖: {topic}")
            continue
        actual_role = str(matched_scene.get("narrative_role", "")).strip()
        if expected_role and actual_role != expected_role:
            errors.append(
                f"contract topic role 不匹配: {topic} 应为 {expected_role}, 实际 Scene {matched_scene['index']} 为 {actual_role or '缺失'}"
            )

    constraints = contract.get("constraints") or {}
    max_same_type = constraints.get("max_consecutive_same_type")
    if isinstance(max_same_type, int) and max_same_type > 0:
        streak = 1
        for i in range(1, len(scenes)):
            if scenes[i]["type"] and scenes[i]["type"] == scenes[i - 1]["type"]:
                streak += 1
                if streak > max_same_type:
                    errors.append(
                        f"contract 连续同类型场景超限: Scene {scenes[i - streak + 1]['index']}-{scenes[i]['index']} 均为 {scenes[i]['type']}"
                    )
                    break
            else:
                streak = 1

    return errors
