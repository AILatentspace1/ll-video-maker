# Plan: ll_video_maker 自主开发循环（一次性 PoC）

## Context

你希望项目能"自动开发功能 → 自动验证 → 自动测试"，并选择了最保守组合：
- **一次性 PoC**（先跑通再决定是否固化为定时任务）
- **Agent 自主选择任务**（从 backlog 里挑一个高价值项）
- **开 PR 等人工 review**（不直接 merge）
- **四层验证全开**：静态 + 单测 + pipeline + 评估

**现状缺口**（来自 Explore 扫描）：
- `.github/workflows/` 不存在，只有 instructions 文档
- 无 `mypy`、无覆盖率配置；`ruff` 已配但未接入流程
- 无 `BACKLOG.md`；`docs/TODOS.md` 只有 2 项
- 16 个 pytest 用例，但没有统一入口脚本把"静态+单测+pipeline+eval"串起来
- 没有 `/auto-feature` 这类自动化 skill 或 slash command

**目标**：搭一套最小可行的"自主开发循环"骨架，让你在 Claude Code 里一条 `/auto-feature` 命令触发一次完整的"选任务 → 实现 → 四层验证 → 开 PR"流程；跑通后再决定是否上定时。

---

## 方案总览

```
/auto-feature (slash command)
      │
      ├─ Step 1. 读 docs/BACKLOG.md + git log + 代码扫描，挑一个任务（写入 .auto-feature/current.md）
      ├─ Step 2. 开 worktree/branch: auto/<slug>-<date>
      ├─ Step 3. TDD 实现（先写测试，再实现）
      ├─ Step 4. 运行 python scripts/verify.py（串起四层验证，本地+CI 同一入口）
      │         ├─ ruff check (静态)
      │         ├─ pytest --cov (单测 + 覆盖率门槛)
      │         ├─ python -m ll_video_maker.main（小话题 pipeline，subprocess 调用）
      │         └─ 解析 script-eval.json，pass=true 且 weighted_total>=75
      ├─ Step 5. 失败 → 最多 2 轮自我修复；仍失败则开 Draft PR 标 [NEEDS HELP]
      └─ Step 6. 成功 → gh pr create，body 含任务说明/验证输出/成本统计
```

---

## 要新建/修改的文件

### 新建

| 路径 | 作用 |
|---|---|
| `docs/BACKLOG.md` | Agent 选任务的菜单；初始播种 5–8 条候选（低风险小功能、测试补齐、文档、工具改进）。含"禁止自主动"的红线清单（prompt 核心、LLM provider 切换、pyproject 重大变更）。 |
| `scripts/verify.py` | **本地 + CI 共用的一键验证入口**（Python，不是 bash）。核心是 `--tier {quick,smoke,full}` 三档（见下"验证分层"小节）；内部用 `subprocess.run` 调 ruff/pytest/main.py；失败即 `sys.exit(非 0)`。 |
| `scripts/check_eval.py` | `verify.py` 导入的模块（也可单独 CLI 调）：接收**显式 `output_dir` 参数**（不做"找最近目录"启发式），解析 `script-eval.json` 并兼容两种并存 schema（见下"schema drift 处理"），返回 `{pass, weighted_total, source_schema, warnings}`。 |
| `.claude/commands/auto-feature.md` | Slash command 定义；指导 Claude 按 6 步走并调 `python scripts/verify.py`；明确边界（只改 src/ tests/ docs/，不动 pyproject/config.py/prompts/）。 |
| `.github/workflows/ci.yml` | **分层设计**：默认 job（所有 PR）跑 `--tier quick`（无 LLM 调用）；条件 job（agents/prompts/producer/middleware/validators 变更时）跑 `--tier smoke`；`workflow_dispatch` 手动触发可选 tier；nightly schedule 跑 `--tier full`。见下"CI 分层"小节。 |
| `.gitignore` 追加 | `.auto-feature/` 工作目录、`coverage.xml`、`.coverage`、`htmlcov/` |

### 修改

| 路径 | 改动 |
|---|---|
| `pyproject.toml` | **[bootstrap layer 修改，非 autonomous]** 加 `[dev]` 依赖：`pytest-cov>=5.0`、`mypy>=1.8`；加 `[tool.mypy]` 最小配置（先只检查 `src/ll_video_maker/middleware` 和 `validators/` 两个严格区）；加 `[tool.coverage.run]` source；**不加 `--cov-fail-under`**（Phase A 只测量不 gate，见"验证分层"小节）。 |
| `CLAUDE.md` | 加"Autonomous Feature Loop"小节，说明 `/auto-feature` 用法、禁止触碰的文件清单、如何审查 PR。 |

