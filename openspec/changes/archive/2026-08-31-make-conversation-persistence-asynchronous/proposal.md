## Why

普通流式多轮对话运行在异步 HTTP/SSE 路径中，但当前 Conversation 的 SQLAlchemy Repository 仍是同步调用。若同步的会话访问、消息写入或历史读取直接发生在事件循环中，数据库延迟会阻塞其他会话的流式请求；同时，请求级 Session 不应跨越整个模型生成过程。

本 Change 为普通流式 Dialogue 建立明确的异步持久化执行边界，在不改变已有会话事实、失败语义和 HTTP/SSE 契约的前提下消除这类阻塞。

## What Changes

- 为普通流式 Dialogue 增加异步 Conversation 持久化 Port，覆盖会话创建/解析、user Message 写入、上下文最近消息读取和 assistant Message 写入。
- 通过独立的同步 Worker 复用现有 Conversation Application 与 Repository；每次短持久化操作创建独立 Session，并在提交或回滚后立即关闭。
- 确保持久化 Session 不跨越 Provider 流式生成，assistant Message 只有在完整回答形成后才通过新的短操作写入。
- 处理异步请求取消、数据库异常和 Worker 关闭，避免已启动的同步事务、Session 或 Conversation 轮次租约提前遗留。
- 调整 Composition Root 和流式 Dialogue 组装，使请求级 Session 不作为普通流式持久化依赖传入运行时。
- 增加事件循环不阻塞、Session 生命周期、取消清理、PostgreSQL 事实一致性和既有流式失败语义测试。
- 不改变请求字段、SSE 事件、Conversation/Message 数据模型、sequence 规则、主体访问校验或上下文预算。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `streaming-chat-multiturn-context`：为已有普通流式多轮对话增加异步持久化执行、短 Session 生命周期和取消收口要求；不改变其上下文内容和消息事实语义。

## Impact

- 影响 `app/platform/dialogue` 的异步 Port、流式 Runtime 和持久化执行边界，以及 `app/composition` 的 Session 工厂和依赖组装。
- 影响普通流式 Dialogue 的单元测试、PostgreSQL 集成测试和架构边界测试；现有同步 Conversation HTTP 接口继续使用同步应用服务。
- 不新增 HTTP/SSE 契约，不新增数据库表、字段、索引或迁移，不引入 Redis、消息队列或新的外部依赖。
- 已确认 Agent 的私有 Worker、Interaction 授权控制面和 Agent continuation 不在本 Change 内；它们继续遵循各自已生效的轮次与资源边界。
