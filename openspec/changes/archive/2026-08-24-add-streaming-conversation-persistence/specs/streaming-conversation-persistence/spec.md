## ADDED Requirements

### Requirement: 普通流式对话保存完整 Conversation 消息

系统 MUST 为已准入 Conversation 的普通流式文本请求先追加有效 user Message，并在流式 LLM 正常结束且拼接回答非空时追加完整 assistant Message。该运行时 MUST 不读取历史消息或构建 ModelContext。

#### Scenario: 新会话保存首轮消息

- **WHEN** 可信主体开始没有 `conversation_id` 的有效普通流式对话
- **THEN** 系统创建归属该主体的 Conversation 并按顺序保存 user 与完整 assistant Message
- **AND** 返回的 Conversation 可由历史读取能力恢复

#### Scenario: 已有会话追加新一轮

- **WHEN** 主体对已准入 Conversation 发起有效普通流式对话
- **THEN** 系统在已有消息之后依次追加本轮 user 和 assistant Message
- **AND** 新消息 sequence 大于原有消息

### Requirement: 未完成流式内容不成为历史事实

系统 MUST 在取消、客户端断开、上游错误、空回答或 assistant 写入失败时不追加 assistant Message。成功写入的 user Message MUST 保留。

#### Scenario: 流式输出失败

- **WHEN** 模型返回部分文本后发生错误或请求被取消
- **THEN** 系统报告受控失败或取消
- **AND** Conversation 只新增本轮 user Message