---

## 关键设计决策

### 1. 任务来源（回答"Agent 自主决定"的实现）
- **不让 agent 完全放飞**——给它 `docs/BACKLOG.md` 作为有界菜单，它从中挑一个"最小可独立完成"的项。
- **我会基于 Explore 扫描直接播种候选**（价值/风险/预计改动行数标签齐全），**所有候选都限定在 autonomous layer 允许范围内**（见下"权限分层"小节，禁止触碰 prompts/provider/核心编排）：
  1. **[高优先]** 给 `check_eval.py` 加 JSON schema 后验证，兼容 canonical↔drift（价值高 / 风险低 / ~100 行，纯工具代码）
  2. `middleware/ratify_l1.py` 单测补齐（价值高 / 风险低 / ~150 行测试）
  3. `validators/*.py` 边界用例（价值中 / 风险低 / ~200 行测试）
  4. 新建 `scripts/list_runs.py` 列出最近 output 目录 eval 分数汇总（价值中 / 风险低，天然兼容两种 schema）
  5. 为 `main.py --help` 输出补 examples 段、更新 README 用法（价值低 / 风险极低，"warm-up"任务）
  6. `docs/` 文档补充：给 `agents/*.py`、`middleware/*.py` 写模块级 docstring（价值低 / 风险低，纯文档）

- **属于 autonomous layer 禁区、需人工单独处理的后续项**（**不放进 `/auto-feature` 的 BACKLOG**，只在 `docs/TODOS.md` 里记待办）：
  - 强化 `prompts/evaluator.md` 让模型严格按 canonical schema 输出（碰 prompt，需人工）
  - `producer.py` magic number 抽离到 `config.py`（改核心编排 + 默认配置，需人工）
  - `docs/TODOS.md` 里的 "eval-the-eval judge validation"（需改 evaluator prompt 行为）
  - 实现 `evals/evaluators.py` + `tests/eval/` + 启用 `full` tier schedule（依赖上一项）
  - 锁定 coverage 门槛（Phase B，等基线出来后独立 PR 加 `--cov-fail-under`）

- Agent 输出 `.auto-feature/current.md` 含：选了哪个、为什么（价值/风险评估）、排除了哪些、预估改动范围。

### 2. 验证分层（verify.py 的 --tier 接口）

| tier | 层级内容 | 用途 | LLM key 需求 | PoC 阶段状态 |
|---|---|---|---|---|
| `quick`（默认） | ruff + pytest + 可选 mypy | 所有普通 PR / 本地快速循环 | ❌ 无 | ✅ 实现 |
| `smoke` | quick + 一次小 topic pipeline + `check_eval`（canonical/drift 都要过 `pass==true AND weighted_total>=75`） | 触碰核心逻辑（agents/prompts/producer/middleware/validators）时 / `/auto-feature` PoC 演示 | ✅ DEEPSEEK_API_KEY | ✅ 实现 |
| `full` | smoke + eval 套件（`pytest tests/eval/`） | 未来：nightly 完整质量评估 | ✅ DEEPSEEK_API_KEY + LANGSMITH_API_KEY | ⚠️ **占位** |

**`full` 的占位策略**（PoC 阶段 `tests/eval/` 和 `evals/evaluators.py` 还不存在，见 `docs/TODOS.md:19/24/46`）：
- `verify.py --tier full` 内部先 `Path("tests/eval").exists()` 检查；不存在时打印 `[SKIP] tests/eval/ not yet implemented — see docs/TODOS.md` 并以 `exit 0` 返回（不当失败）。仍跑 smoke 的全部内容。
- CI workflow 里 **不把 `full` 加到 schedule 触发**，只保留 `workflow_dispatch` 可选入口；nightly 只跑 smoke。等 `evals/evaluators.py` 实现后再加 schedule。
- `docs/BACKLOG.md` 里明确列"实现 evals/evaluators.py + 启用 full tier schedule"作为后置任务。

命令：`python scripts/verify.py --tier quick`（默认）/ `--tier smoke` / `--tier full`（占位）。
另支持 `--topic "量子计算入门"` 覆盖 smoke 默认 topic，`--no-cov` 跳过覆盖率（本地快速迭代）。

