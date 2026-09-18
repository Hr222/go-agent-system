## Why

TM-04 已能领取任务、续租并执行结果，但 Worker 崩溃或租约过期后，任务会停留在 `running`；取消请求也缺少独立调度确认，`retry_wait` 不能自动重新入队。没有恢复与重试调度，Task Management 无法从执行失败和进程故障中继续推进。

## What Changes

- 新增受信任的恢复调度能力：扫描过期 lease，原子结束失效 Attempt，并按取消状态和剩余尝试次数将 Task 转为 `cancelled`、`queued` 或 `failed`。
- 新增可执行时间到达后的自动重新入队调度，保持退避时间和命令幂等。
- 增加协作式取消协调：运行中任务先进入 `cancel_requested`，执行器确认后才进入 `cancelled`；排队任务可直接取消。
- 增加手动重试调度，复用服务端策略、命令回执和既有结果/事件幂等语义。
- 用 PostgreSQL 锁和批量扫描保证多个恢复器不会重复恢复同一 Attempt 或追加重复 Event。
- 不新增公开 HTTP、MCP、Function Calling、前端、Tender 或 E2E 入口；不改变 TM-04 的 Worker 执行器绑定。

## Capabilities

### New Capabilities

- `task-recovery-and-retry`: 定义 lease 恢复、取消协调、退避重入队和手动重试调度行为。

### Modified Capabilities

无。现有 `task-lifecycle-management` 已定义恢复、取消、重试的领域转换；本 Change 新增的是受信任调度器如何触发这些命令的能力边界。

## Impact

- 影响 `app/platform/task` 的恢复/取消/重试 Application 与 Ports，以及 `app/infrastructure/persistence` 的过期候选扫描和批量锁定。
- 影响 `app/composition` 的调度器组装；不开放协议层入口。
- 增加内存与 PostgreSQL 并发、恢复、取消、退避和手动重试测试；不新增外部 Provider，不需要数据回填，必要索引通过兼容迁移增加。
- TM-06 仍负责主体隔离的任务 HTTP，TM-07 仍负责 Tender 业务接入，TM-08/09 仍负责前端和 E2E。
