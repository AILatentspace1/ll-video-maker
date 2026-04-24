---
description: "Scaffold a new subagent for ll_video_maker. Generates agents/<name>.py, prompts/<name>.md, and the producer.py registration patch. Use when adding a new specialist agent to the Producer-Crew pipeline."
name: "New Subagent Scaffold"
argument-hint: "agent name (e.g. fact-checker, translator, narrator)"
agent: "agent"
---

# New Subagent Scaffold

Scaffold a complete new subagent for the `ll_video_maker` Producer-Crew pipeline.

**Agent name**: `$ARGS`

## What to generate

Produce all three components below. Read the existing agent files first to match conventions.

---

### 1. `src/ll_video_maker/agents/<name>.py`

Follow the pattern of [evaluator.py](../../src/ll_video_maker/agents/evaluator.py) and [researcher.py](../../src/ll_video_maker/agents/researcher.py):

```python
"""<Name> subagent — <one-line purpose>."""
from __future__ import annotations

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.runnables import Runnable

from ..llm import get_llm
from ..config import cfg
from ..prompts import render_prompt
from .shared import read_file   # include only if the agent reads files


@tool
def write_<name>_result(output_dir: str, result_json: str) -> str:
    """写入 <name> 结果到 output_dir/<name>-result.json。"""
    ...


SYSTEM_PROMPT = render_prompt("<name>")


def create_<name>_agent() -> Runnable:
    model = get_llm(cfg.SUBAGENT_MODEL, temperature=0.3)   # use cfg.EVALUATOR_MODEL for judge roles
    return create_agent(
        model=model,
        tools=[read_file, write_<name>_result],
        system_prompt=SYSTEM_PROMPT,
        name="<name>",
    )
```

Rules:
- Tools must be `@tool`-decorated functions; include `read_file` from `shared.py` if the agent needs to read artifacts
- Use `cfg.EVALUATOR_MODEL` (temperature=0.2) for judge/eval roles; `cfg.SUBAGENT_MODEL` (temperature=0.3) for generation roles
- Reasoning models (name contains "reasoner"/"reasoning") have temperature omitted automatically by `get_llm()`

---

### 2. `src/ll_video_maker/prompts/<name>.md`

Write a focused system prompt. Use [researcher.md](../../src/ll_video_maker/prompts/researcher.md) and [evaluator.md](../../src/ll_video_maker/prompts/evaluator.md) as reference for tone and structure:

```markdown
# Role: <Display Name>

你是视频生产流水线中的<专业角色描述>。

## Goal

<单句任务目标>

## 输出规范

- 必须调用 `write_<name>_result` 工具写入结果
- 输出格式: <JSON schema 或 Markdown 格式描述>

## 注意事项

- <constraint 1>
- <constraint 2>
```

---

### 3. Registration patches (show as diff-style code blocks)

**`src/ll_video_maker/agents/__init__.py`** — add export:
```python
from .<name> import create_<name>_agent
# add to __all__
```

**`src/ll_video_maker/producer.py`** — two locations:

```python
# Line ~27: add to import
from .agents import create_evaluator_agent, create_researcher_agent, create_scriptwriter_agent, create_<name>_agent

# Line ~447: add to subagents dict inside create_producer()
subagents = {
    "researcher": create_researcher_agent(),
    "scriptwriter": create_scriptwriter_agent(),
    "evaluator": create_evaluator_agent(),
    "<name>": create_<name>_agent(),   # ← add this line
}
```

**`middleware/ratify_l1.py`** — add to `CHECKERS` dict if the agent produces an artifact that needs L1 validation:
```python
CHECKERS = {
    ...
    "<name>": check_<name>,   # implement check_<name>(output_dir) → list[str]
}
```
If no L1 validation is needed, skip this.

---

## After generating

1. Confirm the three files above are complete and consistent (function names, tool names, prompt file name all match `<name>`)
2. Remind the user:
   - Update `_recover_artifact_paths()` in `producer.py` with the new agent's output file paths
   - If the agent writes a new artifact, add it as a field in `VideoProductionState` ([state.py](../../src/ll_video_maker/state.py))
   - The Producer's system prompt ([prompts/producer.md](../../src/ll_video_maker/prompts/producer.md)) may need a new task dispatch instruction for the agent