**门槛细节**：
- 静态：`ruff check --output-format=github` 必须零错误
- 单测（**Phase A：测量，不 gate**）：`pytest --cov=src/ll_video_maker --cov-report=xml --cov-report=term -v`；CI 上传 `coverage.xml` 为 artifact、在 PR 评论显示覆盖率摘要，但**不加 `--cov-fail-under`**，覆盖率不参与合并判定
- 单测（**Phase B：锁门槛，后续 PR**）：等基础设施 PR 合进去、跑过 1-2 次拿到稳定基线后，再在独立 PR 里追加 `--cov-fail-under=<基线-2%>`，并加 `diff-cover` 类工具锁改动行覆盖率
- Pipeline（smoke/full）：固定小话题 `--topic "量子计算入门" --duration 1-3min --style professional --source websearch`，一次 ~4–6 次 LLM 调用
- Eval（smoke/full）：`scripts/check_eval.py` 兼容两种 schema，要求 `pass==true` 且 `weighted_total>=75`

> **为什么分两步**：现在仓库从没跑过 coverage，基线未知。如果首个基础设施 PR 自己就锁 60%，极可能自己把自己卡红（现有 16 个测试很可能覆盖不到 60%）。先测量、看清基线、再锁——这是通用原则，适用于所有"量化指标门槛"（coverage / bundle size / perf budget）。

### 2.5 Schema drift 处理（check_eval.py 的关键逻辑）

仓库里 `script-eval.json` 当前**两种 schema 并存**（2026-04 的实际 run 漂出 canonical）：

| 字段 | Canonical (per evaluator.md) | Drift（2026-04-24 run） |
|---|---|---|
| `pass` | ✅ | ✅ |
| `weighted_total` | ✅ float | ❌ 缺失 |
| `dimensions` | ✅ list(含 weight) | ❌ 缺失 |
| `scores` | ❌ | ✅ dict {name: int} |
| `iteration_fixes` | ✅ | ❌ 缺失 |
| `contract_violations` | ✅ | ❌ 缺失 |

`check_eval.py` 解析策略（按顺序尝试）：

```python
CANONICAL_WEIGHTS = {
    "narrative_flow": 0.25, "pacing": 0.20, "visual_variety": 0.20,
    "audience_fit": 0.15, "content_coverage": 0.20,
}
REQUIRED_DIMS = set(CANONICAL_WEIGHTS)

def parse_eval(data: dict) -> EvalResult:
    if "pass" not in data:
        raise SchemaError("missing required field 'pass'")

    # 1. Canonical: 直接读 weighted_total
    if "weighted_total" in data and "dimensions" in data:
        return EvalResult(passed=data["pass"], weighted_total=data["weighted_total"],
                          schema="canonical", warnings=[])

    # 2. Drift: 从 scores dict 计算
    if "scores" in data and isinstance(data["scores"], dict):
        scores = data["scores"]
        missing = REQUIRED_DIMS - set(scores)
        if missing:
            raise SchemaError(f"drift schema missing dims: {missing}")
        total = sum(scores[k] * CANONICAL_WEIGHTS[k] for k in CANONICAL_WEIGHTS)
        return EvalResult(passed=data["pass"], weighted_total=total,
                          schema="drift",
                          warnings=[f"drift schema: computed weighted_total={total:.1f} from scores"])

    raise SchemaError("unrecognized schema: neither canonical nor drift")
```

- 门槛仍然 `pass==true AND weighted_total>=75`（drift 时计算出来的）
- warnings 要打印出来，让 PR 作者看到漂移告警
- 为了以防未来再漂，脚本要**整体 try/except**，schema 失败时明确打印 "UNKNOWN SCHEMA, human review required" 而不是当成通过

### 2.6 CI 分层（.github/workflows/ci.yml 设计）

四个 job：`quick`（阻塞） → `changes`（路径检测） → `smoke`（条件触发） / `full`（手动占位）。以下是**执行时直接落地的真实 YAML**（无伪代码）：

