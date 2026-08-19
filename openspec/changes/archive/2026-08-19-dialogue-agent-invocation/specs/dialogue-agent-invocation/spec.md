## ADDED Requirements

### Requirement: 对话可以执行一次已授权的结构化 Agent 调用

系统 MUST 在可信主体和 Conversation 校验通过后，将结构化 `AgentCall` 交给 P2.6 受控分发服务。只有分发结果为成功时才视为 Agent 已执行；确认缺失、策略拒绝、目录不可用或运行时失败时 MUST 返回受控状态且不得重复调用 Agent。

#### Scenario: 已确认的 Tender Agent 调用成功

- **WHEN** 当前主体拥有目录要求的权限，结构化调用输入有效且批准提议与调用严格匹配
- **THEN** Dialogue Agent Invocation 调用一次受控 Agent Runtime
- **AND** 返回 `completed` 状态、调用 ID 和结构化结果摘要

#### Scenario: 调用尚未获得确认

- **WHEN** Agent Call 策略返回 `confirmation_required`
- **THEN** 系统返回待确认状态
- **AND** 不调用 Agent Runtime、不写入虚构的助手文本

### Requirement: Agent 调用结果必须关联到 Conversation 事件

系统 MUST 将 `agent_call`、`agent_result` 或 `agent_error` 作为有序 Conversation 事件持久化。每个结果事件 MUST 包含 Conversation ID、调用 ID、能力代码、事件顺序和 JSON 对象载荷。

#### Scenario: 成功结果写入事件

- **WHEN** Agent Runtime 返回可序列化的成功结果
- **THEN** 系统持久化一个 `agent_result` 事件
- **AND** 历史读取可以按事件顺序和调用 ID 找到该结果

#### Scenario: 失败结果写入事件

- **WHEN** 策略校验、目录读取、输入构造或 Agent Runtime 返回受控失败
- **THEN** 系统持久化一个 `agent_error` 事件
- **AND** 事件只包含稳定错误码和安全消息，不包含堆栈、凭据或原始输入

### Requirement: Tender 文件结果只能以安全资源元数据进入事件

系统 MUST 将 Tender Agent 返回的文件对象投影为文件名、媒体类型、大小和服务端资源标识等 JSON 元数据。系统 MUST NOT 将文件原始字节、Provider 响应或执行器对象写入 Conversation 事件或 HTTP JSON 响应。

#### Scenario: Agent 返回包含文件的结果

- **WHEN** Tender Agent 返回分析结果和一个或多个生成文件
- **THEN** 事件保存分析摘要与文件元数据
- **AND** 页面可以显示文件名称、类型和大小

#### Scenario: Agent 结果无法安全投影

- **WHEN** Agent 返回不可序列化对象或不符合白名单结构
- **THEN** 系统返回 `AGENT_OUTPUT_INVALID`
- **AND** 不持久化原始对象或二进制内容

### Requirement: V2 对话入口不暴露内部授权字段

系统 MUST 提供一个可创建或复用 Conversation 的 V2 Agent 调用入口。请求可以包含会话标识、用户可见文本、能力代码和业务输入，但 MUST 拒绝或忽略客户端提供的权限、分发键、执行器地址和批准对象；权限和批准事实必须来自服务端主体与确认边界。

#### Scenario: 页面创建新会话并提交调用

- **WHEN** 页面未提供会话标识但提交合法 Agent 调用请求
- **THEN** 系统创建 Conversation、生成调用 ID 并返回会话标识及受控执行状态

#### Scenario: 客户端伪造内部授权字段

- **WHEN** 请求包含 `dispatch_key`、权限、执行器 URL 或伪造批准对象
- **THEN** 系统拒绝未知字段或不使用这些字段授予执行权限
- **AND** 不因伪造字段绕过策略校验

### Requirement: 单次 Agent Invocation 不自动续写最终助手消息

系统 MUST 在本 Change 中只保存用户请求和 Agent 事件，不自动调用普通 Chat LLM 生成最终自然语言助手消息。Agent 结果必须保留关联 ID，供后续 Dialogue Agent Continuation 使用。

#### Scenario: Agent 执行完成后等待后续续写

- **WHEN** Agent 调用成功并写入 `agent_result` 事件
- **THEN** HTTP 响应返回结构化结果状态
- **AND** 当前 Conversation 不新增虚构的自然语言 assistant Message
