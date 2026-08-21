## Why

后端已能分页读取 Conversation 历史，但该能力只能由应用层调用。浏览器无法在刷新或切换会话后恢复真实消息。

## What Changes

- 新增当前主体读取指定 Conversation 元数据和有序消息页的 HTTP 契约。
- 复用 Conversation Access，按主体范围校验会话后才读取。
- 返回浏览器安全的消息字段与游标，不返回内部上下文、事件载荷或权限。

## Capabilities

### New Capabilities

- `owned-conversation-history-http`: 定义按主体读取会话消息历史的 HTTP 与分页行为。

### Modified Capabilities

- `conversation-history-read`: 允许在不改变只读语义的前提下，经主体访问校验对外提供历史查询。

## Impact

- 影响 Conversation query、HTTP route/schema/assembler 与 HTTP 测试；不修改消息事实和 LLM 调用。
