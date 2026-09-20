## Why

当前 Tender MCP 适配器直接调用 `TenderApplication`，绕过了 Agent Management 已有的能力目录、主体权限、输入契约和统一分发边界。这样 MCP 与 Chat 入口会形成两套授权和错误处理路径，也会让后续异步 Task 接入时需要再次改造 MCP。

## What Changes

- 将三个现有 Tender MCP 工具的执行路径收敛到 `AgentCallDispatcher`。
- MCP 适配器只负责 MCP 参数解析、Base64 解码、结构化调用构造和 MCP 结果/错误映射，不直接调用 `TenderApplication`。
- 为 MCP 请求定义协议到 `RequestPrincipal` 的受控主体映射入口；客户端自报的权限、能力代码和分发键不作为授权依据。
- 继续使用平台能力目录中 Tender 的固定能力代码、输入 Schema、权限和 `dispatch_key`。
- 保持三个工具名称、输入字段、同步返回结构、MCP Embedded Resource 表达和稳定错误码兼容。
- 对主体不可用、能力不可用、输入不合法、运行时失败和结果投影失败提供不泄漏内部细节的 MCP 错误。
- 不在本 Change 中创建 Task、改变 Task 状态机、增加异步 MCP 返回、实现 MCP 外部认证系统或扩展 Tender 业务能力。

## Capabilities

### New Capabilities

- `tender-mcp-agent-dispatch`: 定义 Tender MCP 作为外部 Agent 协议适配器通过统一 Agent 分发边界执行的行为。

### Modified Capabilities

- `tender-agent-skeleton`: 修改 MCP 工具的执行路径和主体/错误边界，但保持现有工具兼容性与 Tender Application 业务语义。
- `controlled-agent-dispatch`: 增加 MCP 协议适配器作为统一 Dispatcher 的调用方，并保持服务端目录、权限、固定分发键和安全结果投影规则。

## Impact

- 影响 `app/interfaces/agent/tender_mcp.py`、MCP 组装入口、AgentCallDispatcher 的调用适配以及相关测试和架构边界检查。
- 可能调整 MCP Server 工厂参数，使其接收 Dispatcher 和协议主体解析依赖；不向 MCP 适配器注入 Repository、Session、Task 或 Provider SDK。
- 不新增数据库表、字段、Task 记录或持久化事务；同步 Tender 仍是一次请求内完成。
- 不改变 MCP 挂载路径、工具名称或 Tender Application Command 的业务字段语义。
- 外部认证系统不在本 Change 内实现；本 Change 只定义可替换的主体解析边界，并在未提供可信主体时拒绝受保护 Tender 能力。
