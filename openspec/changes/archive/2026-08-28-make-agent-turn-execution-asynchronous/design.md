## Context

`serialize-streaming-conversation-turns` 已为普通流式 Chat 定义了进程共享的 `ConversationTurnCoordinator`：先定位 Conversation，再取得租约，写入事实并在整个流结束时释放。后续的 Agent change 虽复用同一协调器，但 `InteractionChatStreamApplication.confirm_agent()` 在取得租约后直接调用同步 Agent 与同步 continuation LLM。该路径阻塞 ASGI 事件循环，使不同 Conversation 不能在长 Agent 轮次期间推进。

当前 Agent 确认同时跨越 Interaction 的一次性 proposal、Dialogue 的 pending invocation 和 Conversation 事实链。请求级 `ApplicationContainer` 持有同步 SQLAlchemy Session，不能传入 worker 线程。若简单以 `asyncio.to_thread()` 包装现有服务，客户端取消会先释放会话锁而底层线程仍继续写入事实，同会话轮次仍可能交错。

## Goals / Non-Goals

**Goals:**

- 让已确认 Agent 轮次与普通 Chat 复用同一进程共享租约，并在长时间同步 Agent/LLM 工作期间让出 ASGI 事件循环。
- 保持 Interaction/Gateway 对确认提议、目录/权限/输入复核和受控分发批准的职责；Conversation turn 生命周期、取消转移和 worker 执行属于 Dialogue Application。
- 使用 worker 私有的 session/container 运行同步 Agent invocation 与 continuation，绝不跨线程使用 HTTP 请求的 Session 或其构建出的持久化服务。
- 锁等待取消不消费任何一次性状态；轮次开始后的客户端取消不提前释放租约，直到后台同步工作达到终态。
- proposal 已消费后的所有拒绝、失败、成功和取消终态均清理 matching pending invocation。

**Non-Goals:**

- 不把 SQLAlchemy Repository 全面迁移为 `AsyncSession`，不改造 Tender Agent 或 Provider 为原生异步接口。
- 不新增数据库 turn/租约、后台队列、Redis、跨进程协调、严格 FIFO 或 HTTP/SSE 协议字段。
- 不改变用户等待确认时的 proposal TTL、展示文本、确认 API 或 Agent 业务结果。
- 不承诺客户端取消后终止不可中断的同步 Agent/Provider 调用；只保证其不破坏同会话事实顺序。

## Decisions

### 1. Interaction 保持确认控制面，Dialogue 提供 Conversation turn 执行边界

新增 Dialogue Application 的异步 Conversation turn 执行入口。它接受已准入的 `conversation_id` 与一个确认操作：先取得既有 `ConversationTurnCoordinator` 租约，再调用该操作；操作返回已批准的 Agent 调用或受控拒绝结果。只有得到已批准调用时，Dialogue 才启动 Agent/continuation worker，并让租约覆盖至 Conversation 事实终态。

Interaction Chat Application 仍负责读取主体绑定的 pending invocation 以定位 Conversation，并把确认操作传入执行入口。该操作在锁内调用 Gateway 消费 proposal、重新校验目录/权限/输入、消费 matching pending invocation，并只把服务端产生的批准分发信息交给 Dialogue。HTTP 层继续只负责 await 应用入口和响应映射；Interaction 不直接获取或释放 `ConversationTurnLease`。

这样保留了 Gateway 作为自然语言确认与受控分发控制面的架构职责，同时让 Dialogue 统一管理 Conversation turn 的租约、supervisor 和事实执行。将租约生命周期继续留在 Interaction 的方案会让每种新 turn 手写 acquire/release；将 proposal 消费移入 Dialogue 则会反向依赖 Interaction 控制面。两者都不采用。

### 2. 用受监督的 worker 任务隔离同步执行，并在取消后保留租约

取得租约并完成一次性状态消费后，Dialogue 入口创建一个由它拥有的异步 supervisor task。该 task 通过 `asyncio.to_thread()` 运行同步 worker，并在自己的 `finally` 中释放租约。请求协程使用 `asyncio.shield()` 等待该 task：

- 在等待租约时取消，`acquire()` 直接传播 `CancelledError`，不创建 supervisor、不消费 proposal/pending；
- 在 supervisor 已启动后取消，HTTP 请求可结束，但 supervisor 和 worker 继续运行并保留租约，直到 Agent/continuation 成功或受控失败；
- supervisor 的完成回调消费异常，避免客户端已取消时留下未检索 task 异常。

这比在外层 `finally` 释放锁安全：`to_thread()` 的线程无法被 `asyncio` 取消，若外层先释放租约，后续同会话 Chat 会与仍在写事件或 assistant 的 worker 交错。不同 Conversation 各自运行独立 worker，事件循环仍可调度普通 Chat、确认请求和等待者。

