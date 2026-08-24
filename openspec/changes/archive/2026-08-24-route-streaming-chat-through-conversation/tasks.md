## 1. Interaction 流式接线

- [x] 1.1 在 Composition Root 注入 Streaming Conversation Runtime，替换普通 `chat.general` 的无状态流式调用。
- [x] 1.2 将运行时事件映射为现有 SSE，首个 `meta` 加入 `conversation_id`，保持 Agent 分支不变。
- [x] 1.3 映射会话与持久化失败为脱敏的浏览器安全错误。

## 2. 验证

- [x] 2.1 覆盖普通 Chat 消息持久化、SSE 元数据、失败映射和 Agent 分支未回归的单元/HTTP 测试。
- [x] 2.2 运行相关 pytest、前端流式 API 契约测试和 OpenSpec 严格校验。
