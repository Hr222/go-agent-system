# owned-task-http-management Specification

## Purpose

定义已认证主体通过 HTTP 查询和控制自身 Task 的安全、幂等、主体隔离、分页和错误隔离行为，明确公开管理协议与受信任执行契约的边界。

## Requirements

### Requirement: Task 查询必须按主体隔离

系统 MUST 提供 `GET /api/v1/tasks` 列表和 `GET /api/v1/tasks/{task_id}` 详情接口。owner MUST 从服务端解析的已认证 `RequestPrincipal` 确定，不能由路径、查询参数或请求体覆盖。响应 MUST 只包含安全 Task 投影，不包含输入指纹、lease、Attempt 内部字段或底层异常；不存在或不属于当前主体的任务 MUST 返回统一的 `TASK_UNAVAILABLE` 未找到结果。

#### Scenario: 主体读取自己的任务列表

- **WHEN** 已认证主体请求任务列表并提供合法的有界 `limit`/cursor
- **THEN** 系统只返回该主体拥有的 Task，并按稳定顺序分页
- **AND** 每条结果只包含安全 Task 投影

#### Scenario: 主体读取其他主体的任务

- **WHEN** 主体使用其他主体的 `task_id` 请求详情
- **THEN** 系统返回统一的 `TASK_UNAVAILABLE` 未找到结果
- **AND** 响应不泄漏任务是否存在、owner、输入指纹或 lease

#### Scenario: 未认证主体读取任务

- **WHEN** 匿名或未认证请求访问任务列表或详情
- **THEN** 系统拒绝请求并返回稳定的主体认证错误
- **AND** 不创建或修改任何 Task 生命周期事实

### Requirement: Task 事件历史必须是安全有序的

系统 MUST 提供 `GET /api/v1/tasks/{task_id}/events` 事件读取接口，并在读取前执行同样的 owner 隔离。响应 MUST 按单 Task 的递增 `sequence` 返回安全事件字段，支持正整数 `after_sequence` 分页；不得返回 lease token、输入原文、输入指纹、Attempt 内部字段、Provider 凭据或完整异常。

#### Scenario: 读取自己的事件历史

- **WHEN** 已认证主体请求自己的 Task 事件并提供合法分页参数
- **THEN** 系统返回按 `sequence` 递增的事件和分页信息
- **AND** 事件元数据只包含领域白名单允许的安全字段

#### Scenario: 事件分页参数无效

- **WHEN** 请求使用非正 `after_sequence`、超限 `limit` 或无效 cursor
- **THEN** 系统返回稳定的 `INVALID_TASK_PAGINATION` 参数错误
- **AND** 不读取或修改其他主体的任务事实

### Requirement: HTTP 取消必须复用协作式生命周期

系统 MUST 提供 `POST /api/v1/tasks/{task_id}/cancel` 取消接口，要求请求携带非空、长度受限的 `command_id`。排队或退避任务 MUST 直接转为 `cancelled`；运行中任务 MUST 只转为 `cancel_requested`，不能由 HTTP 请求强杀 Worker 或 Provider。重复 `command_id` MUST 返回当前安全 Task 投影而不重复追加事件。

#### Scenario: 取消自己的排队任务

- **WHEN** 已认证主体以合法 `command_id` 取消自己的 `queued` 或 `retry_wait` Task
- **THEN** 系统返回 `cancelled` 安全 Task 投影并记录一次取消事实
- **AND** 不创建 Attempt 或暴露 lease

#### Scenario: 请求取消运行中任务

- **WHEN** 已认证主体取消自己的 `running` Task
- **THEN** 系统返回 `cancel_requested` 安全 Task 投影并保留 active Attempt
- **AND** 只有执行器后续确认后才进入 `cancelled`

#### Scenario: 重放取消命令

- **WHEN** 客户端以相同 Task 和 `command_id` 重试已处理的取消请求
- **THEN** 系统返回当前 Task 状态
- **AND** 不追加第二条取消事件或第二个命令回执

### Requirement: HTTP 手动重试必须受策略和主体约束

系统 MUST 提供 `POST /api/v1/tasks/{task_id}/retry` 手动重试接口，要求非空、长度受限的 `command_id`。只有当前主体拥有、状态为 `failed`、服务端允许手动重试且未耗尽最大尝试次数的 Task 才能进入 `queued`；其他情况 MUST 返回固定安全错误码并保持 Task、Attempt 和 Event 不变。重复命令 MUST 返回当前安全 Task 投影。

#### Scenario: 重试允许的失败任务

- **WHEN** 已认证主体以新 `command_id` 重试允许手动重试的 `failed` Task
- **THEN** 系统返回 `queued` 安全 Task 投影并记录一次手动重试事实
- **AND** 后续 Worker 可以按正常流程领取该 Task

#### Scenario: 重试被策略拒绝

- **WHEN** 请求重试不允许手动重试或已耗尽尝试次数的 Task
- **THEN** 系统返回稳定的策略错误码
- **AND** Task、Attempt、Event 和命令回执保持不变

### Requirement: HTTP 边界不得开放受信任执行契约

Task HTTP 接口 MUST 不提供任务创建、Worker 领取、lease 续租、结果回写或恢复调度入口。HTTP 路由 MUST 只能调用 Task Application/Port，不得直接访问 ORM、Session、Repository 或含 lease 的执行器契约；协议错误响应不得包含原始异常或敏感数据。

#### Scenario: 检查公开路由边界

- **WHEN** 外部调用者检查 Task HTTP 路由和响应 Schema
- **THEN** 只能发现主体隔离的查询、事件、取消和重试能力
- **AND** 不存在创建、领取、续租、结果回写或 lease token 响应

#### Scenario: 底层异常被安全映射

- **WHEN** Task Application 或持久化适配器在 HTTP 请求期间失败
- **THEN** 系统返回固定错误代码和通用消息
- **AND** 响应、日志投影和事件中不包含 token、输入、Provider 凭据或完整异常
