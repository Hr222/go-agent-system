## MODIFIED Requirements

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
