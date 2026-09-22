## Context

当前应用启动时只检查知识库表结构。Task Management 已有 PostgreSQL Repository、HTTP 路由和 Worker，但任务表由 `sql/013_task_lifecycle.sql` 显式迁移创建；迁移未执行时，首次访问任务列表会在 Repository 层抛出数据库缺表错误。应用不能在启动时自动改库，也不能把基础设施不可用伪装成空任务列表。

## Goals / Non-Goals

**Goals:**

- 用独立的 schema health 适配器检查 Task 所需的核心表。
- 在 lifespan 日志中区分数据库不可用、Task 表缺失和 Task 表完整三种状态。
- 输出可执行的迁移指引，并保持启动不改库。
- 让检查逻辑可以使用 mock Engine 测试，不依赖真实 PostgreSQL。

**Non-Goals:**

- 不自动执行 SQL 迁移，不引入 Alembic 或新的迁移框架。
- 不改变 Task 的状态机、权限、分页、Worker 或 HTTP 响应契约。
- 不把 schema health 改造成新的公开业务 API。

## Decisions

1. **复用现有 schema health 模式，新增 Task 专用检查。**
   知识库检查已经提供 `REQUIRED_*_TABLES`、安全检查和启动状态模型。Task 检查沿用同一边界，避免把 SQLAlchemy Inspector 泄漏到 Composition Root。相比在 Repository 查询失败时临时捕获异常，启动诊断能更早、也更明确地暴露部署问题。

2. **检查四张核心表而不是只检查 `task`。**
   `task`、`task_attempt`、`task_event`、`task_command_receipt` 共同构成生命周期读写闭环；缺任一张都视为 Task schema 未就绪。迁移指引固定指向 `sql/013_task_lifecycle.sql`，不在运行时拼接 SQL。

3. **数据库不可用时返回 `None` 状态并记录 warning。**
   启动仍保持兼容，允许健康检查或其他不依赖数据库的功能运行；实际任务请求继续由现有错误边界处理。缺表时返回具体表名和指引，但不阻止应用启动，因为数据库初始化通常由部署流程负责。

4. **只增加内部诊断，不修改 HTTP 契约。**
   Task HTTP 路由的主体隔离和错误映射已经是已归档能力；本 Change 只为前端接入提供可靠的运行时前置条件，不借机扩展任务接口。

## Risks / Trade-offs

- [检查只覆盖表存在性，不能证明列、约束或索引完整] -> 迁移脚本保持版本化，相关 Repository 测试继续覆盖字段和行为；后续若需要深度校验再单独建 Change。
- [数据库不可用时应用仍会启动] -> 启动日志明确标记不可用，并保留已有请求级错误日志；部署健康检查可在后续接入该状态。
- [迁移指引依赖工作目录] -> 日志只输出仓库内稳定路径 `sql/013_task_lifecycle.sql`，不读取或暴露环境变量和连接信息。

## Migration Plan

1. 发布代码后观察启动日志，确认 Task schema 状态可见。
2. 在部署环境显式执行 `sql/013_task_lifecycle.sql`。
3. 重启或重新检查，确认四张表均存在。
4. 回滚仅需回滚应用代码；数据库表保留，不执行破坏性回滚 SQL。

## Open Questions

- 是否把 Task schema 状态接入独立的 `/health/ready` 端点，留到运行时可观测性 Change 决定。
