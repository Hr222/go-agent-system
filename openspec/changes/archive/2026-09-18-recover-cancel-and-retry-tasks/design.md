## Context

TM-04 已实现 Worker 的原子领取、lease 续租和结果回写，但 Worker 崩溃后没有组件扫描过期 Attempt；`retry_wait` 也不会在退避时间到达后自动回到 `queued`。现有 `TaskLifecycleService` 和 Domain 已定义 `recover`、`cancel`、`requeue_due`、`retry` 与 `confirm_cancellation` 命令，本 Change 只增加可靠触发这些命令的内部调度边界。

## Goals / Non-Goals

**Goals:**

- 用 PostgreSQL 原子候选扫描恢复过期的 `running`/`cancel_requested` Task，并按既有 Domain 规则写入恢复 Event 和命令回执。
- 让退避到期的 `retry_wait` Task 自动重新入队；相同 Task 在多调度器并发下只追加一次重入队事实。
- 提供协作式取消协调：排队任务直接取消，运行中任务先记录 `cancel_requested`，执行器在安全检查点确认后才完成 `cancelled`。
- 提供受策略约束的手动重试调度，沿用既有幂等键、最大尝试次数和安全错误码。

**Non-Goals:**

- 不新增公开 HTTP、MCP、Function Calling、前端、Tender 或 E2E 入口。
- 不改变 TM-04 的 Worker 执行器注册、lease 签发和结果回写契约；不在恢复器中执行业务任务。
- 不引入跨任务 Workflow、优先级队列、分布式消息系统或新的重试策略 DSL。

## Decisions

### 调度器只调用生命周期 Application

新增 RecoveryCoordinator、RetryScheduler 和 CancellationCoordinator 的 Application/Port。它们只能通过 `TaskLifecycleService` 的现有命令推进状态，不直接修改 Domain、ORM 或 Repository。Composition Root 负责固定组装调度器和时钟，协议层不暴露调度命令。

### 过期恢复使用原子候选锁定

Repository 增加按 `status in ('running', 'cancel_requested')`、active Attempt `lease_expires_at <= now` 的候选扫描，使用父 Task 行锁和 `SKIP LOCKED`。调度器为每个候选生成稳定命令 ID（包含 Task、Attempt 和租约到期事实），调用 `recover`；状态、恢复 Event 和命令回执在同一事务中提交。恢复结果严格复用 Domain：取消请求转 `cancelled`，未耗尽尝试转 `queued`/`retry_wait`，耗尽则转 `failed`。

### 退避重入队和手动重试复用命令回执

RetryScheduler 只扫描 `retry_wait` 且 `available_at <= now` 的 Task，并以稳定的 `requeue` 命令 ID 调用 `requeue_due`。手动重试由受信任内部 Application 接收稳定 command_id，调用既有 `retry`；它不能绕过 `allow_manual_retry` 或 `max_attempts`。重复扫描、进程重启和并发调度都返回当前结果，不重复 Event。

### 协作式取消不强杀执行器

CancellationCoordinator 对 queued/retry_wait Task 直接调用 `cancel`；对 running Task 只记录 `cancel_requested`。Worker 执行上下文增加只读取消检查 Port，执行器在安全检查点停止后调用 `confirm_cancellation`。调度器不终止线程、不撤销外部 Provider 请求，也不把取消原因或输入原文写入 Event。

### 安全、观测与失败隔离

扫描器日志仅记录 task_id、attempt_id、command_id、结果状态和固定错误代码；不记录 lease token、输入指纹、异常原文或业务输入。单个候选失败不影响下一候选；数据库错误回滚当前候选的全部状态/Event/回执。恢复器不自动重复执行过期 Task，恢复后的再次领取留给 TM-04 Worker。

## Risks / Trade-offs

- [扫描批次过大导致锁持有时间过长] → 使用有界 batch、`SKIP LOCKED` 和短事务；每个候选独立提交。
- [恢复器与 Worker 同时操作同一 Task] → 父 Task 行锁和 active Attempt 唯一约束决定单一事实，失败一方读取稳定状态。
- [取消确认长期不发生] → 保留 `cancel_requested` 可观察状态和安全指标；不偷偷强制取消，后续运维策略另行定义。
- [命令 ID 生成不稳定造成重复 Event] → ID 由 Task/Attempt/时间事实确定，不使用进程随机 UUID；回执测试覆盖重启和并发扫描。

## Migration Plan

1. 扩展 Task Repository 的恢复/重入队候选 Port，增加必要的复合索引和可重复迁移。
2. 实现三个内部调度器和取消检查 Port，接入 Composition Root；补内存、PostgreSQL 并发和失败隔离测试。
3. 更新架构基线、主规格和看板，完成全量验证后归档并提交。
4. 回滚时停止调度器组装，不删除已写入的恢复、取消或重试事实；旧 Worker 和生命周期读取继续可用。

## Open Questions

无。主体隔离的任务查询和取消接口由 TM-06 定义；Tender 业务策略由 TM-07 定义。
