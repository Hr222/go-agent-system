## Why

历史的流式多轮对话 Change 已将 Conversation 持久化迁移到独立 Worker，但统一交互入口仍在请求级 `ApplicationContainer` 中执行候选索引、目录查询、Embedding 和结构化识别。自然追问回退上线后该路径成为普通 Chat 的必经路径，导致每个请求重复构建索引、同步准备阻塞事件循环，并让请求级数据库 Session 横跨整个 SSE；持久化门面的重复取消路径还可能在 Worker 收口前释放轮次租约。

## What Changes

- 将能力候选检索服务及其按权限范围的索引缓存提升到进程级生命周期，避免每次交互请求重新生成全量目录 Embedding。
- 将 `/api/v1/interaction/chat/stream` 的同步准备阶段移出异步事件循环，并在 SSE 流开始前释放准备阶段使用的请求级数据库资源。
- 确保普通流式 Chat 的 Conversation 持久化继续使用短生命周期独立 Session，不让请求级 Session 进入流式运行时。
- 修正持久化 Worker 的重复取消处理：在 Worker、事务和 Session 完成收口前不得释放 Conversation 轮次租约，同时保留请求取消语义。
- 增加并发、索引复用、Session 生命周期、重复取消和 PostgreSQL 事实一致性测试。
- 不改变 HTTP 请求字段、SSE 事件、权限校验、Conversation/Message 数据模型、sequence 规则或模型上下文内容。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `intent-candidate-retrieval`: 候选检索实例和按权限范围的索引缓存必须具有进程级生命周期，普通请求查询不得重复执行全量目录 Embedding；权限范围之间仍必须隔离。
- `risk-tiered-chat-interaction`: 统一交互流的同步准备不得阻塞异步事件循环，准备阶段使用的请求级数据库资源不得跨越 SSE 模型流生命周期。
- `streaming-chat-multiturn-context`: 重复取消时必须等待已启动的持久化 Worker 完成事务和 Session 收口后再释放轮次租约。

## Impact

- 影响 `app/interfaces/http/routes/interaction.py`、HTTP 依赖装配、`ApplicationContainer`、Interaction Gateway/Chat Stream 以及候选检索的 Composition Root 生命周期。
- 影响 `app/platform/dialogue/application/streaming_persistence.py` 的取消收口逻辑；不改变 Conversation 同步 Application 和数据库模型。
- 影响普通流式 Chat 的线程池、数据库连接池和 Embedding/结构化 LLM 调用调度，但不新增外部依赖、HTTP 接口或数据库迁移。
- 需要补充异步并发和真实 PostgreSQL 验证；多进程/多实例候选缓存和会话协调仍不在本 Change 范围内。
