# LangChain 1.0 Skills & Middleware 详解

> 基于 LangChain 官方文档（docs.langchain.com）+ Reference API + Web 搜索整理

---

## 1. Skills 支持

### 1.1 LangChain 1.0（`langchain` 包）— 无原生 Skill API

LangChain 1.0 的 `create_agent` **没有原生的 `skills=` 参数**。Skill 作为一种架构模式（Progressive Disclosure），需要自行实现。

**Skills Pattern 核心思想**：Agent 只在 prompt 中看到 skill 名称和一行描述，按需调用工具读取完整 `SKILL.md` 内容。

```
Agent Prompt:
  "You have these skills: /research, /script, /review.
   To use a skill, call the read_skill tool with the skill name."
         │
         ▼
Agent decides to use /research
         │
         ▼
read_skill("research") → reads SKILL.md → injects full instructions into context
```

### 1.2 Deep Agents（`deepagents` 包）— 原生 Skill API

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="google_genai:gemini-3.1-pro-preview",
    skills=["research", "script", "review"],  # 原生支持
)
```

| 特性 | LangChain 1.0 | Deep Agents |
|---|---|---|
| 原生 `skills=` 参数 | 不支持 | 支持 |
| 实现方式 | 自定义 tool + middleware | 内置 |
| Skill 发现 | 手动注册 | 自动发现 |
| 适用场景 | 标准多 agent 编排 | 深度研究、复杂任务 |

### 1.3 Skills + Middleware 实战（LangChain 1.0 推荐方案）

通过 `@dynamic_prompt` 或 `@wrap_model_call` 将 skill 列表注入 system prompt，配合 tool 实现 progressive disclosure：

```python
from langchain.agents import create_agent
from langchain.agents.middleware import dynamic_prompt
from langchain.tools import tool

SKILLS_DIR = ".claude/skills"

@tool
def read_skill(skill_name: str) -> str:
    """Read the full content of a skill by name."""
    path = f"{SKILLS_DIR}/{skill_name}/SKILL.md"
    with open(path) as f:
        return f.read()

@dynamic_prompt
def skill_list_prompt(request):
    """Inject available skill names into system prompt."""
    import os
    skills = [
        d for d in os.listdir(SKILLS_DIR)
        if os.path.isfile(f"{SKILLS_DIR}/{d}/SKILL.md")
    ]
    skill_lines = "\n".join(f"- /{s}" for s in skills)
    return f"Available skills:\n{skill_lines}\nUse read_skill() to load a skill's full instructions."

agent = create_agent(
    model="deepseek-chat",
    tools=[read_skill, ...],
    system_prompt="You are a producer agent...",
    middleware=[skill_list_prompt],
)
```

---

## 2. Middleware 体系

### 2.1 7 个装饰器

LangChain 1.0 Python 版提供 7 个 middleware 装饰器（`from langchain.agents.middleware import ...`）：

| 类型 | 装饰器 | 用途 |
|---|---|---|
| Node-style | `@before_agent` | agent 启动前（每次 invoke 一次） |
| Node-style | `@before_model` | 每次 LLM 调用前 |
| Node-style | `@after_model` | 每次 LLM 响应后 |
| Node-style | `@after_agent` | agent 完成后（每次 invoke 一次） |
| Wrap-style | `@wrap_model_call` | 包裹每次模型调用 |
| Wrap-style | `@wrap_tool_call` | 包裹每次工具调用 |
| **Convenience** | **`@dynamic_prompt`** | **生成动态 system prompt** |

### 2.2 3 个 Prebuilt Middleware

```python
from langchain.agents.middleware import (
    PIIMiddleware,
    SummarizationMiddleware,
    HumanInTheLoopMiddleware,
)
```

| Prebuilt | 用途 |
|---|---|
| `PIIMiddleware` | 脱敏（redact/block PII） |
| `SummarizationMiddleware` | 对话历史压缩 |
| `HumanInTheLoopMiddleware` | 敏感工具调用人工审批 |

### 2.3 `@dynamic_prompt` — 动态 Prompt 便捷装饰器

**Since v1.0** — 基于 `wrap_model_call` 的语法糖。装饰的函数接收 `ModelRequest`，返回 `str` 或 `SystemMessage`。

```python
from langchain.agents.middleware import dynamic_prompt