```yaml
name: verify

on:
  pull_request:
  push:
    branches: [master]
  workflow_dispatch:
    inputs:
      tier:
        description: '验证层级'
        type: choice
        options: [quick, smoke, full]
        default: smoke
  schedule:
    - cron: '0 18 * * *'  # 02:00 CST；PoC 阶段仅触发 smoke，不触发 full

jobs:
  quick:
    # 所有 PR / push 都跑；唯一阻塞合并的 job
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: python scripts/verify.py --tier quick
    concurrency:
      group: quick-${{ github.ref }}
      cancel-in-progress: true

  changes:
    # 用 dorny/paths-filter 判断是否动了核心路径
    runs-on: ubuntu-latest
    outputs:
      core: ${{ steps.filter.outputs.core }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            core:
              - 'src/ll_video_maker/agents/**'
              - 'src/ll_video_maker/prompts/**'
              - 'src/ll_video_maker/producer.py'
              - 'src/ll_video_maker/middleware/**'
              - 'src/ll_video_maker/validators/**'

  smoke:
    # 条件触发：核心路径变更 / schedule / workflow_dispatch(smoke|full)
    needs: [quick, changes]
    if: |
      needs.changes.outputs.core == 'true' ||
      github.event_name == 'schedule' ||
      (github.event_name == 'workflow_dispatch' && inputs.tier != 'quick')
    runs-on: ubuntu-latest
    env:
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: python scripts/verify.py --tier smoke
    concurrency:
      group: smoke-${{ github.ref }}
      cancel-in-progress: true

  full:
    # PoC 阶段仅 workflow_dispatch(tier=full) 触发；不接 schedule
    # 等 tests/eval/ 和 evals/evaluators.py 到位后改 if 表达式加入 schedule
    if: github.event_name == 'workflow_dispatch' && inputs.tier == 'full'
    needs: quick
    runs-on: ubuntu-latest
    env:
      DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
      LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -e ".[dev]"
      - run: python scripts/verify.py --tier full   # verify.py 检测 tests/eval 不存在时 SKIP 并 exit 0
```

**分支保护**：repo 设置里只把 `quick` 设为 required check，`smoke` / `full` 作为通知型（失败不阻塞合并，但 PR 作者能看到）。
- warnings 要打印出来，让 PR 作者看到漂移告警
- 为了以防未来再漂，脚本要**整体 try/except**，schema 失败时明确打印 "UNKNOWN SCHEMA, human review required" 而不是当成通过

### 3. 权限分层（Bootstrap vs Autonomous）

**两层权限明确分开**，禁区只约束自主层：

| 层 | 谁执行 | 可改文件 | 说明 |
|---|---|---|---|
| **Bootstrap layer** | 人工（本次 PoC 搭建）+ 后续人工维护 | `pyproject.toml`、`.github/workflows/**`、`scripts/**`、`.claude/commands/**`、`CLAUDE.md`、`.gitignore`、`docs/**`、新建文件 | 首次搭基础设施、版本升级、CI 调整都走这层 |
| **Autonomous layer** (`/auto-feature`) | Claude 自主 | `src/ll_video_maker/middleware/**`、`src/ll_video_maker/validators/**`、`tests/**`、`scripts/list_runs.py` 等纯工具、`docs/**`、`README.md` | 范围窄，任务来自 `docs/BACKLOG.md` |

**Autonomous layer 禁区清单**（`docs/BACKLOG.md` 顶部明示、`.claude/commands/auto-feature.md` 里再强调一次）：

- ❌ `src/ll_video_maker/prompts/**`（任何 .md prompt 文件）
- ❌ `src/ll_video_maker/llm.py`（provider 工厂）
- ❌ `src/ll_video_maker/config.py`（默认模型、API base）
- ❌ `src/ll_video_maker/producer.py`（核心编排逻辑，包括 magic number 重构）
- ❌ `src/ll_video_maker/agents/{researcher,scriptwriter,evaluator}.py`（agent 构造函数）
- ❌ `pyproject.toml`（依赖升级、元数据）
- ❌ `.github/workflows/**`（CI 自修）
- ❌ `.claude/commands/auto-feature.md`（防止自改规则）

违反禁区时 `/auto-feature` 必须立即停手、报告"需要用户批准才能动 X，放弃本次任务"，不要偷偷改。

**成本护栏**（适用两层）：
- 单次 `/auto-feature` 循环硬上限：**1 次 pipeline 运行**（≈ 0.5–1 美元 deepseek 成本），2 轮自修复
- Branch 全部用 `auto/` 前缀；PR 标题 `[auto-feature] <slug>`，默认 draft，明确要求人工 review

### 4. 为什么不直接跑 `/ralph-loop`
`ralph-loop` 是通用 session loop，没有本项目的"挑任务 + 四层验证 + PR 交付"专门化。 `/auto-feature` 是窄而深的定制，产出物是 PR 而不是变更堆。跑通后你可以决定是否用 `/schedule` 或 `/loop` 把它周期化。

---

## 关键复用点（来自 Explore）

