## Context

Task Management 后续会被拆成多个有依赖关系的 Change。本 Change 是 TM-01，只负责建立 Task 的领域事实来源：状态集合、Task/Attempt/Event 关系、合法转换和幂等语义。当前没有持久化 Task 表、Worker、HTTP 路由、Tender 生产者或前端消费者；这些内容必须在后续 Change 中按看板顺序实现。

## Goals / Non-Goals

**Goals:**

- 建立不依赖基础设施的 Task、Attempt、Event 领域模型和状态转换表。
- 让每个改变状态的 Application 命令具有明确的幂等依据、重复行为和冲突行为。
- 让后续 PostgreSQL、Worker、HTTP 和业务接入 Change 可以直接复用同一领域契约。

**Non-Goals:**

- 不实现 PostgreSQL 模型、迁移、唯一索引或并发锁。
- 不实现 Worker 轮询、lease 调度、恢复进程或 executor 注册表。
- 不实现 HTTP 路由、主体隔离、Tender 接入、前端页面、E2E 或 Workflow。
- 不保证外部副作用的全局 exactly-once；本 Change 只定义平台命令的幂等语义。

## Decisions

### 平台边界和任务模型

新增 `app/platform/task`，包含 Domain 状态与不变量、Application 命令和内存 Ports。业务应用只能通过受信任的提交命令创建 Task；本 Change 不定义 HTTP 创建入口，也不允许领域对象依赖数据库或具体业务 Agent。

`Task` 保存稳定 ID、task type、owner subject、输入指纹、当前状态、尝试计数、最大尝试数、可执行时间、取消信息、结果引用或安全摘要和时间戳。`Attempt` 保存一次领取的序号、worker 标识、lease token、开始/结束时间、幂等 claim 标识和安全失败分类。`Event` 保存单 Task 递增 sequence、transition_id、事件类型、时间和安全元数据。领域模型可以持有输入引用和 lease token，但 Application 返回的安全结果不得暴露它们。

### 当前架构基线

`ARCHITECTURE.md` 将 Task Management 列为平台能力，并在物理目录中记录 `app/platform/task`。文档只说明当前已实现的 Domain、Application、Ports 和内存验证替身；明确不包含 PostgreSQL 持久化、独立 Worker、HTTP 路由、Tender 接入、前端或 Workflow，避免把 TM-01 的基础契约误读为完整任务平台。

### 显式状态机与转换命令

Task 状态固定为 `queued`、`running`、`retry_wait`、`cancel_requested`、`succeeded`、`failed`、`cancelled`：

```text
创建 / 手动重试 / 恢复
        -> queued --领取--> running --成功--> succeeded
                            |  \--不可重试或耗尽--> failed
                            |  \--可重试--> retry_wait --到期--> queued
                            \--取消请求--> cancel_requested --执行器确认--> cancelled

queued 或 retry_wait --取消--> cancelled
```

终态不可被普通领取或取消重写。`succeeded` 必须同时有安全结果摘要或资源引用。运行中取消只记录 `cancel_requested`，执行器在安全检查点自行停止并以当前 lease 完成 `cancelled`；平台不强杀线程或外部 Provider。

`running` 和 `cancel_requested` 必须各自有且只有一个 active Attempt；其他状态不得有 active Attempt。非法转换抛出稳定领域错误，且不得追加事件。

### 幂等提交与重试边界

受信任提交方必须提供 task type、owner、输入和幂等键。以 `(owner_subject, task_type, idempotency_key)` 作为唯一键；相同输入指纹返回原 Task，不同输入指纹返回冲突，绝不静默复用。自动重试只接受执行器分类为 transient 的失败，并按有界退避进入 `retry_wait`。手动重试只允许失败终态且受任务类型策略和最大尝试数约束，保留同一 Task ID 并产生新 Attempt/Event。

不把幂等判断放到 HTTP 层，因为未来 Chat、MCP 和直接业务接口都可能提交 Task；Application Capability 才是所有提交入口共享的事实边界。

Application 命令携带幂等标识，并把幂等判断放在领域/应用边界而不是 HTTP 层：

| 操作 | 幂等依据 | 重复行为 |
|---|---|---|
| 创建 Task | owner + task_type + idempotency_key + input_fingerprint | 返回原 Task；指纹不同则冲突 |
| 领取 | task_id + worker_id + claim_id | 返回原 Attempt，不创建第二次 Attempt |
| 续租 | task_id + attempt_id + lease_token + renewal_sequence | 重放不重复改变结果 |
| 取消 | task_id + command_id | 返回当前取消状态，不重复事件 |
| 手动重试 | task_id + command_id | 只重新入队一次 |
| 成功/失败提交 | task_id + attempt_id + lease_token + result_fingerprint | 相同结果可重放；旧 lease 或不同结果拒绝 |
| 事件写入 | transition_id | 同一转换最多一条生命周期事件 |

本阶段使用内存 Repository 验证这些语义；TM-02 再把唯一约束和事务映射到 PostgreSQL。

### 后续 Change 的边界

PostgreSQL 原子领取、lease 恢复、独立 Worker、owner 范围 HTTP、Tender 接入、前端和 E2E 均不在本 Change 实现。它们只能消费本 Change 固定的 Domain/Application 契约；并发、事务和外部副作用幂等在后续 Change 中补齐。

## Risks / Trade-offs

- [仅内存实现无法证明跨进程并发] → 本 Change 只验证纯领域语义；并发领取、事务和唯一索引明确留给 TM-02/TM-04。
- [状态机过早固化后续需求] → 只固化当前已确认的状态和转换；新增状态必须通过后续独立 Change 修改规格。
- [输入指纹或结果指纹实现不一致] → 领域层要求调用方提供稳定指纹，后续持久化 Change 复用同一字段和唯一约束。

## Migration Plan

1. 实现 `app/platform/task` 的 Domain、Application 和内存 Repository，并用纯 Python 测试固定状态转换和幂等结果。
2. 验证通过后归档 TM-01；TM-02 再将稳定契约映射到 PostgreSQL 持久化。
3. 后续 TM-03～TM-09 按看板依赖逐个创建和实施，不在本 Change 中提前实现。

## Open Questions

- 任务输入快照与结果引用的具体存储由 TM-02 及后续业务 Change 决定；TM-01 只使用指纹和安全摘要。
