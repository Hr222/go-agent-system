## Context

V2 的普通对话已经从 Chat 页面通过 `/api/v1/interaction/chat/stream` 进入 Interaction Gateway。已确认的 Agent 调用也在同一路径中完成，且 P3.2 会将安全的 Agent 结果续写为 assistant Message。旧 V1 路由绕过上述受控边界，不能继续存在。

## Decisions

### 1. 删除 HTTP 外壳，不删除 LLM 领域能力

移除路由模块、路由注册、LlmChat HTTP Schema 与依赖注入函数。`ChatApplication` 和 `StreamingChatApplication` 保留：前者被 Agent 结果续写复用，后者被 Interaction 流式聊天复用。

### 2. 前端只保留 Interaction Chat 协议

删除只访问 `/v1/llm/chat` 或 `/v1/llm/chat/stream` 的前端模块与测试。Chat 页面已经使用 `useInteractionChatStream`，不需要迁移或额外兼容代码。

### 3. 用路由级回归测试锁定退场

删除旧行为测试，新增路由回归测试：旧同步和流式地址均为 `404`，而 V2 `/api/v1/interaction/chat/stream` 仍在路由表中。这样避免未来将旧入口作为临时后门重新注册。

## Risks

- 外部未迁移客户端会收到 `404`。这是既定的接口退场策略；不提供重定向，避免绕过 Gateway。
- 删除过度可能误伤内部 LLM 能力。通过导入搜索和前端构建确认只有旧 HTTP 外壳被删除。
