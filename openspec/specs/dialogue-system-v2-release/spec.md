## Purpose

定义 V2 LLM 对话系统对外可观察的端到端组合行为。具体 Conversation、Dialogue、Interaction 和 Agent 领域规则由各自能力规格维护。

## Requirements

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

### Requirement: 已确认的 Agent 结果完成同一对话轮次

系统 MUST 在有效提议经同一主体确认后执行一次授权的 Agent 调用，并将安全的结果摘要与最终 assistant 回答关联到该 Conversation。取消、失效或续写失败不得伪造 assistant 回答，也不得重复执行 Agent。

#### Scenario: 已确认的调用返回最终回答和安全结果
- **WHEN** 同一主体确认仍有效的 Agent 提议且 Agent 成功完成
- **THEN** 系统返回自然语言 `answer` 和不含敏感字段的 `agent_result` 摘要

#### Scenario: 续写失败保留已完成的 Agent 结果
- **WHEN** Agent 已成功完成但生成最终 assistant 回答的 Provider 调用失败
- **THEN** 系统保留并返回可安全展示的 Agent 结果，不创建伪造的 assistant Message，且不重新执行 Agent

### Requirement: V1 LLM Chat 入口保持退场

系统 MUST 不再提供旧的 `/api/v1/llm/chat` 和 `/api/v1/llm/chat/stream` 入口；调用方必须使用 V2 Interaction 对话入口。

#### Scenario: 访问旧同步入口
- **WHEN** 调用方请求 `/api/v1/llm/chat`
- **THEN** 系统返回 `404`

#### Scenario: 访问旧流式入口
- **WHEN** 调用方请求 `/api/v1/llm/chat/stream`
- **THEN** 系统返回 `404`，且 V2 对话入口仍注册可用
