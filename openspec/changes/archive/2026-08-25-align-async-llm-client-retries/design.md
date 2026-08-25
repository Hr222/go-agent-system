## Context

`OpenAICompatibleClientFactory` 已为同步 Client 显式设置 `max_retries=0`，但只向 `ChatOpenAI` 注入了同步 Completion Client。`langchain-openai 0.3.35` 在缺少 `async_client` 时会创建自己的 `AsyncOpenAI`；该 Client 使用 SDK 默认重试次数，导致 `astream()` 的超时与重试行为不再由项目配置完全控制。

异步 Client 的创建与关闭属于 `infrastructure/llm` 和 Composition Root。Application、Domain、HTTP Schema 与前端不应感知 SDK 实例或重试参数；HTTP 依赖只负责结束请求范围内的资源生命周期。

## Goals / Non-Goals

**Goals:**

- 让 Factory 成为 ChatOpenAI 同步与异步 SDK Client 的唯一构造者。
- 保证同一 Provider 的同步和异步 Client 使用相同的端点、密钥、超时和 `max_retries=0`。
- 在全局和请求级 Container 生命周期中关闭 Factory 管理的异步 Client。
- 用替身测试证明 LangChain 获得已注入的异步 Client，而不是自行创建。

**Non-Goals:**

- 不在本 Change 实现应用级重试、重试分类、Retry-After、退避、限流、熔断或自动 Provider 切换。
- 不修改 LLM Port、流式 SSE 事件、Conversation 持久化、thinking 配置或 HTTP 请求/响应。
- 不迁移所有同步 Completion 调用为流式或 Async API。

## Decisions

### Factory 同时拥有同步与异步 Client

Factory 新增 `create_async_client()`，懒创建并缓存 `AsyncOpenAI`。它和既有 `create_client()` 都使用同一个 `LlmProviderConfig`，并显式传入 `timeout` 与 `max_retries=0`。这保留现有 Provider-neutral 构造入口，不把 GLM 或 DeepSeek 差异泄漏到 Adapter。

替代方案是只给 `ChatOpenAI(max_retries=0)` 传标量参数。该方式依赖 LangChain 内部继续正确转发参数，且无法明确控制由哪个 AsyncOpenAI 实例承担连接和关闭，因此不采用。

### 显式注入 ChatOpenAI 的两组 Completion Client

Factory 创建 `ChatOpenAI` 时同时注入 `client`/`root_client` 与 `async_client`/`root_async_client`，并显式保留 `max_retries=0`。LangChain 因此不会进入自行构造异步 SDK Client 的分支，`invoke()` 与 `astream()` 共享一致的运行参数。

Client Factory 仍只作为 Infrastructure Adapter 被 Composition Root 传入通用 Chat 与 Structured Adapter；不在 Application 或 HTTP 层创建 SDK Client。

### 以异步关闭覆盖请求级和全局 Container

Factory 提供 `aclose()` 来关闭同步与异步 Client。`ApplicationContainer` 暴露对应的异步清理方法；FastAPI 的全局 Container 在 lifespan 关闭时 await 它，请求级 Container 使用 yield dependency 在响应（包括 SSE）结束后 await 它。同步 `close()` 保留给只创建同步 Client 的已有调用点。

这比在 `close()` 中隐式创建后台 Task 更可靠，避免事件循环结束时未等待的协程。请求依赖清理不改变 Route、Schema 或业务调用顺序。

## Risks / Trade-offs

- [第三方 SDK 的关闭接口变动] → 锁定当前依赖版本的替身测试，调用公开 `AsyncOpenAI.close()`；升级依赖时需要重跑该测试。
- [请求级清理影响流式响应生命周期] → 仅在 Generator/SSE 完成或关闭后执行，使用已有流关闭测试和 HTTP 回归测试确认。
- [零 SDK 重试使短暂上游失败更快暴露] → 这是受控、可观测的行为；未来应用级重试会单独拥有预算和错误分类，避免叠加重试。
- [非流式 Adapter 仍使用同步 Client] → 保持现有接口和性能特征，本 Change 只消除流式路径的隐式 SDK 差异。

## Migration Plan

1. 部署无需新增环境变量、数据库迁移或前端更新。
2. 重启后，Factory 仅在实际需要流式 Chat 时创建异步 Client，并使用现有 Provider 配置。
3. 通过最小流式 Chat 验证资源包 Profile 正常完成；如需回滚，恢复 Factory 只注入同步 Client 的版本即可，不影响已持久化会话。

## Open Questions

无阻塞问题。应用级重试策略将在该基础完成后单独确定。
