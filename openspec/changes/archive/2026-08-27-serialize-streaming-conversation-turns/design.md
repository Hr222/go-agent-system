## Context

当前 `StreamingConversationRuntime.execute()` 会创建或解析 Conversation 后立即写入 user Message、读取历史并启动流式 LLM。同一 Conversation 的两个普通请求并发到达时，后到请求可在前一轮结束前写入 user，造成历史上下文交错。

本 Change 只解决单一后端进程中的会话互斥。现有 `ApplicationContainer` 由 HTTP 请求创建，因而会话锁不能作为请求级对象；它必须由 Composition/HTTP 依赖提供为进程共享对象。Conversation Repository 继续使用同步 SQLAlchemy，Provider 治理器继续负责全局 Provider 限流和并发，两者不在本 Change 改造。

## Goals / Non-Goals

**Goals:**

- 对同一 `conversation_id` 的普通 `chat.general` 流式轮次建立进程内互斥。
- 在持有会话锁后才写入 user、读取上下文、调用 LLM 和写入完整 assistant。
- 在成功、异常、超时、取消和流被关闭时释放锁，避免后续请求永久等待。
- 保持不同 Conversation 的普通 Chat 可并行，保持既有 HTTP 与 SSE 事件外形。
- 在没有持有者和等待者时清理对应锁状态，避免长期运行进程无限增长。

**Non-Goals:**

- 不提供严格 FIFO、队列编号、排队位置或显式 `queued` SSE 事件。
- 不协调多个 Uvicorn worker、多个进程或多个服务实例。
- 不创建持久化 turn、租约、幂等键、后台 Worker、Redis 或数据库迁移。
- 不改变 Agent invocation、Agent continuation、Conversation 历史窗口、Token 预算或同步持久化的异步执行边界。
- 不改变浏览器当前页面的发送限制或 SSE 请求字段。

## Decisions

### 1. 用进程共享的会话锁注册表，而不是显式 FIFO 队列

新增一个不依赖 HTTP、持久化或 LLM SDK 的 Application 级协调器。它按 `conversation_id` 管理 `asyncio.Lock`，调用方获得一个可释放的会话锁租约。

协调器自身以独立的异步保护管理注册表与引用计数：等待者在等待锁前增加引用；等待取消和已持有锁的结束路径都减少引用；最后一个引用离开后删除该 Conversation 的锁状态。这样不同 Conversation 不共享一把全局锁，且空会话锁不会永久累积。

选择锁而不是 `asyncio.Queue`，因为 V1 的不变量只有“同一 Conversation 不并发执行”。不需要任务对象、队首、位置、持久化状态或顺序对外承诺。`asyncio.Lock` 当前运行时的公平性不作为业务契约。

### 2. 先解析 Conversation，再获得锁，最后写 user

Runtime 先按既有主体访问语义创建或解析 Conversation；此阶段不写 Message。得到稳定的 Conversation ID 后取得会话锁，并在锁持有期间执行现有的 user 写入、历史读取、Context Builder、Provider 流和 assistant 写入。

已有 Conversation 在等待锁期间被删除或失去可用性时，后续 user 写入或读取沿用现有受控失败语义。新 Conversation 可以在取得锁前以空 Conversation 形式存在；该行为不新增 Message，且不改变既有创建契约。

此顺序避免 B 在等待 A 时提前写入 user，同时不把主体访问校验放在未受控的消息写入之后。

### 3. Runtime 持有可显式关闭的锁租约直到流生命周期结束

`execute()` 在取得锁并完成流前准备后返回一个包装后的异步迭代器。包装器负责：

1. 转发既有 `StreamingConversationEvent`；
2. 在正常耗尽、上游异常、消费者取消或调用方 `aclose()` 时关闭底层流；
3. 无论底层流是否已经开始迭代，都恰好一次释放会话锁租约。

不能只把 `async with lock` 放在尚未开始的异步生成器体内：若 Interaction 在首个事件前关闭该生成器，生成器体的 `finally` 不一定有机会运行，锁可能泄漏。显式关闭包装器为当前 `InteractionChatStreamApplication` 的 `_close_stream()` 路径提供确定释放点。

锁等待在 `execute()` 内完成，现有 Interaction 对“Provider 首个 activity”的超时只在 Runtime 已返回可消费流后开始计算。因此等待前一轮不会被误映射为 `UPSTREAM_TIMEOUT`；V1 也不额外发送排队进度。

### 4. 只把普通 Chat 接入锁边界

Composition Root 创建并持有一份进程共享协调器，将它注入每个请求级 `StreamingConversationRuntime`。`InteractionChatStreamApplication`、HTTP 路由、SSE 序列化和 Provider 适配器不持有或直接操作 Conversation 锁。

只在 `chat.general` 分支使用的 Streaming Conversation Runtime 接入此依赖。Agent continuation 仍维持当前独立链路，后续以 Tender Agent 测试另立 Change 决定其共享会话边界。

## Risks / Trade-offs

- [进程重启丢失等待状态] -> V1 明确不恢复等待请求；连接中断后用户可重新发起请求，后续高可用需求再引入持久化 turn。
- [多 worker 或多实例绕过互斥] -> 规格明确仅限单个后端进程；部署扩展前必须建立共享协调 Change。
- [锁等待期间没有新的 SSE 事件] -> 不改现有协议；HTTP/代理的连接超时仍是 V1 的产品限制，后续可独立增加可恢复的排队状态。
- [消费者在流尚未开始前关闭] -> 使用显式可关闭包装器和一次性释放租约测试，避免锁泄漏。
- [锁注册表无限增长] -> 使用等待者和持有者引用计数，在最后一个引用离开时删除状态。
- [同步数据库操作阻塞事件循环] -> 不在本 Change 扩张到 AsyncSession；后续异步持久化 Change 处理。

## Migration Plan

1. 增加进程内会话锁协调器及其单元测试。
2. 在 Composition/HTTP 组装中创建并注入同一协调器。
3. 重构普通 Streaming Conversation Runtime，使其在 user 写入前取得租约，并以释放包装器覆盖完整流生命周期。
4. 补充 Runtime、Interaction 与架构边界回归测试，验证同会话互斥、跨会话并行、取消、失败和清理。
5. 运行严格 OpenSpec 校验及相关测试。若回滚，移除协调器注入并恢复原 Runtime 调用顺序；本 Change 无数据迁移。

## Open Questions

无。V1 的部署范围、非 FIFO 语义、普通 Chat 范围和失败事实语义均已确定。
