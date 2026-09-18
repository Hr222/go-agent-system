## Why

TM-05 已完成任务恢复、取消和重试的内部能力，但外部调用者还没有主体隔离的任务查询和控制入口。现在需要把安全 Task 投影与既有 Application 命令适配到 HTTP，供后续 Tender 接入和前端联调使用，同时继续禁止浏览器直接创建任务或接触 lease。

## What Changes

- 新增主体隔离的任务列表、详情和生命周期事件查询接口。
- 新增任务取消和手动重试 HTTP 命令，沿用服务端主体、命令幂等和安全错误码。
- 从 `RequestPrincipal` 确定 owner；请求路径、查询参数和请求体不得覆盖任务归属主体。
- 对跨主体或不存在的任务返回统一安全的未找到结果，不泄漏其他主体的存在性、输入指纹或 lease。
- 将 HTTP Schema、依赖注入、异常映射和接口测试放在 `interfaces` 层；复杂状态规则继续由 Task Application 处理。
- 不新增任务创建、Worker 领取、续租、结果回写、恢复调度或含 lease 的公开接口。

## Capabilities

### New Capabilities

- `owned-task-http-management`: 提供主体隔离的 Task 查询、事件读取、取消和手动重试 HTTP 契约。

### Modified Capabilities

无。现有 Task 生命周期和恢复能力通过既有 Application 契约复用，不改变领域状态转换。

## Impact

- 影响 `app/platform/task` 的 owner-scoped 查询 Application/Port 和安全事件投影。
- 影响 `app/interfaces/http` 的路由、Schema、依赖注入和异常映射；复用现有 `RequestPrincipal` 解析边界。
- 影响 `app/infrastructure/persistence` 的主体过滤查询和事件读取适配器；不改变 Task、Attempt、Event 表结构，不需要迁移。
- 增加 HTTP 正常、未认证、跨主体、幂等取消/重试、终态拒绝和敏感字段隔离测试；不接入 Tender、前端或 E2E。
