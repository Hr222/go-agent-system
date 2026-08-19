## ADDED Requirements

### Requirement: V2 对话入口提供完整的受控对话轮次

系统 MUST 通过 `/api/v1/interaction/chat/stream` 提供 V2 对话入口。普通文本对话必须能够在同一入口获得模型输出；需要调用 Agent 能力的请求必须先进入待确认状态，未经显式确认不得执行该能力。

#### Scenario: 普通对话获得回答
- **WHEN** 调用方通过 V2 对话入口提交不需要调用 Agent 的文本
- **THEN** 系统在该入口返回对话输出，且不创建待确认 Agent 调用

#### Scenario: Agent 调用等待确认
- **WHEN** V2 对话识别出需要确认的 Agent 能力
- **THEN** 系统返回可供调用方确认或取消的提议，且在确认前不执行目标 Agent

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
