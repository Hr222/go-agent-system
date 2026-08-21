## 1. Interaction 流式适配

- [ ] 1.1 在 Composition Root 用上下文增强的既有流式 Conversation Runtime 替换 H1 普通 `chat.general` 的运行时依赖，不新增第二个路由分支。
- [ ] 1.2 将同一运行时的流事件映射为现有 SSE，首个 `meta` 加入 `conversation_id`，保持 Agent 分支不变。
- [ ] 1.3 映射 Access、预算、Provider 与持久化失败为脱敏的浏览器安全错误。

## 2. 验证

- [ ] 2.1 覆盖普通 Chat 只走上下文增强的既有运行时、SSE 元数据、失败映射及 Agent 分支未回归的单元/HTTP 测试。
- [ ] 2.2 运行相关 pytest、前端流式 API 契约测试和 OpenSpec 严格校验。
