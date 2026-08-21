## Why

H1 已将普通 Chat 接入流式 Conversation Runtime，C1 会在同一运行时上补齐上下文构建。需要一个独立适配 Change 将已授权普通 Chat 的既有接入点替换为该上下文增强版本，而不改动 Agent 确认分支或新增平行路由。

## What Changes

- 将普通 `chat.general` 的既有 Interaction 流式分支替换为调用已完成的上下文增强流式 Conversation Runtime。
- 在普通 Chat 首个 `meta` 事件返回实际 `conversation_id`，保留既有 delta、complete、error 和心跳语义。
- 把 Dialogue 的受控失败映射为现有浏览器安全 SSE 错误；不暴露历史、上下文或 Provider 原始数据。
- 不实现前端存储或历史 UI，不改变 Agent 确认/续写行为。

## Capabilities

### New Capabilities

- `streaming-dialogue-interaction-adapter`: 定义 Interaction 将既有普通流式 Chat 接入上下文增强运行时的 SSE 替换行为。

### Modified Capabilities

- `dialogue-system-v2-release`: 普通 V2 Chat 使用 Conversation 上下文并在流式元数据返回会话标识。

## Impact

- 影响 Interaction 应用、Composition Root、SSE 事件类型和 HTTP 测试。
- 不新增数据库、HTTP 路由、用户模块或 LLM Provider；依赖已完成 Conversation Access 和流式 Dialogue Runtime。
