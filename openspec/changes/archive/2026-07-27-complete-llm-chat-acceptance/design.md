## Context

当前项目已完成独立 LLM 单轮对话的技术底座和前端调用入口，但 F1 整体仍在进行中。后端通过 `POST /api/v1/llm/chat` 暴露单轮调用，Application 依赖 `ChatLlmPort`，LangChain/GLM 适配器位于 Infrastructure，具体实现由 Composition Root 组装。前端通过 Axios 和 React Query 调用接口，并提供加载、错误和重试状态。

本 Change 的目的不是扩展对话能力，而是把已有行为固化为可验证契约，并补齐 HTTP 层错误分支的测试证据。

## Goals / Non-Goals

**Goals:**

- 固化单轮 HTTP 对话请求、响应和错误映射。
- 覆盖输入校验、空响应、未配置服务和上游失败。
- 保持 Application 只依赖 `ChatLlmPort`，不泄漏具体 SDK。
- 通过现有前端实现、构建和人工验收确认加载、回答、失败和重试行为。

**Non-Goals:**

- 不引入会话存储、上下文记忆、流式输出或工具调用。
- 不引入新的前端测试框架或改变前端状态管理方式。
- 不实现 Tender Agent、文件输入、业务 Prompt、LangGraph 或多 Agent 协作。
- 不修改数据库、外部 API 契约或生产部署配置。

## Decisions

### 1. 保持现有 HTTP -> Application -> Port -> Infrastructure 链路

继续由 HTTP 路由调用 `ChatApplication`，由 Application 依赖 `ChatLlmPort`，由 Infrastructure 负责 LangChain/GLM 适配。相比在路由中直接调用模型 SDK，这样可以保持现有架构边界，并让 Fake 完整替换真实模型。

### 2. 保持当前错误映射

- 参数校验失败由 HTTP Schema 返回 `422`。
- Application 的业务输入错误返回 `400`。
- 服务配置缺失返回 `503`。
- 上游模型失败或模型返回空响应返回 `502`。

错误消息继续使用现有异常文本，不在本 Change 中设计新的统一错误协议。

### 3. 前端采用现有构建和人工验收

当前 `frontend/package.json` 没有 Vitest 或 React Testing Library。为避免为了验收单轮对话引入新的测试基础设施，本 Change 使用现有 TypeScript 构建、源码行为检查和浏览器人工验收确认前端行为。后续若项目需要组件自动化测试，再单独创建 Change。

### 4. 不修改当前功能边界

页面继续明确展示“单轮模型调用验证”和“当前不保存会话历史”。不通过规格或测试暗示已经具备完整 Chat、Agent 或 RAG 能力。

## Risks / Trade-offs

- [Risk] 真实模型服务的响应和耗时具有不确定性。→ 自动化测试全部使用 Fake，真实服务只用于人工联调。
- [Risk] 前端没有现成组件测试框架。→ 本 Change 采用构建检查和固定人工验收清单，不新增测试依赖。
- [Risk] F1 进度文档可能被误读为 F1 已完成。→ proposal、spec 和验收结论明确只完成 LLM 单轮对话切片，不改变 F1 总体状态。

## Migration Plan

无需数据库迁移、配置迁移或接口版本迁移。完成测试和人工验收后，将本 Change 归档，并把 `llm-chat` 正式规格保留在 `openspec/specs/llm-chat/spec.md`。
