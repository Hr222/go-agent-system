## Context

普通 `chat.general` 流式轮次已经通过 `ConversationTurnCoordinator` 在单个后端进程内按 `conversation_id` 串行化。当前对话 Agent 的确认路径却在 `InteractionChatStreamApplication.confirm_agent()` 中同步执行：它消费确认 proposal 和 pending invocation，调用 Tender Agent，持久化 `agent_result` 或 `agent_error`，再由 `DialogueAgentContinuationService` 读取历史、调用 LLM 并写入 assistant Message。

这条路径没有进入既有会话锁。同一 Conversation 的普通 Chat 可以在 Agent 执行或 continuation 期间写入 Message、读取上下文并启动 LLM，导致 Agent continuation 看到的历史快照和最终事实顺序不确定。待确认 proposal 尚未执行 Agent，不应占用会话锁。

本 Change 复用已存在的 Dialogue Application 协调器，不引入新的持久化状态、外部基础设施或跨进程协调。`InteractionChatStreamApplication` 仍是自然语言入口的应用编排层；HTTP 路由只负责 await 该应用服务并保持既有响应映射。Tender Agent 继续经既有受控 Dispatcher 调用，Conversation 的事实读写仍由现有 Application Capability 和 Ports 完成。

## Goals / Non-Goals

**Goals:**

- 将同一 Conversation 中已确认的对话 Agent 完整轮次接入与普通流式 Chat 相同的进程内租约。
- 从消费一次性确认状态开始，持续保护 Agent 执行、结果事实持久化、continuation 上下文构建、LLM 调用和 assistant Message 写入，直至该路径返回。
- 使锁等待可取消；取消的确认请求不消费 proposal 或 pending invocation，不启动 Agent，也不写 Conversation 事实。
- 保持不同 Conversation 并行，保持 proposal 确认协议、HTTP 响应字段、Agent 结果和 continuation 失败语义不变。
- 用受控 Tender Agent 替身验证与普通 Chat 的同会话时序、失败、取消和跨会话隔离。

**Non-Goals:**

- 不改变等待用户确认 proposal 的状态、TTL、展示或确认文案。
- 不提供严格 FIFO、排队位置、排队事件或跨进程/跨实例互斥。
- 不将 confirmation `cancel` 动作纳入本 Change 的锁范围；其不执行 Agent，继续沿用现有取消事实路径。
- 不新增数据库表、事务、幂等键、后台 Worker、消息队列、Redis 或异步 Provider/数据库适配器。
- 不修改 Tender Agent 的业务决策、普通 Chat 的 SSE 协议、Conversation 历史窗口、上下文预算或 API schema。

## Decisions

### 1. 复用进程共享的 `ConversationTurnCoordinator`

Composition Root 保持一份进程共享的协调器，并将同一实例同时注入请求级 `StreamingConversationRuntime` 与 `InteractionChatStreamApplication`。协调器仍属于 Dialogue Application 边界，不依赖 HTTP、数据库、ORM 或 LLM SDK；Composition 只组装对象图。

复用同一注册表而非为 Agent 单独创建锁，是因为互斥不变量以 Conversation 轮次为单位，而非调用类型：普通 Chat 和已确认 Agent 都会写入同一有序会话历史。单独锁会允许两条路径交错，无法解决本 Change 的根因。全局锁会无谓阻塞不同 Conversation，因此不采用。

### 2. `confirm` 先只读定位会话，再等待租约并消费一次性状态

`confirm_agent()` 改为异步应用入口。对 `confirm` 动作，它先从 `InMemoryPendingAgentInvocationStore` 读取主体绑定的 pending invocation，仅用于取得已验证的 `conversation_id`，不删除条目。随后 await 对应会话租约；只有取得锁后才调用 `confirm_dialogue_agent()` 消费 proposal，并消费 pending invocation。

锁等待期间发生 `CancelledError` 时，`ConversationTurnCoordinator.acquire()` 负责回收等待引用；应用入口不调用 proposal 或 pending 的 consume，也不调用 Agent 或 continuation。因此客户端断开不会改变确认状态，用户可使用同一 proposal 重试确认。

