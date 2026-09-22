## Context

`TenderTaskExecutor` 已通过 `TenderTaskResultStorePort` 保存结果副本，但当前 `FilesystemTenderTaskResultStore` 只写入私有 JSON。Task 的 `display_metadata` 已由受信任 Agent 路由保存 `conversation_id`，输入附件存储已经具备 opaque ID、主体和 Conversation 双重校验、完整性验证及过期清理。任务工作区已经能读取成功状态和摘要。

## Goals / Non-Goals

**Goals:**

- 为会话绑定的成功 Tender Task 建立结果文件到 Attachment 资源的映射。
- 资源清单和下载都必须先通过 Task owner、Task 成功状态和 Conversation 绑定校验。
- HTTP 和前端只看到安全元数据与服务器生成下载 URL，不看到文件路径、内部 JSON、Task 输入或 Provider 输出。
- 资源写入保持幂等；部分写入失败时清理已创建附件并使 Task 以固定失败码结束。

**Non-Goals:**

- 不延长 Attachment 保留期，不引入对象存储或数据库资源表。
- 不支持非 Tender Task、未绑定 Conversation 的 Task 或任意浏览器上传结果。
- 不改变 Attachment 下载协议、Task Worker lease 或 Workflow 行为。

## Decisions

1. **结果文件复用 Attachment 存储。** Attachment 已拥有 opaque resource ID、文件完整性与 owner/Conversation 访问控制；结果适配器只保存 task-to-resource manifest。相比新建另一套文件下载系统，这避免复制安全模型和路径泄漏风险。

2. **结果资源 Application 从 Task 元数据推导 Conversation。** 资源查询只接收 `task_id` 和服务端解析的主体。Application 先读取 owner-scoped Task、确认 `succeeded`，再读取受信任的 `display_metadata.conversation_id` 并调用资源 Reader。相比让 URL 接收会话 ID，这不把授权上下文交给浏览器选择。

3. **下载复用 Attachment 路由。** 资源列表响应由服务器生成既有附件下载 URL，其中包含已验证的 Conversation 绑定。下载端点仍会独立校验主体、资源与 Conversation，URL 被篡改或跨主体转发不会获得内容。

4. **写入失败作为不可重试结果保存失败。** 在成功回写 Task 状态前，Executor 必须先保存内部结果和可交付资源。资源阶段失败时清理本次已创建附件并返回固定 `TENDER_RESULT_RESOURCE_STORE_FAILED`，不让 Task 成功却没有可信产物。

## Risks / Trade-offs

- [Attachment 默认保留期届满后任务仍显示成功但资源不可读] -> 资源清单查询和下载均返回不可用，前端明确显示资源已不可用；长期归档另立 Change。
- [同一 Task 的重复 Worker 执行] -> manifest 绑定 task/owner/conversation 并验证每个附件元数据，匹配时复用，不匹配时拒绝。
- [部分附件已写入、manifest 写入失败] -> Adapter 按同一访问上下文丢弃本次创建的附件和临时 manifest。
- [结果文件媒体类型不被 Attachment 允许] -> Adapter 返回受控失败，不能静默保存到未受保护位置。

## Migration Plan

1. 发布代码，不需要 SQL 迁移。
2. 新成功的会话绑定 Tender Task 会生成资源 manifest 和附件资源；旧 Task 无 manifest 时资源接口返回不可用。
3. 回滚仅需回滚应用代码；已生成 Attachment 继续由既有生命周期清理。

## Open Questions

- 长期保留、版本化和跨会话共享的结果资源留待对象存储/归档 Change 处理。
