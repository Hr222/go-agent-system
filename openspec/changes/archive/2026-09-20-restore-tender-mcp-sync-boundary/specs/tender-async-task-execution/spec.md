## MODIFIED Requirements

### Requirement: Tender 异步 Task 路由必须限制在内部调用边界

系统 MUST 只为内部受控 Agent 调用登记 `agent.tender.generate_bid_skeleton` 异步档案。外部 Tender MCP 即使调用同一能力代码，也 MUST 使用同步 Dispatcher，不得因共享 Composition Root 而进入 Task Worker。

#### Scenario: 内部调用进入异步 Task

- **WHEN** 内部 Dialogue 调用已登记的 `agent.tender.generate_bid_skeleton` 能力
- **THEN** 系统按固定档案创建 `queued` Task 并返回 `accepted` execution reference
- **AND** 后续由固定 Tender Executor 消费

#### Scenario: 外部 MCP 调用保持同步

- **WHEN** 外部 Tender MCP 调用 `tender.generate_bid_skeleton`
- **THEN** 系统使用同步 Dispatcher 在当前请求内完成调用
- **AND** MCP 返回既有结构化文件结果，不创建 Task 或返回 `execution_reference`
