## Context

当前 Agent 页面位于 `mock-workspace`，任务列表和详情全部由常量组成。后端 `/api/v1/tasks` 已提供 owner-scoped 列表、详情、事件、取消和重试接口，响应使用 snake_case 字段；前端已有 Axios、TanStack Query 和统一 API 错误处理约定。默认服务端主体解析模式是 anonymous，因此未配置认证时 Task API 会返回 403。

## Goals / Non-Goals

**Goals:**

- 建立独立的 Task API/types/hooks 边界，避免页面直接拼接 Axios 请求。
- 用真实任务数据替换 Agent/Tender 页面上的任务假数据。
- 对 queued/running/retry_wait/cancel_requested 等活动状态轮询，对终态停止轮询。
- 让取消、重试操作具备 pending、错误和缓存刷新状态。
- 保持现有页面视觉布局和导航路径，逐步替换数据源。

**Non-Goals:**

- 不在浏览器暴露 trusted submission API，不新增公开创建任务能力。
- 不实现结果文件下载、资源授权或 Workflow 编辑器。
- 不把 owner_subject 原样作为用户可编辑字段，也不绕过后端主体隔离。

## Decisions

1. **新建 task-management feature 边界。** API 映射、hooks 和展示类型放在独立 feature；既有 mock 页面只负责布局和导航。相比在大页面中直接嵌入请求，这样可以单测协议映射并为后续任务工作区拆分保留边界。

2. **使用 React Query 管理状态。** 列表、详情和事件使用 query；取消和重试使用 mutation，成功后精确失效对应任务查询与列表查询。活动任务通过 `refetchInterval` 轮询，终态返回 `false`。

3. **页面以 UUID 任务标识为真实入口。** 旧的 `TDR-...` 示例链接不再作为真实详情请求；无真实任务时显示空状态。这样不会用无效 ID 触发后端 422/404，也不会继续制造“任务已完成”的假象。

4. **认证失败是产品状态，不是 mock fallback。** API 错误保留 `toApiError` 语义，页面显示“当前工作区未连接到任务主体”的受控提示；不静默回退到硬编码数据。

## Risks / Trade-offs

- [任务列表为空时页面信息密度下降] -> 提供明确空状态和回到对话/Agent 入口，不填充虚假记录。
- [轮询增加请求量] -> 仅对活动状态启用，间隔固定且页面卸载自动取消。
- [服务端 anonymous 模式导致开发环境 403] -> 在页面显示认证提示，并在部署/本地配置中使用 static principal；不从前端伪造主体。
- [后端未来增加字段] -> API mapper 对未知字段保持忽略，当前展示只依赖已归档契约字段。

## Migration Plan

1. 发布前端 feature 和页面接线。
2. 在运行环境配置已认证主体后验证列表、详情和命令操作。
3. 无需数据库迁移；回滚只需恢复前端页面路由和 feature 代码。

## Open Questions

- 任务结果资源和下载按钮留给后续独立 Change，避免把文件授权与任务查询混在一起。
