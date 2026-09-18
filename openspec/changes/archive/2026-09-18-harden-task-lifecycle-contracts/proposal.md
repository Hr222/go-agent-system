## Why

TM-01 已建立任务状态机与幂等基础，但审计规格把“领取”和“开始”写成两项事实，而当前状态机将领取原子地完成为运行开始。同时，事件元数据的 JSON 与脱敏约束、内存仓储位置及 lease 返回边界需要在引入持久化前收紧，避免 TM-02 固化错误契约。

## What Changes

- 明确一次合法领取同时形成领取与开始执行事实，不新增独立的 Worker 启动阶段或第二条生命周期事件。
- 将事件元数据限制为每类事件允许的安全字段和可序列化 JSON 标量，拒绝非有限浮点数、敏感字段和不符合安全代码/指纹格式的值。
- 将仅用于测试的内存仓储移出 Application 运行时代码，并保持 Application 只依赖 `TaskRepositoryPort`。
- 区分安全 `TaskView` 与仅供受信任执行器消费的 lease 结果；本 Change 不新增 HTTP 协议或外部执行器。
- 补充领域、架构边界与规格测试，并同步架构基线和看板中的 TM-01 事实。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `task-lifecycle-management`: 收紧领取即开始的审计语义、事件安全数据要求和执行器 lease 的可见范围。
- `current-architecture-baseline`: 明确 Task Management 的测试替身与受信任执行器边界。

## Impact

- 影响 `app/platform/task` 的领域事件校验和 Application 执行器契约，以及 `tests/task` 的测试替身。
- 不影响 HTTP、数据库模式、迁移、Worker、外部 Provider 或前端；不引入持久化和并发保证。
- 这是 TM-01 归档后的兼容性收紧 Change。TM-02 只能在其验证和归档后创建。
