## MODIFIED Requirements

### Requirement: 普通 Interaction Chat 写入 Conversation

系统 MUST 将已授权的 `chat.general` 流式请求转发给 Streaming Conversation Runtime。Interaction MUST NOT 自行读写 Conversation；需要确认的 Agent 请求 MUST 继续使用既有分支。由服务端 `unrecognized` 通用 Chat 兜底授权的固定 `chat.general` 请求同样 MUST 使用原始用户消息进入该 Runtime。

#### Scenario: 普通请求持久化消息

- **WHEN** Interaction 授权一个普通 `chat.general` 请求
- **THEN** 系统调用 Streaming Conversation Runtime
- **AND** 普通 Chat 不再调用无状态 StreamingChatApplication
- **AND** 完成后的消息可通过 Conversation 历史读取恢复

#### Scenario: 自然追问续写既有 Conversation

- **WHEN** 同一 Conversation 的自然语言追问通过服务端通用 Chat 兜底授权
- **THEN** 系统 MUST 将该追问作为当前 user Message 写入同一 Conversation
- **AND** 系统 MUST 使用既有会话历史构建模型请求并返回 `meta`、`delta` 和 `complete` 事件
- **AND** 刷新后必须能从 Conversation 历史恢复该追问及其完整回答
