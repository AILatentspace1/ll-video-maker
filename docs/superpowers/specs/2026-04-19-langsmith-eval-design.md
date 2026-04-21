# LangSmith 完整评估系统设计

**日期:** 2026-04-19  
**范围:** ll_video_maker — research + script 两个 milestone  
**方案:** C（离线评估 + LLM-as-judge + pytest + 在线生产 feedback）

---

## 1. 整体架构

### 新增文件结构

```
src/ll_video_maker/
  evals/
    __init__.py
    dataset.py        # LangSmith dataset CRUD
    evaluators.py     # 全部 evaluator 函数
    run_eval.py       # client.evaluate() 离线实验入口（CLI）
    online_hook.py    # 生产运行后 create_feedback()

tests/
  eval/
    conftest.py       # pytest-langsmith 配置
    test_research.py  # research 评估测试用例
    test_script.py    # script 评估测试用例
```

### 数据流

```
测试 topic list
      ↓ dataset.py 上传
LangSmith Dataset "video-maker-eval-v1"
      ↓ run_eval.py (client.evaluate)
pipeline_target(inputs) → producer.ainvoke
      ↓
evaluators.py 打分
  ├── l1_research_pass     bool    复用 check_research()
  ├── l1_script_pass       bool    复用 check_script()
  ├── script_weighted_score float  script-eval.json weighted_total
  └── research_quality     float   LLM-as-judge (DeepSeek)
  └── [summary] l1_pass_rate float 全集通过率
      ↓
LangSmith Experiment（可跨版本对比）

生产运行（main.py）:
  online_hook.attach_production_feedback(trace_id, output_dir)
  → client.create_feedback() × N 个维度
```

---

## 2. Dataset 管理 (`evals/dataset.py`)

**Dataset 名称:** `video-maker-eval-v1`

### 测试 topic 列表（8 条）

| topic | duration | style | 覆盖场景 |
|---|---|---|---|
| DeepSeek R2 技术突破 | 1-3min | professional | 基准/短视频 |
| AI Agent 2026 趋势 | 1-3min | professional | 技术综述 |
| OpenAI o3 模型解析 | 3-5min | professional | 中长视频 |
| 大模型降价战 | 1-3min | casual | 商业话题 |
| 量子计算商业化 | 3-5min | storytelling | 叙事风格 |
| Cursor AI 编程助手 | 1-3min | casual | 工具类 |
| 中国 AI 独角兽崛起 | 5-10min | professional | 长内容 |
| Transformer 架构演进 | 3-5min | professional | 技术深度 |

### Example 结构

```python
{
    "inputs": {
        "topic": "DeepSeek R2 技术突破",
        "duration": "1-3min",
        "style": "professional",
        "source": "websearch",
        "eval_mode": "gan"
    }
    # 无 reference_outputs — 用 LLM-as-judge，不需黄金答案
}
```

### 接口

```python
def ensure_dataset(client: Client, name: str = DATASET_NAME) -> Dataset
def upload_examples(client: Client, dataset_id: str) -> None
def sync_dataset() -> None  # CLI: python -m ll_video_maker.evals.dataset
```

**幂等性要求：** `upload_examples` 在创建前先检查 examples 是否已存在：
```python
def upload_examples(client: Client, dataset_id: str) -> None:
    existing = {e.metadata.get("topic") for e in client.list_examples(dataset_id=dataset_id)}
    new_examples = [ex for ex in EXAMPLES if ex["inputs"]["topic"] not in existing]
    if new_examples:
        client.create_examples(dataset_id=dataset_id, examples=new_examples)
```
`sync_dataset()` 可安全多次调用（CI 脚本友好）。

---

## 3. Evaluators (`evals/evaluators.py`)

**行级 evaluator 签名:** `(outputs: dict, inputs: dict) -> EvaluationResult`
**Summary evaluator 签名:** `(outputs: list[dict], reference_outputs: list[dict]) -> dict` （见 3.5）

### 3.1 `l1_research_pass` — 规则二元判断
- 调用 `ratify_l1.check_research(outputs["output_dir"])`
- `key="l1_research_pass"`, `score=1` (pass) / `0` (fail)
- `comment` 填写具体失败原因列表
- **错误处理：** `outputs.get("output_dir")` 为 None 时返回 `score=0, comment="output_dir missing"`

### 3.2 `l1_script_pass` — 规则二元判断
- 调用 `ratify_l1.check_script(outputs["output_dir"], inputs["duration"])`
  - `duration` 从 **`inputs["duration"]`** 取（dataset example 字段）
- `key="l1_script_pass"`, `score=1` (pass) / `0` (fail)
- `comment` 填写具体 violations
- **错误处理：** `output_dir` 缺失时返回 `score=0, comment="output_dir missing"`

### 3.3 `script_weighted_score` — 复用 evaluator agent 输出
- 读取 `outputs["script_eval_json"]["weighted_total"]`（由 `pipeline_target` 返回）
- 主指标: `key="script_weighted_score"`, `score=weighted_total/100` (0.0-1.0)
- 子维度（额外 5 个 feedback）:
  - `dim_narrative_flow` (权重 30%)
  - `dim_contract_compliance` (权重 25%)
  - `dim_data_accuracy` (权重 20%)
  - `dim_pacing` (权重 15%)
  - `dim_visual_variety` (权重 10%)
