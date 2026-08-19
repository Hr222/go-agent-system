## Why

P2.4-P2.6 已经完成结构化 Agent Call、策略校验和受控分发，但这些能力尚未进入 Dialogue Runtime，也没有把 Agent 调用结果关联到 Conversation。当前页面最多只能看到旧交互 Gateway 的执行结果，无法形成 V2 的“对话请求 -> 已确认 Agent -> 对话中的 Agent 结果”链路。

## What Changes

- 新增 Dialogue Agent Invocation 应用服务，在已有 Conversation 中接收一个结构化 `AgentCall` 和可选批准提议。
- 通过 P2.6 `AgentCallDispatcher` 执行单个已授权 Agent，并保留 `call_id`、Conversation 和运行关联标识。
- 将 Agent 成功结果或受控失败结果以不可执行的 Conversation 事件持久化，供历史读取和 P3.2 上下文续写使用。
- 新增一个 V2 对话 Agent 调用 HTTP 入口，并让交互页面能够提交会话、业务输入和确认后的 Agent 请求，展示执行状态与结果摘要。
- 保持现有 `/api/v1/llm/chat`、V1 Interaction Gateway 和 Tender MCP 接口不变；不在本 Change 生成最终自然语言回答。

## Capabilities

### New Capabilities

- `dialogue-agent-invocation`：在 Conversation 中执行一次已授权的结构化 Agent 调用并持久化结果事件。

### Modified Capabilities

- 无。

## Impact

- 后端新增 Dialogue Application 服务、Agent Result 事件领域契约、PostgreSQL 事件持久化适配器、V2 HTTP Schema/Route 和 Composition Root 组装。
- 前端交互页面新增 V2 Agent 调用路径和结果展示；不把 `dispatch_key`、权限、执行器或完整内部提议暴露给浏览器。
- 数据库新增 Conversation 事件表及 SQL 初始化脚本；不引入 Redis、任务管理、重试队列或 Workflow。
- Agent Runtime 结果必须转换为 JSON 安全对象；Tender 文件二进制只保存为受控资源引用/元数据，不直接写入 Conversation 事件。
