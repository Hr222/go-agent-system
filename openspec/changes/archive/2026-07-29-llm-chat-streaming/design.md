## Context

当前 `POST /api/v1/llm/chat` 通过同步调用等待模型生成完整回答，后端一次性返回 JSON，前端也只能在请求完成后展示回答。

本次变更需要增加端到端流式能力，同时保持现有 JSON 接口、请求格式和响应格式不变。当前系统不涉及会话历史、持久化、RAG 或工具调用。

## Goals / Non-Goals

**Goals:**

- 新增 `POST /api/v1/llm/chat/stream` 流式接口。
- 保留 `POST /api/v1/llm/chat` 的现有行为。
- 后端支持从 Application、Port、Provider Adapter 到 HTTP 的异步流式传递。
- 前端能够增量展示模型输出。
- 支持取消、超时、上游失败和客户端断开。
- 支持首 Token 延迟、流持续时间、失败原因和活跃连接数等指标。
- 确保流式请求不会泄漏 Provider 连接和并发配额。

**Non-Goals:**

- 不引入会话历史和上下文记忆。
- 不修改数据库，不保存流式回答。
- 不引入 RAG、工具调用、Agent 编排或 LangGraph。
- 不修改旧 JSON 接口的请求和响应契约。
- 不实现自动重试，重试必须由用户显式触发。

## Decisions

### 1. 使用独立的流式 HTTP 入口

新增：

```text
POST /api/v1/llm/chat/stream
```

保留：

```text
POST /api/v1/llm/chat
```

旧接口继续使用同步 JSON 响应，流式接口使用 `text/event-stream` 响应。客户端不通过内容协商决定模式，避免旧客户端因为请求头变化而产生行为差异。

### 2. 使用 SSE 作为服务端传输格式

流式接口采用 Server-Sent Events（SSE）。

事件分为：

- `meta`：请求开始、模型和 Prompt 版本信息。
- `delta`：模型生成的增量文本。
- `complete`：正常结束、Token 用量和请求标识。
- `error`：首段内容输出后发生的可观察错误。
- `heartbeat`：保持长连接，避免代理将连接判断为空闲。

首个事件发送前，如果输入校验、配置检查或 Provider 建连失败，接口仍返回普通 HTTP 错误状态。首个事件发送后，不能再修改 HTTP 状态，只能发送脱敏的 `error` 事件并关闭连接。

### 3. 保持同步 Port 和 Application 独立

现有 `ChatLlmPort.invoke()` 和 `ChatApplication.execute()` 保持不变，用于旧 JSON 接口。

新增独立的流式 Port 和 Application 契约：

```text
流式 HTTP Route
    -> Streaming Chat Application
    -> Streaming Chat LLM Port
    -> LangChain GLM Adapter
    -> Provider 异步流
```

流式 Application 负责输入清理、Prompt 组装、生命周期和领域错误转换，不暴露 LangChain 或 Provider 类型。

Provider Adapter 可以同时实现同步和异步两个 Port，但两个 HTTP 入口的运行路径相互独立。

### 4. 使用 Provider 原生异步流

流式 Adapter 使用 Provider 或 LangChain 提供的原生异步流能力，不在异步 HTTP 路由中迭代同步 SDK，也不通过线程阻塞模拟流式输出。

Adapter 将 Provider 返回内容转换为项目内部的流式片段，并在流结束时尽力提取模型和 Token 使用信息。Provider 不返回 Token 用量时，相关字段保持为空。

### 5. 前端增加专用流式客户端

普通 JSON 请求继续通过现有 Axios Client。

流式请求在 `services/http` 下增加专用流式客户端，使用浏览器的 `ReadableStream` 和 `AbortSignal` 读取 SSE 分块。该客户端不由页面组件直接调用。

原因是：

- `EventSource` 不支持当前所需的带 JSON Body 的 `POST`。
- 浏览器 Axios 适合普通响应，但不提供稳定的异步流迭代接口。
- `ReadableStream` 能够支持分块读取和取消传播。

前端分层保持：

