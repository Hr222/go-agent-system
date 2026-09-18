## Why

TM-02 已能安全持久化 Task 生命周期，但当前 `TaskLifecycleService.submit` 仍是低层通用命令：调用方可以自行传入 task type、最大尝试次数和重试策略。后续业务应用需要一个稳定的内部提交入口，使客户端输入不能决定任务类别、执行策略或归属范围，也不必提前开放任务创建 HTTP 接口。

## What Changes

- 新增受信任 Task 提交能力，供已注册的服务端业务应用创建任务。
- 通过 Composition 注册提交档案，固定 task type、最大尝试次数、手动重试策略和展示元数据白名单。
- 提交命令只接受服务端已确定的 owner、幂等键、输入指纹和展示元数据；拒绝越权字段、未注册任务类别和不安全展示元数据。
- 复用 TM-02 的 PostgreSQL Repository 与提交幂等语义，不改变状态机、Event 规则或数据库结构。
- 增加应用边界与 PostgreSQL 集成测试，证明重启后重放仍返回同一 Task，且业务应用不会绕过受信任提交入口直接调用低层生命周期提交。

## Capabilities

### New Capabilities

- `trusted-task-submission`: 已注册的服务端生产者以固定策略提交 Task 的内部 Application 能力。

### Modified Capabilities

- `task-lifecycle-management`: Task 创建从低层聚合命令扩展为受信任提交入口，并保持既有创建幂等结果。
- `current-architecture-baseline`: Task Management 架构基线记录受信任内部提交边界及未开放 HTTP 创建入口。

## Impact

- 影响 `app/platform/task` 的 Application 契约与 Composition 组装，以及 Task 测试和架构边界测试。
- 不新增 HTTP 路由、公开协议 Schema、前端页面、Worker、lease 调度、Tender 业务接入或数据库迁移。
- 不新增外部 Provider 或环境变量；持久化继续使用现有 Task Repository。
- 安全边界变化：客户端或未注册调用方不能自行决定 task type、重试策略或展示字段；owner 仍必须由调用该内部能力的服务端可信上下文确定。
