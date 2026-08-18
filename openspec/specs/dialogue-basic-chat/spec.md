# dialogue-basic-chat Specification

## Purpose
TBD - created by archiving change dialogue-basic-chat. Update Purpose after archive.
## Requirements
### Requirement: 系统执行并持久化基础对话轮次
系统 MUST 能够针对已有 Conversation 执行同步文本对话轮次。系统 MUST 先持久化有效用户消息，在取得非空模型回答后持久化 assistant 消息，并返回 Conversation 标识、两条已持久化消息、模型元数据和本轮使用的 `ModelContext`。消息顺序号 MUST 由 Conversation 能力分配。

#### Scenario: 有历史会话获得新的助手回答
- **WHEN** 调用方为已有 Conversation 提交有效用户文本且 LLM 返回非空回答
- **THEN** 系统按顺序持久化新的 user Message 和 assistant Message
- **AND** 返回结果包含两条持久化消息、模型标识、提示版本、用量元数据和 `ModelContext`
- **AND** assistant Message 的顺序号大于本轮 user Message 的顺序号

### Requirement: 系统基于最新有序历史构建模型输入
系统 MUST 在写入本轮用户消息后读取 Conversation 的所有正向历史页，并仅保留策略允许数量的最新消息窗口交给 Context Builder。系统 MUST 通过 `ModelContext` 的顺序将历史 system/user/assistant 消息与当前用户消息传给 LLM；当前用户消息 MUST 不在历史消息和当前用户输入中重复出现。

#### Scenario: 历史跨越多个读取页
- **WHEN** Conversation 的消息数量超过单页读取上限且本轮用户消息已成功写入
- **THEN** 系统读取至最后一页并保留策略允许的最新消息窗口
- **AND** LLM 历史消息保持其原始角色和时间顺序
- **AND** 当前用户消息作为当前用户输入传给 LLM 一次

### Requirement: LLM 文本调用支持可选的有角色历史消息
系统 MUST 允许 `ChatLlmRequest` 携带有序的 system、user、assistant 历史消息。OpenAI-compatible Chat 适配器 MUST 按系统提示、历史消息、当前用户消息的顺序映射请求。未提供历史消息时，现有单轮调用 MUST 保持原有的系统提示加当前用户消息行为。

#### Scenario: Provider 接收带角色的历史消息
- **WHEN** LLM 请求包含 system、user、assistant 三种历史消息和当前用户消息
- **THEN** Provider 接收的消息角色和内容顺序为运行时系统提示、历史 system、历史 user、历史 assistant、当前 user
- **AND** 历史 assistant 消息不得被映射为 user 消息

#### Scenario: 既有单轮调用不提供历史消息
- **WHEN** 现有单轮 Chat 用例创建未携带历史消息的 LLM 请求
- **THEN** Provider 仍只接收系统提示和当前用户消息
- **AND** `/api/v1/llm/chat` 的请求和响应契约保持不变

### Requirement: 系统显式保留失败前已确认的用户事实
系统 MUST 在 Context Builder、LLM 或助手消息写入失败时向调用方返回失败。若本轮 user Message 已成功持久化，系统 MUST 保留它；失败路径 MUST 不持久化虚构或空白的 assistant Message。

#### Scenario: LLM 调用失败
- **WHEN** 用户消息已成功持久化后 LLM 调用失败
- **THEN** 系统返回该失败
- **AND** Conversation 仅新增本轮 user Message，不新增 assistant Message

#### Scenario: 上下文预算无法容纳当前用户消息
- **WHEN** 用户消息已成功持久化但 Context Builder 因当前消息超出预算而拒绝构建
- **THEN** 系统返回上下文预算不足错误
- **AND** Conversation 不新增 assistant Message

### Requirement: 基础 Dialogue Runtime 保持独立边界
Dialogue Runtime MUST 只依赖 Conversation 应用服务、Conversation 领域契约和 LLM 抽象 Port。它 MUST NOT 依赖 HTTP、SQLAlchemy、具体 Provider、Interaction Gateway、Agent Runtime 或 Task Management。本 Change MUST NOT 新增 Dialogue HTTP 路由。

#### Scenario: 运行时在替身服务下执行
- **WHEN** 调用方注入 Conversation 服务、Context Builder 和 LLM Port 的测试替身
- **THEN** Dialogue Runtime 可以完成或报告一轮对话的结果
- **AND** 不需要实例化 HTTP、数据库 ORM、Provider SDK、Gateway 或 Agent

