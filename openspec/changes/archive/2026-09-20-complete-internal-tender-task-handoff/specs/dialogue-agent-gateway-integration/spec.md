## MODIFIED Requirements

### Requirement: Chat 中确认 Agent 提议必须经 Gateway 再校验后执行

系统 MUST 在用户确认或取消时由 Gateway 原子消费短期提议并校验主体绑定。确认成功时 Gateway MUST 只返回服务端生成的 `ApprovedCapabilityDispatch`，并由 Dialogue Agent Invocation 通过 P2.6 Dispatcher 执行一次调用；同步完成时写入 `agent_result`，异步接收时写入受控 `agent_call` 状态，取消时系统 MUST 记录取消终态且不得调用 Agent Runtime。

#### Scenario: 用户确认有效的 Agent 提议

- **WHEN** 当前主体确认一个仍有效且与 Conversation 调用上下文绑定的 Agent 提议
- **THEN** Gateway 返回经过重新校验的批准分发对象但不直接执行目标能力
- **AND** Dialogue Agent Invocation 只调用一次 P2.6 Dispatcher，并写入同步结果、异步接收状态或受控错误终态

#### Scenario: 用户确认后异步调用被接收

- **WHEN** 已批准的内部 Agent 调用被 Dispatcher 异步接收
- **THEN** Chat 确认响应返回 `accepted` 状态、Conversation 标识和安全 execution reference
- **AND** 响应不宣称 Task 已完成，也不包含下载 URL、原始输入、lease 或结果内容

#### Scenario: 用户取消有效的 Agent 提议

- **WHEN** 当前主体取消一个仍有效的 Agent 提议
- **THEN** 系统写入稳定的取消终态事件
- **AND** 系统不调用 Agent Runtime 或普通受控分发器

#### Scenario: 提议失效或主体不匹配

- **WHEN** 确认请求对应的提议已过期、已消费或不属于当前主体
- **THEN** 系统返回稳定的不可用错误
- **AND** 系统不执行 Agent，也不写入另一条结果事件

### Requirement: 对话页面只显示 Agent 的安全执行结果

系统 MUST 将确认后的 Agent 调用状态和安全结果摘要返回给 Chat 页面。页面 MUST 在同一条对话中展示待确认、已接收、执行完成、失败或取消状态，且 MUST NOT 将原始 Agent 输出、二进制文件、内部权限或分发信息作为浏览器响应内容。

#### Scenario: Agent 调用完成

- **WHEN** 已批准的 Agent 调用同步完成
- **THEN** Chat 页面在产生确认卡片的对话中显示完成状态和已白名单投影的结果摘要
- **AND** 系统不在本能力中自动生成新的自然语言 assistant Message

#### Scenario: Agent 调用已交给内部 Task

- **WHEN** 已批准的 Agent 调用异步接收
- **THEN** Chat 页面获得已接收状态和安全 execution reference
- **AND** 当前能力不创建 Task 结果下载、任务工作台或异步完成通知
