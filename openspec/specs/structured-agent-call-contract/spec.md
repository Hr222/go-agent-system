## Purpose

定义 LLM、Interaction Gateway 和 Agent Runtime 之间的结构化单 Agent 调用、结果与错误数据契约。该契约只表达可校验、可序列化的数据，不代表权限、用户确认或执行授权。

## Requirements

### Requirement: 系统提供受控的结构化 Agent 调用请求契约

系统 MUST 提供一个可序列化的结构化 Agent 调用请求，至少包含非空的 `call_id`、目录能力代码和 JSON 对象形式的 `inputs`；可以包含 `conversation_id`、`turn_id`、`run_id` 与 `parent_run_id` 关联标识。请求契约 MUST 拒绝未声明字段、空标识和非对象输入。

#### Scenario: 构造带对话关联信息的 Agent 调用

- **WHEN** 上层提供调用标识、能力代码、对象输入和可选的对话/轮次/运行关联标识
- **THEN** 系统创建结构化 Agent 调用对象
- **AND** 对象可以被序列化并在后续层之间传递

#### Scenario: 调用请求包含执行信息或无效输入

- **WHEN** 请求额外包含 `dispatch_key`、权限、确认状态、工具地址、函数引用，或 `call_id`/能力代码为空，或 `inputs` 不是对象
- **THEN** 系统拒绝创建该调用对象
- **AND** 不产生任何 Agent 执行行为

### Requirement: 系统提供结构化 Agent 成功结果契约

系统 MUST 提供一个与请求关联的成功结果，包含非空 `call_id`、能力代码和 JSON 对象形式的 `output`。成功结果 MUST 拒绝未声明字段，并且不得包含 Provider 原始响应、执行器引用或异常堆栈。

#### Scenario: Agent 返回结构化业务结果

- **WHEN** Agent Runtime 为一个调用返回调用标识、能力代码和对象形式的业务输出
- **THEN** 系统创建成功结果对象
- **AND** 上层可以使用 `call_id` 将结果与原调用和 Conversation 事件关联

#### Scenario: 成功结果缺少关联信息或泄漏执行细节

- **WHEN** 成功结果缺少调用标识或能力代码，输出不是对象，或携带未声明的 Provider、执行器或异常字段
- **THEN** 系统拒绝创建该成功结果
- **AND** 不把该结果视为可用于对话续写的有效 Agent 结果

### Requirement: 系统提供受控的 Agent 失败结果契约

系统 MUST 提供一个与请求关联的失败结果，包含非空的 `call_id`、能力代码、受控的 `error_code`、可安全展示的非空 `message` 和布尔 `retryable`。失败结果 MUST 拒绝未声明字段，且不得携带异常堆栈、凭据、原始请求或执行器对象。

#### Scenario: Agent 以可重试错误结束

- **WHEN** Agent Runtime 返回调用标识、能力代码、受控错误码、安全错误消息并标记 `retryable=true`
- **THEN** 系统创建失败结果对象
- **AND** 上层可以据此决定提示用户或交给后续重试策略

#### Scenario: 失败结果包含空消息或底层异常细节

- **WHEN** 失败结果缺少关联信息、错误码或消息，或额外携带堆栈、凭据、原始请求、URL 或执行器引用
- **THEN** 系统拒绝创建该失败结果
- **AND** 不向调用方暴露底层实现细节

### Requirement: 结构化 Agent 调用契约不等同于执行授权

系统 MUST 将结构化 Agent 调用及其结果视为数据契约，而不是权限、确认或分发决策。创建或序列化这些对象 MUST 不读取能力目录、不调用 LLM/Agent、不验证权限、不创建确认提议且不执行任何能力。

#### Scenario: 创建契约对象

- **WHEN** 调用方仅构造或序列化结构化 Agent 调用、成功结果或失败结果
- **THEN** 系统只完成字段和类型校验
- **AND** 不触发目录访问、用户确认或目标能力执行
