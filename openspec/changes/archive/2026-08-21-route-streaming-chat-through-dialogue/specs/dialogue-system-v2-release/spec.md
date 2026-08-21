## MODIFIED Requirements

### Requirement: V2 对话入口提供完整的受控对话轮次

系统 MUST 通过 `/api/v1/interaction/chat/stream` 提供 V2 对话入口。普通文本对话 MUST 在已准入 Conversation 中由同一条上下文增强流式 Conversation Runtime 使用历史上下文获得模型输出；没有 `conversation_id` 时系统 MUST 创建新 Conversation，并在流式元数据中返回其标识。需要调用 Agent 能力的请求 MUST 先进入待确认状态，未经显式确认不得执行该能力。

#### Scenario: 普通对话获得带上下文的回答

- **WHEN** 调用方通过 V2 对话入口提交不需要调用 Agent 的文本
- **THEN** 系统创建或复用已准入的 Conversation
- **AND** 系统基于该会话历史构建本轮模型上下文并返回对话输出
- **AND** 系统不创建待确认 Agent 调用

#### Scenario: 普通对话返回会话标识

- **WHEN** 普通文本请求开始流式输出
- **THEN** `meta` 事件包含本轮 Conversation 标识
- **AND** 调用方可以使用该标识继续同一会话

#### Scenario: Agent 调用等待确认

- **WHEN** V2 对话识别出需要确认的 Agent 能力
- **THEN** 系统返回可供调用方确认或取消的提议
- **AND** 在确认前不执行目标 Agent
