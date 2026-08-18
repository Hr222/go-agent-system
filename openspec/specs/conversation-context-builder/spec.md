# conversation-context-builder Specification

## Purpose
TBD - created by archiving change conversation-context-builder. Update Purpose after archive.
## Requirements
### Requirement: 系统构建模型中立的会话上下文
系统 MUST 能够从调用方提供的同一 Conversation 有序 Message 窗口构建 `ModelContext`。上下文消息 MUST 保留来源 Message 的标识、角色、原始内容和顺序号；输出消息 MUST 按顺序号升序排列。构建过程 MUST 不调用 LLM、不写入持久化存储。

#### Scenario: 从有序历史构建上下文
- **WHEN** 调用方提供同一 Conversation 中顺序号为 1、2、3 的有效消息和足够的策略、预算
- **THEN** 系统返回关联该 Conversation 的 `ModelContext`
- **AND** 上下文消息按 1、2、3 的顺序排列并保留每条消息的来源标识、角色和原始内容
- **AND** 构建过程不产生模型调用或持久化写入

### Requirement: 系统优先保留最新且连续的消息后缀
系统 MUST 在 `ContextPolicy.max_messages` 和预算约束内，从候选窗口的最新消息开始选择连续后缀，并在返回时恢复为正序。系统 MUST 不跳过无法容纳的较早消息后再选择更早消息。

#### Scenario: 消息数量策略限制历史窗口
- **WHEN** 调用方提供顺序号为 1、2、3、4 的消息，策略最多允许 2 条且预算足够
- **THEN** 系统只返回顺序号为 3、4 的消息
- **AND** 返回顺序仍为 3、4
- **AND** 结果标记省略了 2 条较早消息

#### Scenario: 较早消息无法容纳时保留较新后缀
- **WHEN** 最新两条消息可容纳，但紧邻的较早消息会使总成本超过预算
- **THEN** 系统只返回这两条较新消息
- **AND** 系统不跳过该较早消息再选择更早消息

### Requirement: 系统通过可替换的成本计量执行预算
系统 MUST 通过 Conversation 的消息成本计量 Port 计算上下文成本，并将已用成本与预算上限一同返回。首版 MUST 提供不依赖模型 SDK 的确定性字符计量实现。计量器返回负值、非整数或布尔值时，系统 MUST 拒绝构建。

#### Scenario: 字符计量限制上下文
- **WHEN** 使用字符计量器且候选消息内容总字符数超过成本上限
- **THEN** 系统仅返回能够容纳的最新连续消息后缀
- **AND** 返回的已用成本不得超过预算上限

#### Scenario: 最新消息自身超过预算
- **WHEN** 最新消息的成本大于总预算
- **THEN** 系统拒绝构建并返回明确的上下文预算不足错误
- **AND** 系统不得截断该消息或返回不包含该最新消息的上下文

### Requirement: 系统拒绝无效策略和不一致的历史输入
系统 MUST 拒绝非正整数的消息数量上限或预算上限。系统 MUST 拒绝不属于目标 Conversation、顺序号未严格递增或包含无效领域消息的输入窗口。

#### Scenario: 输入窗口包含其他会话消息
- **WHEN** 调用方传入的消息中存在 `conversation_id` 与目标 Conversation 不一致的记录
- **THEN** 系统拒绝构建上下文
- **AND** 系统不得返回包含该消息的 `ModelContext`

#### Scenario: 输入窗口顺序不正确
- **WHEN** 调用方传入的消息顺序号相等或递减
- **THEN** 系统拒绝构建上下文
- **AND** 系统不得重排输入以掩盖该错误

