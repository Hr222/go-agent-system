## MODIFIED Requirements

### Requirement: 只有策略授权的结构化 Agent 调用才能执行

系统 MUST 在执行 `StructuredAgentCall` 前调用 Agent Call 策略校验。MCP、对话或其他
协议适配器提交的调用只有在目录、主体权限、输入和确认策略结果为 `authorized` 时，
分发服务才可以调用由 Composition Root 注入的 Agent 执行策略；确认缺失、拒绝、不可用
或输入无效时 MUST 返回受控结果且不产生 Agent 执行。

#### Scenario: 调用通过策略校验后执行

- **WHEN** MCP 或其他协议适配器提交的结构化 Agent 调用的目录、可信主体权限、输入和确认提议均通过校验
- **THEN** 分发服务调用一次注入的 Agent 执行策略
- **AND** 将调用关联标识传递到结构化成功或失败结果

#### Scenario: 调用未获授权

- **WHEN** MCP 或其他协议调用的策略结果为 `confirmation_required`、`rejected` 或 `unavailable`
- **THEN** 分发服务返回对应的受控状态和错误码
- **AND** 不调用 Agent 执行策略或 Agent Runtime

### Requirement: Agent 执行目标只能来自当前目录的固定映射

系统 MUST 在执行前按可信主体重新读取当前启用且有权限的 `agent` 目录条目，并将该条目
的固定 `dispatch_key` 交给已组装的 Agent 执行策略。MCP、模型、客户端、确认提议和执行
策略实现不得提供或覆盖执行器地址。

#### Scenario: 目录条目与固定运行时映射一致

- **WHEN** MCP 工具或其他调用映射出的能力条目类型为 `agent` 且其固定分发键已由 Composition Root 注册
- **THEN** 分发服务将能力代码、目录分发键和标准化输入交给 Agent 执行策略
- **AND** 不创建客户端提供的 URL、类名、函数名或目录之外的执行目标

#### Scenario: 目录条目在执行前失效

- **WHEN** 目录条目被禁用、权限变化、类型不再是 `agent` 或固定映射不存在
- **THEN** 分发服务返回 `CAPABILITY_UNAVAILABLE` 或 `DISPATCH_TARGET_UNAVAILABLE`
- **AND** 不执行 Agent 能力或执行策略

### Requirement: Agent 结果必须转换为受控结构化契约

系统 MUST 将可序列化对象结果转换为与原调用关联的 `AgentCallResult`，并将策略、目标、
输入、输出或运行时异常转换为 `AgentCallError`。错误消息 MUST 不包含异常堆栈、凭据、
Provider 原文或完整输入；包含二进制 artifact 的结果 MUST 通过受控附件存储转换为资源
引用后再交给协议适配器。

#### Scenario: Agent 返回 JSON 对象结果

- **WHEN** MCP 或其他协议对应的 Agent Runtime 返回映射或可转换为 JSON 对象的模型结果
- **THEN** 分发服务返回 `AgentCallResult`
- **AND** 结果包含原 `call_id`、能力代码和对象形式的 `output`

#### Scenario: Agent 返回二进制 artifact

- **WHEN** Agent Runtime 返回带文件内容的 Tender artifact
- **THEN** 分发服务将内容写入当前主体可访问的受控附件存储
- **AND** `AgentCallResult` 只暴露文件名、媒体类型、大小和资源标识，不保留可序列化输出中的原始 bytes

#### Scenario: Agent 返回非法结果或执行异常

- **WHEN** Agent Runtime 返回非对象结果、目标未配置、输入构造失败或抛出未受控异常
- **THEN** 分发服务返回稳定错误码的 `AgentCallError`
- **AND** 结果不包含底层异常内容且不再自动重试

### Requirement: 单次分发不产生额外状态和副作用

系统 MUST 在一次分发命令内最多调用一次 Agent Runtime，不写入 Conversation、提议存储
或任务存储，不调用 LLM 或其他能力分发器。MCP 适配器不得通过 Dispatcher 之外的路径
重复执行同一个工具调用。

#### Scenario: 成功或失败后结束当前分发

- **WHEN** MCP 或其他协议对应的 Agent Runtime 返回成功或受控失败
- **THEN** 分发服务返回对应结构化结果
- **AND** 不重复执行、不自行创建重试任务且不写入其他状态存储
