## MODIFIED Requirements

### Requirement: Task 查询必须按主体隔离

系统 MUST 提供 `GET /api/v1/tasks` 列表、`GET /api/v1/tasks/{task_id}` 详情和 `GET /api/v1/tasks/{task_id}/resources` 结果资源接口。owner MUST 从服务端解析的已认证 `RequestPrincipal` 确定，不能由路径、查询参数或请求体覆盖。资源查询还 MUST 要求匹配的 Conversation ID。响应 MUST 只包含安全 Task 或资源投影，不包含输入指纹、lease、Attempt 内部字段、文件字节、物理路径或底层异常；不存在或不属于当前主体的任务和资源 MUST 返回统一的不可用结果。

#### Scenario: 主体读取自己的任务列表

- **WHEN** 已认证主体请求任务列表并提供合法的有界 `limit`/cursor
- **THEN** 系统只返回该主体拥有的 Task，并按稳定顺序分页
- **AND** 每条结果只包含安全 Task 投影

#### Scenario: 主体读取自己的结果资源

- **WHEN** 已认证主体以匹配的 Conversation ID 请求自己已完成 Task 的资源
- **THEN** 系统返回资源 ID、文件名、媒体类型、大小、sha256 和安全下载地址
- **AND** 文件内容仍只能通过既有 Attachment 下载接口取得

#### Scenario: 主体读取其他主体的任务

- **WHEN** 主体使用其他主体的 `task_id` 请求详情
- **THEN** 系统返回统一的 `TASK_UNAVAILABLE` 未找到结果
- **AND** 响应不泄漏任务是否存在、owner、输入指纹或 lease

#### Scenario: 未认证主体读取任务

- **WHEN** 匿名或未认证请求访问任务列表或详情
- **THEN** 系统拒绝请求并返回稳定的主体认证错误
- **AND** 不创建或修改任何 Task 生命周期事实

#### Scenario: 主体读取其他主体或其他 Conversation 的资源

- **WHEN** 主体使用其他主体的 `task_id` 或不匹配的 Conversation ID 请求资源
- **THEN** 系统返回统一的 `TASK_RESOURCES_UNAVAILABLE` 不可用结果
- **AND** 响应不泄漏任务、owner、附件、输入指纹或 lease

#### Scenario: 未认证主体读取资源

- **WHEN** 匿名或未认证请求访问 Task 结果资源
- **THEN** 系统拒绝请求并返回稳定的主体认证错误
- **AND** 不创建、修改或暂存任何资源事实
