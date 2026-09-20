## MODIFIED Requirements

### Requirement: Tender MCP 工具必须保持外部同步结果协议

Tender MCP 的三个工具 MUST 通过统一 Agent 分发执行，但外部 MCP Dispatcher MUST 使用同步执行策略，不得注册或选择内部异步 Task 档案。`generate_bid_skeleton` 成功时 MUST 继续返回既有结构化分析和 `EmbeddedResource` 文件结果。

#### Scenario: 外部 MCP 调用骨架生成工具

- **WHEN** 已解析的可信主体通过能力、权限和输入复核，并调用 `tender.generate_bid_skeleton`
- **THEN** MCP 使用不含异步 Task Route 的 Dispatcher 执行 Tender Agent
- **AND** 调用在当前 MCP 请求内返回结构化分析和 `EmbeddedResource`
- **AND** 不创建 Task、Attempt、Task Event 或 Task 结果资源清单

#### Scenario: 内部异步档案不得污染 MCP

- **WHEN** Composition 同时为内部 Dialogue 注册了 `agent.tender.generate_bid_skeleton` 异步档案
- **THEN** MCP Scope 仍使用同步 Dispatcher
- **AND** MCP 不返回 `accepted`、`execution_reference` 或浏览器下载 URL

#### Scenario: MCP 其他工具保持同步行为

- **WHEN** 主体调用 `tender.extract_bid_format_section` 或 `tender.verify_extraction_boundary`
- **THEN** 工具继续使用同步 Agent Runtime
- **AND** 不创建 Task、Attempt 或 Task Event
