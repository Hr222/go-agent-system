## Why

当前普通流式 Chat 会持久化当前轮次的 user/assistant Message，但流式运行时仍按单轮请求调用模型，不读取同一 Conversation 的历史上下文。因此用户在第二轮追问时，模型无法稳定理解上一轮的指代和结论。

现有 Conversation 历史读取、Context Builder 和 `ChatLlmRequest.history_messages` 已经提供了接入基础。本 Change 只把这些能力接入普通流式 Chat，建立不包含摘要压缩的多轮对话基板。

## What Changes

- 普通流式 Conversation 在写入本轮 user Message 后读取当前会话的有序历史。
- 通过现有 `ConversationContextBuilder` 按最近连续消息窗口和字符成本预算选择模型上下文。
- 将选中的历史消息以原始角色和顺序传入 `ChatLlmRequest.history_messages`，当前 user Message 只作为当前输入传入一次。
- 保持新会话创建、流式 SSE 事件、assistant Message 持久化、取消、超时、上游失败和访问控制语义不变。
- 增加跨轮、跨会话、窗口裁剪、预算不足和失败持久化回归测试。
- 不新增数据库表、HTTP 路由、前端字段或外部 Provider 配置。

## Capabilities

### New Capabilities

- `streaming-chat-multiturn-context`: 定义普通流式 Chat 在同一 Conversation 内使用最近历史上下文的行为。

### Modified Capabilities

- `streaming-conversation-persistence`: 将“流式运行时不读取历史上下文”的首版边界改为读取并选择同一 Conversation 的有序历史，同时保留原有消息持久化和失败语义。

## Impact

- 影响 `app/modules/dialogue/application/streaming_conversation.py` 及其 Composition Root 依赖组装。
- 复用 `ConversationHistoryReadService`、`ConversationContextBuilder` 和现有 LLM Chat Port，不改变模块依赖方向。
- 影响普通流式 Chat 发往 GLM/DeepSeek 的请求消息列表，但不改变 Provider、SSE 或 HTTP 请求外形。
- 不修改 PostgreSQL Schema、Conversation/Message 数据结构或前端代码。
- 本 Change 不包含摘要检查点、上下文压缩、精确 Tokenizer、Redis、异步 Compaction Worker 或跨会话长期记忆。