- **错误处理：** `script_eval_json` 为 None 时返回 `score=0`

### 3.4 `research_quality_judge` — LLM-as-judge（DeepSeek）
- 读取 `outputs["research_file"]` 内容，用 DeepSeek 打分 0-100
- 评分维度:
  - 覆盖度（30%）：关键事实充分，有 hook/setup/development/climax/cta 各角色素材
  - 数据质量（40%）：数字有来源标注，无"约"/"超过"等模糊表述
  - 结构完整性（30%）：9 个章节都有实质内容
- `key="research_quality"`, `score=float 0-1`
- 使用 `langchain_openai.ChatOpenAI`（DeepSeek 兼容接口），structured output 返回 `{"score": int, "reasoning": str}`
- **错误处理：** API 失败时捕获异常，返回 `score=0.0, comment=f"judge failed: {e}"`（不抛出）

### 3.5 `l1_pass_rate` — Summary evaluator（experiment 级别）

**签名与行级 evaluator 不同：**
```python
def l1_pass_rate(outputs: list[dict], reference_outputs: list[dict]) -> dict:
    """计算所有样本 l1_script_pass 的通过率。"""
    pass_count = sum(1 for o in outputs if o.get("l1_script_pass", 0) == 1)
    return {"key": "l1_pass_rate", "score": pass_count / len(outputs) if outputs else 0.0}
```
传入 `summary_evaluators=[l1_pass_rate]`（不是 `evaluators`）

---

## 4. 实验运行器 (`evals/run_eval.py`)

### 目标函数

```python
async def pipeline_target(inputs: dict) -> dict:
    # output_dir 写到 --output-dir 指定路径（默认 ./eval-outputs/）
    base_dir = os.environ.get("EVAL_OUTPUT_DIR", "./eval-outputs")
    output_dir = init_output_dir(inputs["topic"], base_dir)
    producer = create_producer(project_root=base_dir)
    thread_id = f"eval-{uuid4().hex[:8]}"
    result = await producer.ainvoke(
        {"messages": [...user_message...], "output_dir": output_dir, ...},
        config={"configurable": {"thread_id": thread_id}},
    )
    script_eval = json.loads(Path(output_dir, "script-eval.json").read_text())
    return {
        "output_dir": output_dir,
        "research_file": str(Path(output_dir) / "research.md"),
        "script_file": str(Path(output_dir) / "script.md"),
        "script_eval_json": script_eval,
    }
```

### 运行主入口

```python
async def main():
    ls_client = Client()
    results = await ls_client.aevaluate(          # async target → 必须用 aevaluate
        pipeline_target,
        data=DATASET_NAME,
        evaluators=[l1_research_pass, l1_script_pass, script_weighted_score, research_quality_judge],
        summary_evaluators=[l1_pass_rate],
        experiment_prefix=args.experiment_prefix,
        max_concurrency=2,
    )
    print(results.to_pandas())
```

### 运行方式

```bash
# 离线实验（预期耗时 25-40 分钟，8 samples / 2 并发 × ~6 min/sample）
python -m ll_video_maker.evals.run_eval --experiment-prefix "v1.2-prompt-fix"

# 只跑前 2 个样本（快速验证，约 12-15 分钟）
python -m ll_video_maker.evals.run_eval --max-examples 2

# 指定输出目录（避免污染项目根目录）
python -m ll_video_maker.evals.run_eval --output-dir /tmp/eval-runs
```

### 关键参数

- `max_concurrency=2` — 避免 DeepSeek API rate limit
- `experiment_prefix` — 便于在 LangSmith UI 对比多个版本
- `--output-dir` — eval 中间文件输出路径（默认 `./eval-outputs/`，不污染 `./output/`）
- 结果自动以 pandas DataFrame 可查看（`results.to_pandas()`）

---

## 5. 在线 Feedback Hook (`evals/online_hook.py`)

```python
def attach_production_feedback(run_id: str, output_dir: str) -> None:
    """生产运行结束后，把 script-eval.json 评分挂载到 LangSmith trace。
    
    run_id: 由 main.py 生成并传入 ainvoke config，不从 callback 提取。
    """
    if not run_id:
        return  # 静默保护：run_id 为 None 时不调用 API
    script_eval_path = Path(output_dir) / "script-eval.json"
    if not script_eval_path.exists():
        return  # legacy 模式或 eval 未完成时，跳过
    ...
```

**集成到 `main.py`（run_id 显式传递方案）:**
```python
from uuid import uuid4

run_id = str(uuid4())
result = asyncio.run(producer.ainvoke(
    {...},
    config={
        "configurable": {"thread_id": thread_id},
        "run_id": run_id,   # LangSmith 用此作为 root run ID
    },
))
attach_production_feedback(run_id, output_dir)
```

**注意：** `"run_id"` 在 LangGraph RunnableConfig 中须为顶层 key（非 `configurable` 嵌套）。

