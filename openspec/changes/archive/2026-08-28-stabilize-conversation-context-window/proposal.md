## Why

当前普通流式 Chat 在每轮写入 user Message 后，会从第一页开始读取整个 Conversation 历史，再交给上下文构建器裁剪。长会话会造成不必要的数据库扫描、首字节延迟和异步请求路径阻塞。现有架构已经通过进程共享的 Conversation 轮次租约保证同一会话完整轮次串行，本 Change 需要在这个边界内补齐有界读取和同步持久化的异步执行方式。

上下文预算属于 Conversation Context Builder 的职责。本 Change 只增加“租约内按本轮 user sequence 截止的最近窗口”，不把 sequence 快照当成新的并发协调机制，也不重新定义同一会话的轮次顺序。

## What Changes

- 新增面向上下文构建的有界“最近消息快照”读取能力：按本轮 user Message 的 `sequence` 截止，只读取能够参与当前上下文窗口的最近消息，不再扫描完整历史。
- 普通流式 Chat 在既有 Conversation 轮次租约内，于 user Message 写入后固定本轮上下文读取边界；读取能力排除 sequence 更晚的消息。
- 保持同一 Conversation 由既有共享租约完整串行化，保持不同 Conversation 可以并行；sequence 边界是数据库读取约束，不替代租约。
- 将同步 Conversation 持久化访问放在流式 Dialogue 的明确异步执行边界内，避免完整历史读取或消息写入阻塞事件循环。
- 保留现有 `ContextPolicy`、`ContextBudget`、成本计量器、消息角色映射和 user/assistant 持久化失败语义；不另建独立 token 预算体系。
- 增加长历史读取量、并发快照、当前输入唯一性、事件循环不阻塞和失败回归测试，并验证查询使用会话消息顺序索引。

## Capabilities

### New Capabilities

- `conversation-context-window`: 为上下文构建提供按顺序边界读取的最近消息窗口，并定义读取范围、窗口上限和与既有轮次租约的协同语义。

### Modified Capabilities

- `streaming-chat-multiturn-context`: 普通流式 Chat 在既有轮次租约内使用本轮 user `sequence` 截止的有界上下文窗口，并保持同会话轮次串行。

## Impact

- 影响 `app/platform/conversation` 的读取端口与应用契约、`app/infrastructure/persistence/repositories/conversation_history_read_repository.py` 的查询实现，以及 `app/platform/dialogue/application/streaming_conversation.py` 的上下文装载边界。
- 影响 Conversation 和 Dialogue 的 Composition Root 依赖组装，以及相关单元、PostgreSQL 集成和 HTTP/SSE 回归测试；普通 Chat 继续注入与 Agent 路径相同的进程共享轮次租约。
- 不改变 HTTP 请求字段、SSE 事件外形、Provider 协议或 Conversation/Message 数据模型；不新增表、摘要检查点、压缩 Worker、Redis 或跨会话记忆。
- 不改变 Agent invocation/continuation 的上下文链路，也不改变现有上下文预算数值和字符成本计量的兼容行为。
- 需要关注数据库访问执行方式和连接生命周期；验证必须覆盖真实 PostgreSQL 查询、既有租约下的同会话等待与流式取消后的资源释放。
