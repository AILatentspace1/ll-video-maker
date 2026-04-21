### 10.2 环境变量

```bash
POSTGRES_URL=postgresql://...
ANTHROPIC_API_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=video-maker-prod
TTS_API_KEY=...
IMAGE_GEN_API_KEY=...
REMOTION_BIN=/usr/local/bin/remotion
```

---

## 11. 和现有 Claude Code 版的共存策略

### 11.1 共享层（两版共用）

| 资产 | 共享方式 |
|---|---|
| `pipeline-cli` (Node.js) | **同一个 repo**，两版都通过 subprocess 调 |
| Remotion template | 同上 |
| LangSmith dataset | 同上 |
| MCP server（阶段 2 提取后） | 两版都能接入 |
| Reflexion 经验 | **LangChain 版的 Store** 作为主源，Claude Code 版通过 MCP 读取 |

### 11.2 独有层

| LangChain 版独有 | Claude Code 版独有 |
|---|---|
| FastAPI 服务器 | Claude Code SKILL.md |
| Postgres checkpointer | `output/*/state.yaml` |
| 多租户 auth | 单用户本地 |
| Online eval dashboard | ad-hoc 人工审 |

### 11.3 迁移路径

- **阶段 0（现在）**：Claude Code 版继续演进，LangChain 版开 `video-maker-lc` 分支 PoC
- **阶段 1（2-4 周）**：LangChain 版 MVP 跑通 research + script milestone，不做 assets
- **阶段 2（1-2 月）**：assets milestone 串行版完成，打通端到端
- **阶段 3（2-3 月）**：提取 MCP server，两版共用
- **阶段 4（3+ 月）**：加多租户、并行 assets、online eval dashboard，考虑对外开放

---

## 12. 风险与限制

### 12.1 已知风险

| 风险 | 可能性 | 影响 | 缓解 |
|---|---|---|---|
| Middleware 嵌套导致调试困难 | 高 | 中 | 每个 middleware 加详细 LangSmith metadata |
| Checkpointer 体积膨胀（state 里存大字段） | 中 | 高 | 严格只存 path 指针，不存文件内容 |
| Store 变成垃圾堆（reflexion 写太多） | 高 | 中 | 写入前去重，每项目最多写 3 条 |
| Judge 漂移导致 ratify 失效 | 中 | 高 | 周度 calibration + few-shot 自动对齐 |
| Send 并行导致付费 API 成本失控 | 中 | 中 | Rate limit middleware + daily budget 门槛 |

### 12.2 明确不做的事

- ❌ 不支持实时协作（多人同时编辑同一项目）—— 超出本文档范围
- ❌ 不自动翻译 Claude Code 版的 SKILL.md → LangChain 代码 —— 手工迁移更可靠
- ❌ 不在 MVP 包含 web UI —— 先 CLI + Postman 验证 API，UI 后期

---

## 13. 验收标准

MVP 算完成的标志：

1. ✅ 单个视频项目能从 API 请求一路跑到 final/video.mp4
2. ✅ Producer 在 script milestone 前 interrupt 一次，Gary 审核后 resume 能继续
3. ✅ Retry 机制：script 第一次被 judge 拒绝后能带反馈重试 1 次
4. ✅ Postgres checkpointer 中断一次后能 resume
5. ✅ 前端通过 WebSocket 能实时看到 scene 渲染进度
6. ✅ LangSmith 能看到完整 trace，按 milestone 过滤
7. ✅ Online evaluator 在生产 trace 上自动打分，kappa vs 人工 >= 0.65
8. ✅ 和 Claude Code 版跑同一个 topic，两个产出的视频在 pairwise 评测中 tie 或 LangChain 版胜率 >= 40%（说明迁移没明显退化）

---

## 14. 开放问题

以下问题在本 spec 阶段未定，需要实施时决策：

- **Q1**：Reflexion 应该在每个 milestone 后就触发抽取还是只在项目结束？
- **Q2**：`goal.yaml` 是保留（兼容性）还是完全由 API 参数替代？
- **Q3**：用户并发跑多个项目时，是否需要 per-user queue 控制 API rate？
- **Q4**：Remotion 渲染放 FastAPI 同进程（简单）还是独立 worker（可扩展）？
- **Q5**：是否支持"中途切换模式"—— 比如 research 阶段已经用 claude-sonnet，后面几个场景换 haiku 省钱？

---

## 15. 参考

- `ARCHITECTURE-VIDEO-MAKER.md`（Claude Code 版，本项目前身）
- `langchain-session.md`（前期学习文档，包含所有概念的详细展开）
- LangChain 1.0 官方文档：https://docs.langchain.com/oss/python/langchain/overview
- LangGraph durable execution：https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangSmith evaluation：https://docs.langchain.com/langsmith/evaluation
- 本项目配套 issues：`#TBD`（待建）