**上传的 feedback keys:**
- `script_weighted_score` (normalized 0-1)
- `dim_narrative_flow`, `dim_contract_compliance`, `dim_data_accuracy`, `dim_pacing`, `dim_visual_variety`
- `l1_script_pass` (bool)
- `l1_research_pass` (bool)

---

## 6. pytest 集成 (`tests/eval/`)

### conftest.py

```python
import pytest

# langsmith_experiment_metadata fixture 用于附加元数据到实验
@pytest.fixture(scope="session")
def langsmith_experiment_metadata():
    import os
    return {
        "model": os.getenv("PRODUCER_MODEL", "deepseek-chat"),
        "provider": os.getenv("LLM_PROVIDER", "deepseek"),
    }
```

（不需要 `pytest_plugins` — `@pytest.mark.langsmith` 由安装 `langsmith[pytest]` 自动注册）

### test_script.py

```python
import pytest
from langsmith import testing as t   # t 在这里 import
from ll_video_maker.middleware.ratify_l1 import check_script

@pytest.mark.langsmith
@pytest.mark.parametrize("topic,duration", [
    ("DeepSeek R2 技术突破", "1-3min"),
    ("AI Agent 2026 趋势", "1-3min"),
])
async def test_script_quality(topic, duration):
    result = await run_pipeline(topic, duration)
    t.log_inputs({"topic": topic, "duration": duration})
    t.log_outputs(result)
    score = result["script_eval_json"]["weighted_total"]
    t.log_feedback(key="script_weighted_score", score=score / 100)
    assert score >= 75, f"脚本评分 {score} 低于阈值 75"
    assert check_script(result["output_dir"]) == [], "L1 规则未通过"
```

### test_evaluators.py（新增，单元测试 evaluator 逻辑）

```python
# tests/eval/test_evaluators.py — 运行 < 1s，无需调用 pipeline
import json
import pytest
from pathlib import Path
from ll_video_maker.evals.evaluators import l1_research_pass, l1_script_pass, script_weighted_score

def test_l1_research_pass_success(tmp_path):
    (tmp_path / "research.md").write_text("## A\n## B\n## C\n" + "x" * 800 + " https://example.com")
    result = l1_research_pass({"output_dir": str(tmp_path)}, {})
    assert result["score"] == 1

def test_l1_research_pass_fail_short(tmp_path):
    (tmp_path / "research.md").write_text("too short")
    result = l1_research_pass({"output_dir": str(tmp_path)}, {})
    assert result["score"] == 0

def test_l1_research_pass_missing_output_dir():
    result = l1_research_pass({}, {})
    assert result["score"] == 0
    assert "missing" in result["comment"]

def test_script_weighted_score_normal():
    result = script_weighted_score({"script_eval_json": {"weighted_total": 82}}, {})
    assert abs(result["score"] - 0.82) < 0.001

def test_script_weighted_score_none():
    result = script_weighted_score({"script_eval_json": None}, {})
    assert result["score"] == 0
```

### 运行命令

```bash
# 单元测试（< 1 秒）
pytest tests/eval/test_evaluators.py -v

# 端到端 eval 并上传到 LangSmith
LANGSMITH_TEST_SUITE="video-maker-v1.2" pytest tests/eval/test_script.py --langsmith -v

# 指定实验名称
LANGSMITH_TEST_SUITE="v1.2" LANGSMITH_EXPERIMENT="baseline" pytest tests/eval/ --langsmith
```

---

## 7. 依赖变更 (`pyproject.toml`)

新增至 `[project.optional-dependencies]` dev：
```
langsmith[pytest]>=0.3.4    # pytest 集成需要此 extra（非 langsmith>=0.2.0 基础包）
pytest-asyncio>=0.23.0      # 已有，确认版本
pytest>=8.0.0               # 已有
```

新增至 `[tool.pytest.ini_options]`（需要在 pyproject.toml 中添加此节）：
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"        # 所有 async test 自动加 asyncio 支持，无需逐一 @pytest.mark.asyncio
```

不引入 `openevals`（避免 OpenAI 依赖，直接用 DeepSeek 实现 LLM-as-judge）。

---

## 8. 质量门槛

| 指标 | 阈值 | 说明 |
|---|---|---|
| `l1_script_pass` | 1.0 | 硬规则，必须 100% 通过 |
| `script_weighted_score` | ≥ 0.75 | 对应 75/100 分 |
| `l1_pass_rate` (summary) | ≥ 0.87 | 8 个样本中至少 7 个通过 |
| `research_quality` | ≥ 0.70 | research 语义质量底线 |

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open (PLAN) | 8 issues, 3 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**ENG REVIEW FINDINGS (已修复到 spec):**
- 3 Architecture: run_id 提取机制、aevaluate() 指明、output_dir 清理
- 3 Code Quality: summary evaluator 签名、pytest 写法、依赖补全
- 2 Test: evaluator 单元测试补充、duration 来源指明

**TODOS:** 2 deferred (eval-the-eval, CI/CD 集成) → `TODOS.md`

**VERDICT:** ENG REVIEW COMPLETED — 所有问题已在 spec 中修复，0 unresolved decisions。可进入实现阶段。
