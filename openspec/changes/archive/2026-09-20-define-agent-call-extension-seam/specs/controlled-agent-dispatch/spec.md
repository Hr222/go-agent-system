## MODIFIED Requirements

### Requirement: 只有策略授权的结构化 Agent 调用才能执行

系统 MUST 在执行 `StructuredAgentCall` 前调用 Agent Call 策略校验。只有策略结果为 `authorized` 时，分发服务才可以调用由 Composition Root 注入的 Agent 执行策略；确认缺失、拒绝、不可用或输入无效时 MUST 返回受控结果且不产生 Agent 执行。

#### Scenario: 调用通过策略校验后执行

- **WHEN** 结构化 Agent 调用的目录、权限、输入和确认提议均通过校验
- **THEN** 分发服务调用一次注入的 Agent 执行策略
- **AND** 将调用关联标识传递到结构化成功或失败结果

#### Scenario: 调用未获授权

- **WHEN** 策略结果为 `confirmation_required`、`rejected` 或 `unavailable`
- **THEN** 分发服务返回对应的受控状态和错误码
- **AND** 不调用 Agent 执行策略或 Agent Runtime

### Requirement: Agent 执行目标只能来自当前目录的固定映射

系统 MUST 在执行前按可信主体重新读取当前启用且有权限的 `agent` 目录条目，并将该条目的固定 `dispatch_key` 交给已组装的 Agent 执行策略。模型、客户端、确认提议和执行策略实现不得提供或覆盖执行器地址。

#### Scenario: 目录条目与固定运行时映射一致

- **WHEN** 当前目录条目类型为 `agent` 且其固定分发键已由 Composition Root 注册
- **THEN** 分发服务将能力代码、目录分发键和标准化输入交给 Agent 执行策略
- **AND** 不创建目录之外的执行目标

#### Scenario: 目录条目在执行前失效

- **WHEN** 目录条目被禁用、权限变化、类型不再是 `agent` 或固定映射不存在
- **THEN** 分发服务返回 `CAPABILITY_UNAVAILABLE` 或 `DISPATCH_TARGET_UNAVAILABLE`
- **AND** 不执行 Agent 能力或执行策略
