## Why

会话列表需要允许用户清理不再需要的会话。删除属于破坏性操作，必须在当前主体范围内执行真实数据库删除，并确保消息与 Agent 生命周期事件不会留下孤立数据。

## What Changes

- 在会话更多菜单中提供单项“删除”入口。
- 删除前展示二次确认，确认前不得发起删除请求。
- 通过当前主体范围的删除接口真实删除 Conversation 记录。
- 依靠数据库外键级联删除关联消息和事件；失败时事务回滚并保留数据。
- 删除当前会话后清理前端 active conversation、消息和编辑状态；删除其他会话后刷新列表并显示结果反馈。

## Capabilities

### New Capabilities

- `conversation-delete`: 定义当前主体真实删除会话及其级联事实的 HTTP、持久化和 Chat 交互契约。

### Modified Capabilities

- `chat-conversation-list-management`: 增加单项删除、二次确认、成功清理和失败保留要求。

## Impact

- 影响 Conversation 管理应用服务、写端口、PostgreSQL repository、Chat 会话菜单和删除确认 UI。
- 使用现有 `DELETE /api/v1/conversations/{conversation_id}` 契约；不新增数据库迁移，复用 `ON DELETE CASCADE`。
- 删除只作用于当前可信主体拥有的会话；匿名、越权、无效 UUID 和数据库失败均不得删除数据。
- 不包含置顶、多选、批量删除或分享功能。
