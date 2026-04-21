# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LangChain 1.0 reimplementation of the `video-maker` Claude Code skill, covering **research** and **script** milestones only. Uses a Producer-Crew multi-agent pattern: Producer orchestrates researcher → scriptwriter → evaluator subagents via a single dispatch tool.

## Commands

```bash
# Install
pip install -e ".[dev]"

# Run pipeline
python -m ll_video_maker.main --topic "AI Agent 趋势" --duration 1-3min --style professional --source websearch

# With legacy eval (skip GAN contract/evaluator loop)
python -m ll_video_maker.main --topic "..." --eval-mode legacy

# Resume interrupted run
python -m ll_video_maker.main --topic "..." --thread-id video-20260418-205722-video-xxx

# All options
python -m ll_video_maker.main --help
```

## Architecture

### Agent Topology

```
Producer (create_agent)
  ├─ task("researcher", ...)     → Researcher agent  → writes output_dir/research.md
  ├─ task("scriptwriter", ...)   → Scriptwriter agent → writes output_dir/script.md
  └─ task("evaluator", ...)      → Evaluator agent   → writes contract-review.json / script-eval.json
```

All dispatched via a single `task(agent_name, description)` tool in `producer.py:_build_task_tool()`. This is the **only** tool the Producer uses.

### GAN Eval Mode (default, `--eval-mode gan`)

Producer executes these phases for the script milestone:
1. **Contract generation**: Producer directly generates `script-contract.json`
2. **Contract review**: `task("evaluator", "phase: contract_review")` → max 2 revision rounds
3. **Script generation**: `task("scriptwriter", ...)` with contract injected into description
4. **Script evaluation**: `task("evaluator", "phase: eval")` → weighted score (narrative_flow 30%, contract_compliance 25%, data_accuracy 20%, pacing 15%, visual_variety 10%)
5. **Iteration**: If `pass=false`, inject `iteration_fixes` back to scriptwriter, max 2 rounds

### L1 Ratify Middleware (`middleware/ratify_l1.py`)

`make_ratify_middleware()` returns a `@wrap_tool_call` async middleware that intercepts every `task` call:
- Runs `check_research(output_dir)` or `check_script(output_dir, duration)` after handler returns
- On failure: appends feedback to description, retries (max `MAX_RETRY=2`)

Research rules: file >800 chars, >=3 `##` sections, has `https://` URL.
Script rules: scene count in range, no 3+ consecutive same type, required fields per scene type, no deprecated fields (`layer_hint`, `beats`).

### LLM Factory (`llm.py`)

`get_llm(model_name, temperature)` reads `cfg.LLM_PROVIDER`:
- `deepseek`: `ChatOpenAI` pointed at `https://api.deepseek.com/v1`
- `zhipu`/`anthropic`: `ChatAnthropic` (ZhipuAI uses Anthropic-compatible proxy)

## Key Configuration (`.env`)

```
LLM_PROVIDER=deepseek          # deepseek | zhipu | anthropic
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
PRODUCER_MODEL=deepseek-chat
SUBAGENT_MODEL=deepseek-chat
JUDGE_MODEL=deepseek-chat

# LangSmith tracing
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=ll-video-maker

# Path to the original video-maker skill (ratify reference)
VIDEO_MAKER_SKILL_PATH=E:/workspace/orchestrator_skills/.claude/skills/video-maker
```

## Critical Implementation Notes

### Async Requirement
The `wrap_tool_call` middleware only works in async context. Always use `asyncio.run(producer.ainvoke(...))`, never `producer.invoke(...)`.

### Script Format Constraints (enforced by L1 ratify)
- Scene counts: `1-3min→[10,16]`, `3-5min→[18,27]`, `5-10min→[28,43]`
- No 3+ consecutive same-type scenes
- `narration`/`data_card`/`quote_card` require: `scene_intent:`, `content_brief:`, `narration:`
- `data_card` requires `data_semantic:` + non-empty `items:`
- Forbidden fields: `layer_hint:`, `beats:`

### Adding a New Subagent
1. Create `agents/new_agent.py` with `create_new_agent()` → `create_agent(model, tools, system_prompt, name="new_agent")`
2. Add to `subagents` dict in `producer.py:create_producer()`

### Original Skill Reference
`E:/workspace/orchestrator_skills/.claude/skills/video-maker/` — agent prompts (`agents/*.md`), ratify rules (`ratify/*.md`), milestone instructions (`milestones/*.md`) are ground truth for prompt design.
