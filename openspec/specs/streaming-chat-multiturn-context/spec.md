# streaming-chat-multiturn-context Specification

## Purpose

Define how ordinary streaming Chat uses recent history from the current
Conversation while preserving existing persistence and streaming failure
semantics.

## Requirements

### Requirement: 普通流式 Chat 使用同一会话的最近历史

系统 MUST 在普通流式 Chat 成功写入本轮 user Message 后，读取同一 Conversation 的有序历史并通过现有上下文策略选择最近连续消息窗口。模型请求 MUST 使用该窗口中的历史角色和顺序；当前 user Message MUST 只作为当前输入发送一次。

#### Scenario: 已有会话进行第二轮对话

- **WHEN** 主体对已包含首轮 user/assistant Message 的准入 Conversation 发起第二次普通流式 Chat
- **THEN** 模型请求包含首轮消息的原始角色和顺序
- **AND** 本轮 user Message 作为 `user_prompt` 只出现一次
- **AND** 流式响应和 assistant Message 持久化行为保持既有契约

#### Scenario: 新会话进行首轮对话

- **WHEN** 可信主体在没有 `conversation_id` 时发起普通流式 Chat
- **THEN** 系统创建 Conversation 并保存本轮 user Message
- **AND** 模型请求不包含其他 Conversation 的历史
- **AND** 请求成功后保存本轮 assistant Message

### Requirement: 历史上下文受窗口和成本预算约束

系统 MUST 使用既有 Context Builder 的消息数量上限和成本预算选择历史。系统 MUST 保留最新的连续消息后缀并按 sequence 升序传给模型；不得跳过无法容纳的较早消息再选择更早消息，也不得静默截断任何消息内容。

#### Scenario: 历史超过消息窗口

- **WHEN** 当前 Conversation 的持久化历史超过上下文消息数量上限
- **THEN** 模型请求只包含允许范围内的最新连续消息
- **AND** 这些历史消息的顺序保持升序
- **AND** 更早消息仍保留在 Conversation 历史中

#### Scenario: 当前用户消息超出预算

- **WHEN** 本轮 user Message 的成本单独超过上下文预算
- **THEN** 系统返回受控的上下文预算不足失败
- **AND** 已写入的 user Message 保留
- **AND** 不写入 assistant Message

### Requirement: 历史上下文必须绑定当前会话

系统 MUST 只读取并使用当前可信主体已准入 Conversation 的消息。跨会话、越权或历史读取失败时，系统 MUST 拒绝构建模型请求，不得将其他会话消息发送给 Provider。

#### Scenario: 请求携带其他主体的会话标识

- **WHEN** 主体使用不属于自己的 `conversation_id` 发起普通流式 Chat
- **THEN** 系统返回既有会话访问拒绝语义
- **AND** 不读取该会话历史、不调用 Provider 且不写入消息

#### Scenario: 历史读取在 user 写入后失败

- **WHEN** 当前 user Message 已成功写入但历史读取或上下文构建失败
- **THEN** 系统返回受控失败
- **AND** 当前 user Message 保留
- **AND** 不写入 assistant Message

### Requirement: 流式失败不得产生虚构的助手历史

系统 MUST 保持现有普通流式持久化语义：客户端取消、上游错误、空回答或 assistant 写入失败时不得追加 assistant Message；上下文接入不得改变既有 SSE 事件和安全错误映射。

#### Scenario: 第二轮流式生成中途失败

- **WHEN** 模型已返回部分文本后本轮流式请求失败或被取消
- **THEN** 系统按既有受控错误或取消语义结束
- **AND** Conversation 只新增本轮 user Message
- **AND** 不把部分回答作为历史 assistant Message 保存
