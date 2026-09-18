## Context

TM-05 已提供安全 `TaskView`、生命周期命令、恢复/取消/重试协调器和 PostgreSQL 持久化，但 `app/interfaces/http` 尚未暴露 Task 管理入口。现有 Conversation HTTP 已建立 `RequestPrincipal`、owner-scoped Application、统一“不可用”错误和分页响应的模式；TM-06 应复用这些边界，不把主体判断或状态转换写进路由。

## Goals / Non-Goals

**Goals:**

- 提供 owner-scoped 的 Task 列表、详情、事件历史、取消和手动重试 HTTP 能力。
- 从服务端解析的 `RequestPrincipal` 确定 owner，所有读写 Application/Port 都携带主体范围。
- 只投影 `TaskView` 和脱敏事件字段，不暴露输入指纹、lease、Attempt 内部字段或底层异常。
- 保持取消、重试命令的幂等语义，并将领域错误映射为稳定 HTTP 状态和安全代码。
- 用路由、Application、持久化和架构测试证明协议层不能绕过 Task 生命周期。

**Non-Goals:**

- 不新增任务创建、Worker 领取/续租、结果回写或恢复调度的公开接口。
- 不接入 Tender、前端页面、MCP/Function Calling 或 E2E；这些属于后续 Change。
- 不改变 Task、Attempt、Event 表结构和领域状态机，不新增数据库迁移。

## Decisions

### 主体范围由 Application 强制执行

新增 Task 查询 Application 和 owner-scoped Port。路由只把 `RequestPrincipal` 与路径/分页参数传入 Application；Application 在读取 Task、事件以及执行取消/重试前解析非空主体，并调用带 `owner_subject` 条件的 Repository。查询不到或不属于当前主体统一映射为 `TASK_UNAVAILABLE`，避免泄漏资源存在性。替代方案是在路由先查 Task 再授权，会重复授权逻辑并容易产生越权旁路，因此不采用。

### 查询和事件使用安全投影

Task 列表/详情返回现有 `TaskView` 的公开字段；事件读取新增只读安全事件投影，只允许 sequence、event_type、transition_id（如需）和安全白名单元数据。输入指纹、lease token、Attempt 记录、原始异常和持久化内部字段永不进入 HTTP Schema。事件分页按单 Task 的递增 sequence 使用 `after_sequence`，避免引入新的游标编码复杂度。

### 命令接口复用既有生命周期 Application

取消接口接收稳定 `command_id`，调用 `CancellationCoordinator` 或对应 Application；手动重试接口同样接收 `command_id`，调用 `ManualRetryCoordinator`。Application 先完成 owner admission，再复用 `cancel`/`retry` 的命令回执和 Domain 状态校验。重复命令返回当前安全 TaskView；非法状态、策略拒绝和租约相关内部错误映射为固定安全错误码，不把异常文本传给客户端。

### HTTP 适配器和 Composition Root 固定组装

新增 Task Router、Pydantic Schema、Assembler 和 HTTP 依赖函数；路由注册到现有 API Router 下的 `/tasks`。Composition Root 为每个请求注入 PostgreSQL Repository 和 Task Application，路由不直接访问 Session、ORM 或 Repository。Task Application/Ports 不导入 FastAPI、SQLAlchemy 或 HTTP 类型。

### 分页、校验和兼容性

列表接口使用有界 `limit` 与稳定 cursor/排序；事件接口使用正整数 `after_sequence`。请求 Schema 使用 `extra="forbid"`，取消/重试命令拒绝空或过长 command_id。响应字段只增加新的 HTTP 契约，不修改既有 TaskView 或 Worker 内部契约。

## Risks / Trade-offs

- [查询和命令使用不同 Session 导致短暂状态差异] → 每次 HTTP 请求使用同一 Application/Session 依赖，命令以现有事务提交事实为准，读取只返回提交后的聚合。
- [跨主体 ID 探测] → Repository 查询始终带 owner 条件，未命中和跨主体统一为 `TASK_UNAVAILABLE`。
- [事件元数据未来新增字段误暴露] → 事件 Assembler 使用显式字段白名单和架构测试，不直接序列化 Domain/Event 对象。
- [客户端重试命令造成重复转换] → 强制 command_id 并复用既有命令回执唯一约束；重复请求只返回当前 TaskView。

## Migration Plan

无需数据库迁移。部署顺序为先发布 Application/Port 与 HTTP 适配器，再注册路由和依赖；回滚时移除 `/tasks` 路由即可，既有 Task 生命周期、Worker 和内部调度器不受影响。

## Open Questions

无。TM-07 再定义 Tender 提交档案与执行器绑定，TM-08 再消费本 Change 的 HTTP 契约。
