## Purpose

定义统一交互入口如何组合意图识别、权限过滤、用户确认和受控分发，并将该入口作为 Chat 页面的内部路由层。该能力不替换现有直接 Chat、Agent、RAG 或知识库接口。

## Requirements

### Requirement: 统一入口向用户返回可确认的意图结果

系统 MUST 通过独立的统一交互入口接收自然语言请求，并返回识别、澄清、待确认、取消或失败等受控状态；系统不得以模型自由文本作为执行指令。

#### Scenario: 用户请求需要业务能力

- **WHEN** 用户通过统一入口提交自然语言请求
- **THEN** 系统返回识别结果、缺失资料或待确认提议
- **AND** 用户可以在界面中看到拟使用的能力和下一步操作

#### Scenario: 意图识别作为 Chat 内部路由

- **WHEN** 用户在 Chat 中发送自然语言消息
- **THEN** Chat 在后台消费统一交互入口完成候选召回、识别和权限过滤
- **AND** 用户无需进入独立的意图识别页面，只有待执行提议需要批准时才看到确认卡片

### Requirement: 只有明确确认后才能受控分发

系统 MUST 仅在确认结果有效、目录条目启用、权限满足且输入完整时，通过固定分发键调用目标 Application Use Case。

#### Scenario: 用户确认 Agent 能力

- **WHEN** 用户明确确认一个有效的 Tender Agent 提议
- **THEN** Controlled Dispatcher 调用对应 Agent Runtime 用例
- **AND** 分发目标由目录的固定分发键决定

#### Scenario: 用户确认非 Agent 能力

- **WHEN** 用户明确确认一个有效的 RAG 问答或政策判断提议
- **THEN** Controlled Dispatcher 调用对应 Online Application 用例
- **AND** 系统不为了执行该能力启动 Agent Runtime

#### Scenario: 用户未确认或已取消

- **WHEN** 用户未确认、拒绝或取消待确认提议
- **THEN** 系统不调用任何目标能力

### Requirement: 授权来源必须来自服务端请求主体

系统 MUST 通过已归档的服务端请求主体解析契约获取权限，MUST NOT 将客户端文本、请求体中的权限字段、角色字段或分发键视为授权依据。没有用户管理时，系统 MUST 消费匿名主体的空权限集合。

#### Scenario: 匿名用户请求受保护 Agent

- **WHEN** 当前请求没有可验证的用户身份，且目标能力要求受保护权限
- **THEN** 系统返回不可用或澄清状态
- **AND** 系统不调用 Agent Runtime

#### Scenario: 客户端伪造权限字段

- **WHEN** 客户端在请求中提交了额外权限或角色字段
- **THEN** 系统忽略这些字段并使用服务端解析的主体权限
- **AND** 系统不因该字段获得额外分发权限

### Requirement: 目录输入必须映射到真实分发命令

系统 MUST 在分发前将能力目录输入映射到对应的 Application Command；目录不得继续声明无法映射的历史字段。映射失败时，系统 MUST 返回受控失败而不调用目标能力。

#### Scenario: 用户确认政策判断能力

- **WHEN** 用户确认 `policy.review` 的有效提议
- **THEN** 系统仅使用 `scenario_code`、`submitted_materials`、`top_k`、`document_id` 和 `include_history` 构造 `DecisionReviewCommand`
- **AND** 系统不使用无法映射的 `answers` 字段

#### Scenario: 目录输入无法映射

- **WHEN** 已确认能力的目录输入无法构造其目标 Application Command
- **THEN** 系统返回受控分发失败
- **AND** 系统不调用目标能力

### Requirement: HTTP 确认提议必须短期且一次消费

系统 MUST 使用服务端生成的短期确认提议标识关联识别结果，并在确认或取消后使提议不可再次消费。该机制不得创建 Conversation、Task 或持久化业务任务。

#### Scenario: 确认提议被重复提交

- **WHEN** 同一个确认提议已经确认、取消或过期后再次提交确认
- **THEN** 系统拒绝该请求
- **AND** 系统不重复调用目标能力

### Requirement: 既有直接接口保持兼容

系统 MUST 保持现有 Chat、Agent、RAG 和知识库 HTTP 接口的请求与响应行为不变；统一入口是新增入口而非强制中间层。

#### Scenario: 现有调用方使用直接接口

- **WHEN** 现有调用方请求既有业务 HTTP 接口
- **THEN** 系统按现有契约处理该请求
- **AND** 系统不要求其先经过意图识别或确认
