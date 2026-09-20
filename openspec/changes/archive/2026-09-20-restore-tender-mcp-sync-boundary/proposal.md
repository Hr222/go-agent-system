## Why

TM-07.4 为内部 Agent 调用增加了 Tender 异步 Task 路由，但 Composition Root 目前让外部 Tender MCP 复用同一个带异步档案的 Dispatcher。这样 `generate_bid_skeleton` 可能从原有的同步 MCP 结果变为 `accepted` 引用，外部调用方拿不到既定的 `EmbeddedResource` 文件结果。

TM-07.5 又把内部 Task 结果映射成带 Conversation 的 Attachment 下载资源，进一步把浏览器任务管理和外部 Tender Agent 混成同一条交付链路。当前目标是保留 Tender 作为外部可调用的基准 Agent，同时让内部 Task 能力为后续 Dialogue/Workflow 使用；两类入口必须隔离，并撤回这批偏离目标的代码和规格。

## What Changes

- 为 Composition Root 增加显式的 Dispatcher 装配模式：内部 Dialogue 使用 Tender 异步 Task 路由，外部 Tender MCP 使用同步 Dispatcher。
- 恢复 Tender MCP `generate_bid_skeleton` 的同步结构化结果和 `EmbeddedResource` 投影，不创建 Task、Attempt 或 Task Event。
- 增加组合测试，验证两类 Dispatcher 的异步路由集合不同，且内部 Dialogue 的异步 Tender 能力不被移除。
- 撤回 TM-07.5 引入的 Task 结果 Attachment 映射、资源 HTTP 路由、资源规格和测试；当前 Tender 外部 Agent 与内部 Task 都不依赖浏览器下载协议。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `tender-mcp-agent-dispatch`：外部 MCP 调用必须保持同步结果协议，不能进入内部异步 Task 路由。
- `tender-async-task-execution`：异步 Tender 路由仅用于内部受控调用，不改变外部 MCP 的同步行为。

## Impact

- 影响 `app/composition/root.py` 的 Dispatcher 组装、Tender MCP 的组合测试，以及撤回的 Task 结果资源 HTTP/存储边界。
- 不修改 Task 状态机、Attachment 存储、数据库结构、Tender 业务能力或 MCP 工具输入输出字段。
- 不新增外部异步查询、结果下载或浏览器任务管理协议；这些能力必须另行立项。
