"""L1 Ratify — 对应 ratify/research-rules.md 和 ratify/script-rules.md 的规则检查。

拦截 task 工具，执行规则验证，失败时注入 feedback 自动重试（最多 MAX_RETRY 次）。
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from langchain.messages import ToolMessage

logger = logging.getLogger(__name__)
MAX_RETRY = 2


# ── 静态规则检查 ──────────────────────────────────────────────

def check_research(output_dir: str) -> list[str]:
    """对应 ratify/research-rules.md。"""
    path = Path(output_dir) / "research.md"
    if not path.exists():
        return ["research.md 不存在"]

    text = path.read_text(encoding="utf-8")
    errors = []

    if len(text) < 800:
        errors.append(f"research.md 内容过短: {len(text)} chars（需 >800）")

    if len(re.findall(r"^## ", text, re.MULTILINE)) < 3:
        errors.append("章节不足（需 >=3 个 ## 章节）")

    if not re.search(r"https?://", text):
        errors.append("缺少参考来源 URL")

    return errors


def check_script(output_dir: str, duration: str = "1-3min") -> list[str]:
    """对应 ratify/script-rules.md。"""
    path = Path(output_dir) / "script.md"
    if not path.exists():
        return ["script.md 不存在"]

    text = path.read_text(encoding="utf-8")
    errors = []

    # 规则 2: 场景数量
    scene_count = len(re.findall(r"^## Scene", text, re.MULTILINE))
    lo, hi = {"1-3min": (10, 16), "3-5min": (18, 27), "5-10min": (28, 43)}.get(duration, (10, 16))
    if not (lo <= scene_count <= hi):
        errors.append(f"场景数 {scene_count} 不在 [{lo},{hi}]（duration={duration}）")

    # 规则 3: 无连续 3+ 个同类型
    types = re.findall(r"^type:\s*(\w+)", text, re.MULTILINE)
    for i in range(len(types) - 2):
        if types[i] == types[i + 1] == types[i + 2]:
            errors.append(f"连续 3 个同类型场景: {types[i]}（第 {i+1}-{i+3} 场）")
            break

    # 规则 4-5: 必填字段检查
    audio_types = ("narration", "data_card", "quote_card")
    for scene_block in re.split(r"(?=^## Scene)", text, flags=re.MULTILINE):
        m = re.search(r"^type:\s*(\w+)", scene_block, re.MULTILINE)
        if not m or m.group(1) not in audio_types:
            continue
        sid_match = re.search(r"^## Scene (\S+)", scene_block, re.MULTILINE)
        sid = sid_match.group(1) if sid_match else "?"
        for f in ("scene_intent:", "content_brief:", "narration:"):
            if f not in scene_block:
                errors.append(f"Scene {sid} 缺少 {f}")

    # 规则 6: 禁止废弃字段
    if re.search(r"(layer_hint:|beats:)", text):
        errors.append("包含废弃字段 layer_hint 或 beats")

    # 规则 7-8: data_card 约束
    for block in re.findall(r"^## Scene.*?(?=^## Scene|\Z)", text, re.MULTILINE | re.DOTALL):
        if "type: data_card" not in block:
            continue
        sid_match = re.search(r"^## Scene (\S+)", block, re.MULTILINE)
        sid = sid_match.group(1) if sid_match else "?"
        if "data_semantic:" not in block:
            errors.append(f"Scene {sid} (data_card) 缺少 data_semantic")
        if re.search(r"items:\s*\[\]", block) or "items:" not in block:
            errors.append(f"Scene {sid} (data_card) items 为空")

    return errors


CHECKERS = {"research": check_research, "script": check_script}


# ── wrap_tool_call middleware ──────────────────────────────────

def make_ratify_middleware() -> object:
    """返回 l1_auto_ratify middleware（避免循环导入 wrap_tool_call）。"""
    try:
        from langchain.agents.middleware import wrap_tool_call

        @wrap_tool_call
        async def l1_auto_ratify(request, handler):
            if request.tool_call["name"] != "task":
                return await handler(request)

            state = getattr(request, "state", {})
            milestone = getattr(state, "current_milestone", "research")
            output_dir = getattr(state, "output_dir", "")
            ratify_level = getattr(state, "ratify_level", "normal")
            task_desc_orig = request.tool_call["args"].get("description", "")

            if ratify_level == "fast":
                return await handler(request)

            last_feedback = ""
            for attempt in range(MAX_RETRY + 1):
                if last_feedback:
                    request.tool_call["args"]["description"] = (
                        task_desc_orig
                        + f"\n\n## 上次审核反馈（请改进）\n{last_feedback}"
                    )

                result = await handler(request)

                checker = CHECKERS.get(milestone)
                errors: list[str] = []
                if checker and output_dir:
                    try:
                        errors = checker(output_dir)
                    except Exception as e:
                        logger.warning("ratify checker error: %s", e)

                if not errors:
                    logger.info("[L1 PASS] milestone=%s attempt=%d", milestone, attempt)
                    return result

                last_feedback = "\n".join(f"- {e}" for e in errors)
                logger.info("[L1 FAIL] milestone=%s attempt=%d errors=%s", milestone, attempt, errors)

            return ToolMessage(
                content=(
                    f"[L1 审核未通过 — 已重试 {MAX_RETRY} 次]\n"
                    f"里程碑: {milestone}\n最后反馈:\n{last_feedback}"
                ),
                tool_call_id=request.tool_call["id"],
            )

        return l1_auto_ratify

    except ImportError:
        # LangChain 1.0 尚未安装时，返回 passthrough
        async def passthrough(request, handler):
            return await handler(request)
        return passthrough
