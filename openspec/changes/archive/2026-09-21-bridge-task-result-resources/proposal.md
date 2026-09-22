## Why

Tender Task 成功后目前只保存内部结果和摘要，Agent 工作区无法安全列出或下载实际产物。历史版本曾尝试过资源桥接但随后被撤回；现在 Task 运行时和真实工作区已经就绪，需要按当前边界重新建立可审计的结果资源链路，而不是恢复旧耦合。

## What Changes

- 将会话绑定的 Tender 结果文件保存为既有 Attachment 存储中的主体绑定资源，并保留不可泄漏物理路径的资源清单。
- 新增 owner-scoped Task 结果资源查询接口；接口从已授权 Task 的受信任 `conversation_id` 元数据推导绑定，不接收浏览器提供的会话标识。
- 复用既有 Attachment 下载端点的 owner + conversation 校验，服务端为已授权资源生成下载 URL。
- 在任务详情中展示成功任务的真实产物和下载入口；资源不可用、过期或无会话绑定时显示受控状态。

## Capabilities

### New Capabilities

- `task-result-resources`: 已完成 Task 的结果资源保存、主体/会话校验、查询与下载投影。

### Modified Capabilities

- `owned-task-http-management`: 增加 owner-scoped Task 结果资源查询，不开放结果写入或存储内部信息。
- `tender-async-task-execution`: Tender Executor 保存会话绑定的交付资源，并将资源保存失败映射为受控任务失败。
- `task-management-workspace`: 成功任务详情显示服务端返回的结果资源和下载入口。

## Impact

- 影响 Tender Task 结果存储 Port/Adapter、Task Application、Composition Root、Task HTTP Schema/Route，以及前端 Task feature。
- 不新增数据库表，不改变 Task 状态机或公开任务创建能力。
- 依赖现有 Attachment 生命周期；资源到期、内容校验失败或绑定不一致时一律按不可用处理。
- 不涉及外部 Provider、Workflow 调度或多 Agent 编排。