- **Pipeline 入口**：`src/ll_video_maker/main.py` 已经支持 `--topic` 等完整参数，直接 shell 调即可
- **Eval JSON schema**：`producer.py:_extract_eval_state_updates()` 已定义 `pass`/`weighted_total`/`iteration_fixes` 字段，`check_eval.py` 直接读
- **Ratify middleware**：`middleware/ratify_l1.py` 本身就能给 pipeline 兜底，不需要 `/auto-feature` 再做内容校验
- **Ruff 配置**：`pyproject.toml` 已有 `line-length=100 / target-version=py311`，CI 直接用

---

## 验证（如何验证这个 PoC 本身可用）

**手工跑一次**（你接受计划后，在同一 session 里执行）：

```bash
# 1. 确认基础设施就位
ls scripts/verify.py scripts/check_eval.py .claude/commands/auto-feature.md docs/BACKLOG.md

# 2. 先分档跑 verify.py 确保各层通路
python scripts/verify.py --tier quick      # 静态+单测，无 LLM
python scripts/verify.py --tier smoke      # + 小 topic pipeline + eval 校验
# （可选）python scripts/verify.py --tier full   # 完整 eval 套件

# 3. 触发 slash command
# 在 Claude Code 里输入: /auto-feature
# 观察 Claude 选了哪个任务、如何执行、是否开出 PR

# 4. 检查产出
gh pr list --author "@me" --state open
# 打开 PR 查看 body 中的"任务说明 / 验证日志 / 成本统计"是否齐全
```

**成功标准**：
- `/auto-feature` 选了 BACKLOG 中一项，写进 `.auto-feature/current.md`
- 开了 `auto/*` 分支，commit 至少含"代码 + 对应测试 + CHANGELOG/更新说明"
- `scripts/verify.sh` 绿，eval JSON 满足门槛
- GitHub PR 已开（draft），body 完整

**失败降级**：如果 pipeline 阶段因为网络或 API 限流失败，PR 仍然开但标 `[NEEDS HELP: pipeline unverified]`，不占用"成功"额度。

---

## 已确认的决策

1. **CI 分层，不是每 PR 都跑 pipeline**（对齐 `docs/TODOS.md` 现有设计）：
   - `quick`（所有 PR / 默认阻塞）：ruff + pytest，无 LLM 调用
   - `smoke`（条件触发：agents/prompts/producer/middleware/validators 变更、手动 dispatch、nightly）：含真实 pipeline + eval 校验
   - `full`（**PoC 阶段占位**：仅 workflow_dispatch 手动触发；不接 schedule）：等 `tests/eval/` + `evals/evaluators.py` 实现后再开 schedule
   - 只有 `quick` 是合并必过项；`smoke` 是通知型
   - Secrets：`DEEPSEEK_API_KEY` 给 smoke；`LANGSMITH_API_KEY` 留到 full 真正启用时再加
2. **BACKLOG 由我播种**：基于 Explore 扫描直接写 7 条候选（schema drift 修复排首位，见上节"关键设计决策 1"）
3. **立即端到端跑一次**：基础设施建好后，在同一 session 里触发 `/auto-feature` 做演示。预计额外成本 ~0.5–1 美元 deepseek。

## 执行顺序（批准后）

0. **移动本计划文件到 `docs/plans/autonomous-feature-loop.md`**（语义化重命名）；原 `~/.claude/plans/sharded-painting-wirth.md` 删除。plan 与代码一起版本化，便于 review 和演进对比。
1. 建 `docs/BACKLOG.md`（播种 7 条，schema drift 排首位）
2. 建 `scripts/verify.py` + `scripts/check_eval.py`（Python 一套，`--tier {quick,smoke,full}`）
3. 建 `.claude/commands/auto-feature.md`
4. 改 `pyproject.toml`（pytest-cov / mypy / coverage 配置，Phase A 不锁 `--cov-fail-under`）
5. 建 `.github/workflows/ci.yml`（三档 job：quick 默认阻塞、smoke 路径触发、full schedule）
6. 更新 `CLAUDE.md` 和 `.gitignore`
7. **本地先跑 `python scripts/verify.py --tier quick`** 确认静态+单测通路
8. 再本地跑 `python scripts/verify.py --tier smoke` 确认 pipeline+eval 通路（验证 check_eval.py 对两种 schema 的处理）
9. 如果都 OK，触发 `/auto-feature` 做完整端到端演示
10. 人工检查产出的 PR（不 merge）

**注意**：第 8 步需要你确认 GitHub Secrets 已配好且 `.env` 里有可用的 `DEEPSEEK_API_KEY`；否则 pipeline 阶段会失败。
