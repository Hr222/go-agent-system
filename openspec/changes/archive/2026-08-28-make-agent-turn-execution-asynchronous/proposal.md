## Why

已确认的对话 Agent 虽然已接入普通 Chat 使用的会话锁，但获得锁后仍在 ASGI 事件循环中同步执行 Agent 与 continuation LLM。一个长时间 Agent 轮次会阻塞同一进程中其他 Conversation 的请求，未兑现既有会话轮次串行化规格中的跨会话并行承诺；确认失败后还可能留下短期 pending invocation 状态。

需要让已确认 Agent 轮次遵循与普通流式 Chat 一致的 Conversation turn 模型：同会话完整事实链互斥，不同会话能够推进，且所有一次性确认状态在终态后收口。

## What Changes

- 在 Dialogue Application 增加 Conversation turn 异步执行边界；Interaction/Gateway 继续负责 proposal 消费、目录/权限/输入复核和受控分发批准，并通过该边界执行已确认 Agent 轮次而不直接管理租约。
- 在持有共享 `ConversationTurnCoordinator` 租约期间，通过独立 session 的 worker 执行同步 Agent invocation 与 continuation；请求级 SQLAlchemy Session 不得跨线程传递。
- 保持 `confirm` 等待租约时可取消且不消费 proposal/pending；获得租约后的所有终态都收口对应 pending invocation，避免不可重试的残留状态。
- 补充真实 Conversation 写入、Agent 结果、continuation assistant 与普通 Chat 的时序测试，证明同会话不交错且不同 Conversation 可在长 Agent 轮次期间推进。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `conversation-turn-serialization`: 将已确认对话 Agent 纳入完整的进程内 Conversation turn 语义，并要求其长时间同步工作不阻塞其他 Conversation 的轮次开始。

## Impact

- 影响 `app/platform/dialogue` 的 Agent turn 编排、`app/platform/interaction` 的确认入口、Composition Root 的 session factory 与执行器组装，以及相关测试替身。
- HTTP 确认路径、响应字段、SSE 外形、Conversation/Message/Event 数据模型与 Agent 业务决策保持不变；不新增数据库迁移、Redis、队列、后台 Worker 或跨进程协调。
- 同步 SQLAlchemy 仍可保留为基础设施实现，但每个 worker 操作必须创建、提交或回滚并关闭自己的 Session；Provider 与 Agent 执行期间不得占用请求级数据库连接。
