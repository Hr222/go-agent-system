## ADDED Requirements

### Requirement: 成功的异步 Task 产物必须成为受控资源

系统 MUST 在带有 Conversation 绑定的固定 Tender Task 成功生成文件后，为每个非空产物创建一个服务端管理的 Attachment 资源，并保存资源 ID、文件名、媒体类型、大小和 SHA-256。无 Conversation 的既有 MCP Task MUST 保持内部结果保存和成功状态，但不生成可通过浏览器下载的资源。Task、Attempt、Event 和普通状态响应 MUST NOT 保存或返回文件字节、物理路径、Prompt、Provider 响应或内部结果引用。

#### Scenario: Tender Task 成功生成多个文件

- **WHEN** 受信任 Worker 成功执行 `tender.generate_bid_skeleton` 并返回一个或多个已校验产物
- **THEN** 系统为每个产物创建主体和 Conversation 绑定的资源
- **AND** 资源查询返回每个资源的安全元数据和可用下载地址
- **AND** Task/Event 只保留安全摘要和结果指纹

#### Scenario: MCP Task 没有 Conversation 绑定

- **WHEN** 既有 MCP 异步 Tender 调用没有 Conversation ID
- **THEN** Worker 保持既有内部结果保存和成功状态
- **AND** 不生成伪造的浏览器资源、下载地址或 Conversation 绑定

#### Scenario: 没有可交付产物

- **WHEN** Task 成功结果不包含非空文件产物
- **THEN** 系统返回空资源列表或固定的结果契约失败
- **AND** 不创建空文件、伪造资源 ID 或可下载入口

### Requirement: 结果资源查询必须按主体和 Conversation 隔离

系统 MUST 提供 `GET /api/v1/tasks/{task_id}/resources` 只读查询，并要求可信主体和 Conversation ID。查询 MUST 只返回当前主体拥有且绑定该 Conversation 的 Task 资源；Task、Conversation 或资源不存在、过期、校验失败或不匹配时 MUST 返回统一的不可用响应，不区分具体原因。

#### Scenario: 所有权和 Conversation 匹配

- **WHEN** 已认证主体查询自己绑定同一 Conversation 的已完成 Tender Task
- **THEN** 系统返回稳定顺序的资源元数据
- **AND** 每个资源包含可调用现有附件下载接口的安全地址

#### Scenario: 主体或 Conversation 不匹配

- **WHEN** 另一主体或不同 Conversation 查询同一 Task 的资源
- **THEN** 系统返回统一的 `TASK_RESOURCES_UNAVAILABLE` 不可用结果
- **AND** 响应不泄漏 Task、附件或资源是否存在

#### Scenario: Task 尚未成功

- **WHEN** 查询的 Task 处于 `queued`、`running`、`retry_wait`、`cancel_requested`、`cancelled` 或 `failed`
- **THEN** 系统返回统一的不可用结果
- **AND** 不触发 Worker、结果生成或附件写入

### Requirement: 结果资源必须幂等且失败可清理

系统 MUST 以 Task ID 和产物序号保证同一 Task 的结果保存、Worker 重放和进程重启返回同一资源引用。任一产物保存、哈希校验或清单写入失败时 MUST 删除本次已创建的资源，不得发布部分成功清单。

#### Scenario: 重放相同 Task 结果

- **WHEN** 同一 Task 的 Executor 或结果保存调用重复提交相同产物
- **THEN** 系统返回原有资源清单
- **AND** 不创建第二个附件、资源清单或成功结果引用

#### Scenario: 部分产物保存失败

- **WHEN** 多个产物中任一产物无法完整暂存或清单无法原子写入
- **THEN** 系统清理本次已经暂存的附件
- **AND** Worker 收到固定的 `TENDER_RESULT_RESOURCE_STORE_FAILED` 安全失败
- **AND** 查询不到部分成功资源

### Requirement: 结果资源必须复用附件生命周期和下载边界

系统 MUST 使用既有 Attachment Storage 的完整写入、SHA-256、TTL、重启恢复和主体/Conversation 校验。资源下载 MUST 复用现有附件下载接口；系统 MUST 不新增任意资源创建、资源转移、公开文件路径或绕过 Task 授权的下载入口。

#### Scenario: 后端重启后读取未过期资源

- **WHEN** 服务重启后资源清单和附件目录均完整且未过期
- **THEN** 合法主体仍可查询元数据并下载原始文件
- **AND** 返回原始媒体类型和安全文件名

#### Scenario: 资源过期或目录不完整

- **WHEN** 附件已过期、校验失败或清单缺失完整绑定信息
- **THEN** 查询和下载均返回统一不可用结果
- **AND** 系统清理无效资源目录，不恢复为可访问资源
