## Context

TM-07.3 已提供 Agent Call 到受信任 Task 提交器的桥接，但桥接只产生排队任务，不负责消费。当前 Tender 的 `generate_bid_skeleton` 仍由同步 Agent Runtime 直接执行；它的输入通常已经由 Attachment 能力解析为服务端 `ResolvedAttachment`，不能再用通用 JSON 字符串化保存。

本 Change 需要把已有 Task Worker 与 TenderApplication 连接起来，同时保持 Task Domain、HTTP/MCP 适配器和 Tender 业务层的边界。取消、恢复和重试继续由既有 Task Application 负责，Tender Executor 只观察取消并将业务异常转换成安全执行结果。

## Goals / Non-Goals

**Goals:**

- 只为 `agent.tender.generate_bid_skeleton` 登记一个固定异步档案和 `tender.generate_bid_skeleton` Task 类型。
- 以已绑定主体的 Attachment 作为输入快照来源，生成确定性指纹，并把附件引用、会话绑定、文件名和用户焦点作为受控内部执行元数据传递给 Worker。
- 让固定 Tender Executor 通过 Attachment Port 读取快照、调用现有 TenderApplication，并把成功、输入缺失、取消、模型配置失败和可重试上游失败映射为 Task Worker 结果。
- 保留 Task Worker 的 lease 续租和协作式取消边界，并为后续结果资源映射保留内部结果存储 Port。
- 通过 Composition Root 组装所有绑定；无公开创建/领取/回写路由，无动态 Executor 注册。

**Non-Goals:**

- 不改变 Task 状态机、RecoveryCoordinator、RetryScheduler 或 Task HTTP 查询/取消/重试协议。
- 不让 Tender 直接依赖 Task Repository、SQLAlchemy、Worker 实现或 Provider SDK。
- 不实现 TM-07.5 的结果资源 HTTP 映射、下载协议或前端页面。
- 不把 `extract_bid_format_section`、`verify_extraction_boundary`、LangGraph、Subagent 或 Workflow 接入异步任务。

## Decisions

### 1. 复用 Attachment 作为输入快照后端

快照 Port 只接受已通过附件解析的 `ResolvedAttachment`，使用其 `AttachmentRef` 的 `attachment_id`、文件名、媒体类型和 sha256 计算指纹，并保存 `user_focus`、conversation_id 等有限元数据。Worker 通过 `AttachmentStoragePort.read` 和 Task owner 重新校验访问主体后读取内容。

这样不会把文件字节写入 Task JSON 或事件，也不新增第二份文件存储。附件过期或被消费时，Executor 返回安全的不可重试输入失败；后续若需要独立快照保留期，只需替换快照 Port，不改变 Agent→Task 授权边界。

### 2. 使用 Task 内部元数据传递 opaque 引用

TM-07.3 的 `AgentTaskInputSnapshot.snapshot_reference` 在提交时写入档案允许的内部 `snapshot_reference` 字段，并可携带 `conversation_id`、`file_name`、`user_focus` 等有限字符串。现有 `TaskView` 和事件投影不暴露 `display_metadata`，因此这些值只进入受信任 Worker 上下文；字段仍受 `TrustedTaskSubmissionProfile` 白名单校验，调用方不能覆盖。

Worker 上下文新增可信 `owner_subject`，Executor 不接受调用方提供的主体。后续可以在不改变公开契约的情况下把这组元数据迁移到独立 execution metadata 列。

### 3. 固定 Tender Executor 与错误分类

`TenderTaskExecutor` 依赖 TenderApplication、AttachmentStoragePort 和一个内部 `TenderTaskResultStorePort`。它读取并校验单个快照后构造 `TenderGenerateSkeletonCommand`；在调用前后检查取消，在长调用期间通过上下文 `renew_lease` 续租。成功结果计算稳定指纹，将分析和产物数量写入安全结果存储，Task 只记录有限摘要和指纹。

Tender 输入、文档解析、分析契约和渲染错误归类为不可重试；模型服务未配置归为不可重试；上游服务错误归类为可重试并按固定退避时间返回 `retry_at`。原始异常、Prompt、文件内容和 Provider 响应不进入 Task 事件、日志或结果摘要。

### 4. 结果存储只做内部插口

Executor 通过 `TenderTaskResultStorePort.save(task_id, owner_subject, result)` 保存已验证的 `TenderGenerateSkeletonResult` 的安全内部副本或资源引用。当前实现提供进程内测试替身和文件系统适配器，适配器只写 `.runtime/`；它不添加 HTTP/MCP 路由。TM-07.5 再决定如何把该引用映射为 Attachment 资源和下载响应。

### 5. Composition 固定路由

Composition 为 `agent.tender.generate_bid_skeleton` 创建 `AgentTaskRoute`，档案固定 task type、最大尝试次数、手动重试和元数据字段；同一处组装 `TenderTaskInputSnapshotProvider`、受信任提交服务、Tender Executor Registry 和 Worker。默认未注入这些依赖时不注册异步路由，其他 Agent 能力继续走同步策略。

## Risks / Trade-offs

- [附件在任务执行前过期] → 返回 `INPUT_SNAPSHOT_UNAVAILABLE` 不可重试失败；未来可替换为独立快照存储。
- [Task 内部元数据误被当作业务展示字段] → TaskView 不投影 display_metadata，档案只允许固定字段，增加架构测试禁止公开序列化该字段。
- [TenderApplication 生成文件但结果资源尚未可下载] → 当前只保存内部结果副本和安全摘要，明确由 TM-07.5 负责资源映射。
- [LLM 调用超时或 Worker 崩溃] → 使用已有 lease 续租、过期恢复和固定 retry_at；Executor 不自行修改 Task 状态。
- [重复执行产生重复结果副本] → 以 task_id/attempt 作为结果存储幂等键，重复终态回写由既有 Task 命令幂等保护。

## Migration Plan

1. 增加 Tender 快照 Port、Executor 和结果存储 Port，扩展桥接的内部引用传递与 Worker owner 上下文。
2. 在 Composition Root 固定注册 Tender 路由和 task type；未配置附件或结果存储时保持异步能力不可用，不影响同步路径。
3. 使用内存替身覆盖成功、主体隔离、快照缺失、取消、可重试失败和幂等场景，再运行全量后端和 OpenSpec 校验。
4. 若回滚，只移除 Tender 异步路由和 Worker 绑定；既有 Task 数据仍可由安全查询和手动取消/重试管理。

## Open Questions

- TM-07.5 是否将结果存储迁移到 Attachment 资源表，还是保留独立的 Tender 结果仓储；本 Change 只固定 Port，不冻结资源 API。
- 独立快照保留期是否需要超过当前 Attachment retention；如需要，后续只替换快照适配器，不改变 Task 或 Agent Call 契约。
