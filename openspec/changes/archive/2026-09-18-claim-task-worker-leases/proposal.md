## Why

TM-02 已把任务生命周期持久化到 PostgreSQL，TM-03 已提供受信任的服务端提交能力，但目前没有真正的 Worker 消费 queued Task。若没有跨进程原子领取、受控 lease 和执行器绑定，任务只能停留在 `queued`，也无法证明同一任务不会被多个 Worker 同时执行。

## What Changes

- 新增受信任的 Task Worker 执行能力：从 PostgreSQL 原子领取可执行任务，并为每次领取签发内部 lease。
- 将领取、Attempt 创建和唯一 `TASK_CLAIMED` 事件保持在同一持久化事实中；竞争 Worker 只能有一个成功领取者。
- 增加 lease 续租、token/Attempt 校验和安全失效错误语义，执行器不得使用过期或不匹配的 lease 写回结果。
- 增加执行器接口与固定注册绑定；Worker 根据任务类型调用已注册执行器，并通过既有生命周期 Application 提交成功或受控失败结果。
- 覆盖 Worker 异常、执行器拒绝、重复领取和重复结果提交的幂等与安全行为。
- 不新增公开 HTTP、MCP、Function Calling 或前端入口，不改变任务创建档案和 PostgreSQL 表结构之外的既有提交契约。

## Capabilities

### New Capabilities

- `task-worker-execution`: 定义受信任 Worker 的领取、lease、执行器绑定、执行和结果回写行为。

### Modified Capabilities

- `task-lifecycle-management`: 补充跨进程原子领取、lease 有效性和 Worker 结果提交的生命周期要求。

## Impact

- 影响 `app/platform/task` 的 Worker Application/Port 契约，以及 `app/infrastructure/persistence` 的原子领取和 lease 持久化适配。
- 影响 `app/composition` 的 Worker 与执行器注册绑定；执行器只能通过稳定 Application 契约访问任务能力。
- 增加内存测试替身和 PostgreSQL 并发/lease/执行器测试，必要时补充架构边界测试；不引入新的外部 Provider。
- 不实现租约过期恢复扫描、协作式取消、自动或手动重试扩展、任务 HTTP、Tender 接入、前端、E2E 或 Workflow；这些属于后续 Change。
- 不改变已有公开 HTTP 契约（当前不存在任务管理公开接口），不需要数据回填；若需要增加内部持久化字段，将通过兼容迁移明确处理。
