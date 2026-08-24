## Why

当前会话列表只能显示“会话 + 日期”，用户无法快速判断每个会话讨论的主题。首轮用户消息完成后生成简短话题概括，并允许用户修正不准确的描述，可以让历史会话具备可识别、可维护的标题，同时不把标题生成混入模型上下文逻辑。

## What Changes

- 为 Conversation 增加可持久化的话题概括字段，并补充数据库演化脚本。
- 首轮用户消息成功保存后生成简短话题概括；生成失败时使用稳定的文本截断回退，不阻塞本轮对话。
- 会话摘要列表返回话题概括。
- 新增当前主体修改指定会话话题概括的 HTTP 契约，并重新执行主体访问校验。
- Chat 侧栏展示话题概括，并支持用户手动修改和保存。
- 不在本 Change 中实现完整历史摘要、上下文压缩、正文搜索、自动重命名或多用户认证。

## Capabilities

### New Capabilities

- `conversation-topic-summary`: 定义会话话题概括的生成、持久化、修改和主体访问边界。

### Modified Capabilities

- `owned-conversation-list`: 会话摘要列表增加话题概括字段，同时保持主体隔离和最小响应原则。
- `chat-conversation-list-management`: Chat 侧栏展示话题概括，并支持手动修改后刷新列表。

## Impact

- 影响 Conversation Domain/Application、PostgreSQL migration、会话列表和更新 HTTP 接口、Composition Root、Chat 前端及其测试。
- 不改变现有流式 SSE 事件语义，不要求新增 LLM Provider；生成器可使用首轮用户文本的确定性摘要回退。
- 现有没有标题的历史会话保持日期回退显示，可通过后续明确操作补充话题概括。
