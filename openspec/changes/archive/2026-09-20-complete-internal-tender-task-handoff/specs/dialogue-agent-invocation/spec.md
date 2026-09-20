## MODIFIED Requirements

### Requirement: 对话可以执行一次已授权的结构化 Agent 调用

系统 MUST 在可信主体和 Conversation 校验通过后，将结构化 `AgentCall` 交给 P2.6 受控分发服务。分发结果为同步成功或异步 `accepted` 时均视为已受控处理；确认缺失、策略拒绝、目录不可用或运行时失败时 MUST 返回受控状态且不得重复调用 Agent Runtime。

#### Scenario: 已确认的 Tender Agent 调用成功

- **WHEN** 当前主体拥有目录要求的权限，结构化调用输入有效且批准提议与调用严格匹配
- **THEN** Dialogue Agent Invocation 调用一次受控 Agent Runtime
- **AND** 返回 `completed` 状态、调用 ID 和结构化结果摘要

#### Scenario: 已确认调用被异步接收

- **WHEN** 已登记的内部 Agent 能力由 Dispatcher 返回 `accepted` 与有效 execution reference
- **THEN** Dialogue 返回 `accepted` 状态和该受控引用
- **AND** 不将该调用映射为失败、同步结果或 assistant Message

#### Scenario: 调用尚未获得确认

- **WHEN** Agent Call 策略返回 `confirmation_required`
- **THEN** 系统返回待确认状态
- **AND** 不调用 Agent Runtime、不写入虚构的助手文本

### Requirement: Agent 调用结果必须关联到 Conversation 事件

系统 MUST 将 `agent_call`、`agent_result` 或 `agent_error` 作为有序 Conversation 事件持久化。每个结果事件 MUST 包含 Conversation ID、调用 ID、能力代码、事件顺序和 JSON 对象载荷；异步调用被接收时，`agent_call` 事件 MUST 保存 `accepted` 状态及其安全 execution reference。

#### Scenario: 成功结果写入事件

- **WHEN** Agent Runtime 返回可序列化的成功结果
- **THEN** 系统持久化一个 `agent_result` 事件
- **AND** 历史读取可以按事件顺序和调用 ID 找到该结果

#### Scenario: 异步接收状态写入事件

- **WHEN** Dispatcher 接受内部异步 Agent 调用
- **THEN** 系统持久化一个带 `accepted` 状态和 execution reference 的 `agent_call` 事件
- **AND** 不写入 `agent_result`、`agent_error`、原始输入、lease 或任务结果内容

#### Scenario: 失败结果写入事件

- **WHEN** 策略校验、目录读取、输入构造或 Agent Runtime 返回受控失败
- **THEN** 系统持久化一个 `agent_error` 事件
- **AND** 事件只包含稳定错误码和安全消息，不包含堆栈、凭据或原始输入
