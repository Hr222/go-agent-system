## Why

Task Management 的 HTTP 路由和持久化实现已经存在，但本地数据库未应用任务生命周期迁移时，`GET /api/v1/tasks` 会直接变成 500，启动日志也只检查知识库表结构，无法给出任务系统未就绪的明确诊断。现在先把运行时前置条件固定下来，后续前端接入才不会建立在一个启动后才暴露的基础设施错误上。

## What Changes

- 在应用启动阶段检查 Task Management 所需的表结构，并输出明确的缺失表和迁移指引。
- 为 Task schema 检查提供可测试的状态模型，不在应用启动时隐式创建或修改数据库。
- 在任务 HTTP 访问失败时保留现有主体隔离和错误语义，不改变任务生命周期、Worker 或对外创建权限。
- 增加针对 schema 检查和启动诊断的测试，覆盖数据库不可用、表缺失和表完整三种状态。

## Capabilities

### New Capabilities

- `task-runtime-readiness`: 检查并诊断 Task Management 运行时数据库前置条件。

### Modified Capabilities

- `task-lifecycle-management`: 仅补充运行时前置条件诊断，不改变生命周期状态或转移规则。

## Impact

- 影响 `app/composition/runtime.py`、应用 lifespan 启动日志、Task schema health 基础设施和相关测试。
- 不新增 HTTP 路由，不改变现有请求/响应字段，不改变 PostgreSQL 表结构定义；实际数据库仍需由部署流程显式执行 `sql/013_task_lifecycle.sql`。
- 不涉及敏感数据、外部 Provider、Workflow 执行或前端代码。
