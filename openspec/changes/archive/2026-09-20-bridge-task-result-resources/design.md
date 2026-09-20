## Context

TM-07.4 的 Tender Worker 已能生成并校验文件，但 `TenderTaskResultStorePort` 当前只把完整结果写入 `.runtime/`，返回内部 `tender-result:<task_id>` 引用。该引用不能用于浏览器下载，Task 安全投影也没有资源元数据；现有 Attachment Storage 已具备主体、Conversation、TTL、完整写入和重启恢复能力，附件下载接口也已有统一的不可用响应。既有 Tender MCP 调用没有 Conversation 关联字段，不能被本 Change 隐式伪造为浏览器会话。

本 Change 只补齐“异步 Task 结果如何成为受控资源”的边界。它必须保持 Task 生命周期和 Worker lease 契约不变，并让 TM-08 前端能够先查询资源元数据，再调用既有附件下载接口。

## Goals / Non-Goals

**Goals:**

- 在固定 Tender Task 成功保存结果时，将每个生成文件以当前 Task owner 和 Conversation 绑定的 Attachment 资源暂存。
- 按 Task 和可信主体提供只读资源元数据查询，返回可用于既有下载接口的安全字段。
- 以 Task ID 和产物序号保证重试、Worker 重放和进程重启后的资源引用幂等。
- 任一产物暂存失败时清理本次已暂存资源，并返回固定的结果资源保存错误。
- 复用 Attachment Storage 的 TTL、哈希校验、重启恢复和主体/Conversation 校验。
- 保持无 Conversation 的既有 MCP 异步 Task 能完成内部结果保存，不在本 Change 为其新增资源查询或下载协议。

**Non-Goals:**

- 不修改 Task 状态机、Attempt、lease、取消、重试调度或公开创建边界。
- 不新增通用文件上传、任意资源创建、资源转移或资源分享接口。
- 不实现 TM-08 前端、浏览器轮询组件或 TM-09 E2E。
- 不改变同步 Agent 产物的现有投影和下载协议，不引入数据库迁移或外部 Provider。

## Decisions

### 1. 结果资源由受信任结果保存端口创建

在 Tender 结果保存适配器内部，仅当快照包含 Conversation 时逐个调用 `AttachmentStoragePort.stage_attachment`，上下文使用 Worker 可信 owner 和该 Conversation。结果资源记录只保存 AttachmentRef 的安全元数据和 Task/产物序号；文件字节仍由 Attachment Storage 管理。无 Conversation 的 MCP Task 保持 TM-07.4 内部保存，不生成一个无法被现有下载接口安全访问的伪资源。

备选方案是让 HTTP 查询时从 `.runtime` 结果文件临时生成附件。该方案会让读取请求承担写入和权限绑定，导致重试不幂等，也会把受信任执行职责泄漏到接口层，因此不采用。

### 2. 使用 Task 级资源清单保证幂等

结果资源适配器在 `.runtime/` 下保存一个原子替换的资源清单，键为 `task_id`，条目包含产物序号、AttachmentRef 安全字段、owner 和 Conversation 绑定。已存在且完整的清单直接返回，不重复暂存；清单不完整或附件校验失败时按失败处理并清理孤立资源。

该清单是内部恢复索引，不作为 HTTP 文件接口返回；Task/Event 仍只保存原有安全摘要和指纹。后续若需要持久化到数据库，可在不改变 Port 和公开契约的前提下替换适配器。

### 3. 结果查询只读且按双重范围校验

新增 Task Result Resource Application/Port，先按可信主体读取 Task，再要求请求提供 Conversation ID，并确认 Task 的快照绑定与资源清单一致。HTTP 增加 `GET /api/v1/tasks/{task_id}/resources?conversation_id=...`，只返回资源 ID、文件名、媒体类型、大小、sha256 和既有下载地址；主体、Task、Conversation 或资源任一不匹配都统一返回不可用结果。

下载继续走现有 `/api/v1/attachments/{attachment_id}/download`，由 Attachment Storage 再次校验主体和 Conversation。资源查询不返回文件字节、物理路径、lease、内部结果引用或 Provider 响应。

### 4. 失败与生命周期复用现有附件语义

保存任一产物失败时，适配器按本次清单记录删除已经创建的附件，不写入成功清单；Worker 收到固定的 `TENDER_RESULT_RESOURCE_STORE_FAILED` 不可重试错误。附件 TTL、重启恢复、哈希校验和过期清理由既有 Attachment Storage 负责；资源查询发现附件已过期或校验失败时返回统一不可用结果，不泄漏具体原因。

### 5. Composition Root 固定绑定

Composition Root 为 Tender Worker 注入资源化结果保存适配器和资源查询 Application。HTTP 只依赖 Application/Port，不直接访问 `.runtime`、Attachment Storage 内部记录或 Task Repository。除固定 Tender task type 外，不为客户端增加资源生产或 Executor 注册能力。

## Risks / Trade-offs

- [资源清单与附件目录短暂不一致] -> 采用临时清单、完整写入后原子替换，并在启动/查询时校验附件引用；不完整清单按不可用处理并清理孤立目录。
- [Attachment TTL 早于 Task 可见时间] -> 资源查询沿用统一不可用响应；后续可在独立 Change 调整保留策略，不把 TTL 逻辑复制到 Task。
- [文件资源占用运行时磁盘] -> 复用现有附件清理机制和大小限制；本 Change 不增加永久对象存储或后台归档。
- [多 Worker 同一 Task 重放] -> 以 Task ID 清单和原子创建策略保证返回已有资源；任何写入冲突都转换为固定安全错误，不能产生第二套资源。

## Migration Plan

无数据库迁移。部署时先发布资源 Port、适配器和查询路由，再启用 Tender Task 的资源化结果保存；旧 `.runtime` Tender 结果文件不自动转换为公开资源，避免在无法确认 Conversation 绑定时扩大访问范围。回滚时停止新结果资源查询并保留现有附件 TTL 清理，旧内部结果文件仍可由既有 Worker 逻辑处理。

## Open Questions

- 无。TM-08 可直接使用资源元数据中的下载地址和现有附件下载接口；资源预览、延长 TTL、批量打包和跨 Conversation 分享另行建 Change。
