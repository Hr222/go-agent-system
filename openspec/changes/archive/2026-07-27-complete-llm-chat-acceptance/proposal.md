## Why

当前项目已经具备独立 LLM 单轮对话能力，但 F1 整体仍未完成，现有行为还没有沉淀为一组可追踪、可验证的 OpenSpec 契约。本次先收敛 LLM 对话的真实边界和验收证据，避免在进入 Tender Agent 之前扩大工作范围。

## What Changes

- 固化 `POST /api/v1/llm/chat` 的单轮请求和响应行为。
- 固化空消息、超长消息、未配置服务、上游失败和空响应的错误行为。
- 固化前端成功、加载、失败提示和重试行为。
- 明确当前对话不保存历史、不接入知识库、不调用工具、不提供流式输出。
- 补齐后端契约测试、错误分支测试和现有前端验收证据。
- 不修改 F1 总体状态，不开始 Tender Agent、文件输入、业务 Prompt 或投标书骨架工作。

## Capabilities

### New Capabilities

- `llm-chat`: 独立 LLM 单轮对话的 HTTP、Application 和前端可观察行为契约。

### Modified Capabilities

- 无。当前 `openspec/specs/` 尚无已存在的正式能力规格。

## Impact

- 后端接口：`POST /api/v1/llm/chat` 及其请求、响应和错误映射。
- 后端模块：`app/modules/llm`、`app/interfaces/http`、`app/infrastructure/llm` 和 Composition Root 的现有边界验证。
- 前端模块：`frontend/src/features/chat` 的 API 调用、加载态、错误态和重试行为。
- 测试：补充 Application、HTTP、Infrastructure 和前端构建/人工验收证据。
- 阶段范围：F1 仍为进行中；Tender Agent 及后续文件输入能力不在本 Change 内。
- 参考基线：`agent.md`、`ARCHITECTURE.md`、`FRONTEND_ARCHITECTURE.md`、`docs/第三阶段- 后端F1工作进度.md` 和 `docs/第三阶段 - 前端改造工作.md`。
