## Why

普通流式 Chat 会在调用模型前写入本轮 user Message。同一 Conversation 的并发请求因此可能让后到请求提前进入历史，导致前一轮上下文被污染，或让后一轮在前一轮 assistant 尚未完成时开始生成。

V1 先在单个后端进程内阻止同一 Conversation 的普通 Chat 并发执行，以恢复逐轮演化的会话事实；不提前建设持久化任务调度系统。

## What Changes

- 新增进程共享的 Conversation 轮次互斥能力，以 `conversation_id` 隔离普通流式 Chat 的执行。
- 普通 `chat.general` 必须先获得对应会话锁，随后才写入本轮 user Message、构建上下文、调用流式 LLM，并在完成、失败或取消时释放锁。
- 等待锁的请求不得写入 user 或 assistant Message；已获得锁的请求沿用既有 user 保留、完整 assistant 成功后写入的失败语义。
- 保持不同 Conversation 的普通 Chat 可并行，保持既有 HTTP 请求和 SSE `meta`、`delta`、`complete`、`error` 外形。
- 增加同会话并发、不同会话并行、取消、失败和锁注册表回收的回归验证。

## Capabilities

### New Capabilities

- `conversation-turn-serialization`: 定义单个后端进程内，普通流式 Chat 按 Conversation 互斥执行、写入时序和释放语义。

### Modified Capabilities

无。

## Impact

- 影响 `app/platform/dialogue/application/streaming_conversation.py` 的普通流式轮次边界，以及 `app/composition` 与 HTTP 依赖中的进程级对象装配。
- 影响 Interaction 流在等待会话锁时的超时、取消和心跳处理；不增加请求字段、持久化表、公开 SSE 事件或 Provider 协议。
- 新增进程内 `asyncio.Lock` 注册表及其测试替身；不引入 `asyncio.Queue`、Redis、数据库 turn 表、后台 Worker、跨进程协调、严格 FIFO 或 Agent continuation。
- 同步 SQLAlchemy 在异步流路径中的执行边界、最近历史窗口优化和 Token 预算演进继续由独立 Change 处理。
