# ll_video_maker — AI Agent Instructions

LangChain 1.0 multi-agent pipeline for video script production (research + script milestones). Uses a **Producer-Crew pattern**: Producer orchestrates researcher → scriptwriter → evaluator subagents via a single `task(agent_name, description)` tool. See [CLAUDE.md](../CLAUDE.md) for the full reference.

## Commands

```bash
pip install -e ".[dev]"                        # Install
pytest tests/ -v                               # Run tests
python -m ll_video_maker.main --help           # All options
python -m ll_video_maker.main --topic "..." --duration 1-3min --style professional --source websearch
```

## Module Map

| Path | Role |
|------|------|
| `src/ll_video_maker/main.py` | CLI entry point |
| `src/ll_video_maker/producer.py` | Orchestrator; dispatches tasks; milestone state machine |
| `src/ll_video_maker/agents/{researcher,scriptwriter,evaluator}.py` | Subagents |
| `src/ll_video_maker/prompts/*.md` | System prompts loaded via `load_prompt(name)` / `render_prompt(name, **ctx)` |
| `src/ll_video_maker/middleware/ratify_l1.py` | L1 validation middleware; auto-retries on failure |
| `src/ll_video_maker/validators/` | Script-contract, script-plan, and consistency validators |
| `src/ll_video_maker/llm.py` | `get_llm(model, temperature)` — deepseek / zhipu / anthropic factory |
| `src/ll_video_maker/config.py` | `Config` dataclass from `.env` |
| `src/ll_video_maker/state.py` | `VideoProductionState` tracking milestones, retries, artifact paths |
| `src/ll_video_maker/task_context.py` | `infer_milestone()`, `infer_phase()` — parse task description |

## Critical: Always Use Async

```python
# CORRECT
asyncio.run(producer.ainvoke(state))
# WRONG — breaks L1 middleware and LangSmith tracing
producer.invoke(state)
```

The `@wrap_tool_call` middleware in `ratify_l1.py` only works in async context.

## Adding a New Subagent

1. Create `agents/new_agent.py` with `create_new_agent()` returning `create_agent(model, tools, system_prompt, name="new_agent")`
2. Add to `subagents` dict in `producer.py:create_producer()`
3. Add system prompt at `prompts/new_agent.md`

## Script Format Constraints (enforced by L1 Ratify)

Scene counts by duration: `1-3min → [10,16]`, `3-5min → [18,27]`, `5-10min → [28,43]`

Required fields for scene types:
- `narration`, `data_card`, `quote_card` → `scene_intent:`, `content_brief:`, `narration:`
- `data_card` → also `data_semantic:` + non-empty `items:`

Forbidden fields: `layer_hint:`, `beats:`  
No 3+ consecutive scenes of the same `type`.  
Field names must be literal (no Markdown emphasis like `**type:**`).

## Output Artifacts (per run under `output/<timestamp>-video-<slug>/`)

| File | Written by |
|------|-----------|
| `research.md` | Researcher |
| `script-contract.json` | Producer (directly) |
| `contract-review.json` | Evaluator (phase: contract_review) |
| `script-plan.json` | Scriptwriter |
| `script.md` | Scriptwriter |
| `script-eval.json` | Evaluator (phase: eval) |

## Key `.env` Variables

```
LLM_PROVIDER=deepseek          # deepseek | zhipu | zhipu_openai | anthropic
DEEPSEEK_API_KEY=sk-...
PRODUCER_MODEL=deepseek-v4-flash
SUBAGENT_MODEL=deepseek-v4-flash
JUDGE_MODEL=deepseek-v4-flash

LANGCHAIN_TRACING_V2=true      # optional LangSmith
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=ll-video-maker

VIDEO_MAKER_SKILL_PATH=...     # reference skill path for prompt design
```

Reasoning models (name contains "reasoner"/"reasoning"): temperature is **omitted** automatically by `get_llm()`.

## Common Pitfalls

- `contract_topic` in script scenes must **exactly match** a topic string from `script-contract.json`; suffix additions like `(hook)` will fail contract validation.
- Data claims in `data_card` items must be grounded in `research.md`; invented numbers cause evaluator failures.
- When recovering artifact paths, `_recover_artifact_paths()` in `producer.py` checks disk if subagent result dict is missing keys — no need to manually re-parse results.
- LangSmith feedback calls (`get_current_run_tree()`) require async context; they silently degrade if `LANGCHAIN_TRACING_V2` is unset.
