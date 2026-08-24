## Context

Conversation 管理服务和 `DELETE /api/v1/conversations/{conversation_id}` 已具备基础实现，但删除子 change 需要独立验证真实持久化行为、主体边界和 Chat 删除确认。数据库中的 `conversation_message` 与 `conversation_event` 均通过外键 `ON DELETE CASCADE` 关联 Conversation，删除父记录应在同一事务中清理这些事实。

## Goals / Non-Goals

**Goals:**

- 从会话菜单触发单个会话删除，并在请求前展示二次确认。
- 服务端先解析可信主体并校验会话归属，再调用 Conversation 写端口删除父记录。
- 由 PostgreSQL 级联删除消息和事件；任何数据库异常回滚事务。
- 删除成功后失效列表缓存；若删除当前会话，同时清理 active conversation、消息和编辑草稿。
- 覆盖真实数据库级联、匿名、越权、无效 UUID、不存在会话和失败回滚测试。

**Non-Goals:**

- 不实现软删除、回收站、恢复、多选或批量删除。
- 不改变消息、事件的独立写入契约，不新增删除专用数据库迁移。
- 不处理置顶或分享。

## Decisions

### 1. 真实删除 Conversation 父记录

应用层只暴露主体范围的删除用例，具体 repository 对 `ConversationRecord` 执行 `session.delete` 并提交事务。相比前端隐藏或软删除，这能确保列表、历史和事件读取都立即不可见；不可恢复风险由 UI 二次确认和主体校验控制。

### 2. 依赖数据库级联而不是手工删除子表

`conversation_message.conversation_id` 和 `conversation_event.conversation_id` 已声明 `ON DELETE CASCADE`，repository 不直接操作子表，避免遗漏未来新增事实表。集成测试在同一 PostgreSQL schema 中插入父、消息和事件后删除父记录，并分别查询三张表确认全部清理。

### 3. 前端确认状态局部化

Chat 页面保存待删除会话标识，确认框关闭前不调用 mutation。确认成功后由 React Query 失效列表缓存；删除当前会话时清理本地 active id 与消息，失败则保留列表项并显示错误。

### 4. 失败处理与权限边界

HTTP 层把匿名、越权、不存在和无效 UUID 映射为受控拒绝；repository 异常回滚并向上抛出。删除接口不接受客户端 owner 参数，所有权只能来自可信主体。

## Risks / Trade-offs

- [删除不可恢复] → 确认前不请求，服务端仅允许当前主体删除，并在页面明确展示影响范围。
- [级联约束未在历史数据库中生效] → 在现有 PostgreSQL 目标库和测试 schema 中检查外键定义，并补真实级联测试。
- [删除当前会话后残留前端状态] → 删除成功同时清理 active conversation、消息和重命名编辑器，再刷新列表。
- [部分网络失败] → 单项删除失败不改变本地选择或列表项，显示可重试反馈。

## Migration Plan

无新增迁移。部署前确认历史数据库的消息和事件外键均为 `ON DELETE CASCADE`；若缺失，应先补兼容迁移再开放删除入口。代码回滚不恢复已确认删除的数据。

## Open Questions

无。后续多选删除属于独立子 change。
