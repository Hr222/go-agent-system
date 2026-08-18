## Purpose

平台能力目录统一登记平台可调用的 Agent 与非 Agent 能力，为后续意图识别、用户确认和受控分发提供唯一的能力事实来源。

## Requirements

### Requirement: 平台目录表统一描述可调用能力
系统 MUST 以 `platform_capability` 表作为唯一的 Platform Capability Catalog 事实来源，统一描述 Agent 与非 Agent 能力，为后续意图识别、策略分流、用户确认和受控分发提供唯一的能力事实来源。每条记录 MUST 包含稳定能力代码、能力类型、业务描述、输入输出 Schema、必填资料、确认策略、启用状态、权限、超时、错误边界和固定分发键。

确认策略 MUST 具有以下受控语义：`always` 必须经过显式确认；`never` 仅在服务端再次校验目录、权限和输入后可以无需确认执行；`conditional` 在没有已登记的受控条件规则时必须按 `always` 处理。客户端提交的任何字段均不得覆盖目录策略。

#### Scenario: 登记 Agent 能力
- **WHEN** 迁移或受控种子数据登记 Tender Agent 等 Agent 能力
- **THEN** `platform_capability` 保存包含完整受控字段的记录
- **AND** 数据库和应用层共同保证能力代码唯一、分发键可校验

#### Scenario: 登记非 Agent 能力
- **WHEN** 迁移或受控种子数据登记普通 Chat、RAG 问答或政策判断
- **THEN** 该能力与 Agent 使用同一张 `platform_capability` 表和查询契约
- **AND** 系统不要求将其伪装为 Agent

#### Scenario: 服务端读取无需确认策略

- **WHEN** 服务端读取一个已启用、当前主体有权限且确认策略为 `never` 的目录条目
- **THEN** 系统仅在复核输入契约后将其视为无需用户批准的受控执行候选
- **AND** 浏览器不能通过请求体将其他条目改写为无需确认

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
