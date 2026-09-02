## ADDED Requirements

### Requirement: 被取消的 Agent 准备必须记录终态

当统一交互 Gateway 已生成 Agent 待确认提议，但 Chat 客户端在批准事件可达之前取消请求时，系统 MUST 通过 Dialogue Agent Invocation 写入 `agent_error` 事件，错误码为 `AGENT_CALL_CANCELLED`，并 MUST 在用户确认前不调用 Agent Runtime。

#### Scenario: 取消待确认准备并提交终态

- **WHEN** 准备 Worker 已创建 Conversation、用户消息和 `confirmation_required` 事件，随后收到取消信号
- **THEN** 系统追加一个 `AGENT_CALL_CANCELLED` 的 `agent_error` 事件
- **AND** 该 Worker 提交事务并关闭 Session 后才释放准备资源

#### Scenario: 取消收口遇到已消费状态

- **WHEN** 待确认提议已经被确认、取消或过期
- **THEN** 取消收口不重复调用 Agent Runtime 或追加重复终态
- **AND** 调用方仍保持原始取消语义

#### Scenario: 取消收口失败

- **WHEN** 写入取消终态时数据库操作失败
- **THEN** Worker 回滚事务并关闭 Session
- **AND** 系统不把该取消报告为成功的 Agent 执行结果
