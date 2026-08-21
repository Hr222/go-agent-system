## ADDED Requirements

### Requirement: Conversation 保存可信主体归属

系统 MUST 为每个 Conversation 保存非空的 `owner_subject`。该值 MUST 是稳定、不透明的主体标识，不得由客户端请求体、展示名称、角色或模型输出决定。

#### Scenario: 静态主体创建会话

- **WHEN** 可信静态 resolver 提供非空 `subject` 并创建 Conversation
- **THEN** 新 Conversation 保存相同的 `owner_subject`
- **AND** 归属值可由持久化层无损恢复

#### Scenario: 归属键无效

- **WHEN** 应用层尝试以空白或非字符串归属键创建 Conversation
- **THEN** 系统拒绝创建
- **AND** 数据库不保存无归属 Conversation

### Requirement: 既有 Conversation 迁移保持归属可审查

系统 MUST 在为既有 Conversation 引入 `owner_subject` 时先回填受控迁移主体或停止迁移。系统 MUST NOT 静默把未确认归属的数据分配给任意运行时请求主体。

#### Scenario: 存在未归属历史记录

- **WHEN** 迁移发现已有 Conversation 没有受控归属来源
- **THEN** 系统报告并阻止非空约束生效，或使用显式配置的迁移主体完成回填
- **AND** 后续请求主体不会因此获得该记录的隐式访问权
