## Why

流式 Conversation Runtime 完成后，需要让普通浏览器 Chat 使用该运行时，才能把历史 HTTP 和前端恢复变成用户可见闭环。

## What Changes

- 将已授权普通 `chat.general` 流式分支从无状态 StreamingChatApplication 切换到 Streaming Conversation Runtime。
- 在普通 Chat `meta` SSE 事件返回实际 `conversation_id`，保留既有 delta、complete、error 和心跳语义。
- 不读取历史上下文、不实现前端恢复、不改变 Agent 确认/续写。

## Capabilities

### New Capabilities

- `streaming-conversation-interaction-adapter`: 定义普通 Chat 到 Conversation 持久化运行时的 SSE 适配。

### Modified Capabilities

- `dialogue-system-v2-release`: 普通 V2 Chat 创建或续写 Conversation，并通过元数据返回会话标识。

## Impact

- 影响 Interaction 应用、Composition Root、SSE 类型与 HTTP 测试；不新增 HTTP 路由、数据库或 Provider。
