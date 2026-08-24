## Why

历史会话 HTTP 与前端恢复只能读取已保存的消息，但普通流式 Chat 目前不会写入 Conversation。先让普通流式对话保存完整 user/assistant Message，才能独立验收历史会话管理，再在后续 Change 增加上下文窗口。

## What Changes

- 新增不使用历史上下文的流式 Conversation 对话运行时：创建或解析已准入会话、先写 user Message、调用现有流式 LLM、完整成功后写 assistant Message。
- 流式取消、断开、上游错误或空回答只保留 user Message，不持久化部分回答。
- 不读取历史消息、不调用 ContextBuilder、不增加 HTTP/SSE 或前端行为。

## Capabilities

### New Capabilities

- `streaming-conversation-persistence`: 定义普通流式对话将完整消息写入 Conversation 的时序。

### Modified Capabilities

无。

## Impact

- 影响 Dialogue、Conversation、Streaming LLM Port、Composition Root 和后端测试；不新增数据库、HTTP 路由或 Provider 状态。
