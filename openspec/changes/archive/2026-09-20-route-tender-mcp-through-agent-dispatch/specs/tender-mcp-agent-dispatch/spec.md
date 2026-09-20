## ADDED Requirements

### Requirement: Tender MCP 工具必须通过统一 Agent 分发执行

三个 Tender MCP 工具 MUST 将协议输入组装为 `StructuredAgentCall`，并通过
`AgentCallDispatcher` 执行。MCP Adapter MUST NOT 直接取得或调用 `TenderApplication`，也
不得绕过能力目录、主体权限、输入契约或固定分发键。

#### Scenario: 合法主体调用骨架生成工具

- **WHEN** 已解析的可信主体拥有当前目录要求的 Tender 权限，并调用
  `tender.generate_bid_skeleton`
- **THEN** MCP Adapter 使用服务端固定能力代码构造一次结构化调用
- **AND** `AgentCallDispatcher` 完成目录、权限、输入和运行时校验后执行 Tender Agent
- **AND** MCP 返回同步的结构化分析和生成文件资源

#### Scenario: MCP 调用没有受保护权限

- **WHEN** MCP 请求没有可信主体，或主体不满足当前 Tender 能力的权限要求
- **THEN** Dispatcher 返回受控拒绝结果
- **AND** MCP 返回稳定的能力不可用或未授权错误
- **AND** Tender Application、文档解析器和模型服务均不被调用

#### Scenario: MCP 适配器不提供第二条 Tender 执行路径

- **WHEN** 代码审查或架构测试检查 Tender MCP 适配器的依赖
- **THEN** 适配器只依赖 Dispatcher、主体解析、附件 Port 和 MCP 类型
- **AND** 适配器不直接依赖 Tender Application、Repository、SQLAlchemy Session 或 Provider SDK

### Requirement: MCP 主体必须由服务端安全解析

MCP 请求的 `RequestPrincipal` MUST 由服务端注入的 `PrincipalResolverPort` 从协议请求
上下文解析。工具参数、MCP 扩展字段和客户端自报的权限、主体、能力代码或分发键 MUST
NOT 改变解析结果。

#### Scenario: 受控部署使用静态主体

- **WHEN** 服务端配置为静态主体模式，且静态主体包含 Tender 所需权限
- **THEN** MCP 调用使用该服务端配置的主体和权限通过 Dispatcher 校验
- **AND** 请求 Header 中自报的权限不能增加或替换服务端权限

#### Scenario: 匿名主体调用受保护 Tender 能力

- **WHEN** 服务端解析结果为匿名主体
- **THEN** MCP 返回受控的主体不可用或能力不可用错误
- **AND** 系统不得把匿名请求升级为拥有 Tender 权限的主体

#### Scenario: 客户端提交伪造授权字段

- **WHEN** MCP 工具参数中包含 `subject`、`permissions`、`capability_code` 或
  `dispatch_key`
- **THEN** 这些字段不参与主体、能力或执行目标决策
- **AND** 请求仍使用服务端固定映射和解析出的主体执行校验

### Requirement: MCP 工具必须使用固定能力映射和受控调用关联

MCP Adapter MUST 使用服务端固定的工具到能力代码映射；客户端不得选择能力代码或执行
目标。每次工具调用 MUST 生成新的 `call_id` 和 `run_id`，不得创建 Conversation、Task 或
SubAgent 父子关系。

#### Scenario: 三个 V1 工具使用固定映射

- **WHEN** MCP 客户端调用三个已注册的 Tender 工具之一
- **THEN** 系统分别映射到对应的 `tender.*` 能力代码
- **AND** Dispatcher 从当前目录取得对应的 `agent.tender.*` 固定分发键
- **AND** MCP 请求不能替换该映射

#### Scenario: 一次 MCP 请求建立新的关联标识

- **WHEN** MCP 工具调用进入 Dispatcher
- **THEN** 系统生成非空且新的 `call_id` 和 `run_id`
- **AND** `conversation_id`、`turn_id`、`parent_run_id` 保持为空
- **AND** 系统不写入 Task、Conversation 或调用事件持久化

### Requirement: MCP 输入输出必须保持 V1 协议兼容

MCP Server MUST 继续暴露原有三个工具名和公开输入字段，并在调用内严格校验 Base64、
文件大小、文件类型和工具专属字段。成功的二进制结果 MUST 继续以 MCP
`EmbeddedResource` 表达；内部附件 ID、目录字段和 Dispatcher 结构 MUST NOT 泄露给客户端。

#### Scenario: 客户端发现 V1 工具

- **WHEN** MCP 客户端请求工具列表
- **THEN** 返回 `tender.generate_bid_skeleton`、`tender.extract_bid_format_section`
  和 `tender.verify_extraction_boundary`
- **AND** 工具 Schema 保持现有公开字段和必填约束
- **AND** 工具列表不宣称尚未实现的 Tender 能力

#### Scenario: Base64 或文件约束校验失败

- **WHEN** 客户端提交无效 Base64、空文件、非 DOCX 文件或超过配置大小限制的输入
- **THEN** MCP 返回稳定的输入错误
- **AND** Dispatcher 和 Tender Agent 不开始文档解析、模型调用或渲染

#### Scenario: Dispatcher 返回带附件资源的成功结果

- **WHEN** Tender Agent 生成一个或多个 DOCX artifact，Dispatcher 已完成安全附件暂存
- **THEN** MCP 通过 Attachment Port 在当前主体上下文中读取 artifact
- **AND** 返回既有文件元数据及 `EmbeddedResource` 内容
- **AND** MCP 不直接读取文件系统，也不返回内部 `resource_id`

### Requirement: MCP 请求资源和错误必须受控清理与映射

每次 MCP 调用 MUST 使用短生命周期的请求作用域管理数据库 Session、目录读取和附件
访问。成功、拒绝、目录不可用、执行失败和响应投影失败后 MUST 关闭请求资源并清理本次
调用产生的临时附件。MCP 错误 MUST 使用稳定代码和安全消息。

#### Scenario: 请求成功或失败后关闭作用域

- **WHEN** MCP 调用完成、被拒绝或在 Tender 运行时抛出受控失败
- **THEN** 请求作用域关闭 Session 并执行适用的附件清理
- **AND** 长生命周期 MCP Server 不保留该请求的 Session、主体或二进制内容

#### Scenario: 目录或附件存储不可用

- **WHEN** 能力目录不可用，或 Dispatcher 成功后 MCP 无法读取输出附件
- **THEN** MCP 返回受控的能力目录不可用或资源投影错误
- **AND** 错误不包含数据库异常、文件路径、Provider 原文或凭据

#### Scenario: Tender 业务失败映射为稳定 MCP 错误

- **WHEN** Tender 输入、DOCX 解析、模型配置、上游调用、分析结果或渲染阶段失败
- **THEN** MCP 映射到既有稳定错误类别或对应的统一 Dispatcher 错误
- **AND** 错误响应不暴露未审查的异常堆栈或完整输入
