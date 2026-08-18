## ADDED Requirements

### Requirement: 平台目录表统一描述可调用能力
系统 MUST 以 `platform_capability` 表作为唯一的 Platform Capability Catalog 事实来源，统一描述 Agent 与非 Agent 的可调用能力。每条记录 MUST 包含稳定能力代码、能力类型、业务描述、输入输出 Schema、必填资料、确认策略、启用状态、权限、超时、错误边界和固定分发键。

#### Scenario: 登记 Agent 能力
- **WHEN** 迁移或受控种子数据登记 Tender Agent 等 Agent 能力
- **THEN** `platform_capability` 保存包含完整受控字段的记录
- **AND** 数据库和应用层共同保证能力代码唯一、分发键可校验

#### Scenario: 登记非 Agent 能力
- **WHEN** 迁移或受控种子数据登记普通 Chat、RAG 问答或政策判断
- **THEN** 该能力与 Agent 使用同一张 `platform_capability` 表和查询契约
- **AND** 系统不要求将其伪装为 Agent

### Requirement: 目录记录在使用前可验证
系统 MUST 通过数据库约束和应用层校验拒绝能力代码重复、缺少必填字段、类型与分发键不匹配或无效分发键的记录，并且只向消费者返回启用且满足权限条件的能力。

#### Scenario: 写入无效目录记录
- **WHEN** 迁移、种子或受控写入包含重复能力代码、缺失受控字段或无效分发键的记录
- **THEN** 数据库约束或应用层校验报告明确错误
- **AND** 无效记录不进入可调用目录

#### Scenario: 查询禁用或无权限能力
- **WHEN** 消费者查询已禁用或权限不满足的目录记录
- **THEN** Repository/Application 不将该能力作为可调用条目返回

### Requirement: 分发键只能映射到受控 Use Case
系统 MUST 将 `dispatch_key` 视为固定代码标识，并在组装时映射到已知 Application Use Case；系统 MUST 拒绝 URL、类名、函数名或目录外目标作为分发值。

#### Scenario: 目录记录引用已知分发键
- **WHEN** `platform_capability` 记录的分发键与能力类型匹配已组装 Use Case
- **THEN** 目录记录可以被消费者读取
- **AND** 记录不包含可直接执行的外部地址或代码对象

#### Scenario: 目录记录引用未知分发键
- **WHEN** 目录记录的分发键未被 Composition Root 注册或与能力类型不匹配
- **THEN** 系统在加载或校验时报告错误
- **AND** 该记录不可被分发

### Requirement: Agent Runtime 消费而不拥有目录
系统 MUST 让 Agent Runtime 通过 Application Port 和 Repository 从平台目录消费 Agent 条目，并禁止新建与目录并行的 Agent 能力注册来源。

#### Scenario: Runtime 查找 Agent 能力
- **WHEN** Runtime 需要处理已登记的 Agent 能力
- **THEN** 它通过平台目录获取对应 Agent 条目
- **AND** 非 Agent 条目不被交给 Runtime 执行
