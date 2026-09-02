## Why

最近的流式资源生命周期修复只覆盖了 `/chat/stream` 的准备阶段。普通 `/intent` 和确认接口仍在 FastAPI 异步路由中直接执行同步的目录、Embedding、结构化 LLM、RAG 或业务分发操作，慢请求会阻塞同一事件循环上的其他请求。

此外，流式请求在准备阶段断开时，受保护的 Worker 仍可能完成 Agent 待确认事实写入，但客户端已经收不到 `approval_required` 事件，导致短期待确认状态和持久化确认事件不一致且缺少可恢复入口。

## What Changes

- 为普通 `/intent` 识别增加异步 Worker 边界，确保同步候选检索、目录复核和结构化识别不运行在事件循环线程。
- 为非 Agent 确认分发增加异步 Worker 边界，确保 Chat、RAG、策略复核等同步目标执行不阻塞事件循环。
- 为流式 Agent 确认准备增加断连后的明确收口策略：客户端尚未收到批准事件时，不保留无法被客户端继续操作的短期待确认状态，并记录一致的取消终态。
- 将候选索引刷新锁细化到权限范围，避免一个权限范围的慢目录/Embedding 请求阻塞其他范围。
- 保持现有 HTTP 字段、响应结构、SSE 事件名称、权限校验和一次性提议消费语义。
- 增加阻塞替身、断连取消、状态收口和接口契约回归测试。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `risk-tiered-chat-interaction`：普通识别与确认接口的同步工作不得阻塞异步事件循环；流式准备取消时不得遗留客户端无法获知或继续操作的待确认状态。
- `dialogue-agent-gateway-integration`：Agent 确认准备被取消或客户端断连时，短期确认状态与 Conversation 事件必须进入一致的取消终态。
- `intent-candidate-retrieval`：候选索引刷新只串行化同一权限范围，不得让不同权限范围相互阻塞。

## Impact

- 影响 Interaction HTTP 路由、异步 Worker/Port、Composition Root 和 Agent 确认准备的状态收口。
- 不新增 HTTP 路径、请求字段、数据库表或迁移；可能新增一种内部 Conversation 取消事件，但不改变已有消息和调用数据模型。
- 仍使用现有同步 Provider 和数据库适配器，并通过短生命周期 Worker 执行；不新增外部依赖。
- 影响错误映射和状态流转，但保持现有公开错误码和 SSE 事件契约兼容。
- 影响候选索引的并发刷新策略，不改变索引结果或权限过滤规则。
