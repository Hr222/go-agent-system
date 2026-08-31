## ADDED Requirements

### Requirement: 系统能够读取有界的最近消息快照

系统 MUST 为上下文构建提供只读的最近消息快照能力。调用方提供 Conversation 标识、包含上限的 `through_sequence` 和消息数量上限后，系统 MUST 只返回该 Conversation 中 `sequence <= through_sequence` 的最近消息，返回结果 MUST 按 `sequence` 升序排列。该能力 MUST 不扫描或返回上限之外的更早消息。

#### Scenario: 长会话只读取上下文窗口

- **WHEN** 一个 Conversation 已有 100 条消息，当前请求的 user Message 为 `sequence = 101`，上下文消息上限为 20
- **THEN** 最近消息快照只包含顺序号 82 到 101 的消息
- **AND** 返回消息按 82 到 101 升序排列
- **AND** 更早消息仍保留在 Conversation 历史中但不进入本轮模型上下文

#### Scenario: 空历史边界返回空窗口

- **WHEN** 已存在的 Conversation 在给定 `through_sequence` 前没有消息
- **THEN** 系统返回空的最近消息快照
- **AND** 系统不把空窗口伪装成其他 Conversation 的消息

### Requirement: 最近消息快照必须遵守顺序截止边界

系统 MUST 将 `through_sequence` 视为本轮上下文的包含边界。快照 MUST 排除任何顺序号大于该边界的消息，即使这些消息在读取期间已经被其他请求追加。系统 MUST 拒绝非正整数的顺序边界或消息数量上限。

#### Scenario: 读取边界不包含更晚消息

- **WHEN** 最近消息读取被调用时，当前 Conversation 已存在 `sequence = 4` 的消息，但调用方提供 `through_sequence = 3`
- **THEN** 最近消息快照最多包含顺序号为 3 的消息
- **AND** 快照不包含顺序号为 4 的消息
- **AND** 普通流式 Chat 由既有 Conversation 轮次租约保证同一会话的后续轮次不会在当前轮次内提前写入

#### Scenario: 快照参数无效

- **WHEN** 调用方提供非正的 `through_sequence` 或消息数量上限
- **THEN** 系统拒绝构建最近消息快照
- **AND** 系统不执行未受约束的历史读取

### Requirement: 最近消息快照与现有上下文预算协同

系统 MUST 将最近消息快照交给现有 Conversation Context Builder，并继续使用现有 `ContextPolicy`、`ContextBudget` 和成本计量器。最近消息读取上限 MUST 不得大于本轮上下文策略允许的消息数量；预算裁剪、连续后缀选择、最新消息超预算失败和消息内容完整性 MUST 继续由 Context Builder 负责。

#### Scenario: 快照窗口内执行成本预算

- **WHEN** 最近消息快照包含不超过策略上限的消息，但其字符成本超过现有上下文预算
- **THEN** 系统按现有 Context Builder 规则保留能够容纳的最新连续消息后缀
- **AND** 模型请求的已用成本不超过预算上限
- **AND** 系统不为预算裁剪重新读取更早历史

#### Scenario: 当前 user 超出预算

- **WHEN** 快照中最新的当前 user Message 单独超过现有上下文预算
- **THEN** 系统返回受控预算失败
- **AND** 系统不截断当前 user Message、不调用 Provider 且不写入 assistant Message
