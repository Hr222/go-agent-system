## Context

TM-07.1 已将 `AgentCallDispatcher` 与具体执行方式解耦，并为 `accepted` 结果保留了 opaque execution reference；TM-07.2 已让 Tender MCP 经过同一 Dispatcher。Task Management 目前只允许服务端通过 `TrustedTaskSubmissionService` 按固定档案提交，且提交幂等键由 `(owner, task_type, idempotency_key)` 约束。

本 Change 需要把这两条边界连接起来，但不能让 Dispatcher 变成通用 Task 创建器，也不能让调用方选择 Task 策略。异步资格必须由服务端配置，提交必须发生在现有目录、权限、输入和确认复核之后；实际 Tender 输入快照和 Worker Executor 留到 TM-07.4。

## Goals / Non-Goals

**Goals:**

- 定义一个可注入的 Agent→Task 桥接 Application/Port，接收已授权的 `StructuredAgentCall`、当前目录能力和 `RequestPrincipal`。
- 通过服务端固定的异步档案判断能力是否可异步，并将 task type、尝试限制、手动重试和展示字段白名单固定在档案中。
- 为后续业务 Agent 预留安全输入快照 Port；本 Change 只消费标准化的指纹和不含原文的快照引用事实，不把原始输入直接写进 Task。
- 使用 `capability_code + call_id` 生成稳定幂等键，沿用既有受信任提交和输入指纹冲突语义。
- 将成功提交的 Task ID 转换为协议无关的 opaque execution reference，失败时不返回部分引用。
- 让同步策略继续处理未登记异步能力，避免改变当前 MCP、Chat 和同步 Agent 行为。

**Non-Goals:**

- 不实现 Tender 的异步 Consumer、Task Executor、输入快照实际存储、结果资源转换、前端或 E2E。
- 不新增浏览器、HTTP、MCP、Function Calling 的通用 Task 创建路由。
- 不改变 Task 状态集合、Worker lease、取消、恢复、重试或 Task HTTP 访问控制。
- 不引入 LangGraph、Subagent、Workflow、动态插件扫描或客户端可选执行器。

## Decisions

### 1. 用服务端异步档案注册表表达资格

在 Agent Management 内定义只读的异步档案注册表，由 Composition Root 固定绑定 `capability_code -> AsyncTaskProfile`。档案至少包含 profile 标识、固定 `task_type`、`max_attempts`、`allow_manual_retry` 和展示元数据白名单；它不接受客户端字段，也不包含 URL、Python 导入路径或任意 Executor 地址。

Dispatcher 仍先读取当前目录并执行现有 `AgentCallPolicyValidator`。桥接再次确认当前能力代码、能力类型、启用状态和档案绑定一致后才提交。使用 Composition 注册表而不是让客户端在调用中携带异步标志，是为了避免“请求自称异步”或能力目录变化后沿用旧授权；使用独立档案而不是复用检索元数据，是为了不把执行安全配置混入召回字段。

### 2. 由组合策略选择同步执行或 Task 桥接

新增协议无关的策略路由器：已登记异步能力调用 `AgentTaskBridge`，其余能力调用现有同步策略。路由器由 Composition Root 固定组装并作为 Dispatcher 的唯一 `AgentExecutionStrategyPort`；Dispatcher 的授权、目录复核、错误映射和结果投影保持单一入口。

普通同步能力不会因为桥接存在而创建 Task：能力未登记异步档案时，路由器固定调用同步策略；已登记档案但能力类型不符、档案与目录不一致或桥接依赖未配置时，路由器返回稳定的受控失败，不降级为同步执行，避免掩盖生产配置错误。

### 3. 通过受信任提交服务创建 Task

桥接不导入 Task Repository 或 `TaskLifecycleService`，而是依赖 Composition 为该异步档案绑定的 `TrustedTaskSubmissionService`。桥接只构造 `TrustedTaskSubmissionCommand`：

- `idempotency_key` 使用规范化的 `agent:{capability_code}:{call_id}`；owner 仍由 `RequestPrincipal.subject` 决定。
- `input_fingerprint` 由档案绑定的输入快照规范化器产生，使用稳定哈希；规范化器不得把原始输入放入展示元数据、事件或日志。
- `display_metadata` 只包含档案允许的短字符串摘要，例如调用关联标识或用户可见标题；即使业务输入存在同名字段，也不能改变该白名单或其值来源，Task 档案继续负责校验。

