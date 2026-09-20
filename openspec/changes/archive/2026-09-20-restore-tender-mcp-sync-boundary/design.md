## Context

外部 Tender MCP 与内部 Dialogue 共用 `ApplicationContainer`，但两者的执行语义不同：MCP V1 是一次请求内完成并返回 `EmbeddedResource`；Dialogue 才可以把指定能力交给 Task Worker 异步执行。当前共享的 `agent_call_dispatcher()` 默认注册 Tender 异步档案，导致 MCP 入口可能返回 `accepted` 而不是文件结果。

## Decisions

### 1. 在 Composition Root 显式区分 Dispatcher 模式

`ApplicationContainer.agent_call_dispatcher()` 增加仅由 Composition 调用方使用的模式参数。默认内部路径保留 TM-07.4 的异步 Task Route；`tender_mcp_dispatch_scope()` 明确请求同步模式，构造不带 Task Route 的 Dispatcher。两种 Dispatcher 仍共享能力目录、权限策略、固定 dispatch key、Tender Runtime 和附件 Port。

### 2. MCP 保持既有同步协议

MCP 的 `generate_bid_skeleton` 继续通过同步策略执行，成功时由既有适配器读取安全附件并返回结构化分析和 `EmbeddedResource`。由于 Dispatcher 没有异步档案，该请求不会创建 Task、Attempt、Event 或内部 Task 结果资源。

### 3. 撤回 Task 结果下载扩展

本修复撤回 TM-07.5 引入的结果资源存储、Task 资源查询 HTTP、正式规格、归档工件和测试。TM-07.4 恢复为仅保存内部结果副本，外部 MCP 不使用 Task 或 Attachment 下载协议。未来若需要外部异步 Tender，必须另行定义 MCP 的提交、状态查询和结果获取契约。

## Safety and Compatibility

- 外部 MCP 恢复为 TM-07.2 约定的同步行为和输出形状。
- 内部 Dialogue 默认仍注册 `agent.tender.generate_bid_skeleton` 的固定异步档案，因此 TM-07.4 的 Worker、取消、重试和幂等能力不回退。
- 不修改数据库、Task 状态流转或已有 Attachment 生命周期；撤回的资源路由不成为兼容性承诺。

## Verification

- 组合测试检查 MCP Dispatcher 的 Task Route 为空。
- 组合测试检查默认内部 Dispatcher 仍包含 Tender 异步 Route。
- 检查当前代码和正式规格不再包含 Task 结果资源或浏览器下载协议。
- 运行 Tender MCP、Agent Task Bridge、异步 Tender 和架构边界相关测试。
