## ADDED Requirements

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

任务详情页 MUST 查询真实任务详情和 owner-scoped 事件，并展示加载、失败和事件为空状态。

#### Scenario: 任务详情成功
- **WHEN** 任务详情和事件查询成功
- **THEN** 页面显示任务状态、创建/更新时间、结果摘要或失败信息，以及按顺序排列的事件

#### Scenario: 活动任务
- **WHEN** 任务状态为 queued、running、retry_wait 或 cancel_requested
- **THEN** 页面周期性刷新任务和事件，直到进入终态或页面离开

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