这样可以复用既有唯一键和冲突语义：同一主体、能力和 `call_id` 重放返回原 Task；同一幂等键配不同指纹返回 `TaskIdempotencyConflictError`；更换 `call_id` 才表示新的业务提交。Task ID 作为内部生成的随机标识被包装为 opaque execution reference，引用格式不成为客户端可构造的创建协议。

### 4. 将输入快照留给后续 Consumer，但现在固定安全 Port

本 Change 只定义最小的 `AgentTaskInputSnapshotPort`/事实契约：给定已授权调用和异步档案，返回 `input_fingerprint`、可选的 opaque `snapshot_reference` 以及白名单展示摘要。桥接只把指纹和档案允许的摘要交给受信任提交；快照正文由后续业务 Change 按主体和任务 ID 绑定到自己的受控存储，不能由调用方直接传入。

这保留了 TM-07.4 配置 Tender 输入快照和固定 Executor 的插口，同时避免在本 Change 中改造 Task 聚合或把 `StructuredAgentCall.inputs` 序列化到数据库。若快照规范化失败，桥接返回受控失败且不创建 Task。

### 5. 使用稳定的 accepted 结果，不扩展公开协议

Task 提交成功后，异步执行策略返回 `AgentExecutionOutcome.accepted(execution_reference)`；Dispatcher 沿用现有 `AgentCallDispatchResult(status="accepted")` 投影并保留 `call_id`、能力代码及关联字段。失败、幂等冲突、能力不可用和未授权均转换为既有受控错误，不返回 TaskView 内部字段、输入指纹、lease 或快照正文。

本 Change 不规定 MCP/HTTP 如何轮询或下载结果。后续 TM-07.4/07.5 决定业务 Executor 和资源引用后，协议层才可以选择是否暴露这个引用。

### 6. 错误与事务边界

桥接只把受信任提交服务视为 Task 写入边界。快照规范化在提交前完成；提交异常不会被包装成已接受引用。既有 Task 提交的数据库事务负责 Task 与初始 Event 的原子性，桥接不增加第二套回执表或补偿事务。幂等重放由 Task 生命周期返回当前安全投影，桥接再次生成同一 execution reference。

## Risks / Trade-offs

- [异步档案配置与能力目录不一致] → 档案绑定包含能力代码和期望 task type；每次分发重新读取目录并拒绝不一致配置，生产组装测试覆盖失效配置。
- [调用关联字段过长或包含不安全字符] → 只使用已通过 `StructuredAgentCall` 校验的 `call_id`/能力代码，并在幂等键构造处执行长度和字符规范化；对无法规范化的值返回稳定输入错误。
- [输入指纹无法代表真实快照] → 快照规范化器是显式 Port，必须由后续 Consumer 提供确定性实现；桥接不自行对任意 Python 对象做字符串化。
- [Task 提交成功但协议调用方断开] → 依赖既有 Task 幂等键，重试可取回同一 Task；不在桥接层引入跨存储分布式事务。
- [调用方误把 accepted 当作完成] → `accepted` 继续与 `completed` 使用不同状态和引用字段；本 Change 不改变现有同步策略和协议适配器的状态映射，并在测试中验证不产生同步输出。
- [未来需要独立执行引用映射] → 当前引用只作为不透明字符串消费，禁止依赖格式解析；后续可以增加引用映射 Port，而不修改授权和提交契约。

## Migration Plan

1. 增加异步档案、输入快照事实、桥接 Port 和组合策略路由器，默认注册表为空，确保现有能力全部走同步策略。
2. 为桥接增加内存替身测试，覆盖授权前不提交、无档案拒绝、成功提交、同调用重放、输入冲突和快照失败。
3. 在 Composition Root 绑定既有 `TrustedTaskSubmissionService`，运行 Agent、Task 和架构边界测试；不需要数据库迁移。
4. TM-07.4 再注册 Tender 档案、快照存储和 Executor。若本 Change 验证失败，可移除路由器绑定并恢复原同步策略，不影响既有 Task 数据。

## Open Questions

- TM-07.4 是否需要把 `snapshot_reference` 写入独立资源表，还是由 Task type Executor 通过外部输入仓储按 Task ID 查询；本 Change 只固定 Port，不预选存储实现。
- 当同一 `call_id` 在同一主体下跨 profile 迁移时，是否需要 profile 版本加入幂等键；默认使用能力代码和 call_id，profile 变更应通过新的能力代码或显式迁移决定。
