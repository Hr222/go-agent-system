## Context

当前 Tender 运行时返回 `GeneratedTenderArtifact`，其中包含文件字节。`AgentCallDispatcher` 为了保证 Conversation 事件可 JSON 序列化，会把字节替换成大小标记；`AgentResultProjector` 随后生成展示用 `resource_id`。这个标识并不对应可读取资源，因此聊天页面只能显示文件名。

附件暂存已有随机 ID、哈希校验、主体和会话绑定、TTL 清理机制，但元数据仅在进程内保存。后端重启会使仍在磁盘上的文件无法再通过访问校验，不能作为 Agent 结果下载的可靠存储基础。

## Goals / Non-Goals

**Goals:**

- 将 Agent 生成文件在受控分发边界写入服务端临时存储，并把可下载资源 ID 放进安全结果摘要。
- 通过当前主体和 Conversation ID 双重校验下载文件，始终不暴露物理路径、文件字节或其他主体的资源存在性。
- 使临时附件及 Agent 产物的访问元数据在后端重启后、TTL 内可恢复。
- 在聊天结果卡片提供直接下载操作。

**Non-Goals:**

- 不实现长期文件归档、文件版本管理、跨会话共享、预览或多文件打包。
- 不改变 Tender 生成、模型选择、确认策略或 Conversation 历史加载。
- 不为浏览器开放任意 Agent 调用或原始文件目录。

## Decisions

### 复用临时附件存储承载生成产物

`FilesystemAttachmentStorage` 已提供随机标识、完整写入、哈希校验、TTL 和访问上下文校验。Agent 分发器仅依赖 `AttachmentStoragePort`，在成功拿到 Agent 原始输出后，将符合 `file_name`、`media_type`、`content: bytes` 形态的 `artifacts` 或 `artifact` 写入该端口。写入后的引用替换原始字节，再进入 JSON 投影。

这样 Agent 应用层不访问文件系统，基础设施仍由 Composition Root 注入。与新建仅供 Tender 使用的存储相比，该做法也可复用给后续的图片、表格等 Agent 产物。

### 在附件目录保存原子元数据清单

每个暂存目录写入不含文件内容的元数据清单，记录引用、主体、会话和到期时间。存储初始化时恢复未到期记录，并清理无效、过期或校验不通过的目录。清单通过临时文件替换写入。

使用 PostgreSQL 新表也能实现恢复，但这会增加迁移和文件/数据库双写一致性。本 change 的临时文件生命周期与现有本地附件存储一致，故选择同目录清单；它不用于长期留存。

### 下载地址由会话作用域绑定

新增 `GET /api/v1/attachments/{attachment_id}/download?conversation_id={uuid}`。路由以当前 `RequestPrincipal` 和 URL 中的 Conversation ID 构造受信访问上下文，只在二者与资源记录都匹配、且资源仍可用时返回 `FileResponse` 和 `Content-Disposition: attachment`。

对未知、过期、已消费或无权资源统一返回受控的不可用响应，不区分“资源不存在”和“无权访问”。页面从当前活动会话和结果中的 `resource_id` 组成地址，下载按钮不会接触文件内容。

### 产物存储失败使调用受控失败

如果任一生成文件未能完整暂存，分发器删除该次已暂存产物并返回 `AGENT_ARTIFACT_STORE_FAILED`。不会写入含有无效资源 ID 的成功事件，也不会把原始字节持久化。

## Risks / Trade-offs

- [临时文件占用磁盘] → 复用既有大小限制与 TTL 清理；只保留成功暂存的产物。
- [文件与元数据清单异常中断] → 使用临时文件原子替换，初始化时验证并清理不完整目录。
- [匿名主体没有用户隔离] → 仍强制 Conversation ID 匹配；正式用户模块接入后由 `RequestPrincipal` 自动提供主体隔离。
- [旧的占位 `resource_id` 不可下载] → 它们没有对应文件字节，下载接口返回受控不可用；重新执行后生成新资源。

## Migration Plan

1. 发布后，新上传附件和新生成产物写入元数据清单。
2. 已在内存、无清单的旧附件与旧占位结果不迁移，仍按不可用处理；用户重新上传或重新执行即可。
3. 回滚时移除新路由和前端入口即可，TTL 目录会由现有清理逻辑回收。

## Open Questions

无。当前采用现有临时保留期，长期归档需求另立 change。
