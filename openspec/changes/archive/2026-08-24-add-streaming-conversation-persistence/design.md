## Context

现有 StreamingChatApplication 是无状态的，Conversation WriteService 已能按会话顺序追加 Message。Access Change 提供已准入会话。

## Goals / Non-Goals

**Goals:** 为普通流式模型调用建立可恢复的消息事实。

**Non-Goals:** 不读取历史、不构建 ModelContext、不改变 Interaction/SSE、不中断 Agent 流程。

## Decisions

- 新增不依赖 HTTP 的 Streaming Conversation Runtime，依赖 Access、ConversationWriteService 和 StreamingChatLlmPort。
- 先写 user，流式文本仅请求内累积；正常非空完成才写 assistant。
- 后续 Context Runtime 扩展该 Runtime 的请求构造，保留消息时序和失败语义。

## Risks / Trade-offs

- [本阶段模型无历史] → 明确是临时可验收的历史事实链路，下一阶段只新增 ContextBuilder 选择。
