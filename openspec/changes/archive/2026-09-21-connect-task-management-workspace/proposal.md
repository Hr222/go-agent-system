## Why

Agent 工作区目前展示的是硬编码任务和静态详情，用户看不到 Dialogue/Agent 实际创建的 Task，也无法观察运行状态、事件、取消或重试结果。Task Management 后端已经具备 owner-scoped 查询和命令接口，现在需要把现有视觉工作区接到这些真实接口上，形成可用的任务入口。

## What Changes

- 增加前端 Task API client 和 React Query 查询/命令 hooks，映射任务列表、详情、事件、取消和重试接口。
- 将 Agent 总览、Tender Agent 任务列表和任务详情页改为读取真实 Task 数据，并对运行中任务进行有限轮询。
- 在任务详情中展示真实状态、时间、失败信息和事件时间线；命令操作使用服务端返回结果并刷新缓存。
- 增加加载、空列表、未认证、任务不可用和请求失败状态，不再用伪造任务数据冒充后端结果。
- 保留任务创建的受信任边界；浏览器本 Change 不新增任意 Task 创建接口。

## Capabilities

### New Capabilities

- `task-management-workspace`: 在 Agent 工作区消费并操作 owner-scoped Task 数据。

### Modified Capabilities

- `owned-task-http-management`: 前端正式消费现有任务查询、事件和命令契约，不改变后端路径和权限规则。

## Impact

- 影响 `frontend/src/features/task-management`、Agent/Tender 页面、路由和相关样式/测试。
- 不改变 PostgreSQL schema、Task 状态机、后端 HTTP 响应字段或任务创建权限。
- 需要部署环境提供已认证主体配置；匿名主体访问任务时前端显示受控的未授权状态。
- 不涉及 Workflow 执行、结果资源下载或多 Agent 编排。