### 3. worker 每次执行创建私有 Composition 依赖与 SQLAlchemy Session

Dialogue Application 只依赖 `DialogueAgentTurnWorkerPort`，而不是 `ApplicationContainer`、`Session`、Repository 或 `SessionLocal`。Composition Root 绑定一个私有 worker factory；其具体实现为每个已确认 Agent turn 建立同步 Session，组装 `DialogueAgentInvocationService`、`DialogueAgentContinuationService` 及其 Dispatcher/LLM 依赖，执行完整事实链后在 `finally` 中关闭资源。Composition 只负责创建此对象图，不参与确认、状态转换或请求转发。

worker 返回纯应用结果值；Interaction 的 HTTP 响应仍由原请求协程构建。对话事实保持当前服务的提交/回滚语义，不需要数据迁移。选择每轮私有 worker 而不是共享请求 Session，避免 SQLAlchemy 非线程安全使用和请求结束后 Session 被关闭；选择单个同步 worker 而不是把每次 Repository 调用分别切线程，避免 Agent event 与 continuation 上下文之间暴露未受保护的时序间隙。

### 4. 在锁内一致地收口 proposal 与 pending invocation

确认 turn 在取得租约后由 Interaction 的确认操作执行 proposal 消费与能力校验，再始终消费或删除 matching pending invocation。proposal 不可用、能力校验拒绝、pending 已失效、Agent 失败、continuation 失败和 cancel 都必须得到既有受控响应，且不保留不可再成功确认的 pending 状态。worker 只接受 Gateway 已复核并产生的批准分发信息，不接收客户端提供的能力代码、分发键或输入作为执行依据。

等待锁前不得消费任一状态；同一 proposal 的并发确认仍以 proposal 的一次性消费作为最终裁决。此顺序保留取消可重试语义，同时修复“proposal 已消费但 pending 仅等待 TTL 清理”的状态泄漏。

### 5. 用受控阻塞 worker 验证事实与调度，而非只验证锁注册表

测试使用会阻塞的同步 Agent 或 continuation 替身，并以线程安全事件确认 worker 已开始。测试在 Agent worker 被阻塞时发起：

1. 同 Conversation 普通 Chat，断言没有写 user、读取历史或调用 LLM；
2. 不同 Conversation 普通 Chat 或确认 Agent，断言可到达其模型/Agent 起点；
3. 释放 worker 后，同 Conversation Chat 读取 Agent result 与 continuation assistant 的完整终态；
4. 已启动 worker 的请求取消，断言租约保留到 worker 结束；等待锁的请求取消，断言 proposal/pending 可重试；
5. proposal 已消费但后续拒绝时，断言 pending 被清理。

保留协调器自身的等待、取消、引用回收单元测试；新增测试补足它无法证明的跨模块事实顺序与事件循环让出行为。

## Risks / Trade-offs

- [客户端取消后同步 Agent 继续运行] → supervisor 持有租约直到终态，保证事实顺序；响应不再等待结果，后续可另立 Change 提供可取消 Provider。
- [每个 Agent turn 新建 container/session 增加组装开销] → 只用于已确认且可能长时间运行的 Agent 轮次，并在完成后立即关闭资源；用连接释放测试验证。
- [worker 数量过多] → 本 Change 不新建队列或并发配额，继续由现有 Provider 治理器和部署线程资源约束；需要显式容量控制时另立 Change。
- [同一 turn 的 proposal/pending 跨两个内存 store 不能原子事务] → 在同一会话租约内按确定顺序消费，并在每个终态清理 pending；单进程范围内避免重复 Agent 执行。
- [多 worker 或多实例仍可能绕过互斥] → 延续既有规格，仅保证单个后端进程；跨进程协调另立 Change。

## Migration Plan

1. 增加 Dialogue Conversation turn 异步入口、worker Port/factory 与结果契约，保持现有确认 HTTP schema。
2. 将 Interaction 确认入口改为在该入口的锁内执行 Gateway 确认操作；移除其直接租约生命周期管理。
3. 使用私有 worker container/session 组装同步 Agent invocation 与 continuation，并实现 supervisor 的取消和异常回收。
4. 补充同/跨 Conversation、状态收口、Session 隔离、取消和资源释放测试，随后运行严格 OpenSpec 与后端回归。
5. 无数据迁移。回滚时恢复同步确认路径并移除 worker 入口；已写入的 Conversation event/Message 与 HTTP 契约无需回滚。

## Open Questions

无。线程不可中断时的租约保留、每轮私有 Session 和单进程范围均为本 Change 的明确边界。
