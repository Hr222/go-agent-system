## Why

TM-07.4 已能把内部 Tender 调用提交为 Task，但正常服务启动没有持续运行的 Worker 入口；同时 Dialogue 收到 `accepted` 后会将其降级为失败，无法把安全执行引用交还给 Chat。这样 Task 基础设施虽已存在，内部异步调用却不能形成可用闭环。

本 Change 只完成第一个内部异步 Consumer 的运行与交接，不扩展外部 Tender MCP、浏览器 Task 工作台、结果下载、Workflow 或多 Agent 编排。

## What Changes

- 提供独立、受信任的 Tender Task Worker 运行入口，以有限轮询和每轮独立资源生命周期消费既有 `tender.generate_bid_skeleton` Task；HTTP 进程不内嵌 Worker。
- 让 Dialogue、Agent Turn 与 Chat 确认响应保留 `accepted` 状态，并返回受控的 `execution_reference`；Conversation 的既有 `agent_call` 事件记录该引用，但不写入原始输入、lease 或结果内容。
- 保持异步 Task 终态只由既有 Task 查询/事件契约观察；本 Change 不把 Task 完成结果回灌为 Conversation assistant 消息。
- 同步运行说明、架构和进度文档，区分“Worker 可运行”和“未来 Workflow/前端尚未实现”。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `task-worker-execution`: Worker 必须有独立的受信任运行入口和受控轮询生命周期。
- `dialogue-agent-invocation`: 已接收的异步 Agent 调用必须作为受控非失败状态记录并返回执行引用。
- `dialogue-agent-gateway-integration`: Chat 确认响应必须能表达异步调用已接收，而不伪报为完成或失败。

## Impact

- 影响 Task Worker 的 Composition 与新的本地运行模块，以及应用配置、运行说明和相应测试。
- 确认接口既有 `status` 与 `execution_result` 字段将开始合法返回 `accepted` 和受控 `execution_reference`；不新增 HTTP 路由或请求字段。
- 不修改 Task 持久化模型、状态机、外部 Provider 契约、外部 MCP 输出或敏感数据边界。
