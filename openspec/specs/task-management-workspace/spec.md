# task-management-workspace Specification

## Purpose
TBD - created by archiving change connect-task-management-workspace. Update Purpose after archive.
## Requirements
### Requirement: Agent 工作区必须显示真实的主体任务

Agent 工作区 MUST 通过 Task HTTP 查询显示当前已认证主体拥有的任务，不得使用静态任务记录替代后端结果。

#### Scenario: 返回任务列表
- **WHEN** 当前主体的 Task 列表查询成功
- **THEN** Agent 总览和 Tender Agent 列表显示服务端返回的任务、状态和更新时间

#### Scenario: 没有任务
- **WHEN** 当前主体的 Task 列表为空
- **THEN** 页面显示明确的空状态，并保留进入对话或 Agent 的入口

#### Scenario: 查询未授权
- **WHEN** Task API 返回主体未认证或访问拒绝
- **THEN** 页面显示受控的未授权提示，且不回退到伪造任务数据

### Requirement: 任务详情必须显示状态和事件

任务详情页 MUST 查询真实任务详情和 owner-scoped 事件，并展示加载、失败和事件为空状态。任务进入终态后 MUST 保留已读取的事件时间线，并停止事件轮询。

#### Scenario: 任务详情成功
- **WHEN** 任务详情和事件查询成功
- **THEN** 页面显示任务状态、创建/更新时间、结果摘要或失败信息，以及按顺序排列的事件

#### Scenario: 活动任务
- **WHEN** 任务状态为 queued、running、retry_wait 或 cancel_requested
- **THEN** 页面周期性刷新任务和事件，直到进入终态或页面离开

#### Scenario: 终态任务
- **WHEN** 任务状态为 succeeded、failed 或 cancelled
- **THEN** 页面首次读取并展示已有事件，且不再周期性刷新事件

#### Scenario: 任务不可用
- **WHEN** 后端返回任务不可用
- **THEN** 页面显示任务不存在或不可访问状态，不展示旧的 mock 详情

### Requirement: 任务命令必须使用后端结果

任务详情页 MUST 通过现有取消和重试接口执行命令，并在成功后刷新真实任务状态。

#### Scenario: 取消任务
- **WHEN** 用户确认取消且服务端接受命令
- **THEN** 页面显示服务端返回的新状态并刷新事件

#### Scenario: 重试任务
- **WHEN** 用户触发重试且服务端接受命令
- **THEN** 页面显示重新排队状态并恢复活动任务轮询

#### Scenario: 命令失败
- **WHEN** 服务端拒绝或命令请求失败
- **THEN** 页面显示错误提示，保留当前服务端任务数据，不伪造成功状态

### Requirement: 成功任务详情必须展示结果资源

任务详情页 MUST 对成功 Task 查询服务端结果资源清单，并展示文件名、媒体类型、大小和下载入口。页面不得自行拼接资源 ID、Conversation ID 或存储路径。

#### Scenario: 展示可下载资源
- **WHEN** 成功 Task 的资源清单查询返回一个或多个资源
- **THEN** 页面展示每个资源的安全元数据和服务端提供的下载 URL

#### Scenario: 资源不可用
- **WHEN** 服务端返回资源不可用或资源列表为空
- **THEN** 页面显示受控资源不可用状态，不伪造下载文件或结果内容