@dynamic_prompt
def milestone_context(request):
    """根据运行时状态注入动态上下文"""
    milestone = request.state.get("current_milestone", "")
    feedback = request.state.get("last_feedback", "")
    parts = [f"[Current milestone: {milestone}]"]
    if feedback:
        parts.append(f"[Previous feedback:\n{feedback}]")
    return "\n".join(parts)

agent = create_agent(
    model="deepseek-chat",
    tools=[...],
    system_prompt="Base prompt here.",
    middleware=[milestone_context],
)
```

等价的手写 `wrap_model_call`：

```python
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse
from langchain.messages import SystemMessage
from typing import Callable

@wrap_model_call
def milestone_context(
    request: ModelRequest,
    handler: Callable[[ModelRequest], ModelResponse],
) -> ModelResponse:
    text = build_dynamic_text(request.state)
    if not text:
        return handler(request)
    blocks = list(request.system_message.content_blocks) + [
        {"type": "text", "text": f"\n{text}"}
    ]
    return handler(request.override(system_message=SystemMessage(content=blocks)))
```

### 2.4 `@dynamic_prompt` vs `@wrap_model_call` vs Class

| 维度 | `@dynamic_prompt` | `@wrap_model_call` | `AgentMiddleware` |
|---|---|---|---|
| 代码量 | 最少（只返回 prompt） | 中等 | 最多 |
| 能否修改 response | 不能 | 能 | 能 |
| 能否短路/跳过 handler | 不能 | 能（不调用 handler） | 能 |
| 多 hook 组合 | 不支持 | 不支持（单 hook） | 支持 |
| async 版本 | 自动处理 | 需写 `awrap_model_call` | 需写 `awrap_*` |
| 适用场景 | 纯 prompt 注入 | 需要修改 request/response | 复杂中间件 |

### 2.5 Class-based Middleware

需要多 hook 组合或跨 hook 状态共享时使用：

```python
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.runtime import Runtime
from typing import Any, Callable

class LoggingMiddleware(AgentMiddleware):
    def before_model(self, state, runtime: Runtime) -> dict[str, Any] | None:
        print(f"Calling model with {len(state['messages'])} messages")
        return None

    def after_model(self, state, runtime: Runtime) -> dict[str, Any] | None:
        print(f"Model returned: {state['messages'][-1].content}")
        return None

    async def abefore_model(self, state, runtime: Runtime) -> dict[str, Any] | None:
        return None

    async def aafter_model(self, state, runtime: Runtime) -> dict[str, Any] | None:
        return None
```

### 2.6 执行顺序

```
middleware = [m1, m2, m3]

Before hooks (正序):     m1.before_agent → m2.before_agent → m3.before_agent
                          m1.before_model → m2.before_model → m3.before_model

Wrap hooks (嵌套):       m1.wrap_model_call ─┐
                          m2.wrap_model_call ─┤→ model
                          m3.wrap_model_call ─┘

After hooks (逆序):      m3.after_model → m2.after_model → m1.after_model
                         m3.after_agent → m2.after_agent → m1.after_agent
```

### 2.7 Agent Jumps（提前退出）

`before_model` 可以返回 `jumpTo` 提前终止执行：

```python
from langchain.agents.middleware import before_model

@before_model
def content_guard(state, runtime):
    last_msg = state["messages"][-1].content if state["messages"] else ""
    if "BLOCKED" in last_msg:
        return {
            "messages": [AIMessage("I cannot respond to that request.")],
            "jumpTo": "end",
        }
    return None
```

可用 jump target：`"end"` | `"tools"` | `"model"`

---

## 3. Context & State

### 3.1 Runtime Context（只读，per-invocation）

通过 `context_schema` 定义，invoke 时传入，middleware 通过 `request.runtime.context` 访问：

```python
from dataclasses import dataclass

@dataclass
class Context:
    user_id: str
    tenant_id: str
    model_preference: str = "default"

