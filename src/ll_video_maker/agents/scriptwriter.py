"""Scriptwriter subagent — 对应 agents/scriptwriter.md（3-Pass 生成）。"""
from __future__ import annotations

from pathlib import Path

from langchain.agents import create_agent
from langchain_core.runnables import Runnable
from langchain.tools import tool
from ..llm import get_llm
from ..config import cfg


@tool
def read_research(research_file: str) -> str:
    """读取 research.md 内容。"""
    try:
        return Path(research_file).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        return f"[读取失败] {e}"


@tool
def write_script(output_dir: str, content: str) -> str:
    """将脚本写入 {output_dir}/script.md，返回文件路径。"""
    path = Path(output_dir) / "script.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


@tool
def write_contract(output_dir: str, contract_json: str) -> str:
    """将脚本合约写入 {output_dir}/script-contract.json（GAN eval mode）。"""
    import json
    path = Path(output_dir) / "script-contract.json"
    try:
        json.loads(contract_json)
    except json.JSONDecodeError as e:
        return f"[JSON 验证失败] {e}"
    path.write_text(contract_json, encoding="utf-8")
    return str(path)


SYSTEM_PROMPT = """你是视频制作团队的编剧。根据调研报告撰写分镜脚本。

## 3-Pass 流程（在思考中完成前两步）

**Pass 1 — 素材盘点**：从 research.md 分类提取：
- 可量化数据 → data_card 候选
- 引言/金句 → quote_card 候选
- 叙事事实 → 按 narrative_role 分类（hook/setup/development/climax/cta）

**Pass 2 — 章节大纲**：Hook + Chapter[] + CTA
- 每章以 title_card 开头（Hook/CTA 除外）
- 每章 2-5 个内容场景
- 高密度场景不连续

**Pass 3 — 完整输出 script.md**

## script.md 格式

脚本顶部写 style_spine 代码块：
```style_spine
lut_style: <推导值>
aspect_ratio: <来自 goal>
visual_strategy: image_heavy|image_light|image_none
pacing: slow|moderate|fast
tone: <描述>
glossary: [专有名词, 最多12个]
```

每个场景格式：
```
## Scene N
type: narration|data_card|quote_card|title_card|transition
scene_intent: <一句话意图>
content_brief: <内容简介>
narration: <旁白文本，口语化>
```

## 场景类型规则
| type | audio | image | 必填字段 |
|------|-------|-------|---------|
| narration | 是 | 是 | scene_intent, content_brief, narration |
| data_card | 是 | 否 | scene_intent, content_brief, narration, data_semantic, items |
| quote_card | 是 | 否 | scene_intent, content_brief, narration |
| title_card | 否 | 否 | — |
| transition | 否 | 否 | — |

## 约束
- 无连续 3+ 个同类型场景
- data_card 必须有 data_semantic + items（非空）
- narration 禁止有 data_semantic 字段
- 禁止 layer_hint 和 beats 字段

## 流程
1. 用 read_research 读取调研报告
2. 生成脚本
3. 用 write_script 写入文件，返回路径
"""


def create_scriptwriter_agent() -> Runnable:
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.6)
    return create_agent(
        model=model,
        tools=[read_research, write_script, write_contract],
        system_prompt=SYSTEM_PROMPT,
        name="scriptwriter",
    )
