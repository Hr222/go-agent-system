## Why

TM-07.4 已能在受信任 Worker 中生成 Tender 文件，并把结果保存在 `.runtime/` 内部结果存储中，但 Task 的安全状态只返回摘要和指纹，调用方没有受主体与会话约束的资源引用，也无法通过现有附件下载能力取得生成文件。TM-08 前端联调需要一个稳定的结果资源契约，因此现在补齐 Task 结果到 Attachment 资源的安全桥接。

## What Changes

- 为具有 Conversation 绑定的已完成 Tender Task 结果建立主体绑定、会话绑定的 Attachment 资源记录，并以资源元数据替换内部结果存储中的文件字节交付职责；无 Conversation 的既有 MCP 调用保持内部结果保存，避免改变其已接受 Task 的执行语义。
- 在 Task 结果查询边界增加只读的资源元数据读取能力，返回资源 ID、文件名、媒体类型、大小、哈希和现有下载入口所需的会话绑定信息；不返回文件字节、物理路径、内部结果引用或租约。
- 使异步 Tender Executor 的结果保存具有幂等性：同一 Task 重放不得产生重复资源；任一产物保存失败时清理本次已保存资源并以受控错误结束。
- 复用现有 AttachmentStoragePort 和主体/Conversation 访问校验，不新增通用 Task 创建、Executor 注册或绕过授权的下载入口。
- 补充 Task HTTP、Attachment 访问隔离、重启恢复和失败清理的自动化验证，并更新架构与进度文档。

## Capabilities

### New Capabilities

- `task-result-resources`: 为已完成的受信任 Task 保存和读取主体隔离的结果资源元数据，并复用既有附件下载契约。

### Modified Capabilities

- `agent-artifact-download`: 增加异步 Task 结果资源与现有 Agent 产物下载契约之间的安全衔接，保持主体、会话、TTL 和统一不可用响应规则不变。
- `owned-task-http-management`: 增加已完成 Task 的结果资源元数据查询，不扩大 Task HTTP 的创建、领取、续租或结果写回权限。

## Impact

- 影响 `app/business/agents/tender` 的结果端口和 Executor、`app/platform/attachment` 的资源契约、`app/platform/task` 的只读结果资源 Application，以及 Task/Attachment HTTP Schema、路由和 Composition Root 绑定。
- 复用现有文件系统附件存储和 `.runtime/` 结果存储；不引入数据库迁移或外部 Provider 变化。
- HTTP 契约新增受主体隔离的资源元数据查询，现有附件下载 URL 和错误语义保持兼容。
- 结果资源仍受附件 TTL、主体和 Conversation 绑定约束；不把文件字节、Prompt、Provider 响应、lease 或物理路径写入 Task/Event/Conversation 投影。
