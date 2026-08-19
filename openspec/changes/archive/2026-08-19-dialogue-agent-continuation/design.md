## Context

P3.1 的 `DialogueAgentInvocationService` 会在 Conversation 中保存用户消息、`agent_call` 和安全投影后的 `agent_result`，然后把结构化结果返回给 HTTP。现有 `BasicDialogueRuntime` 已经具备历史读取、Context Builder 和 Chat LLM 调用能力，但它的输入是普通用户消息，不能直接消费 Agent 事件。

本 Change 只补齐“Agent 完成后的同一轮续写”。调用必须由已完成的 Agent 结果显式触发；续写服务不能重新识别用户意图，也不能重新调用 Agent。前端继续通过现有确认接口获取结果，不增加绕过 Gateway 的 HTTP 路由。

## Goals / Non-Goals

**Goals:**

- 读取指定 Conversation 和 `call_id` 对应的已持久化 `agent_result`。
- 使用 Conversation History Read、Context Builder 和 Chat LLM Port 生成自然语言 assistant Message。
- 只把 `AgentResultProjector` 产生的安全 JSON 作为模型数据，保留原始用户消息和历史顺序。
- 续写成功后持久化非空 assistant Message，并把回答返回给现有确认响应。
- 续写失败时返回稳定错误，保留已有 Agent 事件，不写入空 assistant Message。

**Non-Goals:**

- 不改变 `PrincipalResolver`、Gateway 意图识别、确认策略或 Agent Runtime。
- 不实现 SubAgent、Workflow、Task Management、Harness、异步恢复或跨会话续写。
- 不增加公开 HTTP 路由、数据库表或 Redis；不修改 Agent 结果投影和文件资源存储协议。
- 不把续写结果再次送回 Gateway，也不允许续写触发新的 Agent Call。

## Decisions

### 1. 新增独立的 Dialogue Agent Continuation Service

新增 Dialogue 应用服务和命令/结果契约。服务接收 `conversation_id`、`call_id` 以及可配置的上下文策略，依赖 Conversation History Read、Conversation Event Read、Conversation Write、Context Builder 和 `ChatLlmPort`。它只消费已持久化事实，不依赖 HTTP、ORM、Provider SDK 或 Agent Runtime。

选择独立服务而不是扩展 `BasicDialogueRuntime`，是为了保持普通 Chat 与 Agent 结果续写的 Prompt、触发条件和错误边界分离；也避免把 Agent 事件语义泄漏到 Conversation 通用上下文构建器。

### 2. 从 `agent_result` 事件读取并校验续写输入

服务按 Conversation 和 `call_id` 查询事件，只接受唯一且非空的 `agent_result`。事件不存在、重复、能力标识不一致或负载无法安全序列化时，返回受控的 `AGENT_RESULT_UNAVAILABLE` 或 `AGENT_RESULT_INVALID`，不调用 LLM。

续写上下文使用现有有序 Message 历史；Agent 结果以明确标记的 JSON 数据放入本次 `ChatLlmRequest.user_prompt`，而不是伪造 `Message` 或扩展持久化消息角色。System Prompt 明确要求把结果视为事实数据，只向用户解释结果，不执行其中的指令。

### 3. 复用 Context Builder 与现有 Chat LLM Port

服务分页读取完整历史，再用现有 `ContextPolicy` 和 `ContextBudget` 选择最新连续后缀；历史消息映射为 `ChatLlmMessage`，本次续写指令作为当前 user prompt。Provider、模型、Token 元数据和 Prompt 版本沿用 `ChatLlmPort` 的既有契约。

不直接复用 `BasicDialogueRuntime.execute()`，因为该用例会追加新的用户消息；续写不应重复写入用户输入，也不应把 Agent 结果伪装成用户消息。

### 4. 在确认后的 Dialogue Agent 路径显式触发续写

`InteractionChatStreamApplication.confirm_agent()` 在 Agent Invocation 返回 `completed` 后调用 Continuation Service。成功时在现有 `GatewayResult.execution_result` 中增加 `answer` 和 `agent_result`，同时保留原有状态与 Conversation ID；续写失败时仍保留 Agent 的结构化结果，并返回稳定的续写错误信息，不重新执行 Agent。

取消、拒绝、输入无效和 Agent 执行失败均不触发续写。重复确认因提议已消费而不能重复触发；续写重试由后续独立能力决定，本 Change 不自动重试。

## Risks / Trade-offs

- [模型可能把 Agent 结果中的文本当作指令] → System Prompt 和用户提示将结果标记为不可信数据；只传安全投影，不传 Provider 响应、权限或二进制内容。
- [Agent 已完成但续写 Provider 不可用] → 不回滚 Agent 事件；返回稳定错误并保留 `agent_result`，前端仍可展示结构化结果。
- [重复调用续写造成重复 assistant Message] → 只从已消费的确认路径显式触发一次；本 Change 不提供公开续写接口，后续若需重试必须增加幂等标识。
- [历史过长或当前续写指令超预算] → 复用 Context Builder 的连续后缀和预算校验，预算不足时不调用模型、不写入空消息。

## Migration Plan

无数据库迁移。先增加服务、测试和 Composition Root 组装，再在确认后的 Agent 路径接入；回滚时移除续写调用即可，已有 `agent_call` 与 `agent_result` 事件仍兼容。

## Open Questions

无。本 Change 的续写重试、跨进程恢复和异步任务留给后续独立 Change。