```text
ChatPage
    -> useChatStream
    -> chatApi
    -> streamingHttpClient
    -> /api/v1/llm/chat/stream
```

### 6. 前端使用独立的流状态机

流式请求状态包含：

```text
idle
  -> connecting
  -> streaming
  -> completed

streaming
  -> cancelled
  -> failed
```

发送请求后，页面立即创建用户消息和空的助手消息。收到 `delta` 后追加到助手消息，收到 `complete` 后补充模型、耗时和 Token 信息。

用户取消时：

- 停止前端读取。
- 保留已经收到的文本。
- 将助手消息标记为“已取消”。
- 不显示为服务端错误。
- 释放当前 `AbortController`。

页面通过批量更新或动画帧合并增量内容，避免每个 Token 都触发一次完整渲染。

### 7. 取消、超时和并发治理

后端需要区分：

- Provider 建连超时。
- 首 Token 超时。
- 流式空闲超时。
- 总请求超时。
- 客户端主动取消。
- 并发容量不足。

客户端断开后，HTTP 生成器必须停止消费 Provider 流，并释放当前请求占用的并发配额。

流式请求不自动重试，避免同一次用户操作产生重复模型调用和重复计费。

### 8. Provider Client 使用应用生命周期管理

当前 `ApplicationContainer` 由请求创建，Factory 缓存仅在单个请求内有效。

本次设计将 Provider Client 和模型 Adapter 的生命周期提升到应用级 Composition Root 管理范围，并在应用关闭时释放可关闭资源。请求级 Application 只保存请求状态，不保存跨请求的 Prompt、消息内容或用户数据。

### 9. 生产代理和响应头

流式响应至少设置：

```text
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

生产代理需要关闭响应缓冲，配置长连接、读取超时、发送超时和心跳策略。心跳间隔必须小于代理的最短空闲超时时间。

### 10. 日志、指标和敏感信息

日志只记录：

- 请求标识。
- 模型标识。
- Prompt 版本。
- 请求阶段。
- 首 Token 延迟。
- 总耗时。
- 事件数量。
- 结束原因。
- 错误码。

不得记录 Prompt、增量文本、鉴权头、API Key 或未经审查的 Provider 异常原文。

至少增加以下指标：

- 首 Token 延迟。
- 流式请求总时长。
- 完成、取消、超时和失败次数。
- 活跃流数量。
- 并发拒绝数量。
- Token 使用量。

指标标签不得包含用户输入。

## Risks / Trade-offs

- SSE 只支持服务端向客户端推送，未来如果需要双向交互，需要重新设计协议。
- 不同 Provider 的 Token 用量可能只能在流结束时获得，甚至无法获得，因此用量字段允许为空。
- 代理配置错误可能导致内容已经在后端生成，但浏览器长时间收不到数据；通过代理验收和心跳降低风险。
- 客户端断开不一定能立即中断 Provider 请求；通过取消传播、超时和资源释放测试验证。
- 前端流式客户端需要使用 `ReadableStream`，这是对现有 Axios 统一请求约束的受控例外，并集中在 HTTP 基础设施层。
- 应用级 Provider Client 生命周期调整可能影响现有同步调用；必须保留旧 JSON 接口回归测试。

## Migration Plan

1. 增加流式 Port、Application 和 Provider Adapter，同时保持现有同步 Port 不变。
2. 增加 SSE 路由和后端事件契约测试。
3. 增加前端流式 HTTP 客户端、Hook 和增量消息状态。
4. 增加取消、超时、代理缓冲和并发限制测试。
5. 先通过新流式入口进行验证，旧客户端继续使用原 JSON 入口。
6. 若流式能力出现问题，前端停止调用新入口即可回退到旧 JSON 接口。
7. 本次不需要数据库迁移或数据回滚。

## Open Questions

- 当前 GLM Provider 是否能在异步流结束事件中稳定返回完整 Token 用量？
- 生产环境允许的最大并发流数量和单请求总时长是多少？
- 反向代理使用哪套配置，具体空闲超时和缓冲参数需要在部署环境中确认。
- 是否需要通过配置开关控制流式入口的启用范围？
