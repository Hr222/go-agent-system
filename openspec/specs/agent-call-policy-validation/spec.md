## Purpose

为结构化 Agent 调用提供独立的策略校验边界，确保调用目标、输入、权限、确认状态和目录事实在进入执行阶段前得到一致且安全的校验。

## Requirements

### Requirement: 系统按目录重新校验结构化 Agent 调用

系统 MUST 在校验 `StructuredAgentCall` 时从平台能力目录重新读取目标条目，并确认条目已启用、当前主体满足权限且能力类型为 `agent`。调用对象中的能力代码不得覆盖目录事实。

#### 场景：调用目标是当前主体可用的 Agent 能力

- **WHEN** 结构化调用的能力代码对应已启用、权限满足且类型为 `agent` 的目录条目
- **THEN** 系统继续执行输入和确认策略校验
- **AND** 不调用任何 Agent 或业务执行器

#### 场景：能力不存在、禁用、无权限或不是 Agent

- **WHEN** 目录无法返回可用条目，当前主体无权访问，或条目类型为 `chat`、`knowledge_qa` 或 `policy_decision`
- **THEN** 系统返回受控拒绝或不可用结果
- **AND** 不产生授权结果或执行行为

### Requirement: 系统按目录输入 Schema 校验调用输入

系统 MUST 使用当前目录条目的输入 Schema 和必填字段校验 `StructuredAgentCall.inputs`。缺失字段、未知字段或类型不匹配时，系统 MUST 返回稳定的输入校验错误，不得进入确认或授权。

#### 场景：Agent 调用输入符合目录契约

- **WHEN** 调用输入满足目录声明的字段、必填资料和 JSON 类型
- **THEN** 系统继续评估确认策略

#### 场景：Agent 调用输入不符合目录契约

- **WHEN** 调用输入缺少必填字段、包含未声明字段或字段类型不匹配
- **THEN** 系统返回 `INPUT_VALIDATION_FAILED`
- **AND** 系统不返回已授权状态

### Requirement: 系统按确认策略决定授权状态

系统 MUST 以目录中的 `confirmation_policy` 为唯一事实来源。`always` 和未配置独立条件规则的 `conditional` MUST 在没有匹配批准时返回需要确认；`never` 在目录、权限和输入校验通过后可以返回已授权。

#### 场景：需要显式确认的 Agent 调用

- **WHEN** Agent 调用通过目录、权限和输入校验，且策略为 `always` 或 `conditional`，但没有批准分发对象
- **THEN** 系统返回 `confirmation_required`
- **AND** 系统不返回已授权调用

#### 场景：无需确认的 Agent 调用

- **WHEN** Agent 调用通过目录、权限和输入校验，且策略为 `never`
- **THEN** 系统返回 `authorized`
- **AND** 系统不调用 Agent Runtime 或其他执行器

### Requirement: 系统严格匹配已确认提议

系统 MUST 将传入的 `ApprovedCapabilityDispatch` 与当前结构化调用和目录条目进行精确匹配：能力代码、目录固定 `dispatch_key` 和输入对象均必须一致。缺失或不匹配时不得返回已授权状态；校验服务不得消费提议存储。

#### 场景：已确认提议与调用和目录一致

- **WHEN** 需要确认的调用带有由确认层产生的批准分发对象，且能力代码、固定分发键和输入完全一致
- **THEN** 系统返回 `authorized`
- **AND** 返回结果仍不执行 Agent 或其他业务能力

#### 场景：已确认提议与调用或目录不一致

- **WHEN** 批准对象的能力代码、分发键或输入与当前调用/目录任一不一致
- **THEN** 系统返回 `APPROVAL_MISMATCH`
- **AND** 系统不返回已授权状态

### Requirement: 策略校验失败不泄漏内部信息

系统 MUST 将目录异常、能力不可用、权限不足、输入无效、确认缺失和提议不匹配映射为稳定错误码和安全消息。校验过程 MUST 不调用 LLM、Agent Runtime、Provider、Dispatcher 或业务 Use Case。

#### 场景：目录服务不可用

- **WHEN** 读取能力目录时发生基础设施或 Provider 异常
- **THEN** 系统返回 `CAPABILITY_CATALOG_UNAVAILABLE`
- **AND** 返回消息不包含异常堆栈、凭据、权限集合或原始输入
