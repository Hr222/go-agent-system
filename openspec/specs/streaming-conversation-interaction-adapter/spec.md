## Purpose

定义普通 Interaction Chat 接入 Streaming Conversation Runtime 的持久化与 SSE 适配契约。

## Requirements

### Requirement: 普通 Interaction Chat 写入 Conversation

系统 MUST 将已授权的 `chat.general` 流式请求转发给 Streaming Conversation Runtime。Interaction MUST NOT 自行读写 Conversation；需要确认的 Agent 请求 MUST 继续使用既有分支。

#### Scenario: 普通请求持久化消息

- **WHEN** Interaction 授权一个普通 `chat.general` 请求
- **THEN** 系统调用 Streaming Conversation Runtime
- **AND** 普通 Chat 不再调用无状态 StreamingChatApplication
- **AND** 完成后的消息可通过 Conversation 历史读取恢复

### Requirement: 普通 Chat SSE 返回 Conversation 标识

普通 Chat 的首个 `meta` SSE 事件 MUST 包含服务器确定的 `conversation_id`，并继续包含既有 request ID、模型和 Prompt 版本字段。系统 MUST 在收到首个上游活动后发送该事件；上游活动可以是可展示正文或内部 reasoning，但内部 reasoning 不得写入 SSE 内容。

#### Scenario: 新会话流式输出

- **WHEN** 普通 Chat 创建新 Conversation 后收到首个上游活动
- **THEN** 首个非心跳事件是含有效 `conversation_id` 的 `meta`
- **AND** 后续 delta、complete、error 和心跳字段保持浏览器安全
- **AND** reasoning 不作为 `delta` 内容发送
