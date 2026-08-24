## Why

会话话题概括已经可以通过主体范围接口修改，但 Chat 侧栏需要一个明确、就近的重命名入口。将重命名作为独立子 change，可以先完成会话名称维护，再按依赖顺序实现删除和置顶。

## What Changes

- 在每条会话的更多菜单中提供“重命名”入口。
- 复用现有 `PATCH /api/v1/conversations/{conversation_id}/topic-summary` 契约保存或清除名称。
- 支持编辑、保存、取消、空白清除和保存失败后的草稿保留。
- 保存成功后刷新会话列表缓存并显示反馈；不得切换当前会话或修改消息历史。

## Capabilities

### New Capabilities

- `conversation-rename`: 定义 Chat 侧栏重命名交互，以及主体范围话题概括更新的调用约束。

### Modified Capabilities

- `chat-conversation-list-management`: 增加从会话菜单进入重命名、保存和失败反馈的要求。

## Impact

- 影响 `frontend/src/features/chat/pages/ChatPage.tsx`、会话列表 API/hooks 的缓存失效行为及组件测试。
- 复用现有话题概括 HTTP、应用服务、持久化和主体访问校验，不新增后端路由或数据库迁移。
- 不包含会话删除、置顶、批量操作或分享实现；这些属于后续独立子 change。
