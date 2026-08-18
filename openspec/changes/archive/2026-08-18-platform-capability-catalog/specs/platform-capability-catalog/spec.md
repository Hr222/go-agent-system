## ADDED Requirements

### Requirement: V2 模块通过目录端口消费能力事实
系统 MUST 将 `platform_capability` 及其只读目录端口作为平台能力的唯一事实来源。Interaction Gateway、Agent Runtime 和后续编排能力 MUST 通过 `CapabilityCatalogPort` 获取可用条目，不得维护与目录并行的能力注册表；目录 MUST 统一表达 Agent 与非 Agent 能力。

#### Scenario: 消费者读取当前主体可用的能力
- **WHEN** Gateway、Agent Runtime 或后续编排能力以当前主体权限查询能力目录
- **THEN** 系统仅返回已启用且满足目录权限要求的条目
- **AND** 返回的条目保留能力代码、类型、输入输出 Schema、确认策略和受控分发键

#### Scenario: Agent Runtime 查询目录
- **WHEN** Agent Runtime 请求可处理的能力
- **THEN** 系统仅从目录返回 `capability_type = agent` 的已授权条目
- **AND** 非 Agent 条目不得被 Agent Runtime 当作 Agent 执行

### Requirement: 目录不承担对话编排或执行职责
平台能力目录 MUST 只负责能力事实、静态受控配置校验和可见性过滤。目录不得识别用户自然语言、创建确认提议、授权结构化调用、校验某次调用输入或执行 Agent 与其他 Use Case。

#### Scenario: 读取目录条目
- **WHEN** 调用方读取某个可用能力或能力列表
- **THEN** 系统仅返回目录条目或不可用结果
- **AND** 系统不得在该读取过程中创建提议、写入 Conversation 或调用任何能力处理器

#### Scenario: 后续调用链使用目录条目
- **WHEN** 后续模块基于目录条目形成候选、确认或调用请求
- **THEN** 候选识别、确认策略、输入校验和实际分发分别由对应模块处理
- **AND** 目录查询结果不得直接视为本次请求已获执行授权
