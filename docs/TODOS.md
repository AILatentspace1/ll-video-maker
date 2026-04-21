# TODOS

## eval-the-eval: research_quality_judge prompt 验证

**What:** 验证 `research_quality_judge` 的 judge prompt 自身的评分方向是否正确。

**Why:** LLM-as-judge 如果 prompt 漂移或 DeepSeek 对中文评分标准理解有偏差，`research_quality` 指标会悄悄失效——数字变化，但方向错误。

**Pros:**
- 防止"指标看起来正常但实际判断错误"的隐性风险
- 一旦发现 judge 偏差，可以直接调整 prompt 而不影响被评估的 pipeline

**Cons:**
- 需要手工准备 3-5 个黄金样本（1-2 个已知好的 research.md，1-2 个已知差的）
- 工作量约 2-4h

**Context:**
- 涉及文件：`evals/evaluators.py` 的 `research_quality_judge` 函数
- 实现方式：在 `tests/eval/test_evaluators.py` 中加 `test_judge_direction()`
  - mock 一个 800+ 字、3 个章节、有 URL、有具体数字的 research.md → 期望 score >= 0.70
  - mock 一个只有 150 字的 research.md → 期望 score <= 0.30
- 需要真实调用 DeepSeek，用 `@pytest.mark.slow` 标记，不进入默认测试集

**Depends on:** `evals/evaluators.py` Section 3.4 实现完成后

---

## CI/CD 集成：定期自动运行 eval

**What:** 在 CI 中定期（如每天或每次 PR 修改 agent prompt）自动运行 `pytest tests/eval/ --langsmith`。

**Why:** 目前 eval 只能手动触发。如果有人修改了 researcher/scriptwriter/evaluator 的 prompt 但没跑 eval，可能静默降低输出质量。

**Pros:**
- 自动质量护栏，每次 prompt 变更有指标对比
- LangSmith UI 自动生成版本对比图

**Cons:**
- CI 需要配置 `LANGSMITH_API_KEY` + `DEEPSEEK_API_KEY` 为 secrets
- 运行时间 25-40 分钟，需要专用 CI job（不阻塞普通 PR 流程）

**Context:**
- 建议触发条件：`agents/*.py`, `agents/*.md` 文件变更时触发（不是每次 push）
- 运行 `--max-examples 2` 做快速 smoke check，完整 8 examples 每周一次

**Depends on:** eval 系统先手动运行 2-3 次确认稳定后再接入 CI
