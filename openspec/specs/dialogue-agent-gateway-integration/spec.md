## Purpose

定义在正常 Chat 对话中通过统一交互 Gateway 识别 Agent 意图、请求用户确认并执行一次受控 Agent 调用的稳定契约。

## Requirements

### Requirement: Chat 中的 Agent 调用必须由自然语言意图识别发起

系统 MUST 只在 Chat 收到用户自然语言后，通过统一交互 Gateway 完成候选召回、意图识别、权限过滤和确认提议生成。Chat 可以携带用户上传文件的服务端引用等原始上下文；浏览器 MUST NOT 在 Chat Agent 调用请求中提交能力代码、分发键、批准对象或调用标识作为执行授权，且原始上下文 MUST 经 Gateway 与目录校验后才可形成调用输入。

#### Scenario: 自然语言被识别为需要确认的 Agent 能力

- **WHEN** 用户在 Chat 中提交自然语言，Gateway 识别到当前主体可用且需要确认的 Agent 能力
- **THEN** 系统创建或复用 Conversation，追加用户消息并写入状态为 `confirmation_required` 的 `agent_call` 事件
- **AND** SSE 返回带有确认摘要、提议标识和 Conversation 标识的待确认事件

#### Scenario: 用户请求不是 Agent 能力

- **WHEN** Gateway 将 Chat 请求识别为普通聊天、澄清、无法识别或非 Agent 能力
- **THEN** 系统沿用该请求原有的 Chat 或统一交互处理路径
- **AND** 不创建 Agent 调用事件或待确认 Agent 上下文

### Requirement: Chat 中确认 Agent 提议必须经 Gateway 再校验后执行

系统 MUST 在用户确认或取消时由 Gateway 原子消费短期提议并校验主体绑定。确认成功时 Gateway MUST 只返回服务端生成的 `ApprovedCapabilityDispatch`，并由 Dialogue Agent Invocation 通过 P2.6 Dispatcher 执行一次调用；取消时系统 MUST 记录取消终态且不得调用 Agent Runtime。

#### Scenario: 用户确认有效的 Agent 提议

- **WHEN** 当前主体确认一个仍有效且与 Conversation 调用上下文绑定的 Agent 提议
- **THEN** Gateway 返回经过重新校验的批准分发对象但不直接执行目标能力
- **AND** Dialogue Agent Invocation 只调用一次 P2.6 Dispatcher，并写入 `agent_result` 或 `agent_error` 终态事件

#### Scenario: 用户取消有效的 Agent 提议

- **WHEN** 当前主体取消一个仍有效的 Agent 提议
- **THEN** 系统写入稳定的取消终态事件
- **AND** 系统不调用 Agent Runtime 或普通受控分发器

#### Scenario: 提议失效或主体不匹配

- **WHEN** 确认请求对应的提议已过期、已消费或不属于当前主体
- **THEN** 系统返回稳定的不可用错误
- **AND** 系统不执行 Agent，也不写入另一条结果事件

### Requirement: 对话页面只显示 Agent 的安全执行结果

系统 MUST 将确认后的 Agent 调用状态和安全结果摘要返回给 Chat 页面。页面 MUST 在同一条对话中展示待确认、执行完成、失败或取消状态，且 MUST NOT 将原始 Agent 输出、二进制文件、内部权限或分发信息作为浏览器响应内容。

#### Scenario: Agent 调用完成

- **WHEN** 已批准的 Agent 调用成功完成
- **THEN** Chat 页面在产生确认卡片的对话中显示完成状态和已白名单投影的结果摘要
- **AND** 系统不在本能力中自动生成新的自然语言 assistant Message

### Requirement: 独立 Agent 调用页面和 HTTP 入口必须移除

系统 MUST NOT 注册独立的 Agent Invocation HTTP 路由、页面或导航入口。Agent 调用只能通过 Chat 的自然语言、Gateway 提议和确认流程发起。

#### Scenario: 客户端请求旧直达地址

- **WHEN** 浏览器请求旧的 `/api/v1/dialogue/agent-invocations` 地址
- **THEN** 系统返回未找到状态
- **AND** 系统不创建 Conversation、不执行 Agent Runtime