@wrap_model_call
def context_aware(request, handler):
    user_id = request.runtime.context.user_id
    return handler(request)

agent = create_agent(
    model="deepseek-chat",
    middleware=[context_aware],
    context_schema=Context,
)

result = agent.invoke(
    {"messages": [...]},
    context=Context(user_id="u1", tenant_id="acme"),
)
```

### 3.2 Custom State（可读写，跨 hook）

middleware 可以扩展 agent state：

```python
from langchain.agents.middleware import AgentMiddleware

class CounterMiddleware(AgentMiddleware):
    def after_model(self, state, runtime):
        count = state.get("model_call_count", 0)
        return {"model_call_count": count + 1}
```

State 字段以下划线 `_` 开头为 private（不包含在 invoke 返回结果中）。

---

## 4. 其他常见 Middleware 用例

### 4.1 Dynamic Model Selection

```python
from langchain.agents.middleware import wrap_model_call
from langchain.chat_models import init_chat_model

@wrap_model_call
def dynamic_model(request, handler):
    if len(request.messages) > 10:
        model = init_chat_model("claude-sonnet-4-6")
    else:
        model = init_chat_model("claude-haiku-4-5-20251001")
    return handler(request.override(model=model))
```

### 4.2 Dynamic Tool Selection

```python
@wrap_model_call
def tool_selector(request, handler):
    relevant_tools = select_relevant_tools(request.state, request.runtime)
    return handler(request.override(tools=relevant_tools))
```

### 4.3 Prompt Caching (Anthropic)

```python
from langchain.agents.middleware import wrap_model_call
from langchain.messages import SystemMessage

@wrap_model_call
def cached_context(request, handler):
    new_content = list(request.system_message.content_blocks) + [
        {
            "type": "text",
            "text": "Large document to analyze:\n<document>...</document>",
            "cache_control": {"type": "ephemeral"},
        }
    ]
    new_sys = SystemMessage(content=new_content)
    return handler(request.override(system_message=new_sys))
```

---

## 5. 关键 API 速查

```python
# 导入
from langchain.agents import create_agent
from langchain.agents.middleware import (
    before_agent, before_model, after_model, after_agent,
    wrap_model_call, wrap_tool_call,
    dynamic_prompt,                       # Convenience
    AgentMiddleware,                       # Class-based
    PIIMiddleware, SummarizationMiddleware, HumanInTheLoopMiddleware,  # Prebuilt
    ModelRequest, ModelResponse,
)
from langchain.chat_models import init_chat_model
from langchain.messages import SystemMessage, AIMessage, HumanMessage

# request API
request.system_message          # SystemMessage（始终是对象，即使 create_agent 传字符串）
request.system_message.content_blocks  # content blocks 列表
request.state                   # agent state
request.runtime.context         # 调用时传入的只读上下文
request.override(system_message=..., model=..., tools=...)  # 返回修改后的 request

# handler（wrap-style）
handler(request)  # 执行请求，可多次调用（retry）或不调用（短路）
```

---

## 6. 参考

- [dynamic_prompt | LangChain Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/dynamic_prompt)
- [wrap_model_call | LangChain Reference](https://reference.langchain.com/python/langchain/agents/middleware/types/AgentMiddleware/wrap_model_call)
- [LangChain 1.0 Release Notes](https://docs.langchain.com/oss/python/releases/langchain-v1)
- [Custom Middleware | LangChain Docs](https://docs.langchain.com/oss/python/langchain/middleware/custom)
- [Prebuilt Middleware | LangChain Docs](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [Deep Agents Skills | LangChain Docs](https://docs.langchain.com/oss/python/deepagents/skills)
- [LangChain Skills Pattern | LangChain Docs](https://docs.langchain.com/oss/python/langchain/multi-agent/skills)
- [LangChain+Skills 中间件实战 - 知乎](https://zhuanlan.zhihu.com/p/1995210331119714420)
- [LLM之Agent（二十九）｜LangChain 1.0核心组件介绍](https://developer.volcengine.com/articles/7577300925698539546)
