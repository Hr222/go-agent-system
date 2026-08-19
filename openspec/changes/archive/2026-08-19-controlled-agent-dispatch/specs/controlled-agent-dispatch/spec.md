## ADDED Requirements

### Requirement: 只有策略授权的结构化 Agent 调用才能执行

系统 MUST 在执行 `StructuredAgentCall` 前调用 Agent Call 策略校验。只有策略结果为 `authorized` 时，分发服务才可以调用 Agent Runtime；确认缺失、拒绝、不可用或输入无效时 MUST 返回受控结果且不产生 Agent 执行。

#### Scenario: 调用通过策略校验后执行

- **WHEN** 结构化 Agent 调用的目录、权限、输入和确认提议均通过校验
- **THEN** 分发服务调用一次 Agent Runtime
- **AND** 将调用关联标识传递到结构化成功或失败结果

#### Scenario: 调用未获授权

- **WHEN** 策略结果为 `confirmation_required`、`rejected` 或 `unavailable`
- **THEN** 分发服务返回对应的受控状态和错误码
- **AND** 不调用 Agent Runtime

### Requirement: Agent 执行目标只能来自当前目录的固定映射

系统 MUST 在执行前按可信主体重新读取当前启用且有权限的 `agent` 目录条目，并使用该条目的固定 `dispatch_key` 调用已组装的 Agent Runtime。模型、客户端和确认提议不得提供或覆盖执行器地址。

#### Scenario: 目录条目与固定运行时映射一致

- **WHEN** 当前目录条目类型为 `agent` 且其固定分发键已由 Composition Root 注册
- **THEN** 分发服务将能力代码、目录分发键和标准化输入交给 Agent Runtime
- **AND** 不创建目录之外的执行目标

#### Scenario: 目录条目在执行前失效

- **WHEN** 目录条目被禁用、权限变化、类型不再是 `agent` 或固定映射不存在
- **THEN** 分发服务返回 `CAPABILITY_UNAVAILABLE` 或 `DISPATCH_TARGET_UNAVAILABLE`
- **AND** 不执行 Agent 能力

### Requirement: Agent 结果必须转换为受控结构化契约

系统 MUST 将可序列化对象结果转换为与原调用关联的 `AgentCallResult`，并将策略、目标、输入、输出或运行时异常转换为 `AgentCallError`。错误消息 MUST 不包含异常堆栈、凭据、Provider 原文或完整输入。

#### Scenario: Agent 返回 JSON 对象结果

- **WHEN** Agent Runtime 返回映射或可转换为 JSON 对象的模型结果
- **THEN** 分发服务返回 `AgentCallResult`
- **AND** 结果包含原 `call_id`、能力代码和对象形式的 `output`

#### Scenario: Agent 返回非法结果或执行异常

- **WHEN** Agent Runtime 返回非对象结果、目标未配置、输入构造失败或抛出未受控异常
- **THEN** 分发服务返回稳定错误码的 `AgentCallError`
- **AND** 结果不包含底层异常内容且不再自动重试

### Requirement: 单次分发不产生额外状态和副作用

系统 MUST 在一次分发命令内最多调用一次 Agent Runtime，不写入 Conversation、提议存储或任务存储，不调用 LLM 或其他能力分发器。

#### Scenario: 成功或失败后结束当前分发

- **WHEN** Agent Runtime 返回成功或受控失败
- **THEN** 分发服务返回对应结构化结果
- **AND** 不重复执行、不自行创建重试任务且不写入其他状态存储