在取得锁后，proposal 或 pending 可能已被其他请求处理或过期。此时沿用既有受控 `rejected`/`DIALOGUE_AGENT_CONTEXT_UNAVAILABLE` 响应，不执行 Agent。一次性 proposal 的消费继续阻止重复确认。`cancel` 不等待租约，维持原有消费 proposal 与取消 invocation 事实的时序。

### 3. 租约覆盖同步 Agent 执行与 continuation 的完整事实链

取得租约后，应用入口在 `try/finally` 中执行既有确认编排：受控 Agent dispatch、`agent_result` 或 `agent_error` 事实持久化、continuation 历史读取与上下文构建、LLM 调用及 assistant Message 写入。无论 Agent 拒绝、失败、continuation 不可用、Conversation Access 错误还是调用异常，`finally` 都恰好一次释放租约。

现有 Agent 与 continuation 服务保持同步实现；异步入口只用于可取消地等待 `asyncio` 租约，不改变 Provider 或 SQLAlchemy 的执行模型。HTTP 路由改为 `await application.confirm_agent(command)`，响应仍使用相同的 `GatewayResult` 到 schema 的映射。应用层不暴露锁、租约或排队状态给接口层和客户端。

### 4. 以受控时序测试证明共享边界

在 Interaction 测试中使用可阻塞的 Tender Agent/continuation 替身和现有普通 Chat 流替身。先启动同一 Conversation 的确认 Agent，使其停留在受控执行点；随后启动普通 Chat，断言其在 Agent 的结果与 assistant 事实完整写入前不追加 user Message、不构建上下文且不调用 LLM。释放 Agent 后，断言普通 Chat 继续且历史包含 Agent 的终态。

同一组测试还覆盖：Agent 失败后释放锁、等待租约的确认任务取消后可由同一 proposal 重试、以及不同 Conversation 的普通 Chat 或确认 Agent 不相互等待。现有协调器单元测试继续验证租约的取消和引用回收；架构测试确认协调器仍只由 Composition 注入，而 continuation 服务本身不直接持有协调器。

## Risks / Trade-offs

- [确认请求在同会话长轮次后等待] -> 这是确保事实顺序的必要代价；不新增超时、排队事件或 FIFO 承诺，客户端沿用现有请求生命周期。
- [锁等待后 proposal 或 pending 已失效] -> 取得锁后重新执行既有一次性消费与可用性检查，返回受控拒绝结果且不启动 Agent。
- [取消语义被路由异常处理吞没] -> 保持 `CancelledError` 向 ASGI 任务传播，不把它转换为业务失败；测试确认取消前未发生 consume。
- [同步 Agent 或 Provider 工作占用事件循环] -> 本 Change 不扩大执行模型；继续复用已有同步边界，异步化或 Worker 化另立 Change。
- [多 worker 或多实例绕过互斥] -> 明确仅保证单进程；部署扩展时再设计共享协调机制。
- [共享协调器回归普通 Chat] -> 保持现有同一实例注入，并以同会话、跨会话和失败测试覆盖两类轮次。

## Migration Plan

1. 在 Change 中补充本设计、会话轮次串行化 delta spec 和可追溯任务清单，并执行严格 OpenSpec 校验。
2. 将共享协调器注入 Interaction Chat Application，把确认 Agent 入口和 HTTP 确认路由改为异步等待租约。
3. 在租约覆盖范围内保留既有 Agent invocation 与 continuation 调用顺序和错误映射。
4. 增加受控时序、失败、取消和跨会话测试，并运行受影响 pytest、架构检查、严格 OpenSpec 校验与 diff 检查。
5. 无数据迁移。回滚时移除 Interaction 侧协调器注入并恢复同步确认入口；已持久化 Conversation 事实、确认 API 和数据库结构无需回滚。

## Open Questions

无。锁范围、取消前不得消费一次性状态、单进程边界和 `cancel` 动作不加锁均由 proposal 明确限定。
