"""Producer — research + script 两个 milestone 的主控 Agent。

流程:
  1. research → researcher agent → L1 ratify
  2. script  → GAN: 合约生成 → 合约审查(evaluator) → scriptwriter → 评估(evaluator) → 迭代
             → legacy: scriptwriter → L1 ratify
"""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path
from typing import Annotated

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
from .state import VideoProductionState


# ── 单一派发工具 ─────────────────────────────────────────────────

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
        invoke_input = {"messages": [{"role": "user", "content": description}]}
        for key in ("output_dir", "current_milestone", "ratify_feedback"):
            val = getattr(state, key, None)
            if val:
                invoke_input[key] = val

        result = subagents[agent_name].invoke(invoke_input)

        updates: dict = {"messages": [ToolMessage(
            content=result["messages"][-1].content,
            tool_call_id=tool_call_id,
        )]}
        # 回传产出路径
        for key in ("research_file", "script_file", "contract_file"):
            if val := result.get(key):
                updates[key] = val

        return Command(update=updates)

    return task


# ── Producer system prompt ───────────────────────────────────────

PRODUCER_PROMPT = """你是 video-maker 的 Producer（制片人），负责推进 research 和 script 两个里程碑。

## 工具
- task(agent_name, description): 派发给 researcher / scriptwriter / evaluator

## 里程碑 1: research
1. 派发 researcher，description 包含:
   - topic, source, duration, style
   - output_dir（researcher 写 research.md 到此目录）
   - 来源参数：notebook_url / local_file（如有）
2. 等待 researcher 完成
3. L1 ratify 自动执行（middleware），失败会自动重试并注入反馈

## 里程碑 2: script (GAN mode)

### Phase 1 — 合约生成（Producer 直接生成，不派发 agent）
生成 script-contract.json，包含:
```json
{
  "version": 1,
  "target_scene_count": {"min": <N>, "max": <N>},
  "target_duration_frames": {"min": <N>, "max": <N>},
  "narrative_structure": {"opening_type": "hook|story", "closing_type": "cta"},
  "audience": "<technical|general>",
  "key_topics": [{"topic": "...", "narrative_role": "hook|setup|development|climax|cta"}],
  "constraints": {"max_consecutive_same_type": 3, "min_visual_break_scenes": 1}
}
```
场景数量规则: 1-3min→{10,16}, 3-5min→{18,27}, 5-10min→{28,43}
帧数范围: duration中位秒数 × [0.6,1.2] × 30fps

验证: version=1, key_topics.length>=2, target_scene_count.min>=2, target_duration_frames.min>=300
将合约写入 {output_dir}/script-contract.json，然后派发 evaluator 做合约审查。

### Phase 2 — 合约审查
派发 evaluator，description:
  "合约审查。contract_file: {output_dir}/script-contract.json, phase: contract_review"
若 overall=rejected: 按 suggestion 修改合约，最多 2 轮，仍 rejected 则继续并记 warning。

### Phase 3 — 生成脚本
派发 scriptwriter，description 包含:
  - topic, duration, style, aspect_ratio, lut_style
  - research_file 路径
  - output_dir
  - contract 约束说明（注入到 description）
  - 上次 evaluator 反馈（迭代时注入）

### Phase 4 — 脚本评估（最多 2 轮迭代）
派发 evaluator，description:
  "脚本评估。artifact_file: {output_dir}/script.md, contract_file: {output_dir}/script-contract.json,
   research_file: {research_file}, phase: eval"

若 pass=true 则完成。
若 pass=false: 提取 iteration_fixes → 注入到下一轮 scriptwriter 的 description → 重新 Phase 3+4。
最多 2 轮; 超出则用最优版本继续。

## 完成
两个里程碑都完成后报告:
```
[OK] 视频脚本制作完成！
research: {output_dir}/research.md
script:   {output_dir}/script.md
```
"""


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
        tools=[task_tool],
        system_prompt=PRODUCER_PROMPT,
        middleware=[ratify_mw],
        state_schema=VideoProductionState,
        checkpointer=InMemorySaver(),
        name="video_producer",
    )
