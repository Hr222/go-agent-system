## MODIFIED Requirements

### Requirement: V2 对话入口提供完整的受控对话轮次

系统 MUST 通过 `/api/v1/interaction/chat/stream` 提供 V2 对话入口。普通文本对话 MUST 创建或续写已准入 Conversation，并在流式元数据中返回其标识；此阶段普通 Chat 仍只使用当前请求文本调用模型。需要调用 Agent 能力的请求 MUST 先进入待确认状态，未经显式确认不得执行该能力。

#### Scenario: 普通对话获得回答

- **WHEN** 调用方通过 V2 对话入口提交不需要调用 Agent 的文本
- **THEN** 系统创建或复用已准入 Conversation 并返回模型输出
- **AND** 系统保存本轮完整 user 和 assistant Message
- **AND** 系统不创建待确认 Agent 调用

#### Scenario: 普通对话返回会话标识

- **WHEN** 普通文本请求开始流式输出
- **THEN** `meta` 事件包含本轮 Conversation 标识
- **AND** 调用方可以使用该标识读取或继续同一会话

#### Scenario: Agent 调用等待确认

- **WHEN** V2 对话识别出需要确认的 Agent 能力
- **THEN** 系统返回可供调用方确认或取消的提议
- **AND** 在确认前不执行目标 Agent
