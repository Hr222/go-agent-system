## 1. 流式 Runtime 接入历史上下文

- [ ] 1.1 扩展 `StreamingConversationRuntime` 的依赖组装，注入 `ConversationHistoryReadService` 与 `ConversationContextBuilder`，并保持 Dialogue/Conversation/LLM 的依赖方向不变。
- [ ] 1.2 在本轮 user Message 写入后按历史游标读取当前 Conversation 全部必要页面，校验游标前进并将有序消息交给 Context Builder。
- [ ] 1.3 使用 Context Builder 结果构造带角色的 `ChatLlmRequest.history_messages`，确保当前 user Message 不在历史中重复出现。
- [ ] 1.4 保持首轮创建、主体访问校验、SSE 事件、Provider 流关闭、assistant 写入和失败映射行为不变。

## 2. 组合与边界验证

- [ ] 2.1 更新 Composition Root 和应用容器测试，验证流式 Runtime 获得历史读取服务与上下文构建器的真实组装。
- [ ] 2.2 更新架构边界测试，确认 Dialogue 只依赖 Conversation 应用契约和 LLM Port，不依赖 Repository、ORM 或具体 Provider。

## 3. 测试与验收

- [ ] 3.1 增加流式多轮测试，覆盖首轮无历史、第二轮角色/顺序传递、当前输入不重复和跨页历史读取。
- [ ] 3.2 增加窗口裁剪、预算不足、跨会话拒绝、历史读取失败和并发/失败持久化回归测试。
- [ ] 3.3 运行目标后端测试、架构测试、全量后端测试、前端回归、OpenSpec 严格校验、Ruff、compileall、前端构建和 `git diff --check`。
